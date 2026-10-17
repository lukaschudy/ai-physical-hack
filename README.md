# AI Physical Hack

## Architecture

### 1. Observe and compare

Retrieve reference annotations once after the contributor states the task. Reuse them for each new batch.

```mermaid
flowchart TD
    A["Contributor<br/>States intended task"] --> B["Jev<br/>Retrieves task references"]
    B --> C["Shift<br/>10 images / 10 seconds"]
    C --> D["Gemini Flash<br/>Images → structured text"]
    D --> E["Jev<br/>Compares text with references"]
    E --> F{"Suspicious or<br/>needs clarification?"}
    F -->|No| T{"Task finished?"}
    T -->|No| N["Continue<br/>Capture the next batch"]
    T -->|Yes| V["Session verdict<br/>Section 3 below"]
    F -->|Yes| Y["Escalate to Astra<br/>Follow-up flow below"]

    classDef normal fill:#dcfce7,stroke:#166534,color:#14532d;
    classDef escalate fill:#fef3c7,stroke:#92400e,color:#78350f;
    classDef verdict fill:#dbeafe,stroke:#1e40af,color:#1e3a8a;
    class N normal;
    class Y escalate;
    class V verdict;
```

**Continue** returns to Shift’s next batch, without repeating reference retrieval.

### 2. Clarify with voice

Astra receives the **original images**, **Flash’s structured text**, **reference annotations**, **Jev’s escalation reason**, and **session context**.

```mermaid
flowchart TD
    A["Astra<br/>Reviews images + text + context"] --> B["Astra<br/>Generates a follow-up question"]
    B --> C["ElevenLabs<br/>Voices the question in Shift"]
    C --> D["Contributor<br/>Answers by voice"]
    D --> S["ElevenLabs STT<br/>Transcribes the answer"]
    S --> E["Session context<br/>Stores the transcript"]
    E --> F["Resume recording<br/>Capture the next batch"]

    classDef resume fill:#dcfce7,stroke:#166534,color:#14532d;
    class F resume;
```

The next batch goes through **Flash → Jev**. Jev uses the updated session context when comparing the new annotations.

### 3. Session verdict

When the contributor ends the task, Jev scores the whole session.

```mermaid
flowchart TD
    A["Contributor<br/>Ends the task"] --> B["Jev<br/>Reviews all batches + Q&A"]
    B --> C["Fraud score<br/>0–100"]
    C --> D{"Decision"}
    D --> E["Accept"]
    D --> F["Review<br/>Send to a human"]
    D --> G["Reject"]

    classDef accept fill:#dcfce7,stroke:#166534,color:#14532d;
    classDef review fill:#fef3c7,stroke:#92400e,color:#78350f;
    classDef reject fill:#fee2e2,stroke:#991b1b,color:#7f1d1d;
    class E accept;
    class F review;
    class G reject;
```

The verdict includes the evidence: flagged batches with timestamps, Jev’s reasons, and each follow-up question with its transcribed answer.

## Full flow

1. **The contributor states their intended task.**
2. **Jev retrieves the relevant reference annotations** from MicroAGI’s database: legitimate and fraudulent examples for that task.
3. **Shift collects a batch of 10 images over 10 seconds.**
4. **Gemini Flash converts those images into structured text annotations**, describing the activity frame by frame.
5. **Jev compares the live annotations with the retrieved references**, considering the declared task and previous answers.
6. **If everything looks consistent, continue recording** and process the next batch.
7. **If Jev detects suspicious behaviour or needs clarification, escalate to Astra.** Send:
   - The original batch images.
   - Gemini Flash’s structured text.
   - Relevant reference annotations and Jev’s reason for escalating.
   - The declared task and conversation history.
8. **Astra examines the images and text together and generates a targeted follow-up question.** ElevenLabs voices the question in Shift for the contributor.
9. **The contributor answers by voice; ElevenLabs speech-to-text transcribes it.** The transcript enters the session context. The next image batch goes through Gemini Flash, and Jev assesses the new annotations with that additional context.
10. **When the contributor ends the task, Jev issues a session verdict:** a fraud score (0–100), a decision (**Accept**, **Review** by a human, or **Reject**), and the evidence (flagged batches with timestamps, Jev’s reasons, follow-up questions with transcribed answers).

