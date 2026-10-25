"""生成 4:3 比赛作品封面。输出为 1600×1200 JPG 与 PNG。"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables/competition'
ASSETS = ROOT / 'data/competition-build/assets'
FONT_MEDIUM = '/System/Library/Fonts/STHeiti Medium.ttc'
FONT_LIGHT = '/System/Library/Fonts/STHeiti Light.ttc'
W, H, SCALE = 1600, 1200, 2


def font(size, bold=False):
    return ImageFont.truetype(FONT_MEDIUM if bold else FONT_LIGHT, size * SCALE)


def rounded(draw, box, radius, fill, outline=None, width=1):
    scaled = tuple(v * SCALE for v in box)
    draw.rounded_rectangle(
        scaled, radius=radius * SCALE, fill=fill, outline=outline,
        width=width * SCALE,
    )


def ellipse(draw, box, fill, outline=None, width=1):
    scaled = tuple(v * SCALE for v in box)
    draw.ellipse(scaled, fill=fill, outline=outline, width=width * SCALE)


def polygon(draw, points, fill):
    draw.polygon([(x * SCALE, y * SCALE) for x, y in points], fill=fill)


def text(draw, xy, value, size, fill, bold=False, anchor=None):
    draw.text(
        (xy[0] * SCALE, xy[1] * SCALE), value, font=font(size, bold),
        fill=fill, anchor=anchor,
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    image = Image.new('RGB', (W * SCALE, H * SCALE), '#f8fbff')
    draw = ImageDraw.Draw(image)

    # Calm diagonal gradient with a warm paper area for a crop-safe title.
    for y in range(H * SCALE):
        t = y / (H * SCALE)
        left = (11 + round(8 * t), 35 + round(13 * t), 66 + round(18 * t))
        draw.line((0, y, W * SCALE, y), fill=left)
    glow = Image.new('RGBA', image.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    ellipse(gd, (-220, 710, 940, 1480), (37, 99, 235, 115))
    ellipse(gd, (970, -270, 1870, 700), (28, 181, 166, 78))
    glow = glow.filter(ImageFilter.GaussianBlur(180 * SCALE))
    image = Image.alpha_composite(image.convert('RGBA'), glow).convert('RGB')
    draw = ImageDraw.Draw(image)

    # Subtle route motif keeps key content away from the visual edge.
    for offset, alpha in [(0, 70), (26, 38)]:
        layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.arc(
            ((570 + offset) * SCALE, (-60 + offset) * SCALE,
             (1730 + offset) * SCALE, (1100 + offset) * SCALE),
            start=115, end=335, fill=(170, 206, 255, alpha),
            width=4 * SCALE,
        )
        image = Image.alpha_composite(image.convert('RGBA'), layer).convert('RGB')
    draw = ImageDraw.Draw(image)

    # Brand and headline stay inside a safe central region for later cropping.
    rounded(draw, (92, 78, 438, 132), 27, '#1f68ed')
    ellipse(draw, (111, 94, 127, 110), '#ffffff')
    text(draw, (139, 91), '2026 / 养老服务协同', 23, 'white', True)

    polygon(draw, [(100, 196), (132, 168), (164, 196)], '#ffffff')
    rounded(draw, (110, 193, 154, 248), 4, '#ffffff')
    polygon(draw, [(119, 228), (132, 210), (145, 228)], '#2563eb')

    text(draw, (100, 276), '颐养通', 104, '#ffffff', True)
    text(draw, (100, 420), '让每一次上门照护', 56, '#ffffff', True)
    text(draw, (100, 498), '都有记录、有依据、有温度', 56, '#ffffff', True)
    text(draw, (106, 606), '社区养老协同 · 履约凭证 · 双层结算', 29, '#c8dcff')

    for x, title, sub, color in [
        (104, '社区签约', '高龄补贴', '#2563eb'),
        (295, '老人选人', '自主预约', '#158579'),
        (486, '上门留痕', '打卡合影', '#2563eb'),
    ]:
        rounded(draw, (x, 691, x + 164, 800), 20, (255, 255, 255, 242))
        rounded(draw, (x + 18, 713, x + 28, 723), 5, color)
        text(draw, (x + 39, 704), title, 26, '#183456', True)
        text(draw, (x + 39, 748), sub, 21, '#60748c')

    rounded(draw, (105, 868, 697, 944), 22, '#f5b84b')
    text(draw, (130, 885), '公司付费  ·  个人与社区免费使用平台', 26, '#183456', True)
    text(draw, (106, 1007), 'Mac 本地可运行', 25, '#c8dcff', True)
    text(draw, (106, 1055), '作品编号 1024', 22, '#91adda')

    # Product story panel: recognizable care people, protective home, and a proof card.
    rounded(draw, (815, 131, 1503, 1068), 55, (246, 250, 255, 247))
    rounded(draw, (854, 171, 1464, 1026), 42, '#eef4ff')

    # Home outline.
    polygon(draw, [(925, 443), (1164, 248), (1403, 443)], '#183456')
    rounded(draw, (954, 420, 1374, 854), 34, '#ffffff')
    rounded(draw, (1082, 625, 1246, 854), 26, '#d8e6fb')
    polygon(draw, [(1159, 517), (1212, 573), (1199, 581), (1212, 599),
                   (1179, 644), (1139, 599), (1152, 589), (1140, 577)],
            '#2563eb')

    # Caregiver and elder as simple, dignified editorial figures.
    # They sit inside the image's central crop-safe area.
    ellipse(draw, (990, 456, 1090, 556), '#d9aa82')
    rounded(draw, (974, 535, 1104, 765), 51, '#2563eb')
    ellipse(draw, (1025, 432, 1085, 490), '#263955')
    rounded(draw, (1011, 568, 1065, 735), 24, '#ffffff')
    ellipse(draw, (1193, 471, 1286, 564), '#d8aa85')
    rounded(draw, (1177, 545, 1308, 780), 52, '#158579')
    ellipse(draw, (1204, 458, 1275, 515), '#d8dce1')
    rounded(draw, (1184, 570, 1308, 608), 19, '#b9e4de')
    polygon(draw, [(1195, 567), (1297, 567), (1278, 625), (1214, 625)],
            '#5fc3b5')

    # Evidence card layered over the scene.
    rounded(draw, (1032, 811, 1436, 1037), 28, '#183456')
    rounded(draw, (1052, 832, 1114, 894), 20, '#f5b84b')
    text(draw, (1083, 861), '✓', 32, '#183456', True, 'mm')
    text(draw, (1128, 830), '订单有凭证', 29, 'white', True)
    text(draw, (1054, 907), '地址打卡 · 结束合影 · 原始账本', 16, '#c8dcff')
    text(draw, (1054, 958), '社区 → 公司    180 服务币', 20, 'white', True)
    text(draw, (1054, 1000), '公司 → 员工    107.50', 18, '#91adda')
    text(draw, (1249, 1000), '酬金依据', 16, '#91adda')

    # Small electric-bike route badge.
    rounded(draw, (867, 872, 1014, 1028), 24, '#f5b84b')
    text(draw, (887, 892), '电瓶车行程', 20, '#183456', True)
    ellipse(draw, (886, 963, 916, 993), None, '#183456', 4)
    ellipse(draw, (966, 963, 996, 993), None, '#183456', 4)
    draw.line((916 * SCALE, 978 * SCALE, 966 * SCALE, 978 * SCALE),
              fill='#183456', width=6 * SCALE)
    draw.line((941 * SCALE, 978 * SCALE, 926 * SCALE, 950 * SCALE),
              fill='#183456', width=5 * SCALE)

    image = image.resize((W, H), Image.Resampling.LANCZOS)
    jpg = OUT / '颐养通_作品封面_4x3.jpg'
    png = OUT / '颐养通_作品封面_4x3.png'
    image.save(jpg, 'JPEG', quality=94, optimize=True, progressive=True)
    image.save(png, 'PNG', optimize=True)
    assert image.size == (1600, 1200)
    assert jpg.stat().st_size < 10 * 1024 * 1024
    print(jpg)
    print(png)


if __name__ == '__main__':
    main()
