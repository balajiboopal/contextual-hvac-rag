# Prompt: Rebuild This Voice Pipeline In Another Repo

Use this prompt with another coding agent when you want the open-source version of this project to implement the same proposed voice architecture as this repository.

## Copy-Paste Prompt

```md
Implement an additive voice-query pipeline for the existing WhatsApp bot. Do not rewrite the existing text-message path. Keep the current text bot behavior intact and add a parallel voice path.

Goal:
- support inbound WhatsApp voice notes
- transcribe them using free open-source models
- query the existing Contextual agent with the transcript
- optionally synthesize the answer back into a WhatsApp voice note
- degrade gracefully to text if voice processing fails

Constraints:
- free/self-hosted models only
- good support for Indian languages, especially the major ones
- do not introduce paid STT/TTS providers
- preserve the current inbound-only WhatsApp cost guardrails

Recommended model stack:
- STT: faster-whisper
- TTS default: AI4Bharat/Indic-TTS
- TTS fallback: ai4bharat/indic-parler-tts

Why:
- faster-whisper is the practical low-latency open-source STT baseline
- Indic-TTS is the faster Indian-language TTS path
- indic-parler-tts provides broader Indic language fallback

Modules to add under src/contextual_hvac_rag/bot_whatsapp:
- media.py
- audio_convert.py
- stt.py
- tts.py
- voice_router.py

Behavior to implement:

1. Webhook parsing
- extend the normalized inbound message model to include:
  - message_type: text | audio
  - text: optional
  - audio_media_id: optional
- continue supporting the current text flow unchanged
- for audio messages, capture the Meta media id from audio.id

2. Inbound audio flow
- fetch media metadata from Meta Graph API
- download the audio file
- convert to mono WAV/PCM, 16kHz using ffmpeg
- transcribe with faster-whisper
- if transcript is empty or STT fails, send a short text fallback reply

3. Contextual query
- reuse the existing Contextual agent client
- send the transcript as the user message
- keep the same conversation/cost guard rules as the current bot unless the existing bot is stateless

4. Outbound reply policy
- text input -> text reply (unchanged)
- audio input -> audio reply by default
- if TTS fails or language unsupported -> send text reply instead
- do not send both text and audio by default
- one inbound user message should produce one outbound reply

5. TTS routing
- use Indic-TTS for supported languages first
- use indic-parler-tts as fallback
- if unsupported by both:
  - fall back to a text reply

6. Audio output
- synthesize speech
- convert to WhatsApp-friendly OGG/Opus using ffmpeg
- upload the media to WhatsApp
- send as an audio / voice-note style message

7. Config / env vars
Add:
- BOT_ENABLE_VOICE=false
- BOT_VOICE_REPLY_MODE=audio
  - supported values: audio, text, auto
- BOT_STT_MODEL_SIZE=small
- BOT_STT_DEVICE=cpu
- BOT_STT_COMPUTE_TYPE=int8
- BOT_TTS_DEFAULT_BACKEND=indic_tts
- BOT_TTS_FALLBACK_BACKEND=indic_parler
- BOT_TEMP_DIR=./data/tmp_audio
- FFMPEG_BINARY=ffmpeg

Optional:
- BOT_MAX_AUDIO_SECONDS=30
- BOT_STT_LANGUAGE_HINT=

8. Dependencies
Use:
- faster-whisper
- torch
- transformers
- soundfile
- optional torchaudio

Assume ffmpeg is installed as a system dependency.

9. Failure handling
Required:
- media download failure -> text fallback
- STT failure -> text fallback
- TTS failure -> text fallback
- unsupported language -> text fallback
- never let voice handling break text handling

10. Logging
Log:
- inbound message type
- media download success/failure
- transcript length
- detected language
- STT latency
- Contextual latency
- TTS latency
- outbound reply mode (text vs audio)

11. Rollout shape
Implement in a way that supports staged validation:
- first make voice notes transcribe to text and use existing text replies
- then add TTS + outbound audio

Implementation constraints:
- Python 3.11+
- additive only
- type hints
- concise docstrings
- preserve existing webhook, store, and guard behavior unless a minimal extension is required

After implementing, provide:
- files added/changed
- env vars added
- system dependencies required
- exact local run instructions
- risks and latency tradeoffs
```

## Usage Note

For best results, also paste these alongside the prompt:

- [AGENT_CONTEXT.md](/c:/Users/balaj/Documents/Contextual/Contextual-API/docs/agent/AGENT_CONTEXT.md)
- [voice_pipeline_blueprint.md](/c:/Users/balaj/Documents/Contextual/Contextual-API/docs/voice_pipeline_blueprint.md)

at the top of the request.
