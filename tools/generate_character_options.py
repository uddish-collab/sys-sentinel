"""Generate visual preview of 4 minimalist, non-slop character concepts for SENTI."""

import os
import sys
import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QLinearGradient,
    QPainterPath,
    QImage,
)
from PySide6.QtWidgets import QApplication

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = QApplication.instance() or QApplication(sys.argv)

w, h = 900, 320
img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
img.fill(QColor("#0a0a0c"))

p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

# Draw Title Header
p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
p.setPen(QColor("#f5f6f8"))
p.drawText(QRectF(0, 16, w, 28), Qt.AlignmentFlag.AlignCenter, "SENTI CHARACTER REDESIGN — 4 MINIMALIST OPTIONS")

p.setFont(QFont("Segoe UI", 9))
p.setPen(QColor("#8e939c"))
p.drawText(QRectF(0, 42, w, 22), Qt.AlignmentFlag.AlignCenter, "Pure minimalist, hand-crafted vector companions (No complex AI robot slop)")

cards = [
    {
        "id": "A",
        "title": "Option A: The Pebble",
        "subtitle": "Pure Mochi-Style Squircle",
        "desc": "Ultra-clean matte squircle, two ink pill eyes, hidden paws that wave.",
    },
    {
        "id": "B",
        "title": "Option B: The Neko Sentinel",
        "subtitle": "Minimalist Geometric Ears",
        "desc": "Soft rounded body with sleek micro-ears and expressive happy crescents.",
    },
    {
        "id": "C",
        "title": "Option C: The Nimbus",
        "subtitle": "Floating Cloud Sprite",
        "desc": "Gentle floating scalloped base with detached hovering paws.",
    },
    {
        "id": "D",
        "title": "Option D: The Visor Astronaut",
        "subtitle": "Cyber-Luxury Minimalist",
        "desc": "Ceramic pebble shell with tinted obsidian visor and glowing eyes.",
    },
]

card_w = 200
card_h = 220
spacing = 18
start_x = (w - (4 * card_w + 3 * spacing)) / 2
start_y = 75

