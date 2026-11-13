# The Still Man — content pipeline

Automated weekly content for The Still Man (Instagram + TikTok). Calm confidence, built daily.

## How it works

1. A weekly file in `content/weeks/YYYY-MM-DD.yaml` (Monday of the week) lists every post: date, time, captions, voiceover, b-roll searches, carousel slides.
2. Pushing that file runs **Build week** (GitHub Actions):
   - voiceover with ElevenLabs (voice K. V. Hagen – Deep Warm Natural Narrator), with word timings;
   - portrait b-roll from Pexels, graded to the brand look;
   - Reels rendered with word-synced captions (`pipeline/reel.py`), carousels with the brand template (`pipeline/carousel.py`);
   - output committed to `docs/<week>/`, served by GitHub Pages, with `docs/<week>/manifest.json`.
3. Scheduled Claude tasks publish from the manifest: Instagram via Windsor.ai, TikTok via Metricool.

## Secrets (Settings → Secrets and variables → Actions)

- `PEXELS_API_KEY` — free key from https://www.pexels.com/api/
- `ELEVENLABS_API_KEY` — from https://elevenlabs.io/app/settings/api-keys

## Brand

Ground `#15171A`, ink `#EDE8DF`, muted `#A39E95`, bronze `#C08A4E` (one bronze element per frame). Fraunces for titles, Inter for captions. No faces, no "you + flaw" copy (Meta personal-attributes policy). Fonts are SIL OFL.

## Run locally

```bash
pip install requests pyyaml pillow cairosvg
cd pipeline && PEXELS_API_KEY=... ELEVENLABS_API_KEY=... python build_week.py ../content/weeks/2026-11-16.yaml
```

B-roll videos come from Pexels (free license); credits are stored in each manifest.
