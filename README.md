# Lux Media Factory

Zero-credit cloud video production for LuxInitium brands.

## Pipeline

1. The assistant updates `content/current.json`.
2. GitHub Actions renders a 1080×1920 MP4 with Python, Pillow, and FFmpeg.
3. The current video and cover are published under the stable `media-latest` release.
4. The assistant can send the media URL to Metricool for scheduling.

## Latest output

- [Latest video](https://github.com/LuxInitium/lux-media-factory/releases/download/media-latest/latest.mp4)
- [Latest cover](https://github.com/LuxInitium/lux-media-factory/releases/download/media-latest/cover.png)

The repository is public. Never store passwords, customer data, invoices, supplier conversations, API keys, or private business records here.
