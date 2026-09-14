import json
import math
import os
import subprocess
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "content" / "current.json"
ASSETS = ROOT / "assets"
BUILD = ROOT / "build"
OUTPUT = ROOT / "output"
W, H, FPS = 1080, 1920, 30


def font(size, bold=False):
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for name in names:
        if os.path.exists(name):
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def color(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def gradient(top, bottom):
    image = Image.new("RGB", (W, H), top)
    draw = ImageDraw.Draw(image)
    for y in range(H):
        p = y / max(1, H - 1)
        row = tuple(round(top[i] * (1 - p) + bottom[i] * p) for i in range(3))
        draw.line((0, y, W, y), fill=row)
    return image


def cover_image(path):
    source = Image.open(path).convert("RGB")
    return ImageOps.fit(source, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def glow(base, xy, radius, fill):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse((xy[0] - radius, xy[1] - radius, xy[0] + radius, xy[1] + radius), fill=fill)
    layer = layer.filter(ImageFilter.GaussianBlur(radius // 2))
    return Image.alpha_composite(base.convert("RGBA"), layer)


def wrap_to_pixels(draw, text, fnt, width, max_lines=5):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:max_lines]


def fitted_headline(draw, text, width, max_lines=4):
    for size in range(108, 51, -3):
        fnt = font(size, True)
        lines = wrap_to_pixels(draw, text, fnt, width, max_lines + 1)
        if len(lines) <= max_lines:
            return lines, fnt
    return wrap_to_pixels(draw, text, font(52, True), width, max_lines), font(52, True)


def add_logo(image):
    logo_path = ASSETS / "logo.png"
    if not logo_path.exists():
        return image
    logo = Image.open(logo_path).convert("RGBA")
    logo.thumbnail((250, 120), Image.Resampling.LANCZOS)
    image.alpha_composite(logo, (W - logo.width - 70, 65))
    return image


def remote_media(scene, index):
    url = scene.get("media_url")
    if not url:
        return None
    target = BUILD / f"remote-{index:02d}.jpg"
    request = urllib.request.Request(url, headers={"User-Agent": "LuxMediaFactory/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        target.write_bytes(response.read())
    return target


def make_slide(scene, cfg, index, total):
    palette = cfg["colors"]
    top, bottom = color(palette["background_top"]), color(palette["background_bottom"])
    accent, white = color(palette["accent"]), color(palette["text"])

    media_name = scene.get("media")
    media_path = ASSETS / media_name if media_name else remote_media(scene, index)
    if media_path and media_path.exists():
        image = cover_image(media_path)
        image = ImageEnhance.Contrast(image).enhance(1.08)
        shade = Image.new("RGBA", (W, H), (3, 6, 13, 105))
        lower = Image.new("RGBA", (W, H), (3, 6, 13, 0))
        mask = Image.new("L", (W, H))
        md = ImageDraw.Draw(mask)
        for y in range(H):
            md.line((0, y, W, y), fill=int(30 + 205 * (y / H)))
        lower.putalpha(mask)
        image = Image.alpha_composite(image.convert("RGBA"), shade)
        image = Image.alpha_composite(image, lower)
    else:
        image = gradient(top, bottom).convert("RGBA")
        image = glow(image, (930, 170), 370, (*accent, 72))
        image = glow(image, (90, 1450), 450, (32, 78, 190, 35))

    draw = ImageDraw.Draw(image)
    pad = 72

    # Reading-progress rail
    draw.rounded_rectangle((pad, 66, W - pad, 76), radius=5, fill=(255, 255, 255, 35))
    progress = pad + int((W - 2 * pad) * ((index + 1) / total))
    draw.rounded_rectangle((pad, 66, progress, 76), radius=5, fill=accent)

    eyebrow = scene.get("eyebrow", cfg["brand"]).upper()
    eyebrow_font = font(29, True)
    box = draw.textbbox((0, 0), eyebrow, font=eyebrow_font)
    pill_w = box[2] + 48
    draw.rounded_rectangle((pad, 158, pad + pill_w, 218), radius=30, fill=(*accent, 255))
    draw.text((pad + 24, 171), eyebrow, font=eyebrow_font, fill=(10, 12, 18))

    lines, headline_font = fitted_headline(draw, scene["headline"], W - 2 * pad)
    line_gap = 18
    headline_h = len(lines) * (headline_font.size + line_gap)
    y = max(360, 860 - headline_h // 2)
    for line in lines:
        draw.text((pad, y), line, font=headline_font, fill=white, stroke_width=1, stroke_fill=(0, 0, 0))
        y += headline_font.size + line_gap

    body = scene.get("body", "")
    if body:
        body_font = font(43)
        body_lines = wrap_to_pixels(draw, body, body_font, W - 2 * pad, 4)
        y += 48
        draw.rectangle((pad, y + 8, pad + 8, y + len(body_lines) * 63 - 5), fill=accent)
        for line in body_lines:
            draw.text((pad + 32, y), line, font=body_font, fill=(224, 228, 236), stroke_width=1, stroke_fill=(0, 0, 0))
            y += 63

    # CTA scene gets a stronger closing plate
    if index == total - 1:
        draw.rounded_rectangle((pad, 1460, W - pad, 1588), radius=28, fill=accent)
        cta = scene.get("cta", "FOLLOW THE BEGINNING").upper()
        cta_font = font(34, True)
        tw = draw.textbbox((0, 0), cta, font=cta_font)[2]
        draw.text(((W - tw) / 2, 1503), cta, font=cta_font, fill=(8, 10, 15))

    draw.line((pad, 1690, W - pad, 1690), fill=(255, 255, 255, 60), width=2)
    draw.text((pad, 1735), cfg["brand"], font=font(39, True), fill=white)
    draw.text((pad, 1792), cfg["tagline"], font=font(24, True), fill=accent)
    draw.text((W - 137, 1735), f"{index + 1:02d}", font=font(36, True), fill=(150, 154, 166))
    image = add_logo(image)

    path = BUILD / f"slide-{index:02d}.png"
    image.convert("RGB").save(path, optimize=True)
    return path


def run(command):
    print(" ".join(map(str, command)), flush=True)
    subprocess.run(command, check=True)


def main():
    BUILD.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    scenes = cfg["scenes"]
    segments = []

    for index, scene in enumerate(scenes):
        slide = make_slide(scene, cfg, index, len(scenes))
        segment = BUILD / f"segment-{index:02d}.mp4"
        duration = float(scene.get("duration", 4))
        frames = max(1, int(duration * FPS))
        fade_out = max(0, duration - 0.3)
        vf = (
            f"scale=1200:2134,"
            f"zoompan=z='zoom+0.0005':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},"
            f"fade=t=in:st=0:d=0.22,fade=t=out:st={fade_out}:d=0.3,"
            "format=yuv420p"
        )
        run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(slide),
            "-vf", vf, "-t", str(duration), "-r", str(FPS),
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            str(segment),
        ])
        segments.append(segment)

    concat = BUILD / "concat.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
    final_video = OUTPUT / "latest.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-c", "copy", "-movflags", "+faststart", str(final_video),
    ])
    Image.open(BUILD / "slide-00.png").save(OUTPUT / "cover.png")
    print(f"Created {final_video}", flush=True)


if __name__ == "__main__":
    main()
