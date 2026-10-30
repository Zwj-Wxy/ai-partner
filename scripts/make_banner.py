# -*- coding: utf-8 -*-
"""生成 README 顶部横幅 docs/banner.png（跑一次即可，可重复生成）。

用法： python scripts/make_banner.py
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "banner.png")

W, H = 1280, 420
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"

TITLE = "AI 智能伴侣"
SUBTITLE = "会记住你每一次聊天的 AI 伴侣"
TAGS = "Streamlit  +  DeepSeek     本地运行     数据不上云     可打包 exe"


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def main() -> None:
    # 1. 对角渐变背景
    base = Image.new("RGB", (W, H))
    px = base.load()
    c1, c2, c3 = (20, 12, 44), (58, 24, 84), (120, 40, 110)
    for y in range(H):
        for x in range(W):
            t = (x / W) * 0.65 + (y / H) * 0.35
            if t < 0.6:
                px[x, y] = lerp(c1, c2, t / 0.6)
            else:
                px[x, y] = lerp(c2, c3, (t - 0.6) / 0.4)
    img = base.convert("RGBA")

    # 2. 右下角粉色光晕
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(28, 0, -1):
        r = int(70 + i * 11)
        alpha = int(9 * (1 - i / 29))
        gd.ellipse([1120 - r, 300 - r, 1120 + r, 300 + r], fill=(255, 107, 157, alpha))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(18)))

    # 3. 右侧爱心（参数方程，边缘柔化）
    heart = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(heart)
    cx, cy, scale = 1075, 205, 8.6
    pts = []
    for deg in range(0, 3600):
        t = math.radians(deg / 10)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * scale, cy - y * scale))
    hd.polygon(pts, fill=(255, 118, 165, 205))

    # 高光
    hl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hld = ImageDraw.Draw(hl)
    hld.ellipse([cx - 120, cy - 150, cx - 30, cy - 60], fill=(255, 255, 255, 70))
    heart = Image.alpha_composite(heart, hl.filter(ImageFilter.GaussianBlur(22)))
    img = Image.alpha_composite(img, heart)

    # 4. 文字（注意：必须在所有 alpha_composite 之后取 Draw，否则画到已被替换的旧图上）
    draw = ImageDraw.Draw(img)
    f_title = ImageFont.truetype(FONT_BOLD, 92)
    f_sub = ImageFont.truetype(FONT_REG, 30)
    f_tag = ImageFont.truetype(FONT_REG, 21)

    draw.text((78, 96), TITLE, font=f_title, fill=(255, 255, 255, 255))
    draw.text((82, 212), SUBTITLE, font=f_sub, fill=(255, 214, 230, 235))

    # 分隔细线
    draw.line([(84, 268), (128, 268)], fill=(255, 107, 157, 255), width=4)
    draw.text((82, 292), TAGS, font=f_tag, fill=(214, 205, 230, 215))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.convert("RGB").save(OUT, "PNG", optimize=True)
    print(f"saved: {OUT} ({os.path.getsize(OUT) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
