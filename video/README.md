# Explainer video: "Ask before you flag"

A 75-second product-concept explainer for the interactive verification agent proposed for MicroAGI's Shift app. The scenario is synthetic and every model output on screen is simulated. It is not a production integration, and it makes no claims about accuracy, latency or cost.

The MP4 (1920×1080, 30 fps, H.264 + AAC 192 kbps, 75.0 s) is attached to a GitHub release rather than committed.

## Files

| File | What |
| --- | --- |
| `index.html` | The whole animation. `render(t)` draws the frame for t seconds. Open it in a browser to preview: space pauses, clicking the bar scrubs. |
| `render.py` | Renders frames with Playwright and Chromium, then pipes them into ffmpeg. `stills <t…>` makes key frames and a contact sheet. |
| `mix.py` | Synthesises all sound design from the timeline, places the speech, ducks under it, and writes `build/mix.wav`. |
| `subtitles.srt` | Subtitles for the two spoken lines (also burned into the video). |
| `sound_events.json` | Every sound cue with its timestamp, the speech placement, and the ducking regions. All are generated from the animation timeline. |
| `audio/` | ElevenLabs speech: the agent question and the contributor answer. |
| `fonts/` | Inter Display Black, plus Inter Medium, SemiBold and Bold (SIL Open Font License). |

## Rebuild

```bash
uv venv /tmp/vidtools/.venv && uv pip install --python /tmp/vidtools/.venv playwright numpy
PY=/tmp/vidtools/.venv/bin/python
$PY render.py stills 2.5 9.5 23.5 44 55 65 73   # check frames + stills/contact.png
$PY render.py video                             # build/video.mp4 + timeline.json + subtitles.srt
$PY mix.py                                      # build/mix.wav + sound_events.json
ffmpeg -i build/video.mp4 -i build/mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k \
  -movflags +faststart -shortest build/ai-physical-hack-explainer.mp4
```

`render.py` expects Chromium at `/usr/bin/chromium`.

## Delivery notes

- **Scenario:** industrial bracket assembly replaces towel folding, as requested. The ambiguous clip shows the same bracket bolted, unbolted and bolted again. The legitimate clip shows new brackets going into a finished bin. Everything is illustrated; no real footage is used.
- **Speech:** made with ElevenLabs (`eleven_multilingual_v2`). Agent: "River" (calm, neutral). Contributor: "Chris" (casual). These are not placeholders.
- **Fonts:** Inter Display Black for headlines and Inter for UI text, both downloaded because nothing heavy was installed. Monospace is DejaVu Sans Mono (installed).
- **Palette:** the brief's palette, plus one extra colour, violet `#8B5CF6`, for ElevenLabs. Green is reserved for resolved states, so it couldn't be used for a fifth component.
- **Timing:** 0–6 hook · 6–13 same motion / different evidence · 13–27 Stage 1 · 27–46 Stage 2 · 46–66 Stage 3 · 66–70 punchline · 70–75 close. Capture and processing are compressed on screen, and the batch views are labelled "Timing condensed".
- **Architecture shown:** task → Jev retrieval (once, pinned to the session) → 10-image batch → Gemini Flash text → Jev comparison (it routes, it doesn't write questions) → Astra gets the images and text, the references and the context → ElevenLabs voices the question → the spoken answer is transcribed into session context → the next batch goes through Flash, and Jev reassesses. The answer alone leaves the concern open ("Context added · concern still open"); the new visual evidence resolves it.
- **Not shown:** the end-of-session verdict, because it isn't in the brief.
