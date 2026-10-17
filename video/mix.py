"""Synthesize sound design from build/timeline.json, place the speech, duck under it, write build/mix.wav.

Every sound is generated here (no samples). Cue times come from window.TIMELINE in index.html.
"""

import json
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
SR = 48000
rng = np.random.default_rng(7)  # fixed seed: the noise in whooshes is reproducible

PENTA = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24]
CHORDS = [  # MIDI notes of the pad, one chord per scene
    [48, 55, 64, 71], [45, 52, 60, 67], [41, 48, 57, 64], [50, 57, 65, 72],
    [46, 53, 62, 69], [43, 50, 60, 67], [48, 55, 64, 72],
]


def hz(midi: float) -> float:
    return 440 * 2 ** ((midi - 69) / 12)


def tvec(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def onepole_lp(x: np.ndarray, cutoff: np.ndarray | float) -> np.ndarray:
    a = np.exp(-2 * np.pi * np.broadcast_to(cutoff, x.shape) / SR)
    y, prev = np.empty_like(x), 0.0
    for i in range(len(x)):  # short sounds only
        prev = (1 - a[i]) * x[i] + a[i] * prev
        y[i] = prev
    return y


def bell(f: float, dur: float, decay: float) -> np.ndarray:
    t = tvec(dur)
    tone = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.01 * t) + 0.12 * np.sin(2 * np.pi * f * 3.98 * t)
    return tone * np.exp(-t / decay) * np.minimum(1, t / 0.004)


def tick(p: int) -> np.ndarray:
    f = 880 * 2 ** (PENTA[p % len(PENTA)] / 12)
    return 0.22 * bell(f, 0.18, 0.045)


def hit() -> np.ndarray:
    t = tvec(0.9)
    f = 45 + 50 * np.exp(-t / 0.06)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.28)
    thump = onepole_lp(rng.standard_normal(len(t)), 400.0) * np.exp(-t / 0.03) * 3
    return 0.4 * (body + thump)


def whoosh(dur: float, lo: float, hi: float, gain: float) -> np.ndarray:
    t = tvec(dur)
    x = rng.standard_normal(len(t))
    shape = np.sin(np.pi * t / dur) ** 2
    cutoff = lo + (hi - lo) * shape
    return gain * onepole_lp(x, cutoff) * shape


def pad(chord: list[int], dur: float) -> np.ndarray:
    t = tvec(dur)
    out = np.zeros(len(t))
    for n in chord:
        f = hz(n)
        for det in (-0.12, 0.12):
            ph = 2 * np.pi * f * 2 ** (det / 12) * t
            out += np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph)
    env = np.minimum(1, t / 1.4) * np.minimum(1, (dur - t) / 1.4)
    lfo = 1 + 0.08 * np.sin(2 * np.pi * 0.2 * t)
    return 0.018 * out * env * lfo


def sound(cue: dict) -> tuple[np.ndarray, float]:
    """(mono signal, pan -1..1)"""
    kind, p = cue["type"], cue["p"]
    if kind == "tick":
        return tick(p), -0.3 + 0.12 * (p % 6)
    if kind == "hit":
        return hit(), 0.0
    if kind == "whoosh":
        return whoosh(0.75, 300, 4500, 0.10), 0.0
    if kind == "swish":
        return whoosh(0.5, 600, 6000, 0.06), 0.3
    if kind == "amber":
        a, b = bell(hz(76), 0.35, 0.09), bell(hz(72), 0.5, 0.12)
        out = np.zeros(int(0.65 * SR))
        out[: len(a)] += a
        out[int(0.13 * SR):][: len(b)] += b
        return 0.2 * out, 0.0
    if kind == "notify":
        out = np.zeros(int(0.9 * SR))
        for i, n in enumerate((84, 91)):
            s = bell(hz(n), 0.7, 0.18)
            out[int(i * 0.12 * SR):][: len(s)] += s
        return 0.16 * out, 0.0
    if kind == "chime":
        out = np.zeros(int(2.0 * SR))
        for i, n in enumerate((72, 76, 79, 84)):
            s = bell(hz(n), 1.6, 0.4)
            out[int(i * 0.09 * SR):][: len(s)] += s
        return 0.16 * out, 0.0
    raise ValueError(kind)


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) / 32768


def main() -> None:
    tl = json.loads((BUILD / "timeline.json").read_text())
    n = int(tl["duration"] * SR)
    fx = np.zeros((n, 2))  # music + effects bus
    voice = np.zeros(n)
    starts = [s for _, s, _ in tl["scenes"]] + [tl["duration"]]

    def add(bus, sig, t0, pan=0.0):
        i = int(t0 * SR)
        seg = sig[: max(0, n - i)]
        if bus is voice:
            voice[i: i + len(seg)] += seg
        else:
            fx[i: i + len(seg), 0] += seg * np.sqrt((1 - pan) / 2) * 1.4142
            fx[i: i + len(seg), 1] += seg * np.sqrt((1 + pan) / 2) * 1.4142

    for c in tl["cues"]:
        if c["type"] == "pad":
            i = c["p"]
            t0 = max(0, starts[i] - 0.6)
            add(fx, pad(CHORDS[i], starts[i + 1] + 0.9 - t0), t0)
        else:
            sig, pan = sound(c)
            add(fx, sig, c["t"], pan)

    regions = []
    for s in tl["speech"]:
        sig = read_wav(HERE / s["file"])
        sig = sig / np.abs(sig).max() * 0.7
        add(voice, sig, s["t"])
        regions.append((s["t"], s["t"] + len(sig) / SR))

    # duck the music + effects bus under speech
    t = np.arange(n) / SR
    duck = np.ones(n)
    for a, b in regions:
        g = np.clip(np.minimum((t - (a - 0.25)) / 0.25, ((b + 0.5) - t) / 0.5), 0, 1)
        duck = np.minimum(duck, 1 - 0.72 * g)
    mix = 0.4 * fx * duck[:, None] + voice[:, None]  # speech leads; effects sit ~8 dB under
    fade = np.clip((tl["duration"] - t) / 1.4, 0, 1)
    mix *= fade[:, None]
    mix *= 0.89 / np.abs(mix).max()  # peak at -1 dBFS

    with wave.open(str(BUILD / "mix.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    (BUILD / "sound_events.json").write_text(json.dumps(
        {"cues": tl["cues"], "speech": tl["speech"], "ducking_regions_s": regions}, indent=1))
    print(f"mix.wav {tl['duration']} s, {len(tl['cues'])} cues, speech regions {regions}")


if __name__ == "__main__":
    main()