for i, c in enumerate(cards):
    cx = start_x + i * (card_w + spacing)
    cy = start_y
    card_rect = QRectF(cx, cy, card_w, card_h)

    # Card background
    p.setPen(QPen(QColor(255, 255, 255, 14), 1.0))
    p.setBrush(QColor("#141518"))
    p.drawRoundedRect(card_rect, 16.0, 16.0)

    # Badge ID
    p.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
    p.setPen(QColor("#00e5ff"))
    p.drawText(QRectF(cx + 12, cy + 12, 40, 20), Qt.AlignmentFlag.AlignLeft, c["id"])

    # Mascot container center
    mcx = cx + card_w / 2.0
    mcy = cy + 70.0

    # Draw specific character
    p.save()
    p.translate(mcx, mcy)

    if c["id"] == "A":
        # OPTION A: The Pebble (Pure Mochi squircle)
        # Body
        body_rect = QRectF(-34, -26, 68, 52)
        bg = QLinearGradient(0, -26, 0, 26)
        bg.setColorAt(0.0, QColor("#f4f4f6"))
        bg.setColorAt(1.0, QColor("#d6d7dc"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(body_rect, 22.0, 22.0)

        # Little waving right paw
        paw = QRectF(24, -20, 12, 18)
        p.save()
        p.translate(30, -11)
        p.rotate(-25)
        p.setBrush(QColor("#ededf0"))
        p.drawRoundedRect(QRectF(-6, -9, 12, 18), 6.0, 6.0)
        p.restore()

        # Eyes
        p.setBrush(QColor("#1a1412"))
        p.drawRoundedRect(QRectF(-17, -5, 8, 14), 4.0, 4.0)
        p.drawRoundedRect(QRectF(9, -5, 8, 14), 4.0, 4.0)

        # Subtle peach blush
        p.setBrush(QColor(255, 120, 120, 70))
        p.drawEllipse(QPointF(-24, 7), 5.0, 3.0)
        p.drawEllipse(QPointF(24, 7), 5.0, 3.0)

    elif c["id"] == "B":
        # OPTION B: The Neko Sentinel (Ears)
        # Ears behind
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#d2d4da"))
        # Left ear
        path_l = QPainterPath()
        path_l.moveTo(-28, -14)
        path_l.lineTo(-20, -38)
        path_l.lineTo(-8, -22)
        path_l.closeSubpath()
        p.drawPath(path_l)
        # Right ear
        path_r = QPainterPath()
        path_r.moveTo(28, -14)
        path_r.lineTo(20, -38)
        path_r.lineTo(8, -22)
        path_r.closeSubpath()
        p.drawPath(path_r)

        # Inner ear pink
        p.setBrush(QColor(255, 140, 160, 140))
        path_in_l = QPainterPath()
        path_in_l.moveTo(-24, -16)
        path_in_l.lineTo(-19, -32)
        path_in_l.lineTo(-11, -22)
        path_in_l.closeSubpath()
        p.drawPath(path_in_l)

        path_in_r = QPainterPath()
        path_in_r.moveTo(24, -16)
        path_in_r.lineTo(19, -32)
        path_in_r.lineTo(11, -22)
        path_in_r.closeSubpath()
        p.drawPath(path_in_r)

        # Body
        body_rect = QRectF(-32, -24, 64, 50)
        bg = QLinearGradient(0, -24, 0, 26)
        bg.setColorAt(0.0, QColor("#f6f6f8"))
        bg.setColorAt(1.0, QColor("#dcdde2"))
        p.setBrush(bg)
        p.drawRoundedRect(body_rect, 22.0, 22.0)

        # Waving paw
        p.save()
        p.translate(26, -10)
        p.rotate(-20)
        p.setBrush(QColor("#f0f0f4"))
        p.drawRoundedRect(QRectF(-6, -9, 12, 18), 6.0, 6.0)
        # Little pink pad
        p.setBrush(QColor(255, 140, 160, 160))
        p.drawEllipse(QPointF(0, -2), 3.0, 3.0)
        p.restore()

        # Happy eyes (^ ^)
        p.setPen(QPen(QColor("#1a1412"), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Left happy arc
        path_eye_l = QPainterPath()
        path_eye_l.moveTo(-18, 2)
        path_eye_l.quadTo(-13, -7, -8, 2)
        p.drawPath(path_eye_l)
        # Right happy arc
        path_eye_r = QPainterPath()
        path_eye_r.moveTo(6, 2)
        path_eye_r.quadTo(11, -7, 16, 2)
        p.drawPath(path_eye_r)

        # Blush
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 120, 140, 80))
        p.drawEllipse(QPointF(-20, 9), 5.0, 3.0)
        p.drawEllipse(QPointF(18, 9), 5.0, 3.0)

    elif c["id"] == "C":
        # OPTION C: The Nimbus (Cloud Sprite)
        p.setPen(Qt.PenStyle.NoPen)
        cloud_path = QPainterPath()
        cloud_path.moveTo(-30, 10)
        cloud_path.quadTo(-34, -24, 0, -28)
        cloud_path.quadTo(34, -24, 30, 10)
        # Scalloped bottom
        cloud_path.quadTo(20, 22, 10, 16)
        cloud_path.quadTo(0, 24, -10, 16)
        cloud_path.quadTo(-20, 22, -30, 10)
        cloud_path.closeSubpath()

        bg = QLinearGradient(0, -28, 0, 20)
        bg.setColorAt(0.0, QColor("#ffffff"))
        bg.setColorAt(1.0, QColor("#dce3ec"))
        p.setBrush(bg)
        p.drawPath(cloud_path)

        # Hovering waving paw
        p.save()
        p.translate(34, -8)
        p.rotate(-30)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(-5, -8, 10, 16), 5.0, 5.0)
        p.restore()

        # Eyes: dot-style cute wide eyes
        p.setBrush(QColor("#181920"))
        p.drawEllipse(QPointF(-14, 0), 4.5, 5.5)
        p.drawEllipse(QPointF(14, 0), 4.5, 5.5)

        # Cyan glow cheeks
        p.setBrush(QColor(34, 211, 238, 90))
        p.drawEllipse(QPointF(-20, 8), 4.5, 3.0)
        p.drawEllipse(QPointF(20, 8), 4.5, 3.0)

    elif c["id"] == "D":
        # OPTION D: The Visor Astronaut (Cyber-Luxury)
        body_rect = QRectF(-33, -26, 66, 52)
        bg = QLinearGradient(0, -26, 0, 26)
        bg.setColorAt(0.0, QColor("#f2f3f5"))
        bg.setColorAt(1.0, QColor("#c8cad0"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(body_rect, 22.0, 22.0)

        # Dark tinted obsidian glass visor
        visor_rect = QRectF(-25, -12, 50, 26)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        p.setBrush(QColor("#0d0e12"))
        p.drawRoundedRect(visor_rect, 13.0, 13.0)

        # Glowing cyan pill eyes inside visor
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#00e5ff"))
        p.drawRoundedRect(QRectF(-15, -6, 7, 13), 3.5, 3.5)
        p.drawRoundedRect(QRectF(8, -6, 7, 13), 3.5, 3.5)

        # Waving astronaut glove
        p.save()
        p.translate(28, -12)
        p.rotate(-25)
        p.setBrush(QColor("#e8e9ed"))
        p.drawRoundedRect(QRectF(-6, -9, 12, 18), 6.0, 6.0)
        p.setBrush(QColor("#00e5ff"))
        p.drawRoundedRect(QRectF(-4, 4, 8, 3), 1.5, 1.5)
        p.restore()

    p.restore()

    # Text details
    p.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
    p.setPen(QColor("#f5f6f8"))
    p.drawText(QRectF(cx + 8, cy + 120, card_w - 16, 20), Qt.AlignmentFlag.AlignCenter, c["title"])

    p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
    p.setPen(QColor("#8e939c"))
    p.drawText(QRectF(cx + 8, cy + 142, card_w - 16, 18), Qt.AlignmentFlag.AlignCenter, c["subtitle"])

    p.setFont(QFont("Segoe UI", 8))
    p.setPen(QColor("#6b7079"))
    p.drawText(QRectF(cx + 12, cy + 164, card_w - 24, 46), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, c["desc"])

p.end()

output_path = os.path.join(REPO_ROOT, "screenshots", "character_options.png")
img.save(output_path)
print(f"Generated {output_path} successfully!")
