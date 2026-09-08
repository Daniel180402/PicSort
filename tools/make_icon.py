"""Generate the PicSort app icon (PNG, ICO, ICNS) with Pillow.

Run: python tools/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "picsort" / "assets"
SIZE = 1024
SS = 4  # supersampling factor for smooth edges
C = SIZE * SS

INDIGO = (43, 45, 107)
TEAL = (31, 182, 166)
CARD = (250, 250, 252)
SKY_TOP = (120, 190, 240)
SKY_BOTTOM = (215, 238, 250)
SUN = (255, 196, 61)
MOUNTAIN_FAR = (95, 126, 175)
MOUNTAIN_NEAR = (52, 78, 128)
GROUND = (64, 168, 120)


def gradient(width: int, height: int, top: tuple, bottom: tuple, diagonal: bool = False) -> Image.Image:
    y = np.linspace(0, 1, height)[:, None]
    x = np.linspace(0, 1, width)[None, :]
    t = (0.65 * y + 0.35 * x) if diagonal else np.broadcast_to(y, (height, width))
    top_a, bottom_a = np.array(top, float), np.array(bottom, float)
    rgb = top_a + (bottom_a - top_a) * t[..., None]
    return Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA")


def rounded_mask(width: int, height: int, radius: int) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, fill=255)
    return mask


def shadow(width: int, height: int, radius: int, blur: int, opacity: int) -> Image.Image:
    pad = blur * 3
    img = Image.new("RGBA", (width + 2 * pad, height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle([pad, pad, pad + width, pad + height], radius=radius, fill=(0, 0, 0, opacity))
    return img.filter(ImageFilter.GaussianBlur(blur))


def photo_card(width: int, height: int, with_picture: bool) -> Image.Image:
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    radius = width // 14
    card.paste(Image.new("RGBA", (width, height), CARD + (255,)), (0, 0), rounded_mask(width, height, radius))
    if not with_picture:
        return card
    border = width // 16
    pw, ph = width - 2 * border, height - 2 * border
    picture = gradient(pw, ph, SKY_TOP, SKY_BOTTOM)
    draw = ImageDraw.Draw(picture)
    r = pw // 7
    draw.ellipse([pw * 0.66 - r, ph * 0.28 - r, pw * 0.66 + r, ph * 0.28 + r], fill=SUN + (255,))
    draw.polygon([(0, ph * 0.78), (pw * 0.30, ph * 0.40), (pw * 0.55, ph * 0.70), (pw * 0.72, ph * 0.52), (pw, ph * 0.80), (pw, ph), (0, ph)], fill=MOUNTAIN_FAR + (255,))
    draw.polygon([(0, ph), (0, ph * 0.86), (pw * 0.22, ph * 0.60), (pw * 0.48, ph * 0.86), (pw * 0.62, ph * 0.74), (pw * 0.85, ph), ], fill=MOUNTAIN_NEAR + (255,))
    draw.rectangle([0, ph * 0.90, pw, ph], fill=GROUND + (255,))
    card.paste(picture, (border, border), rounded_mask(pw, ph, radius // 2))
    return card


def paste_rotated(base: Image.Image, layer: Image.Image, center: tuple[int, int], angle: float) -> None:
    rotated = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    base.alpha_composite(rotated, (center[0] - rotated.width // 2, center[1] - rotated.height // 2))


def build() -> Image.Image:
    canvas = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    margin = int(C * 0.08)  # transparent margin so the icon sits well on macOS
    inner = C - 2 * margin
    background = gradient(inner, inner, INDIGO, TEAL, diagonal=True)
    canvas.paste(background, (margin, margin), rounded_mask(inner, inner, inner // 5))

    cw, ch = int(inner * 0.56), int(inner * 0.44)
    cx, cy = C // 2, int(C * 0.52)
    for angle, offset, with_picture in ((-14, (-int(inner * 0.06), -int(inner * 0.05)), False), (7, (int(inner * 0.05), -int(inner * 0.02)), False), (-3, (0, int(inner * 0.03)), True)):
        centre = (cx + offset[0], cy + offset[1])
        paste_rotated(canvas, shadow(cw, ch, cw // 14, int(inner * 0.02), 110), (centre[0], centre[1] + int(inner * 0.025)), angle)
        paste_rotated(canvas, photo_card(cw, ch, with_picture), centre, angle)

    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = build()
    icon.save(ASSETS / "icon.png")
    icon.resize((256, 256), Image.LANCZOS).save(ASSETS / "icon_256.png")
    icon.save(ASSETS / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon.save(ASSETS / "icon.icns")
    print("wrote", sorted(p.name for p in ASSETS.iterdir()))


if __name__ == "__main__":
    main()
