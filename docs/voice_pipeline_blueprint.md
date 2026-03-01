# Voice Pipeline Blueprint

This document describes the recommended voice-query extension for the existing WhatsApp bot so the same design can be implemented in another repository.

The goal is to add:

- inbound WhatsApp voice-note support
- speech-to-text (STT)
- text-to-speech (TTS)
- outbound WhatsApp voice-note replies

without breaking the current text-message flow.

## Design Goal

Keep the existing text bot path unchanged.

Add a parallel voice path:

1. receive inbound WhatsApp audio
2. fetch/download media from Meta
3. normalize audio locally
4. transcribe with a free open-source STT model
5. query the existing Contextual agent using the transcript
6. synthesize the text answer into speech
7. upload/send audio back to WhatsApp as a voice note

If voice processing fails, the system should degrade gracefully to a text reply.

## Recommended Model Stack

Use only free/self-hosted models.

### STT

Recommended default:

- `faster-whisper`

Why:

- strong multilingual baseline
- practical latency for self-hosted inference
- good engineering maturity
- suitable for Indian language support when paired with reasonable model size

Suggested starting config:

- model size: `small`
- device: `cpu` or `cuda`
- compute type: `int8` on CPU

### TTS

Recommended fast-path:

- `AI4Bharat/Indic-TTS`

Recommended fallback:

- `ai4bharat/indic-parler-tts`

Why this split:

- `Indic-TTS` is the speed-first option for common Indian languages
- `indic-parler-tts` is the broader-language fallback when you need coverage beyond the faster path

## Indian Language Strategy

Use a hybrid routing strategy:

- default TTS backend: `Indic-TTS`
- fallback backend: `indic-parler-tts`

This preserves:

- lower latency for common Indian languages
- broader language coverage when needed

If the detected language is unsupported by both:

- do not fail the request
- send a text reply instead of a voice reply

## WhatsApp Voice Behavior

### Inbound

Current bot behavior:

- text messages are processed
- non-text messages are ignored

Voice support requires:

- parsing `audio` messages from the webhook payload
- capturing the Meta `audio.id` media identifier

### Outbound

Recommended policy:

- text query -> text reply
- voice query -> voice reply by default
- if TTS fails -> text reply fallback

Do not send both a text and a voice reply by default. One inbound message should map to one outbound message.

## Proposed Modules

Add these modules under:

- `src/contextual_hvac_rag/bot_whatsapp/`

### `media.py`

Responsibilities:

- fetch media metadata from Meta Graph API
- download inbound audio by media id
- upload generated audio for outbound sending

Key operations:

- resolve media URL
- download audio bytes
- upload synthesized audio bytes

### `audio_convert.py`

Responsibilities:

- convert inbound WhatsApp audio into an STT-friendly format
- convert synthesized TTS output into a WhatsApp voice-note-friendly format

Recommended tools:

- `ffmpeg`

Suggested conversions:

- inbound: mono WAV/PCM, 16kHz
- outbound: OGG with Opus codec

### `stt.py`

Responsibilities:

- load and reuse the `faster-whisper` model
- transcribe normalized audio
- return:
  - transcript text
  - detected language
  - optional timing metadata

Important:

- load the model once at process startup
- do not reload the model per request

### `tts.py`

Responsibilities:

- route to the configured TTS backend
- use `Indic-TTS` for supported languages
- use `indic-parler-tts` as fallback
- return generated audio in a temporary file or byte form

Important:

- keep the backend selection explicit and deterministic
- do not let unsupported languages fail the full request

### `voice_router.py`

Responsibilities:

- orchestrate the full voice pipeline:
  - download
  - convert
  - transcribe
  - query Contextual
  - synthesize
  - send reply

This should keep the main app logic cleaner and isolate the voice-specific flow.

## Webhook Data Model Changes

The current inbound model only carries text.

To support voice, expand the normalized inbound message model to include:

- `message_type`: `text` or `audio`
- `text`: optional
- `audio_media_id`: optional

