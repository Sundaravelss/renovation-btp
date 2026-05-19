# Avatar Generation — Workflow & Learnings

This folder ships the **agent avatar assets** used across the ai-agency website,
plus the script that produced them and the prompt-engineering learnings collected
while iterating.

When we add a new role (or refresh an existing one), reuse this exact workflow.

---

## File layout

```
public/avatars/
├── photoreal/
│   ├── <role>.png            with-background still (source `_ok.png` from old_presets)
│   ├── <role>.alpha.png      transparent still (BiRefNet)
│   ├── <role>.mp4            8s seamless-loop video, original background
│   └── <role>.alpha.webm     8s seamless-loop video, transparent (alpha channel)
├── stylized/
│   ├── <role>.mp4
│   ├── <role>.alpha.webm
│   └── <role>.alpha.png
├── old_presets/              every previous generation, renamed by version
│   ├── old_photoreal/        all photoreal experiments (test/v2/v3/v5/v6/...)
│   │   ├── first_generation/ original gpt-image-2 stills + first mp4s
│   │   └── <role>[.alpha]-<version>[-<variant>].{mp4,webm,png}
│   └── old_stylized/         same shape for stylized
├── generate_avatar_loop.py   the generator (this directory's pipeline)
└── README.md                 (this file)
```

Roles currently in production: `assistant`, `commercial`, `comptable`,
`customer-care`, `marketing`, `recrutement`, `sales`, `social-media`. All 8
roles exist in both `photoreal/` and `stylized/`.

### Selection table — what shipped per role

The recipe each shipped clip was generated with. Use this as the starting
point when re-generating a role; only deviate if the source still has
changed.

| Role | Photoreal recipe | Stylized recipe |
|---|---|---|
| assistant      | v4 — early prompt (warm smile, no looking-down)         | v8 — `--style stylized --prompt-variant va` |
| commercial     | v8 — `--style photoreal --prompt-variant va`            | v4 — early prompt (alpha-only)              |
| comptable      | v6 — `--style photoreal --prompt-variant vb` (va over-laughed) | v7 — `--style stylized --prompt-variant va` |
| customer-care  | v5 — early single-prompt era (kept as-is)               | v7 — `--style stylized --prompt-variant va` |
| marketing      | v6 — `--style photoreal --prompt-variant va`            | v7 — `--style stylized --prompt-variant va` |
| recrutement    | v6 — `--style photoreal --prompt-variant va`            | v6 — `--style stylized --prompt-variant vb` (va was too active) |
| sales          | v6 — `--style photoreal --prompt-variant va`            | v7 — `--style stylized --prompt-variant va` |
| social-media   | v6 — `--style photoreal --prompt-variant va`            | v7 — `--style stylized --prompt-variant va` |

Defaults that worked for almost everyone:
- **Photoreal → `va`** (warm growing-smile arc). Only `comptable` needed `vb`.
- **Stylized → `va`** (lively but expression-locked, with v7 prompt that
  added visible blinks + hair micro-sway). Only `recrutement` preferred `vb`.

