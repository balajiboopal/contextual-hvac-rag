"""HTTP client wrapper for Contextual datastore ingestion and agent querying."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from contextual_hvac_rag.config import Settings

LOGGER = logging.getLogger(__name__)
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class ContextualClientError(RuntimeError):
    """Base exception for Contextual client errors."""


class ContextualAPIResponseError(ContextualClientError):
    """Raised when the Contextual API returns a non-success response."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"Contextual API error {status_code}: {body}")
        self.status_code = status_code
        self.body = body


@dataclass(slots=True)
class IngestResult:
    """Parsed result for a document ingest request."""

    status_code: int
    document_id: str | None
    payload: dict[str, Any]


@dataclass(slots=True)
class AgentQueryResult:
    """Parsed result for an agent query request."""

    status_code: int
    conversation_id: str | None
    answer_text: str
    payload: dict[str, Any]


class ContextualClient:
    """Small sync HTTP wrapper with retries and consistent request formatting."""

    def __init__(
        self,
        settings: Settings,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
    ) -> None:
        self._settings = settings
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._client = httpx.Client(
            base_url=settings.contextual_api_base.rstrip("/"),
            timeout=timeout_seconds,
            headers={
                "Authorization": (
                    f"Bearer {settings.contextual_api_key.get_secret_value()}"
                    if settings.contextual_api_key
                    else ""
                ),
            },
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._client.close()

    def __enter__(self) -> ContextualClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def ingest_document(
        self,
        *,
        filename: str,
        file_bytes: bytes,
        custom_metadata: dict[str, Any],
    ) -> IngestResult:
        """Upload a PDF document with custom metadata to the datastore."""

        if not self._settings.contextual_datastore_id:
            raise ContextualClientError("CONTEXTUAL_DATASTORE_ID is not configured.")

        response = self._request_with_retries(
            "POST",
            f"/datastores/{self._settings.contextual_datastore_id}/documents",
            files={"file": (filename, file_bytes, "application/pdf")},
            data={"custom_metadata": json.dumps(custom_metadata)},
        )
        payload = self._parse_json(response)
        document_id = payload.get("document_id") or payload.get("id")
        return IngestResult(
            status_code=response.status_code,
            document_id=str(document_id) if document_id is not None else None,
            payload=payload,
        )

    def query_agent(
        self,
        *,
        message: str,
        conversation_id: str | None = None,
    ) -> AgentQueryResult:
        """Send a query to the configured agent and return the parsed response."""

        if not self._settings.contextual_agent_id:
            raise ContextualClientError("CONTEXTUAL_AGENT_ID is not configured.")

        body: dict[str, Any] = {"message": message}
        if conversation_id:
            body["conversation_id"] = conversation_id

        response = self._request_with_retries(
            "POST",
            f"/agents/{self._settings.contextual_agent_id}/query",
            json=body,
        )
        payload = self._parse_json(response)
        answer_text = (
            payload.get("answer")
            or payload.get("output_text")
            or payload.get("response")
            or ""
        )
        returned_conversation_id = payload.get("conversation_id")
        return AgentQueryResult(
            status_code=response.status_code,
            conversation_id=(
                str(returned_conversation_id)
                if returned_conversation_id is not None
                else conversation_id
            ),
            answer_text=str(answer_text),
            payload=payload,
        )

    def _request_with_retries(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an HTTP request with bounded retries for transient failures."""

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.RequestError as exc:
                last_error = exc
                LOGGER.warning(
                    "Contextual request failed on attempt %s/%s: %s",
                    attempt,
                    self._max_retries,
                    exc,
                )
                if attempt == self._max_retries:
                    break
                time.sleep(self._backoff_seconds * attempt)
                continue

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                LOGGER.warning(
                    "Retrying Contextual request after status %s on attempt %s/%s",
                    response.status_code,
                    attempt,
                    self._max_retries,
                )
                time.sleep(self._backoff_seconds * attempt)
                continue

            if response.is_error:
                raise ContextualAPIResponseError(response.status_code, response.text)
            return response

        raise ContextualClientError(
            f"Contextual request failed after {self._max_retries} attempts: {last_error}"
        )

    @staticmethod
    def _parse_json(response: httpx.Response) -> dict[str, Any]:
        """Parse a JSON response body into a dictionary."""

        try:
            payload = response.json()
        except ValueError as exc:
            raise ContextualClientError("Contextual API returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise ContextualClientError("Contextual API returned a non-object JSON payload.")
        return payload

