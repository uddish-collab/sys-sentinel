"""Generate assets/senti.ico containing multi-size PNG-embedded icons (16 to 256 px).

Renders the full-bleed high-contrast Senti mascot face for crystal-clear visibility
across all Windows Explorer view modes (details, list, tiles, large icons).
"""

import math
import os
import struct
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from PySide6.QtCore import Qt, QPointF, QRectF, QBuffer, QIODevice
from PySide6.QtGui import (
    QImage, QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient, QPainterPath
)
from PySide6.QtWidgets import QApplication


ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]


def render_app_icon(size: int) -> QImage:
    """Render the full-bleed, bold Senti mascot face on a transparent canvas."""
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    cx = size / 2.0
    cy = size / 2.0

    # 1. Helmet Geometry (Fills 90% of bounding box, no wasted space)
    bw = size * 0.88
    bh = size * 0.80
    bx = cx - bw / 2.0
    by = cy - bh / 2.0 + (size * 0.02)
    corner_r = bw * 0.34
    body_rect = QRectF(bx, by, bw, bh)

    # Outer dark silhouette border for contrast against bright backgrounds
    p.setPen(QPen(QColor(10, 12, 18, 180), max(1.0, size * 0.04)))
    p.setBrush(QColor(15, 18, 26))
    p.drawRoundedRect(body_rect.adjusted(-0.5, -0.5, 0.5, 0.5), corner_r, corner_r)

    # Ceramic White / Cyber Platinum Helmet Gradient
    shell_grad = QLinearGradient(bx, by, bx, by + bh)
    shell_grad.setColorAt(0.0, QColor("#ffffff"))
    shell_grad.setColorAt(0.5, QColor("#e8ecf4"))
    shell_grad.setColorAt(1.0, QColor("#cbd5e1"))

    border_pen_w = max(1.0, size * 0.035)
    p.setPen(QPen(QColor("#00e5ff"), border_pen_w))  # Cyan signature trim
    p.setBrush(shell_grad)
    p.drawRoundedRect(body_rect, corner_r, corner_r)

    # Top specular gloss hairline (for size >= 32)
    if size >= 32:
        spec_path = QPainterPath()
        spec_path.moveTo(bx + corner_r * 0.6, by + border_pen_w)
        spec_path.lineTo(bx + bw - corner_r * 0.6, by + border_pen_w)
        p.setPen(QPen(QColor(255, 255, 255, 230), max(1.2, size * 0.025), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(spec_path)

    # 2. Obsidian Deep Black Matte Visor (Large, prominent focal point)
    vw = bw * 0.78
    vh = bh * 0.52
    vx = cx - vw / 2.0
    vy = cy - vh / 2.0 + (size * 0.015)
    visor_rect = QRectF(vx, vy, vw, vh)
    vr = vh / 2.0

    p.setPen(QPen(QColor("#0d1117"), max(1.0, size * 0.02)))
    p.setBrush(QColor("#06070a"))
    p.drawRoundedRect(visor_rect, vr, vr)

    # 3. Signature Glowing Cyan Eyes (#00e5ff)
    eye_w = max(2.5, vw * 0.22)
    eye_h = max(3.5, vh * 0.54)
    spacing = vw * 0.23

    for side in (-1, 1):
        ex = cx + side * spacing
        ey = cy + (size * 0.015)

        # Ambient Eye Glow (for size >= 32)
        if size >= 32:
            glow_r = eye_w * 1.5
            glow_grad = QRadialGradient(ex, ey, glow_r)
            glow_grad.setColorAt(0.0, QColor(0, 229, 255, 130))
            glow_grad.setColorAt(1.0, QColor(0, 229, 255, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow_grad)
            p.drawEllipse(QPointF(ex, ey), glow_r, glow_r)

        # Eye Core Capsule
        eye_rect = QRectF(ex - eye_w / 2.0, ey - eye_h / 2.0, eye_w, eye_h)
        eye_r = eye_w / 2.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#00e5ff"))
        p.drawRoundedRect(eye_rect, eye_r, eye_r)

        # Eye Specular Dot (size >= 32)
        if size >= 32:
            spec_w = max(1.5, eye_w * 0.35)
            spec_h = max(1.5, eye_h * 0.30)
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawEllipse(QRectF(ex - eye_w * 0.20, ey - eye_h * 0.28, spec_w, spec_h))

    p.end()
    return img


def create_png_bytes(size: int) -> bytes:
    """Render the application icon at the given size and encode as transparent PNG bytes."""
    img = render_app_icon(size=size)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    png_bytes = bytes(buf.data())
    buf.close()
    return png_bytes


def build_ico(sizes, output_path: str):
    """Pack multi-size PNGs into a standard Windows ICO file."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    images_data = []
    for s in sizes:
        png_data = create_png_bytes(s)
        images_data.append((s, png_data))

    num_images = len(images_data)
    # Header: idReserved (2), idType (2 = 1 for icon), idCount (2)
    header = struct.pack("<HHH", 0, 1, num_images)

    entries = []
    # Offset starts after header (6 bytes) + entries (16 * num_images bytes)
    current_offset = 6 + (16 * num_images)

    for size, data in images_data:
        w_byte = 0 if size >= 256 else size
        h_byte = 0 if size >= 256 else size
        data_len = len(data)

        entry = struct.pack(
            "<BBBBHHII",
            w_byte,
            h_byte,
            0,              # Color count (0 for 32bpp)
            0,              # Reserved
            1,              # Color planes
            32,             # Bits per pixel
            data_len,       # Image byte size
            current_offset, # File offset
        )
        entries.append(entry)
        current_offset += data_len

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(header)
        for entry in entries:
            f.write(entry)
        for _, data in images_data:
            f.write(data)

    print(f"Generated multi-size icon: {output_path} ({len(sizes)} sizes: {sizes})")


if __name__ == "__main__":
    assets_dir = os.path.join(REPO_ROOT, "assets")
    ico_path = os.path.join(assets_dir, "senti.ico")
    build_ico(ICON_SIZES, ico_path)
