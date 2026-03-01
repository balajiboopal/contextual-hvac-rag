"""Media helpers for WhatsApp Cloud API audio flows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from contextual_hvac_rag.config import Settings

GRAPH_API_BASE = "https://graph.facebook.com/v22.0"


class MediaTransferError(RuntimeError):
    """Raised when media download or upload fails."""


class WhatsAppMediaClient:
    """Download inbound media and upload outbound audio media."""

    def __init__(self, settings: Settings, *, timeout_seconds: float = 30.0) -> None:
        self._settings = settings
        self._client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._client.close()

    def download_media(self, *, media_id: str) -> tuple[bytes, str | None]:
        """Resolve and download inbound media bytes from Meta."""

        access_token = self._require_access_token()
        metadata_response = self._client.get(
            f"{GRAPH_API_BASE}/{media_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        if not isinstance(metadata, dict):
            raise MediaTransferError("Media metadata response was not a JSON object.")

        url = metadata.get("url")
        if not isinstance(url, str) or not url.strip():
            raise MediaTransferError("Meta did not return a download URL for the media.")

        binary_response = self._client.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        binary_response.raise_for_status()
        return binary_response.content, binary_response.headers.get("Content-Type")

    def upload_audio(self, *, audio_path: Path) -> str:
        """Upload an audio file to Meta and return the uploaded media id."""

        access_token = self._require_access_token()
        phone_number_id = self._require_phone_number_id()

        with audio_path.open("rb") as handle:
            response = self._client.post(
                f"{GRAPH_API_BASE}/{phone_number_id}/media",
                headers={"Authorization": f"Bearer {access_token}"},
                data={"messaging_product": "whatsapp", "type": "audio/ogg"},
                files={"file": (audio_path.name, handle, "audio/ogg")},
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise MediaTransferError("Media upload response was not a JSON object.")

        media_id = payload.get("id")
        if not isinstance(media_id, str) or not media_id.strip():
            raise MediaTransferError("Meta did not return an uploaded media id.")
        return media_id

    def _require_access_token(self) -> str:
        access_token = self._settings.wa_access_token
        if access_token is None:
            raise MediaTransferError("WA_ACCESS_TOKEN is not configured.")
        return access_token.get_secret_value()

    def _require_phone_number_id(self) -> str:
        phone_number_id = self._settings.wa_phone_number_id
        if not phone_number_id:
            raise MediaTransferError("WA_PHONE_NUMBER_ID is not configured.")
        return phone_number_id
