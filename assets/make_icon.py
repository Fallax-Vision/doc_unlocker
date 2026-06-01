#!/usr/bin/env python3
"""
Generate assets/icon.ico - a simple blue->purple rounded badge with a white
key. Run once to (re)create the icon:  py assets/make_icon.py
Requires Pillow:  py -m pip install --user pillow
"""
import os
from PIL import Image, ImageDraw

S = 256
HERE = os.path.dirname(os.path.abspath(__file__))


def gradient(size, top, bottom):
    img = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        d.line([(0, y), (size, y)], fill=(r, g, b, 255))
    return img


def main():
    # Rounded gradient background
    bg = gradient(S, (47, 109, 246), (124, 58, 237))   # #2f6df6 -> #7c3aed
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=52, fill=255)
    badge = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    badge.paste(bg, (0, 0), mask)

    # White key on its own layer (fill=(0,0,0,0) punches transparent holes)
    key = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    k = ImageDraw.Draw(key)
    white = (255, 255, 255, 255)
    clear = (0, 0, 0, 0)
    # bow (ring)
    k.ellipse([46, 84, 142, 180], fill=white)
    k.ellipse([74, 112, 114, 152], fill=clear)
    # shaft
    k.rounded_rectangle([130, 116, 214, 148], radius=10, fill=white)
    # teeth
    k.rounded_rectangle([186, 148, 202, 184], radius=4, fill=white)
    k.rounded_rectangle([160, 148, 174, 174], radius=4, fill=white)

    out = Image.alpha_composite(badge, key)
    ico_path = os.path.join(HERE, "icon.ico")
    out.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                              (64, 64), (128, 128), (256, 256)])
    out.save(os.path.join(HERE, "icon.png"))
    print("wrote", ico_path)


if __name__ == "__main__":
    main()
