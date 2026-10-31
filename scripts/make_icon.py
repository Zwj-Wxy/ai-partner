# -*- coding: utf-8 -*-
"""生成应用图标：粉紫渐变圆角方块 + 白色爱心。

输出：
  assets/app-icon.png   512x512，用于 Streamlit 的 page_icon（变成窗口/标签图标）
  assets/app.ico        多尺寸，用于 Windows 桌面快捷方式
"""

import math
import os

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets")

SIZE = 512
TOP = (255, 143, 177)      # 浅粉
BOTTOM = (226, 62, 122)    # 玫红


def gradient(size: int) -> Image.Image:
    """竖向渐变（逐行插值，比逐像素快很多）。"""
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    for y in range(size):
        ratio = y / (size - 1)
        color = tuple(round(TOP[i] + (BOTTOM[i] - TOP[i]) * ratio) for i in range(3))
        draw.line([(0, y), (size, y)], fill=color)
    return img


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def heart_points(cx: float, cy: float, scale: float, count: int = 240):
    """参数方程画爱心。"""
    points = []
    for i in range(count):
        t = 2 * math.pi * i / count
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        points.append((cx + x * scale, cy - y * scale))
    return points


def build_icon() -> Image.Image:
    base = gradient(SIZE).convert("RGBA")
    base.putalpha(rounded_mask(SIZE, 112))

    # 爱心：先画一层柔和的白色阴影，再画实体
    heart = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    hd = ImageDraw.Draw(heart)
    pts = heart_points(SIZE / 2, SIZE / 2 - 6, SIZE / 38)
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon(
        [(x, y + 14) for x, y in pts], fill=(120, 20, 60, 90)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    heart = Image.alpha_composite(heart, shadow)
    hd = ImageDraw.Draw(heart)
    hd.polygon(pts, fill=(255, 255, 255, 255))
    return Image.alpha_composite(base, heart)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    icon = build_icon()

    # assets/ 是源文件（给快捷方式用 ico），resources/ 里那份会被打包进程序当窗口图标
    resources_dir = os.path.join(ROOT, "resources")
    os.makedirs(resources_dir, exist_ok=True)

    png_path = os.path.join(OUT_DIR, "app-icon.png")
    icon.save(png_path, "PNG")
    shipped = os.path.join(resources_dir, "app-icon.png")
    icon.save(shipped, "PNG")

    ico_path = os.path.join(OUT_DIR, "app.ico")
    icon.save(ico_path, "ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    for path in (png_path, shipped, ico_path):
        print("saved: %s (%d bytes)" % (path, os.path.getsize(path)))


if __name__ == "__main__":
    main()
