import json
import os
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "content" / "current.json"
BUILD = ROOT / "build"
OUTPUT = ROOT / "output"
W, H, FPS = 1080, 1920


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def fit_lines(draw, text, max_width, start_size, bold=True, max_lines=4):
    for size in range(start_size, 42, -2):
        fnt = font(size, bold)
        avg = max(8, size // 2)
        wrapped = textwrap.wrap(text, width=max(10, max_width // avg))
        if len(wrapped) <= max_lines and all(draw.textbbox((0, 0), line, font=fnt)[2] <= max_width for line in wrapped):
            return wrapped, fnt
    return textwrap.wrap(text, width=24)[:max_lines], font(42, bold)


def make_slide(scene, cfg, index):
    top = rgb(cfg["colors"]["background_top"])
    bottom = rgb(cfg["colors"]["background_bottom"])
    accent = rgb(cfg["colors"]["accent"])
    white = rgb(cfg["colors"]["text"])

    image = Image.new("RGB", (W, H))
    px = image.load()
    for y in range(H):
        t = y / (H - 1)
        row = tuple(int(top[c] * (1 - t) + bottom[c] * t) for c in range(3))
        for x in range(W):
            px[x, y] = row

    draw = ImageDraw.Draw(image)
    draw.ellipse((650, -180, 1260, 430), fill=tuple(min(255, int(v * .22)) for v in accent))
    draw.rectangle((74, 215, 176, 227), fill=accent)

    small = font(34, True)
    draw.text((74, 155), scene.get("eyebrow", cfg["brand"]).upper(), font=small, fill=accent)

    lines, headline_font = fit_lines(draw, scene["headline"], 920, 104, True, 4)
    y = 430
    for line in lines:
        draw.text((74, y), line, font=headline_font, fill=white)
        y += headline_font.size + 24

    body_font = font(47)
    body_lines = textwrap.wrap(scene.get("body", ""), width=34)
    y += 55
    for line in body_lines:
        draw.text((78, y), line, font=body_font, fill=(218, 222, 231))
        y += 68

    draw.line((74, 1650, 1006, 1650), fill=(65, 70, 83), width=2)
    draw.text((74, 1700), cfg["brand"], font=font(42, True), fill=white)
    draw.text((74, 1765), cfg["tagline"], font=font(25, True), fill=accent)
    draw.text((920, 1710), f"{index + 1:02d}", font=font(35, True), fill=(100, 105, 118))

    path = BUILD / f"slide-{index:02d}.png"
    image.save(path, quality=95)
    return path


def run(cmd):
    print(" ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def main():
    BUILD.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    segments = []

    for index, scene in enumerate(cfg["scenes"]):
        slide = make_slide(scene, cfg, index)
        segment = BUILD / f"segment-{index:02d}.mp4"
        duration = float(scene.get("duration", 5))
        frames = max(1, int(duration * FPS))
        vf = (
            f"scale=1200:2134,"
            f"zoompan=z='min(zoom+0.00055\\,1.08)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={W}x{H}:fps={FPS},format=yuv420p"
        )
        run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(slide),
            "-vf", vf, "-t", str(duration), "-r", str(FPS),
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            str(segment),
        ])
        segments.append(segment)

    concat_file = BUILD / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{p.as_posix()}'\n" for p in segments),
        encoding="utf-8",
    )
    final_video = OUTPUT / "latest.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy", "-movflags", "+faststart",
        str(final_video),
    ])
    (BUILD / "slide-00.png").replace(OUTPUT / "cover.png")
    print(f"Created {final_video}")


if __name__ == "__main__":
    main()