The v7 stylized prompt is the one that actually produced visible motion;
v6 stylized was too static (see learning #1 below).

---

## Pipeline overview

```
source PNG (≈ 1024x1792, 9:16)
        │
        ▼
fal-ai/bytedance/seedance/v1/pro/image-to-video
   • image_url + end_image_url = SAME PNG → seamless start==end loop
   • duration = "8" (5 / 8 / 10 supported)
   • resolution = "720p"
   • camera_fixed = true
        │
        ▼
<role>.mp4  (with-background, ~7 MB)
        │
        ├─→ fal-ai/ben/v2/video  (output_format=webm)  →  <role>.alpha.webm  (~2 MB)
        └─→ fal-ai/birefnet/v2  (model="Portrait")   →  <role>.alpha.png   (matted source still)
```

Why three artefacts per role:
- **`.mp4`** — drop-in `<video autoplay muted loop playsinline>`, works everywhere.
- **`.alpha.webm`** — VP9+alpha; same `<video>` tag, sits on any site background. Chromium / Firefox / Safari 16+. Use the alpha PNG as fallback for older Safari.
- **`.alpha.png`** — static cutout for slow connections, `<noscript>`, or non-video contexts.

Approx cost per role: **~$0.55** ($0.40 i2v + $0.10 video matte + $0.005 image matte).

---

## Generator script

`generate_avatar_loop.py` is self-contained. It reads `FAL_KEY_*` from
`/Users/u1060059/Downloads/setup/my_paperclip/my_setup/.env` (first non-empty),
uploads via the fal SDK, polls, downloads outputs.

### Quick recipes

Photoreal, lively warm growing-smile (default `va`):
```bash
python3 generate_avatar_loop.py \
  --image old_presets/old_photoreal/first_generation/<source>_ok.png \
  --variant keep --style photoreal --prompt-variant va --duration 8 \
  --matte --matte-png \
  --out photoreal/<role>.mp4
```

Photoreal, reserved (preserves source expression — use when `va` over-laughs):
```bash
python3 generate_avatar_loop.py \
  --image old_presets/old_photoreal/first_generation/<source>_okk.png \
  --variant keep --style photoreal --prompt-variant vb --duration 8 \
  --matte --matte-png \
  --out photoreal/<role>.mp4
```

Stylized 3D (Pixar-look), lively but expression-locked (default `va`):
```bash
python3 generate_avatar_loop.py \
  --image old_presets/old_stylized/first_generation/<source>_ok.png \
  --variant keep --style stylized --prompt-variant va --duration 8 \
  --matte --matte-png \
  --out stylized/<role>.mp4
```

CLI flags:
- `--style {photoreal,stylized}` — picks the prompt template.
- `--prompt-variant {va,vb}` — `va` = lively, `vb` = reserved/almost-still.
- `--variant {gradient,matte,keep}` — only `keep` is used in production. `gradient` and `matte` are kept for future experimentation but Seedance ignores backdrop changes when given a confident input image.
- `--duration` — 5, 8, or 10 seconds. 8 is the chosen default.
- `--matte` — adds video alpha matting (`fal-ai/ben/v2/video`).
- `--matte-png` — also matte the source PNG (`fal-ai/birefnet/v2`).
- `--model {seedance,kling}` — Kling produces invasive bokeh backgrounds; do not use for production.

### Adding a NEW agent

1. Generate the source still (`old_presets/.../<role>_ok.png` or `_okk.png`).
2. Decide `style` (photoreal vs stylized).
3. **Render BOTH `va` and `vb` in parallel** to a temp dir — the cost
   delta is trivial (~$0.55) and it avoids a re-render later. Past batches
   that skipped this step always needed a second pass. See the selection
   table above for which variant ended up shipping per role; defaults are
   photoreal=`va`, stylized=`va`, but ~25% of roles needed `vb`.
4. Spot-check both mp4 + alpha.webm. Use `vb` if:
   - photoreal laughs too much (source still already has a wide smile)
   - stylized has too-active mouth/eye motion (source has expressive features)
5. The script writes `<role>.mp4`, `<role>.alpha.webm`, `<role>.alpha.png` together.
6. Move any previous version of that role into `old_presets/old_<style>/` with
   the `<role>[.alpha]-<version>[-<variant>].<ext>` naming pattern (e.g.
   `marketing-v6-vb.mp4`).
7. Also copy the matching with-bg PNG to `photoreal/<role>.png` (we keep
   both with-bg and without-bg PNGs for photoreal — useful as `<video poster=>`).

---

## Prompt-engineering learnings (read this before tweaking prompts)

These were learned the hard way over 8 generations (test → v2 → v3 → v4 → v5
→ v6 → v7 → v8). Most of the rules below were paid for with at least one
botched batch.

### 1. Never use the word "breathing"

Seedance and Kling both overshoot the word "breathing" — instead of a soft
chest rise you get an artificial pump that breaks the welcoming feel. The
v6 stylized prompt used "breathing rhythm" and produced clips so static they
looked like still images; the v7 stylized prompt removed the word entirely
and replaced it with concrete cues, and only then did motion become visible.

Use natural alive cues instead:
- one or two slow natural blinks
- subtle hair / fabric (collar, suit shoulders) micro-sway
- soft natural smile micro-shift (corners gently lift, never opens into a laugh)
- tiny living-presence head drift (smaller than a nod, never a tilt)

### 2. Don't say "head nod" or "chin lift"

Both produce a literal head-tilt. On stylized avatars the model interprets
"chin lift" as eyes drifting upward — v3 stylized had the avatars **looking
up at the ceiling** the whole clip. The fix:
> "Eyes stay locked on the viewer at all times — never look up, never look
> down, never look away. Head stays level and centered."

### 3. Photoreal needs a smile arc, stylized needs expression-lock

- **Photoreal `va`** ("smile grows gently to a genuine warm welcoming smile
  around the middle and eases back") produced lively warmth on every role
  except `comptable`, where the source still already had a wide smile and
  the model amplified it into laughter.
- **Photoreal `vb`** preserves the source expression and only allows blinks +
  micro-motion. Used for `comptable` after `va` over-laughed.
- **Stylized `va`/`vb`** must explicitly forbid smile change. Without that,
  Seedance amplifies cartoon mouths into wide grins, talking shapes, or
  squinting eyes (v4 stylized had the commercial's eyes drift down and
  half-close mid-clip — caused by the smile-grow wording bleeding into the
  cartoon eye rig).

### 4. Background prompting is mostly ignored

`--variant gradient` / `--variant matte` were attempts to repaint the
backdrop. Seedance treats the input image as ground truth and refuses to
repaint it (v2 confirmed this on both styles). So we always run BiRefNet
matting downstream and use **`--variant keep`** for everything. This is
fine — alpha matting works regardless of the source background colour, and
the matted PNG/WebM can sit on any site background.

### 5. Seamless looping requires `end_image_url`

Seedance's `end_image_url` (and Kling's `tail_image_url`) constrains the
final frame. Pass the SAME URL as `image_url` and the loop seam becomes
invisible. Without it the loop seam is jarring; the script always wires
this. Do not disable it.

### 6. Kling 2.1 Master is unusable for this site

Tested in `test/`. Kling produces a strong overlapping bokeh-blur background
that clashes with the dark site palette and can't be turned off — even with
`--variant matte` in the prompt. Stick with Seedance Pro.

### 7. Seedance ignores `negative_prompt`

It only takes a `prompt` field. To suppress unwanted motion (looking down,
laughing, smile growing), repeat the constraint **inline** in the positive
prompt. Don't rely on the negative-prompt block in the script — it's only
sent to Kling, and we don't use Kling.

### 8. Generate two variants per role and pick

For most roles `va` (lively) wins, but always render `vb` (reserved) at the
same time. The marginal cost is ~$0.55 and it lets you pick the right
balance per character. We did this from v6 onward and it caught
`photoreal/comptable` (laughed too hard on `va`) and
`stylized/recrutement` (too active on `va`) — both shipped from `vb`.

### 9. Save the source PNGs

`old_presets/old_<style>/first_generation/` holds the original gpt-image-2
stills (`*_ok.png`, `*_okk.png`) — these are the canonical faces. Always
re-render from these, not from a previously matted/edited version. Two
sources can exist per role (`_ok` and `_okk`) — pick the one with the most
neutral expression for `va` recipes, since the model will animate from
that pose.

### 10. Stylized vb is for already-expressive sources

If the source still already has lots of personality (e.g. spiky hair,
animated mouth shape), even the locked-down stylized `va` will exaggerate
it. For those, switch to `vb` which adds only blinks + micro-sway.
`stylized/recrutement` was the textbook case.

---

## Pricing reference (FAL, late 2026 rates)

| Step | Model | Cost |
|---|---|---|
| i2v | `fal-ai/bytedance/seedance/v1/pro/image-to-video` | $0.05 / sec output |
| video matte | `fal-ai/ben/v2/video` | flat ~$0.10 / 8s clip |
| image matte | `fal-ai/birefnet/v2` (Portrait) | ~$0.005 / image |
| (alt i2v, unused) | `fal-ai/kling-video/v2.1/master/image-to-video` | $0.10–0.50 / sec output |

Per role @ 8s: **~$0.55** for one variant; **~$1.10** if rendering both `va` and `vb` (recommended workflow). Eight roles × 2 styles × 2 variants ≈ **$18** for a full sweep — what we actually spent on the 8-role v6+v7+v8 batches.

---

## Embedding in the website

Recommended pattern for the agent-showcase tile:

```html
<picture>
  <video
    autoplay muted loop playsinline preload="metadata"
    poster="/avatars/photoreal/<role>.png">
    <source src="/avatars/photoreal/<role>.alpha.webm" type="video/webm">
    <source src="/avatars/photoreal/<role>.mp4"        type="video/mp4">
  </video>
</picture>
```

For older Safari without alpha-WebM support, the `<video>` falls back to the
opaque `.mp4`. For browsers without video at all, the `poster` PNG shows.

For an alpha-aware tile (gradient site bg shows through the avatar's
absent-background area), prefer `.alpha.webm` over `.mp4`.

---

## When something feels off

Common rendering issues and fixes (each row corresponds to a real botch
caught during the v1→v8 iteration):

| Symptom | Cause from history | Fix |
|---|---|---|
| Photoreal laughs too much | v6 photoreal `comptable` (`va` over-amplified existing smile) | Use `vb` for that role |
| Photoreal feels dull / static | v3 photoreal — old "subtle breathing + blink" wording | Use the v4+ `va` prompt with the warm-smile arc |
| Stylized barely moves | v6 stylized — "breathing rhythm" overshoot collapsed motion | Use the v7 prompt (concrete cues, no "breathing") |
| Stylized eyes drift / half-close | v4 stylized — smile-grow wording bled into cartoon eyes | Use `vb` (locks expression) |
| Avatar looking up at ceiling | v3 stylized — "small chin lift as a quiet greeting" | Replace with explicit "head stays level, eyes locked on viewer" |
| Avatar looking down | v3 photoreal — "head nod" wording | Same — explicit "no looking down" inline |
| Bokeh background appears | `test/` Kling clips | Stick to `--model seedance` (default) |
| Loop seam visible | Pre-script experiments missing `end_image_url` | Script always wires it — don't disable |
| Identity drifts mid-clip | Single i2v call without seed-image on both ends | Always pass the same URL as both `image_url` and `end_image_url` |
| Background mismatch with site | Tried `--variant gradient` / `matte` to repaint | Don't fight Seedance — use `keep` + `--matte` for an alpha video that drops onto any site bg |
