"""Official WhatsApp Cloud API sender."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from contextual_hvac_rag.bot_whatsapp.guards import (
    GuardViolation,
    InboundTrigger,
    ensure_inbound_reply_allowed,
    ensure_non_template_message,
)
from contextual_hvac_rag.bot_whatsapp.store import StoreProtocol
from contextual_hvac_rag.config import Settings

LOGGER = logging.getLogger(__name__)
GRAPH_API_BASE = "https://graph.facebook.com/v22.0"


class WhatsAppCloudAPI:
    """Minimal wrapper for sending text replies with policy guardrails."""

    def __init__(self, settings: Settings, *, timeout_seconds: float = 15.0) -> None:
        self._settings = settings
        self._client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._client.close()

    def send_text_reply(
        self,
        *,
        wa_id: str,
        text: str,
        trigger: InboundTrigger | None,
        store: StoreProtocol,
    ) -> dict[str, Any]:
        """Send a plain text WhatsApp reply, enforcing inbound-only rules."""

        missing = self._settings.missing_whatsapp_vars()
        if missing:
            raise GuardViolation(
                f"Missing required WhatsApp settings: {', '.join(missing)}"
            )

        ensure_non_template_message("text")
        ensure_inbound_reply_allowed(trigger=trigger, store=store)

        access_token = self._settings.wa_access_token
        phone_number_id = self._settings.wa_phone_number_id
        if access_token is None or phone_number_id is None:
            raise GuardViolation("WhatsApp credentials are not fully configured.")

        response = self._client.post(
            f"{GRAPH_API_BASE}/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {access_token.get_secret_value()}"},
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": wa_id,
                "type": "text",
                "text": {"preview_url": False, "body": text[:4096] or "No response available."},
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("WhatsApp Cloud API returned a non-object JSON payload.")
        LOGGER.info("Sent WhatsApp reply to %s", wa_id)
        return payload

    def send_template(self, *_: object, **__: object) -> None:
        """Explicitly forbid template sends in this repository."""

        raise GuardViolation("Template messages are disabled by policy in this project.")