**Declare task → Retrieve references → Image batch → Flash annotations → Jev comparison → Astra follow-up when needed → ElevenLabs voice → Spoken answer → ElevenLabs STT → Next batch → Session verdict.**

## Development

Needs [uv](https://docs.astral.sh/uv/) and [pnpm](https://pnpm.io/) (Node 22.12+).

```bash
scripts/dev.sh   # installs missing deps, runs backend :8000 + frontend :5173; Ctrl-C stops both
```

Open http://localhost:5173 (contributor flow). Vite proxies `/api` to the backend.

Or run each side yourself:

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload
cd frontend && pnpm install && pnpm dev
```

### Checks (same as CI)

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm typecheck && pnpm test && pnpm build
```

`.github/workflows/ci.yml` runs these on every push and PR, offline (`USE_FAKES=1`).

### Environment

Copy `backend/.env.example` to `backend/.env`. Real environment variables override it.

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Flash annotations, Jev comparison + verdict |
| `ANTHROPIC_API_KEY` | Astra follow-up questions |
| `ELEVENLABS_API_KEY` | Question voice (TTS) + answer transcription (STT) |
| `USE_FAKES` | `0` (default) = real clients where a key is set, fakes elsewhere; `1` = offline fakes everywhere |
| `DATA_DIR` | Sessions DB, images, audio (default `./var`, relative to `backend/`) |
| `FLASH_MODEL`, `JEV_MODEL`, `ASTRA_MODEL` | Model ids (defaults in `backend/app/config.py`) |
| `ELEVENLABS_VOICE_ID`, `ELEVENLABS_TTS_MODEL`, `ELEVENLABS_STT_MODEL` | ElevenLabs voice + models |

### Fakes and live tests

Without API keys (or with `USE_FAKES=1`) every external service uses an offline fake, so the whole flow runs locally.

Each service is chosen independently: e.g. with only `GEMINI_API_KEY` set, Astra and ElevenLabs stay fake.

`backend/tests/test_live.py` (marker `live`) calls each real client once. Each test skips unless `USE_FAKES=0` and its key is set.

```bash
cd backend && uv run pytest -m live   # live tests only; plain `uv run pytest` excludes them
```

### Demo with a recorded video

Make Chrome replay a video file as the webcam (and a WAV as the microphone), so the demo is repeatable:

```bash
ffmpeg -i demo.mp4 -vf fps=30 -pix_fmt yuv420p demo.y4m   # .y4m is uncompressed: keep clips short
ffmpeg -i answer.m4a -ar 48000 -ac 1 answer.wav
open -na "Google Chrome" --args --user-data-dir=/tmp/chrome-demo \
  --use-fake-ui-for-media-stream --use-fake-device-for-media-stream \
  --use-file-for-fake-video-capture="$PWD/demo.y4m" \
  --use-file-for-fake-audio-capture="$PWD/answer.wav" http://localhost:5173
```

On Linux, run `google-chrome` with the same flags. The video loops.

### Reviewer page

http://localhost:5173/#/sessions lists all sessions; `#/sessions/<id>` shows one session's verdict, evidence, and Q&A. Sessions persist in `DATA_DIR`.

### Modules

| Module | Role |
| --- | --- |
| `backend/app/models.py` / `frontend/src/types.ts` | Shared contract |
| `references.py` + `data/references.json` | Jev's reference retrieval |
| `annotate.py` | Gemini Flash annotation |
| `jev.py` | Jev per-batch comparison |
| `verdict.py` | Jev session verdict |
| `astra.py` | Astra follow-up question |
| `tts.py` / `stt.py` | ElevenLabs voice + transcription |
| `store.py` | Sessions + stored images/audio |
| `pipeline.py` / `main.py` | Orchestration + HTTP API |
