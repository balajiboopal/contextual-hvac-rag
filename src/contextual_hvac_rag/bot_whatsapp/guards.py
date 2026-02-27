"""Guardrails that enforce inbound-only WhatsApp messaging."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from contextual_hvac_rag.bot_whatsapp.store import StoreProtocol

LOGGER = logging.getLogger(__name__)
CUSTOMER_SERVICE_WINDOW_SECONDS = 24 * 60 * 60


class GuardViolation(RuntimeError):
    """Raised when a WhatsApp send violates the inbound-only policy."""


@dataclass(frozen=True, slots=True)
class InboundTrigger:
    """Represents the inbound event authorizing a reply."""

    wa_id: str
    message_id: str
    user_message_ts: int


def ensure_non_template_message(message_type: str) -> None:
    """Block all non-text and template message attempts."""

    if message_type != "text":
        raise GuardViolation("Only plain text replies are allowed by policy.")


def ensure_inbound_reply_allowed(
    *,
    trigger: InboundTrigger | None,
    store: StoreProtocol,
    now_ts: int | None = None,
) -> None:
    """Ensure an outbound reply is directly tied to a recent inbound user message."""

    if trigger is None:
        LOGGER.warning("Blocked outbound WhatsApp send: no inbound trigger was supplied.")
        raise GuardViolation("Outbound WhatsApp sends require an inbound trigger.")

    effective_now = now_ts if now_ts is not None else int(time.time())
    if effective_now - trigger.user_message_ts > CUSTOMER_SERVICE_WINDOW_SECONDS:
        LOGGER.warning(
            "Blocked outbound WhatsApp send for %s: inbound trigger is outside the 24h window.",
            trigger.wa_id,
        )
        raise GuardViolation("Inbound trigger is older than the 24-hour customer service window.")

    last_seen_ts = store.get_last_user_message_ts(trigger.wa_id)
    if last_seen_ts is None:
        LOGGER.warning(
            "Blocked outbound WhatsApp send for %s: no stored inbound timestamp exists.",
            trigger.wa_id,
        )
        raise GuardViolation("No stored inbound user activity exists for this WhatsApp user.")

    if effective_now - last_seen_ts > CUSTOMER_SERVICE_WINDOW_SECONDS:
        LOGGER.warning(
            "Blocked outbound WhatsApp send for %s: last user activity is outside the 24h window.",
            trigger.wa_id,
        )
        raise GuardViolation("The user is outside the 24-hour customer service window.")

