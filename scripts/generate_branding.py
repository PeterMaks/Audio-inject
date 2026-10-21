# scripts/generate_branding.py
from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT_DIR = Path(__file__).resolve().parent.parent
TAURI_DIR = ROOT_DIR / "desktop" / "src-tauri"
ICONS_DIR = TAURI_DIR / "icons"
INSTALLER_DIR = TAURI_DIR / "installer"


def create_master_icon(size: int = 1024) -> Image.Image:
    """Render a 1024x1024 Apple-style squircle icon with a vinyl disc & acoustic waveform."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Outer Apple squircle base (Obsidian dark glass)
    pad = int(size * 0.06)
    radius = int(size * 0.225)
    draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=radius,
        fill=(14, 16, 24, 255),
        outline=(255, 255, 255, 48),
        width=max(2, int(size * 0.008)),
    )

    # 2. Ambient Apple Blue & Indigo radial glow layer
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse(
        [int(size * 0.18), int(size * 0.18), int(size * 0.82), int(size * 0.82)],
        fill=(10, 132, 255, 115),
    )
    gdraw.ellipse(
        [int(size * 0.30), int(size * 0.28), int(size * 0.75), int(size * 0.78)],
        fill=(94, 92, 230, 110),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=int(size * 0.09)))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # 3. Concentric Lossless Disc grooves
    cx, cy = size // 2, size // 2
    for r_factor, alpha in [(0.34, 70), (0.28, 50), (0.22, 40)]:
        r = int(size * r_factor)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(255, 255, 255, alpha),
            width=max(2, int(size * 0.005)),
        )

    # 4. Acoustic Waveform Bars across the center
    bar_count = 11
    bar_width = int(size * 0.026)
    spacing = int(size * 0.046)
    start_x = cx - ((bar_count - 1) * spacing) // 2
    heights = [0.10, 0.16, 0.24, 0.18, 0.32, 0.40, 0.30, 0.20, 0.26, 0.15, 0.09]

    for i, h_factor in enumerate(heights):
        x = start_x + i * spacing
        half_h = int(size * h_factor * 0.5)
        color = (10, 132, 255, 255) if i % 2 == 0 else (48, 209, 88, 240)
        draw.rounded_rectangle(
            [x - bar_width // 2, cy - half_h, x + bar_width // 2, cy + half_h],
            radius=bar_width // 2,
            fill=color,
        )

    return img


def generate_tauri_icons(master: Image.Image) -> None:
    """Export all PNG, ICO, and ICNS files required by Tauri v2."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    master.save(ICONS_DIR / "icon.png", format="PNG")

    png_targets = {
        "32x32.png": 32,
        "128x128.png": 128,
        "128x128@2x.png": 256,
        "Square30x30Logo.png": 30,
        "Square44x44Logo.png": 44,
        "Square71x71Logo.png": 71,
        "Square89x89Logo.png": 89,
        "Square107x107Logo.png": 107,
        "Square142x142Logo.png": 142,
        "Square150x150Logo.png": 150,
        "Square284x284Logo.png": 284,
        "Square310x310Logo.png": 310,
        "StoreLogo.png": 50,
    }

    for filename, px in png_targets.items():
        resized = master.resize((px, px), Image.Resampling.LANCZOS)
        resized.save(ICONS_DIR / filename, format="PNG")

    # Multi-resolution Windows .ico (16px to 256px)
    master.save(
        ICONS_DIR / "icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    # Apple .icns container
    master.save(ICONS_DIR / "icon.icns", format="ICNS")
    print(f"[+] Generated all Tauri v2 icons in {ICONS_DIR}")


def create_studio_banner(width: int, height: int, master_icon: Image.Image, sidebar: bool) -> Image.Image:
    """Create a 24-bit RGB BMP for NSIS or WiX installer surfaces."""
    canvas = Image.new("RGB", (width, height), (14, 15, 22))
    draw = ImageDraw.Draw(canvas)

    # Subtle vertical/horizontal studio gradient
    for y in range(height):
        ratio = y / max(1, height - 1)
        r = int(14 + 8 * ratio)
        g = int(15 + 14 * ratio)
        b = int(22 + 32 * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Accent line along the border edge
    if sidebar:
        draw.line([(width - 1, 0), (width - 1, height)], fill=(10, 132, 255), width=2)
        icon_px = min(96, int(width * 0.56))
        badge = master_icon.resize((icon_px, icon_px), Image.Resampling.LANCZOS)
        canvas.paste(badge, ((width - icon_px) // 2, int(height * 0.14)), badge)
    else:
        draw.line([(0, height - 1), (width, height - 1)], fill=(10, 132, 255), width=2)
        icon_px = int(height * 0.72)
        badge = master_icon.resize((icon_px, icon_px), Image.Resampling.LANCZOS)
        canvas.paste(badge, (width - icon_px - 12, (height - icon_px) // 2), badge)

    return canvas.convert("RGB")


def generate_installer_bitmaps(master: Image.Image) -> None:
    """Export 24-bit RGB BMPs for NSIS (.exe) and WiX (.msi) installers."""
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)

    # NSIS (.exe) bitmaps
    create_studio_banner(164, 314, master, sidebar=True).save(
        INSTALLER_DIR / "nsis-sidebar.bmp", format="BMP"
    )
    create_studio_banner(150, 57, master, sidebar=False).save(
        INSTALLER_DIR / "nsis-header.bmp", format="BMP"
    )

    # WiX (.msi) bitmaps
    create_studio_banner(493, 312, master, sidebar=True).save(
        INSTALLER_DIR / "wix-dialog.bmp", format="BMP"
    )
    create_studio_banner(493, 58, master, sidebar=False).save(
        INSTALLER_DIR / "wix-banner.bmp", format="BMP"
    )
    print(f"[+] Generated 24-bit NSIS & WiX installer bitmaps in {INSTALLER_DIR}")


if __name__ == "__main__":
    master_icon = create_master_icon(1024)
    generate_tauri_icons(master_icon)
    generate_installer_bitmaps(master_icon)