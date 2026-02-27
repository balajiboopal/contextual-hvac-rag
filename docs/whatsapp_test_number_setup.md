# WhatsApp Test Number Setup

This guide prepares the repository for local development using Meta's WhatsApp Cloud API test number.

## What You Need From Meta

- A Meta developer account
- A Meta app with the WhatsApp product enabled
- The provided test phone number in the WhatsApp sandbox
- A test recipient number that you add in the Meta dashboard
- A temporary or long-lived access token from the WhatsApp product page

## Values You Need To Copy Into `.env`

- `WA_ACCESS_TOKEN`
  - Use the token from the Meta app's WhatsApp product page.
- `WA_PHONE_NUMBER_ID`
  - Use the phone number ID for the Meta-provided test number.
- `WA_VERIFY_TOKEN`
  - Pick any random string and use the same value in Meta webhook configuration.
- `CONTEXTUAL_API_KEY`
  - Required so inbound messages can be sent to the Contextual agent query API.
- `CONTEXTUAL_AGENT_ID`
  - Required for the WhatsApp bot path.

## Local Startup

1. Install dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

2. Start the app:

   ```bash
   uvicorn contextual_hvac_rag.bot_whatsapp.app:app --host 0.0.0.0 --port 8000
   ```

3. Verify local readiness:

   ```bash
   curl http://127.0.0.1:8000/healthz
   ```

4. Expose the app publicly with a tunnel:

   ```bash
   ngrok http 8000
   ```

   or

   ```bash
   cloudflared tunnel --url http://127.0.0.1:8000
   ```

## Meta Webhook Configuration

Use your public tunnel URL and configure:

- Callback URL: `https://<public-host>/whatsapp/webhook`
- Verify token: the same string stored in `WA_VERIFY_TOKEN`

Subscribe the app to the WhatsApp message webhook events required for inbound messaging.

## Test Number Limitations

- The Meta test number is only for limited development and sandbox use.
- Only approved test recipient numbers can interact with it.
- It is not a production sender number.

## What This Repository Already Enforces

- Replies only happen after inbound user messages.
- Template sends are blocked.
- Proactive outbound sends are blocked.
- If the last user activity is outside the 24-hour service window, sends are blocked.

## Quick Local Test Flow

1. Confirm `/healthz` returns `"status": "ok"`.
2. Confirm `GET /whatsapp/webhook` succeeds from Meta webhook verification.
3. Send a message from the approved recipient number to the Meta test number.
4. Check the terminal logs for:
   - webhook received
   - Contextual query succeeded or failed
   - WhatsApp reply sent or blocked

## Common Failure Points

- `403` on webhook verification:
  - `WA_VERIFY_TOKEN` does not match Meta.
- Inbound webhook arrives but no reply is sent:
  - `CONTEXTUAL_API_KEY` or `CONTEXTUAL_AGENT_ID` is missing
  - `WA_ACCESS_TOKEN` or `WA_PHONE_NUMBER_ID` is missing
  - the inbound message payload is not a supported text message
- Reply send fails:
  - test number is not permitted to message that recipient
  - Meta token expired
