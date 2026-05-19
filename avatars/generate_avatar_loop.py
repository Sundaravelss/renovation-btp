#!/usr/bin/env python3
"""generate_avatar_loop.py — fal.ai image-to-video looping avatar generator.

Takes an approved still and produces a seamless-loop welcoming-employee
clip. Two background variants:

  --variant gradient  → keeps a warm gold-amber gradient backdrop in-frame
  --variant matte     → forces a flat plain backdrop (input for alpha matting)

With --matte the produced mp4 is also fed through `fal-ai/ben/v2/video` to
produce a transparent WebM (VP9 + alpha) saved as <out>.alpha.webm.

With --matte-png the *source* PNG is run through `fal-ai/birefnet/v2` to
produce a transparent PNG saved as <out>.alpha.png — a free static fallback.

Models:
  seedance  →  fal-ai/bytedance/seedance/v1/pro/image-to-video  (default)
  kling     →  fal-ai/kling-video/v2.1/master/image-to-video

FAL key is read from /Users/u1060059/Downloads/setup/my_paperclip/my_setup/.env
(first non-empty FAL_KEY_*).

Usage:
  python3 generate_avatar_loop.py \\
    --image /path/to/avatar.png \\
    --variant gradient \\
    --duration 8 \\
    --out  /path/to/avatar.gradient.mp4

  python3 generate_avatar_loop.py \\
    --image /path/to/avatar.png \\
    --variant matte --matte --matte-png \\
    --duration 8 \\
    --out  /path/to/avatar.matte.mp4
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib import request as urlreq, error as urlerr

ENV_PATH = Path("/Users/u1060059/Downloads/setup/my_paperclip/my_setup/.env")

MODELS: dict[str, str] = {
    "seedance": "fal-ai/bytedance/seedance/v1/pro/image-to-video",
    "kling": "fal-ai/kling-video/v2.1/master/image-to-video",
}

VIDEO_MATTE_MODEL = "fal-ai/ben/v2/video"
IMAGE_MATTE_MODEL = "fal-ai/birefnet/v2"

PROMPT_PHOTOREAL_VA = (
    "A warm welcoming portrait loop. The subject offers a friendly natural "
    "smile that grows gently from polite to a genuine warm welcoming smile "
    "around the middle of the clip and eases back. Eyes stay locked on the "
    "viewer at all times — never look up, never look down, never look away. "
    "Head stays level and centered — no chin lift, no chin drop, no nodding, "
    "no tilting. Posture is open, calm, approachable. Motion is minimal and "
    "elegant — no head sway, no jitter, no talking, no chewing, no laughing. "
    "Skin texture preserved, identity preserved exactly. Camera holds still. "
    "Vertical 9:16. Seamless loop where the final frame matches the first."
)

PROMPT_PHOTOREAL_VB = (
    "A reserved professional portrait loop. The subject's facial expression "
    "is preserved exactly as it is in the input image — do not grow the "
    "smile, do not shrink the smile, do not laugh, do not show new teeth, do "
    "not change the mouth shape. Eyes stay locked on the viewer the entire "
    "clip, with one or two natural slow blinks at most. Head stays level "
    "and centered — no chin lift, no chin drop, no nodding, no tilting. "
    "Motion is extremely subtle — only a very faint natural breathing "
    "rhythm. No head sway, no jitter, no talking, no chewing. Skin texture "
    "preserved, identity preserved exactly. Camera holds still. Vertical "
    "9:16. Seamless loop where the final frame matches the first."
)

PROMPT_STYLIZED_VA = (
    "A lively stylized 3D animated portrait loop, like a friendly Pixar "
    "character coming to life on screen. Clear visible motion throughout: "
    "the chest and shoulders rise and fall with natural breathing, the hair "
    "and any soft fabric (suit shoulders, collar) sway with very gentle "
    "micro-motion, the eyes blink two or three times naturally and slowly. "
    "The mouth makes a soft natural smile breathing — corners gently "
    "lifting and easing, never opening into a laugh, never showing new "
    "teeth. The head has a subtle alive presence with the smallest natural "
    "drift, never nodding down, never tilting, never turning away. Eyes "
    "stay locked on the viewer the whole time — no looking up, no looking "
    "down, no looking away. Identity preserved exactly, stylized 3D look "
    "preserved exactly. Camera holds still. Vertical 9:16. Seamless loop "
    "where the final frame matches the first."
)

PROMPT_STYLIZED_VB = (
    "A calm but clearly alive stylized 3D portrait loop. The character is "
    "breathing visibly: chest and shoulders rise gently up and down with a "
    "soft natural rhythm, the hair has a faint micro-sway, and the eyes "
    "perform two slow natural blinks. The expression stays warm and "
    "consistent throughout — the smile does not grow, does not shrink, does "
    "not change shape, no laughing, no new teeth showing. Head stays level "
    "and centered with only a very faint living presence — no nodding, no "
    "tilting, no turning. Eyes stay wide open and locked on the viewer the "
    "entire time — no looking up, no looking down, no looking away. "
    "Stylized 3D look preserved exactly, identity preserved exactly. Camera "
    "holds still. Vertical 9:16. Seamless loop where the final frame "
    "matches the first."
)

PROMPT_TABLE: dict[tuple[str, str], str] = {
    ("photoreal", "va"): PROMPT_PHOTOREAL_VA,
    ("photoreal", "vb"): PROMPT_PHOTOREAL_VB,
    ("stylized", "va"): PROMPT_STYLIZED_VA,
    ("stylized", "vb"): PROMPT_STYLIZED_VB,
}

# Back-compat aliases for callers that still import these names.
PROMPT_PHOTOREAL = PROMPT_PHOTOREAL_VA
PROMPT_STYLIZED = PROMPT_STYLIZED_VA
PROMPT_BASE = PROMPT_PHOTOREAL_VA

PROMPT_VARIANT_SUFFIX: dict[str, str] = {
    "gradient": (
        " Background: a soft warm gradient backdrop, smooth transition from "
        "creamy beige into muted gold and deep amber, professional and "
        "inviting. Background stays still — no bokeh drift, no particles, no "
        "shimmer."
    ),
    "matte": (
        " Background: a clean uniform plain medium-grey backdrop with no "
        "texture, no objects, no light spill onto the subject — the backdrop "
        "must be flat and uniform so it can be removed cleanly later."
    ),
    "keep": (
        " Background: keep the original backdrop from the input image "
        "exactly as it is — same lighting, same colour, same texture. Do not "
        "introduce new bokeh, particles, shimmer, camera motion, or "
        "depth-of-field changes. The background must remain visually "
        "unchanged."
    ),
}

NEGATIVE = (
    "looking up, looking down, looking away, gaze drift, head tilt, chin "
    "lift, chin drop, nodding, head sway, exaggerated motion, talking, "
    "chewing, tongue, extra fingers, identity drift, warping, flicker, text, "
    "logos, harsh shadows on face"
)


def load_fal_key(env_path: Path = ENV_PATH) -> str:
    if not env_path.exists():
        raise FileNotFoundError(f".env not found at {env_path}")
    pattern = re.compile(r"^\s*(FAL_KEY[_A-Z0-9]*)\s*=\s*(.+?)\s*$")
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        if not raw or raw.lstrip().startswith("#"):
            continue
        m = pattern.match(raw)
        if not m:
            continue
        secret = m.group(2).strip().strip('"').strip("'")
        if secret:
            return secret
    raise RuntimeError(f"No usable FAL_KEY_* found in {env_path}")


def build_prompt(variant: str, style: str, prompt_variant: str = "va") -> str:
    base = PROMPT_TABLE[(style, prompt_variant)]
    suffix = PROMPT_VARIANT_SUFFIX.get(variant, "")
    return base + suffix


def build_args(model: str, image_url: str, variant: str, duration: int, style: str,
               prompt_variant: str = "va") -> dict:
    prompt = build_prompt(variant, style, prompt_variant)
    if model == "seedance":
        return {
            "prompt": prompt,
            "image_url": image_url,
            "end_image_url": image_url,
            "resolution": "720p",
            "duration": str(duration),
            "camera_fixed": True,
        }
    if model == "kling":
        return {
            "prompt": prompt,
            "negative_prompt": NEGATIVE,
            "image_url": image_url,
            "tail_image_url": image_url,
            "duration": str(duration),
            "aspect_ratio": "9:16",
            "cfg_scale": 0.5,
        }
    raise ValueError(f"unknown model {model}")


def extract_video_url(payload: dict) -> str:
    v = payload.get("video")
    if isinstance(v, dict) and "url" in v:
        return v["url"]
    if isinstance(v, list) and v and "url" in v[0]:
        return v[0]["url"]
    raise RuntimeError(f"no video url in payload keys={list(payload)}")


def download(url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urlreq.Request(url, method="GET")
    try:
        with urlreq.urlopen(req, timeout=300) as resp:
            data = resp.read()
            dest.write_bytes(data)
            return len(data)
    except urlerr.HTTPError as e:
        raise RuntimeError(f"download failed {e.code}: {url}") from e


def _on_update_factory(stage: str):
    def on_update(update):
        cls = type(update).__name__
        logs = ""
        if hasattr(update, "logs") and update.logs:
            last = update.logs[-1] if isinstance(update.logs, list) else update.logs
            if isinstance(last, dict):
                logs = f" — {last.get('message', '')[:100]}"
        print(f"  · [{stage}] {cls}{logs}", flush=True)

    return on_update


def matte_video(video_url: str, out_path: Path, fal_client_mod) -> int:
    """Run video alpha matting via fal-ai/ben/v2/video. Saves alpha WebM."""
    print(f"\n[matte-video] {VIDEO_MATTE_MODEL} (this can take a few min)…", flush=True)
    result = fal_client_mod.subscribe(
        VIDEO_MATTE_MODEL,
        arguments={"video_url": video_url, "output_format": "webm"},
        with_logs=True,
        on_queue_update=_on_update_factory("matte-video"),
    )
    matted_url = result.get("video", {}).get("url") if isinstance(result.get("video"), dict) else None
    if not matted_url:
        raise RuntimeError(f"no matted video url in payload: {list(result)}")
    nbytes = download(matted_url, out_path)
    print(f"  · saved {out_path} ({nbytes / 1024:.1f} KB)")
    return nbytes


def matte_png(image_path: Path, out_path: Path, fal_client_mod) -> int:
    """Run image alpha matting via fal-ai/birefnet/v2. Saves transparent PNG."""
    print(f"\n[matte-png] {IMAGE_MATTE_MODEL}…", flush=True)
    image_url = fal_client_mod.upload_file(str(image_path))
    result = fal_client_mod.subscribe(
        IMAGE_MATTE_MODEL,
        arguments={
            "image_url": image_url,
            "model": "Portrait",
            "output_format": "png",
            "refine_foreground": True,
        },
        with_logs=True,
        on_queue_update=_on_update_factory("matte-png"),
    )
    matted_url = result.get("image", {}).get("url") if isinstance(result.get("image"), dict) else None
    if not matted_url:
        raise RuntimeError(f"no matted image url in payload: {list(result)}")
    nbytes = download(matted_url, out_path)
    print(f"  · saved {out_path} ({nbytes / 1024:.1f} KB)")
    return nbytes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, type=Path)
    ap.add_argument("--model", default="seedance", choices=tuple(MODELS))
    ap.add_argument("--variant", default="gradient", choices=tuple(PROMPT_VARIANT_SUFFIX))
    ap.add_argument("--style", default="photoreal", choices=("photoreal", "stylized"),
                    help="photoreal = warm growing-smile; stylized = preserve expression, eyes wide open.")
    ap.add_argument("--prompt-variant", dest="prompt_variant", default="va",
                    choices=("va", "vb"),
                    help="va = lively/welcoming; vb = reserved/almost-still (no smile change).")
    ap.add_argument("--duration", type=int, default=8,
                    help="Clip length in seconds (Seedance accepts 5/8/10).")
    ap.add_argument("--out", required=True, type=Path,
                    help="Output mp4 path. Alpha outputs are derived from this stem.")
    ap.add_argument("--matte", action="store_true",
                    help="Also run video matting; saves <out-stem>.alpha.webm")
    ap.add_argument("--matte-png", dest="matte_png", action="store_true",
                    help="Also matte the source PNG; saves <out-stem>.alpha.png")
    args = ap.parse_args()

    if not args.image.exists():
        print(f"ERROR: --image not found: {args.image}", file=sys.stderr)
        return 1

    key = load_fal_key()
    os.environ["FAL_KEY"] = key
    masked = key[:6] + "…" + key[-4:]
    print(f"FAL key  : {masked}")
    print(f"Source   : {args.image}")
    print(f"Model    : {args.model} → {MODELS[args.model]}")
    print(f"Variant  : {args.variant}")
    print(f"Style    : {args.style}")
    print(f"PromptVar: {args.prompt_variant}")
    print(f"Duration : {args.duration}s")
    print(f"Output   : {args.out}")
    print(f"Matte    : video={args.matte}  png={args.matte_png}")

    import fal_client  # noqa: WPS433 (deferred; SDK is heavy)

    print("\n[1/3] Uploading source image to fal storage…", flush=True)
    image_url = fal_client.upload_file(str(args.image))
    print(f"  · uploaded: {image_url}")

    print("\n[2/3] Submitting i2v job (2-5 min)…", flush=True)
    result = fal_client.subscribe(
        MODELS[args.model],
        arguments=build_args(args.model, image_url, args.variant, args.duration,
                             args.style, args.prompt_variant),
        with_logs=True,
        on_queue_update=_on_update_factory("i2v"),
    )

    print("\n[3/3] Downloading video…", flush=True)
    video_url = extract_video_url(result)
    nbytes = download(video_url, args.out)
    print(f"  · saved {args.out} ({nbytes / 1024:.1f} KB)")

    if args.matte:
        alpha_out = args.out.with_suffix(".alpha.webm")
        try:
            matte_video(video_url, alpha_out, fal_client)
        except Exception as exc:  # surface but don't lose the mp4
            print(f"  · matte-video failed: {exc}", file=sys.stderr)

    if args.matte_png:
        alpha_png = args.out.with_suffix(".alpha.png")
        try:
            matte_png(args.image, alpha_png, fal_client)
        except Exception as exc:
            print(f"  · matte-png failed: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