Suggested normalized shape:

- `message_id`
- `wa_id`
- `timestamp`
- `message_type`
- `text`
- `audio_media_id`

Current text behavior must remain unchanged.

## Processing Flow

### Text Path

Keep the current behavior:

1. parse text
2. query Contextual
3. format reply
4. send text reply

### Voice Path

Recommended flow:

1. webhook receives `audio`
2. fetch media metadata from Meta
3. download the audio file
4. convert inbound audio to WAV/mono/16k
5. transcribe with `faster-whisper`
6. if transcript is empty:
   - send a short text fallback
7. query Contextual with the transcript
8. synthesize the answer into audio
9. convert to OGG/Opus
10. upload the audio to WhatsApp
11. send a single voice-note reply

### Failure Policy

This must be robust:

- media download failure -> text fallback
- STT failure -> text fallback
- TTS failure -> text fallback
- unsupported language -> text fallback

Never let voice handling break the existing text-query path.

## Config / Env Vars

Recommended new env vars:

- `BOT_ENABLE_VOICE=false`
- `BOT_VOICE_REPLY_MODE=audio`
  - supported values: `audio`, `text`, `auto`
- `BOT_STT_MODEL_SIZE=small`
- `BOT_STT_DEVICE=cpu`
- `BOT_STT_COMPUTE_TYPE=int8`
- `BOT_TTS_DEFAULT_BACKEND=indic_tts`
- `BOT_TTS_FALLBACK_BACKEND=indic_parler`
- `BOT_TEMP_DIR=./data/tmp_audio`
- `FFMPEG_BINARY=ffmpeg`

Optional future vars:

- `BOT_STT_LANGUAGE_HINT=`
- `BOT_TTS_DEFAULT_VOICE=`
- `BOT_MAX_AUDIO_SECONDS=30`

## Dependencies

Likely Python/runtime dependencies:

- `faster-whisper`
- `torch`
- `transformers`
- `soundfile`
- optional `torchaudio`

System dependency:

- `ffmpeg`

Keep `ffmpeg` as an explicit runtime dependency rather than trying to reimplement codec handling in Python.

## Latency Expectations

Voice will be slower than the current text-only flow.

Current text uncached path:

- roughly `14–17s` in this repository’s current environment

Voice path adds:

- media download
- STT
- TTS
- media upload

So the voice path will usually be materially slower.

Expected practical target:

- short voice notes: acceptable but slower than text
- long voice notes: noticeably slower

The objective is not to beat text latency. The objective is to keep voice usable and robust.

## How To Minimize Voice Latency

Preserve these practices:

1. use `faster-whisper` with `base` or `small`, not a very large model
2. default to `Indic-TTS` for the fastest supported languages
3. keep recordings short
4. load STT/TTS models once and reuse them
5. avoid sending both text and voice for the same user message
6. minimize unnecessary re-encoding steps

## Cost / Hosting Reality

The models are free to use, but inference is not free operationally.

You still pay in:

- CPU time
- optional GPU time
- memory usage
- longer response latency

So this is "free models" rather than "zero-cost production."

## Suggested Rollout Order

Implement in stages:

1. add inbound `audio` detection only
2. add STT so voice notes become text queries with text replies
3. validate transcription quality, especially for Indian languages
4. add TTS and outbound voice-note replies
5. add language routing and text fallback logic

This staged rollout reduces debugging complexity.

## Logging / Observability

When implemented, log:

- inbound message type
- media download success/failure
- transcript text length
- detected language
- STT latency
- Contextual latency
- TTS latency
- outbound reply mode (`text` or `audio`)

This is critical because voice adds multiple failure points compared with the current text-only bot.

## Recommended Exact Policy

Preserve this runtime policy:

- if inbound is text:
  - use the existing text flow
- if inbound is audio:
  - try STT
  - query Contextual
  - try TTS
  - if TTS succeeds, send a voice note
  - otherwise, send a text reply

This gives the best reliability while keeping the voice feature optional and additive.
