"""Webhook parsing tests."""

from __future__ import annotations

from contextual_hvac_rag.bot_whatsapp.webhook import parse_inbound_messages


def test_parse_inbound_messages_extracts_audio_media_id() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.123",
                                    "from": "15551234567",
                                    "timestamp": "1700000000",
                                    "type": "audio",
                                    "audio": {"id": "media-456"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    messages = parse_inbound_messages(payload)

    assert len(messages) == 1
    assert messages[0].message_type == "audio"
    assert messages[0].audio_media_id == "media-456"
    assert messages[0].text == ""
