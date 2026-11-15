"""Generate assets/senti.ico containing multi-size PNG-embedded icons (16 to 256 px).

Renders the transparent orb mascot without window background.
"""

import os
import struct
import sys

# Ensure src/ is on python path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication
from senti_mascot import render_mascot_image


ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]


def create_png_bytes(size: int) -> bytes:
    """Render the orb mascot at the given size and encode as transparent PNG bytes."""
    img = render_mascot_image(size=size, is_orb=True)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    png_bytes = bytes(buf.data())
    buf.close()
    return png_bytes


def build_ico(sizes, output_path: str):
    """Pack multi-size PNGs into a standard Windows ICO file."""
    # Ensure headless/offscreen app exists for Qt rendering
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
        # In ICO, a width/height of 256 is encoded as 0
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
