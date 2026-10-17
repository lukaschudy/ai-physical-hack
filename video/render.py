"""Render index.html to frames with Playwright + Chromium and pipe them into ffmpeg.

  render.py stills 3.5 12 20 ...   -> stills/t03.50.png ... + stills/contact.png
  render.py video                   -> build/video.mp4 (silent) + build/timeline.json + build/subtitles.srt
"""

import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
CHROMIUM = "/usr/bin/chromium"


def open_page(p):
    browser = p.chromium.launch(executable_path=CHROMIUM, args=["--force-color-profile=srgb"])
    page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    page.goto((HERE / "index.html").as_uri() + "?render")
    page.evaluate("window.READY")
    return browser, page


def srt_time(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_timeline(page) -> dict:
    tl = page.evaluate("window.TIMELINE")
    BUILD.mkdir(exist_ok=True)
    (BUILD / "timeline.json").write_text(json.dumps(tl, indent=1))
    srt = [
        f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{who}: {text}\n"
        for i, (a, b, who, text) in enumerate(tl["subs"], 1)
    ]
    (BUILD / "subtitles.srt").write_text("\n".join(srt))
    return tl


def stills(times: list[float]) -> None:
    out = HERE / "stills"
    out.mkdir(exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    with sync_playwright() as p:
        browser, page = open_page(p)
        for t in times:
            page.evaluate(f"render({t})")
            page.screenshot(path=str(out / f"t{t:05.2f}.png"))
        browser.close()
    files = sorted(out.glob("t*.png"))
    cols = 4
    rows = -(-len(files) // cols)
    inputs = sum((["-i", str(f)] for f in files), [])
    labels = "".join(
        f"[{i}:v]scale=480:270,drawtext=text='{f.stem[1:]}s':x=8:y=8:fontsize=22:"
        f"fontcolor=white:box=1:boxcolor=black@0.6[v{i}];"
        for i, f in enumerate(files)
    )
    pads = "".join(f"[v{i}]" for i in range(len(files)))
    layout = "|".join(f"{(i % cols) * 480}_{(i // cols) * 270}" for i in range(len(files)))
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex",
         f"{labels}{pads}xstack=inputs={len(files)}:layout={layout}:fill=black[o]",
         "-map", "[o]", "-frames:v", "1", str(out / "contact.png")],
        check=True,
    )
    print(f"{len(files)} stills, contact sheet {cols}x{rows}: {out / 'contact.png'}")


def video() -> None:
    BUILD.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser, page = open_page(p)
        tl = write_timeline(page)
        n = round(tl["duration"] * tl["fps"])
        ff = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(tl["fps"]),
             "-c:v", "png", "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
             "-pix_fmt", "yuv420p", "-r", str(tl["fps"]), str(BUILD / "video.mp4")],
            stdin=subprocess.PIPE,
        )
        for i in range(n):
            page.evaluate(f"render({i / tl['fps']})")
            ff.stdin.write(page.screenshot(type="png"))
            if i % 150 == 0:
                print(f"frame {i}/{n}", flush=True)
        ff.stdin.close()
        ff.wait()
        browser.close()
    print("wrote", BUILD / "video.mp4")


if __name__ == "__main__":
    if sys.argv[1] == "stills":
        stills([float(x) for x in sys.argv[2:]])
    else:
        video()
