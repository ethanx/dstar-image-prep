#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps


def parse_size(s: str) -> Tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Invalid size '{s}'. Use like 640x480.") from e


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def is_image_file(p: Path) -> bool:
    return p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def add_watermark(
    img: Image.Image,
    identity_text: str,
    caption_text: str = "",
    margin: int = 14,
) -> Image.Image:
    if not identity_text and not caption_text:
        return img

    img = img.copy()
    draw = ImageDraw.Draw(img)

    # Font (Windows-safe for now)
    try:
        font_main = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
        font_caption = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
    except OSError:
        font_main = ImageFont.load_default()
        font_caption = ImageFont.load_default()

    lines = []

    # Identity block (callsign | location)
    if identity_text:
        for line in identity_text.split("|"):
            lines.append((line, font_main))

    # Optional caption line
    if caption_text:
        lines.append((caption_text, font_caption))

    # Measure total block
    line_heights = []
    line_widths = []

    for text, font in lines:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_widths.append(w)
        line_heights.append(h)

    total_height = sum(line_heights) + (len(lines) - 1) * 4
    max_width = max(line_widths)

    # Bottom-left placement
    x = margin
    y = img.height - total_height - margin

    # Draw lines
    for (text, font), h in zip(lines, line_heights):
        draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0))
        draw.text((x, y), text, font=font, fill=(255, 255, 255))
        y += h + 4

    return img


def resize_to_fit(img: Image.Image, size: Tuple[int, int], mode: str) -> Image.Image:
    target_w, target_h = size

    # Fix phone EXIF orientation and ensure RGB
    img = ImageOps.exif_transpose(img).convert("RGB")

    if mode == "exact":
        return img.resize((target_w, target_h), Image.LANCZOS)

    src_w, src_h = img.size
    src_ratio = src_w / src_h
    tgt_ratio = target_w / target_h

    if mode == "contain":
        # Fit inside target, keep aspect, letterbox
        if src_ratio > tgt_ratio:
            new_w = target_w
            new_h = round(target_w / src_ratio)
        else:
            new_h = target_h
            new_w = round(target_h * src_ratio)

        resized = img.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
        canvas.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
        return canvas

    if mode == "cover":
        # Fill target, keep aspect, crop center
        if src_ratio > tgt_ratio:
            new_h = target_h
            new_w = round(target_h * src_ratio)
        else:
            new_w = target_w
            new_h = round(target_w / src_ratio)

        resized = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return resized.crop((left, top, left + target_w, top + target_h))

    raise ValueError(f"Unknown resize mode: {mode}")


def save_jpeg_under_limit(
    img: Image.Image,
    out_path: Path,
    max_kb: int = 200,
    quality_start: int = 88,
    quality_min: int = 35,
    quality_step: int = 3,
) -> Tuple[int, int]:
    max_bytes = max_kb * 1024
    q = quality_start

    # baseline JPEG, non-progressive, smaller chroma subsampling
    while q >= quality_min:
        img.save(
            out_path,
            format="JPEG",
            quality=q,
            optimize=True,
            progressive=False,
            subsampling=2,
        )
        size_bytes = out_path.stat().st_size
        if size_bytes <= max_bytes:
            return q, size_bytes
        q -= quality_step

    # Couldn’t reach target size: keep smallest generated
    size_bytes = out_path.stat().st_size
    return q + quality_step, size_bytes


def build_output_name(in_path: Path, prefix: str, suffix: str) -> str:
    stem = in_path.stem
    prefix = prefix.strip()
    suffix = suffix.strip()
    name = stem
    if prefix:
        name = f"{prefix}_{name}"
    if suffix:
        name = f"{name}_{suffix}"
    return f"{name}.jpg"


def process_one(in_path: Path, out_dir: Path, size: Tuple[int, int], max_kb: int,
                mode: str, watermark: str, caption: str, prefix: str, suffix: str) -> None:
    out_name = build_output_name(in_path, prefix, suffix)
    out_path = out_dir / out_name

    with Image.open(in_path) as img:
        img2 = resize_to_fit(img, size=size, mode=mode)
        img2 = add_watermark(img2, watermark, caption)
        q, b = save_jpeg_under_limit(img2, out_path, max_kb=max_kb)

    print(f"OK  {in_path.name} -> {out_path.name}  ({b/1024:.1f} KB, quality={q}, {size[0]}x{size[1]}, mode={mode})")

def run_convert(input_path: str, out_dir: str = "OUT", size=(640, 480), max_kb: int = 200,
                mode: str = "cover", watermark: str = "", caption: str = "", prefix: str = "", suffix: str = "") -> None:
    """
    Programmatic entry point for GUI usage.
    Accepts a file path OR a folder path.
    """
    in_path = Path(input_path).expanduser().resolve()
    out_dir_path = Path(out_dir).expanduser().resolve()
    ensure_output_dir(out_dir_path)

    if in_path.is_dir():
        files = [p for p in sorted(in_path.iterdir()) if p.is_file() and is_image_file(p)]
        if not files:
            raise RuntimeError(f"No supported image files found in folder: {in_path}")
        for f in files:
            process_one(f, out_dir_path, size, max_kb, mode, watermark, caption, prefix, suffix)
    elif in_path.is_file():
        if not is_image_file(in_path):
            raise RuntimeError(f"Unsupported image type: {in_path.suffix}")
        process_one(in_path, out_dir_path, size, max_kb, mode, watermark, caption, prefix, suffix)
    else:
        raise RuntimeError(f"Input not found: {in_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Prep images for D-STAR (ID-52-friendly baseline JPG).")
    ap.add_argument("input", help="Input image file OR a folder (batch).")
    ap.add_argument("-o", "--out", default="OUT", help="Output folder (default: OUT)")
    ap.add_argument("--size", type=parse_size, default=(640, 480), help="Target size like 640x480 (default)")
    ap.add_argument("--max-kb", type=int, default=200, help="Max file size in KB (default 200)")
    ap.add_argument("--mode", choices=["cover", "contain", "exact"], default="cover",
                    help="cover=crop, contain=letterbox, exact=distort. Default cover.")
    ap.add_argument("--watermark", default="", help="Watermark text (e.g., KF0VOX 73)")
    ap.add_argument("--caption", default="", help="Optional caption line (landmark, elevation, event name)",)
    ap.add_argument("--prefix", default="", help="Prefix added to output filename")
    ap.add_argument("--suffix", default="", help="Suffix added to output filename")
    args = ap.parse_args()

    in_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    ensure_output_dir(out_dir)

    if in_path.is_dir():
        files = [p for p in sorted(in_path.iterdir()) if p.is_file() and is_image_file(p)]
        if not files:
            raise SystemExit(f"No supported image files in: {in_path}")
        for f in files:
            process_one(f, out_dir, args.size, args.max_kb, args.mode, args.watermark, args.caption, args.prefix, args.suffix)
    elif in_path.is_file():
        if not is_image_file(in_path):
            raise SystemExit(f"Unsupported image type: {in_path.suffix}")
        process_one(in_path, out_dir, args.size, args.max_kb, args.mode, args.watermark, args.caption, args.prefix, args.suffix)
    else:
        raise SystemExit(f"Input not found: {in_path}")


if __name__ == "__main__":
    main()