from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from scripts._shared import project_path


MAX_LONG_EDGE = 2000
JPEG_QUALITY = 85


@dataclass
class NormalizedImageResult:
    source: str
    generated: str
    reason: str
    original_format: str
    output_format: str
    original_bytes: int
    output_bytes: int
    resized: bool


def _lazy_pillow():
    from PIL import Image, ImageOps

    return Image, ImageOps


def _flatten_for_jpeg(image):
    Image, _ = _lazy_pillow()
    if image.mode in {"RGBA", "LA"}:
        background = Image.new("RGB", image.size, (255, 255, 255))
        alpha = image.getchannel("A")
        background.paste(image.convert("RGBA"), mask=alpha)
        return background
    if image.mode == "P":
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        alpha = rgba.getchannel("A")
        background.paste(rgba, mask=alpha)
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _has_alpha(image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True
    return image.mode == "P" and "transparency" in image.info


def _resize_if_needed(image):
    Image, _ = _lazy_pillow()
    width, height = image.size
    longest = max(width, height)
    if longest <= MAX_LONG_EDGE:
        return image, False
    scale = MAX_LONG_EDGE / float(longest)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS), True


def normalize_image_for_docx(
    project_root: Path | str,
    source_path: Path,
    *,
    reason: str,
) -> NormalizedImageResult:
    Image, ImageOps = _lazy_pillow()

    stat = source_path.stat()
    source_bytes = stat.st_size
    with Image.open(source_path) as opened:
        image = ImageOps.exif_transpose(opened)
        original_format = (
            image.format or source_path.suffix.lstrip(".") or "unknown"
        ).upper()
        resized_image, resized = _resize_if_needed(image)
        output_format = "PNG" if _has_alpha(resized_image) else "JPEG"
        prepared = (
            resized_image
            if output_format == "PNG"
            else _flatten_for_jpeg(resized_image)
        )

        key = sha256(
            "|".join(
                [
                    str(source_path.resolve()),
                    str(stat.st_mtime_ns),
                    str(stat.st_size),
                    output_format,
                    str(MAX_LONG_EDGE),
                    str(JPEG_QUALITY),
                ]
            ).encode("utf-8")
        ).hexdigest()[:16]

        generated_dir = project_path(project_root, "temp/generated-images")
        generated_dir.mkdir(parents=True, exist_ok=True)
        output_ext = ".png" if output_format == "PNG" else ".jpg"
        output_path = generated_dir / f"{source_path.stem}-{key}{output_ext}"

        save_kwargs = {}
        if output_format == "JPEG":
            save_kwargs = {"format": "JPEG", "quality": JPEG_QUALITY, "optimize": True}
        else:
            save_kwargs = {"format": "PNG", "optimize": True}

        prepared.save(output_path, **save_kwargs)

    return NormalizedImageResult(
        source=str(source_path),
        generated=str(output_path),
        reason=reason,
        original_format=original_format,
        output_format=output_format,
        original_bytes=source_bytes,
        output_bytes=output_path.stat().st_size,
        resized=resized,
    )
