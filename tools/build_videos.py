"""生成两份中文旁白 MP4：项目介绍与 Mac 本地启动使用。"""
from pathlib import Path
import json
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'data/competition-build/video-work'
OUT = ROOT / 'deliverables/competition'
SLIDES = ROOT / 'data/competition-build'
ASSETS = SLIDES / 'assets'
FONT_MEDIUM = '/System/Library/Fonts/STHeiti Medium.ttc'
FONT_LIGHT = '/System/Library/Fonts/STHeiti Light.ttc'
W, H = 1280, 720
SCENE_GAP = 0.2
NAVY, BLUE, TEAL = '#183456', '#2563EB', '#158579'
INK, MUTED, PALE = '#20344C', '#60748C', '#EEF4FF'


def run(args):
    subprocess.run(args, check=True)


def probe(path):
    return float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path),
    ], text=True).strip())


def font(size, bold=False):
    return ImageFont.truetype(FONT_MEDIUM if bold else FONT_LIGHT, size)


def wrap(draw, value, width, ft):
    lines = []
    for paragraph in value.split('\n'):
        current = ''
        for char in paragraph:
            if current and draw.textlength(current + char, font=ft) > width:
                lines.append(current)
                current = char
            else:
                current += char
        lines.append(current)
    return lines


def cover(path, value, box, ft, fill=INK, align='left', spacing=7):
    image = Image.open(path).convert('RGB')
    image = ImageOps.fit(image, (box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
    return image


def fit_picture(image, box, radius=18):
    target = Image.new('RGBA', image.size, (0, 0, 0, 0))
    mask = Image.new('L', image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius, 255)
    target.paste(image.convert('RGBA'), (0, 0), mask)
    target.thumbnail((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
    return target


def put_picture(canvas, path, box, radius=18):
    image = Image.open(path).convert('RGB')
    image = ImageOps.contain(image, (box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
    image = fit_picture(image, box, radius)
    canvas.alpha_composite(
        image,
        (box[0] + (box[2] - box[0] - image.width) // 2,
         box[1] + (box[3] - box[1] - image.height) // 2),
    )


def pill(draw, box, value, fill, text_fill, size=20):
    draw.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=fill)
    draw.text((box[0] + 18, box[1] + (box[3] - box[1]) // 2), value,
              font=font(size, True), fill=text_fill, anchor='lm')


def header(canvas, step, total, title, subtitle, label):
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, W, 120), fill=NAVY)
    draw.rectangle((0, 0, W, 8), fill=BLUE)
    pill(draw, (42, 35, 184, 83), f'{step:02d} / {total:02d}', BLUE, 'white', 18)
    draw.text((206, 36), title, font=font(36, True), fill='white')
    draw.text((208, 84), subtitle, font=font(18), fill='#C8DCFF')
    draw.text((W - 44, 51), label, font=font(18, True), fill='#91ADDA', anchor='ra')


def caption(draw, value, step):
    lines = wrap(draw, value, 1190, font(22))
    if len(lines) > 2:
        lines = lines[:2]
        lines[-1] = lines[-1][:-1] + '…'
    if len(lines) > 1 and len(lines[-1].strip('。！？；')) <= 2:
        last = lines.pop()
        lines[-1] += last
    height = 16 + len(lines) * 30
    top = H - height - 20
    draw.rounded_rectangle((24, top, W - 24, H - 20), radius=14,
                           fill=(10, 29, 53, 230), outline=(93, 126, 173, 180), width=1)
    for i, line in enumerate(lines):
        draw.text((46, top + 12 + i * 30), line, font=font(22), fill='white')


def slide_frame(slide, narration, step, total, title, subtitle):
    canvas = Image.new('RGBA', (W, H), 'white')
    image = Image.open(slide).convert('RGB')
    image = ImageOps.fit(image, (W, 630), Image.Resampling.LANCZOS)
    canvas.paste(image, (0, 0))
    draw = ImageDraw.Draw(canvas)
    caption(draw, narration, step)
    return canvas.convert('RGB')


def custom_frame(step, total, title, subtitle, narration, draw_content, label='Mac 本地使用'):
    canvas = Image.new('RGBA', (W, H), '#F6F9FD')
    header(canvas, step, total, title, subtitle, label)
    draw = ImageDraw.Draw(canvas)
    draw_content(canvas, draw)
    caption(draw, narration, step)
    return canvas.convert('RGB')


def draw_terminal(canvas, draw):
    draw.rounded_rectangle((54, 153, 1226, 594), 25, fill='#101B2D')
    draw.rounded_rectangle((54, 153, 1226, 198), 25, fill='#1A2A43')
    for i, color in enumerate(('#FF6B62', '#F5B84B', '#44C97B')):
        draw.ellipse((80 + i * 29, 168, 96 + i * 29, 184), fill=color)
    draw.text((250, 176), '终端 — 颐养通本地启动', font=font(17, True), fill='#C8DCFF', anchor='mm')
    lines = [
        ('$', 'cd ~/Downloads/颐养通参赛材料/产品', '#91ADDA', '#FFFFFF'),
        ('$', 'bash 启动本地.command', '#91ADDA', '#FFFFFF'),
        ('✓', '正在检查 Mac 专用 Python 环境', '#44C97B', '#D8F5E5'),
        ('✓', '首次运行会安装依赖，请保持网络连接', '#44C97B', '#D8F5E5'),
        ('→', '本机地址：http://127.0.0.1:8000', '#71A7FF', '#FFFFFF'),
        ('…', '服务运行中。关闭终端即可停止。', '#F5B84B', '#FFF2D0'),
    ]
    for i, (mark, value, mark_c, text_c) in enumerate(lines):
        y = 235 + i * 49
        draw.text((90, y), mark, font=font(22, True), fill=mark_c)
        draw.text((124, y), value, font=font(21), fill=text_c)
    draw.rounded_rectangle((72, 535, 1208, 574), 12, fill='#192B46')
    draw.text((94, 555), '首次启动需要 Python 3.9+；后续仍可使用双击启动。',
              font=font(16), fill='#C8DCFF', anchor='lm')


def draw_file_card(icon, title, detail, box, accent=BLUE):
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    # Actual drawing occurs in parent closure; retained as a small helper by caller.


def draw_finder(canvas, draw):
    draw.rounded_rectangle((48, 150, 1232, 590), 24, fill='white', outline='#D7E2EF', width=2)
    draw.rectangle((49, 151, 273, 589), fill='#EAF0F8')
    draw.text((82, 181), '颐养通参赛材料', font=font(21, True), fill=NAVY)
    for i, value in enumerate(('材料', '产品', 'data', 'README.md')):
        if i == 1:
            draw.rounded_rectangle((63, 228 + i * 56, 258, 274 + i * 56), 12, fill='#DCE8FF')
        draw.text((82, 242 + i * 56), value, font=font(18, True), fill=BLUE if i == 1 else INK)
    draw.text((312, 183), '产品', font=font(28, True), fill=NAVY)
    files = [
        ('▶', '启动本地.command', '双击启动产品', '#2563EB'),
        ('HTML', 'web / index.html', '前端页面', '#158579'),
        ('DB', 'data / care-mac-demo.db', '独立演示数据', '#F5B84B'),
        ('MD', 'README.md', '完整说明', '#60748C'),
    ]
    for i, (mark, title, detail, color) in enumerate(files):
        x, y = 317 + (i % 2) * 435, 236 + (i // 2) * 151
        draw.rounded_rectangle((x, y, x + 393, y + 124), 17, fill=PALE, outline='#D7E2EF', width=1)
        draw.rounded_rectangle((x + 18, y + 20, x + 91, y + 91), 17, fill=color)
        draw.text((x + 54, y + 55), mark, font=font(13 if mark != '▶' else 24, True),
                  fill='white', anchor='mm')
        draw.text((x + 111, y + 22), title, font=font(19, True), fill=NAVY)
        draw.text((x + 111, y + 65), detail, font=font(16), fill=MUTED)
    draw.rounded_rectangle((55, 542, 1224, 577), 12, fill='#E8F7F2')
    draw.text((80, 559), '第一次启动：自动建立项目内 .venv-mac；互联网只用于下载依赖。',
              font=font(16, True), fill=TEAL, anchor='lm')


def draw_login(canvas, draw):
    draw.rounded_rectangle((48, 151, 1232, 588), 24, fill='#EAF0F8')
    put_picture(canvas, ASSETS / 'community-contracts.png', (65, 165, 890, 574), 18)
    draw.rounded_rectangle((915, 165, 1215, 574), 22, fill=NAVY)
    draw.text((945, 196), '本地访问', font=font(24, True), fill='#C8DCFF')
    draw.text((945, 240), '127.0.0.1', font=font(36, True), fill='white')
    draw.text((945, 285), ':8000', font=font(32, True), fill='#71A7FF')
    draw.text((945, 350), '虚构账号', font=font(20, True), fill='#F5B84B')
    draw.text((945, 393), '社区\n养老公司\n服务员\n顾客', font=font(18), fill='white', spacing=11)
    draw.text((1130, 393), '13900000000\n13900000001\n13800001001\n13800002001',
              font=font(15), fill='#C8DCFF', spacing=15)
    draw.text((945, 535), '账号密码详见提交说明', font=font(13), fill='#91ADDA')


def draw_two_screens(canvas, draw, left, right, left_title, right_title):
    for x, path, title in ((52, left, left_title), (651, right, right_title)):
        draw.rounded_rectangle((x, 150, x + 577, 590), 22, fill='white', outline='#D7E2EF', width=2)
        draw.text((x + 22, 170), title, font=font(21, True), fill=BLUE)
        put_picture(canvas, path, (x + 17, 212, x + 560, 573), 14)


def draw_steps(canvas, draw):
    draw.rounded_rectangle((55, 154, 1225, 591), 24, fill='white', outline='#D7E2EF', width=2)
    for i, (n, title, detail) in enumerate([
        ('1', '启动服务', '双击启动本地.command，等待终端显示 127.0.0.1:8000。'),
        ('2', '登录体验', '用提交说明中的社区、公司、服务员或顾客账号登录。'),
        ('3', '完成流程', '签约与补贴 → 自主预约 → 打卡合影 → 查看账本与结算。'),
        ('4', '停止服务', '关闭启动终端；下次仍从同一文件启动，演示数据会保留。'),
    ]):
        y = 190 + i * 92
        draw.ellipse((90, y, 142, y + 52), fill=BLUE if i < 3 else TEAL)
        draw.text((116, y + 26), n, font=font(20, True), fill='white', anchor='mm')
        draw.text((175, y - 1), title, font=font(23, True), fill=NAVY)
        draw.text((175, y + 35), detail, font=font(17), fill=MUTED)


def make_scene(index, frame, narration, folder, voice='Tingting', rate=185):
    png = folder / f'frame-{index:02d}.png'
    aiff = folder / f'voice-{index:02d}.aiff'
    mp4 = folder / f'scene-{index:02d}.mp4'
    frame.save(png)
    run(['say', '-v', voice, '-r', str(rate), '-o', str(aiff), narration])
    duration = probe(aiff)
    total = duration + SCENE_GAP
    fade_out = max(0.1, total - 0.28)
    run([
        'ffmpeg', '-y', '-loop', '1', '-framerate', '25', '-i', str(png),
        '-i', str(aiff), '-t', f'{total:.3f}',
        '-vf', f"fade=t=in:st=0:d=0.22,fade=t=out:st={fade_out:.3f}:d=0.25,format=yuv420p",
        '-af', f'adelay=120|120,apad=pad_dur={SCENE_GAP}',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
        '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-ac', '2',
        '-shortest', '-movflags', '+faststart', str(mp4),
    ])
    return mp4, duration


def srt_time(seconds):
    ms = round(seconds * 1000)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def write_srt(path, rows):
    blocks = []
    start = 0.0
    for i, (narration, voice_duration) in enumerate(rows, 1):
        end = start + voice_duration
        blocks.append(f'{i}\n{srt_time(start)} --> {srt_time(end)}\n{narration}\n')
        start += voice_duration + SCENE_GAP
    path.write_text('\n'.join(blocks), encoding='utf-8')


def make_video(name, scenes, folder, rate):
    folder.mkdir(parents=True, exist_ok=True)
    scene_files = []
    subtitle_rows = []
    for i, (frame, narration) in enumerate(scenes, 1):
        mp4, duration = make_scene(i, frame, narration, folder, rate=rate)
        scene_files.append(mp4)
        subtitle_rows.append((narration, duration))
        print(f'{name}: 场景 {i}/{len(scenes)}  {duration:.1f}s')
    concat = folder / 'concat.txt'
    concat.write_text(''.join(f"file '{p.name}'\n" for p in scene_files), encoding='utf-8')
    silent = folder / 'joined.mp4'
    run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat),
         '-c', 'copy', '-movflags', '+faststart', str(silent)])
    final = OUT / name
    shutil.copy2(silent, final)
    write_srt(final.with_suffix('.srt'), subtitle_rows)
    print(f'{final}: {probe(final):.1f}s, {final.stat().st_size / 1024 / 1024:.1f} MB')


def project_scenes():
    values = [
        ('new-slide-01.png', '这是颐养通，面向居家养老服务公司的社区养老协同与结算工具。社区负责签约和补贴，老人自主选择服务员，平台只向公司收取使用费。', '定位与客户', '公司付费，个人和社区免费'),
        ('new-slide-02.png', '真实的问题不是再做一张预约表，而是把补贴、服务、凭证和结算串在同一笔订单里。当前需求仍要通过真实公司访谈和一期试用验证，材料不声称已有付费客户。', '真实问题', '把一笔服务的账说清楚'),
        ('new-slide-03.png', '产品包含社区、老人、服务员和公司四个角色。社区管理准入与高龄补贴，老人跨签约公司自主选人，服务员留下凭证，公司核算项目与员工酬金。', '四个角色', '一条记录贯穿四端'),
        ('new-slide-04.png', '预约之前先确认合同有效期，再选择同一家公司的服务员与项目。价格、酬金和地址形成快照；系统检查工作时段、冲突缓冲和可预约余额。', '签约与预约', '先签约，再由老人自己选'),
        ('new-slide-05.png', '服务员骑电瓶车出行时，可以查看按预约排序的次日行程。产品估算路线距离、雨雪影响、午餐占用和电量，并提示订单间隔是否合理。自动推送提醒已经列为下一阶段。', '行程助手', '路线、天气、中餐与电量'),
        ('new-slide-06.png', '服务开始前必须填写实际地址并获取浏览器定位，服务结束后上传征得同意的合影，缺少任一项都不能完成扣款。照片受访问控制并保存哈希值，社区和公司仍需人工核验真实性。', '履约凭证', '开始打卡，结束合影'),
        ('new-slide-07.png', '补贴、充值和消费全部进入追加式服务币账本。差错通过退款或冲正保留原记录并追加调整，所有演示数值均为虚构，系统没有真实收单或支付。', '服务币账本', '每笔来源与去向可查'),
        ('new-slide-08.png', '同一份履约记录支持社区对公司、公司对员工两层结算。两层分别防止重复计入；已结算订单发生退款时，系统追加负数调整进入后续批次。结算明细可以导出 CSV。', '双层结算', '社区对公司，公司对员工'),
        ('new-slide-09.png', '这是一项可以向公司接单的服务：安装初始化、四端培训、首期账本与双层结算样例交付。产品在本机运行，首次安装依赖需要联网，不需要云服务器才能演示主业务。', '可交付产品', '安装、培训、样例一起交付'),
        ('new-slide-10.png', '商业上只向养老服务公司收费，个人与社区免费使用平台。建议按月订阅、按服务员规模分档，但价格尚未经过真实客户验证，当前没有订阅扣款功能。', '收费与验收', '公司订阅，建议价格待验证'),
        ('new-slide-11.png', '下一阶段允许普通顾客只预约、线下自行结算，不发也不扣服务币。服务员可以分享服务名片，让优秀的、平时不熟悉人工智能的服务员被更多人看见；AI 在后台处理路线、提醒和摘要。', '扩展模式', '让好服务员被更多人看见'),
        ('new-slide-12.png', '养老上门服务进入私人家庭，产品必须同时考虑老人授权、家属联系、现场安全、隐私和长期信任。技术负责把报价与履约记录说清楚，人工核验、身份审查和紧急救助仍由公司与社区承担。', '上门行业差异', '安全、尊严与长期信任'),
        ('new-slide-13.png', '评委可以先看客户和问题，再用产品走签约、预约与留痕，随后核对账本和两层结算，最后讨论待验证的订阅价格。提交材料包含可运行包、样例、可编辑演示文稿、视频和封面。', '验收方式', '能跑、能查、能讲清'),
    ]
    total = len(values)
    scenes = []
    for i, (slide, narration, title, subtitle) in enumerate(values, 1):
        frame = slide_frame(
            SLIDES / slide, narration, i, total, title, subtitle
        )
        scenes.append((frame, narration))
    return scenes


def mac_scenes():
    total = 7
    values = [
        (
            custom_frame(
                1, total, 'Mac 本地启动与使用', '从解压到登录，再到四端业务与结算',
                '这个视频从解压开始，演示怎样在这台 Mac 上启动和使用颐养通。产品使用本地 SQLite，不会连接线上服务。',
                lambda c, d: draw_steps(c, d),
            ),
            '这个视频从解压开始，演示怎样在这台 Mac 上启动和使用颐养通。产品使用本地 SQLite，不会连接线上服务。',
        ),
        (
            custom_frame(
                2, total, '第一次启动', '双击启动脚本，终端自动准备 Mac 专用环境',
                '打开提交包里的产品文件夹，双击启动本地.command。第一次运行会创建 Mac 专用 Python 环境，并安装所需依赖；这一步需要联网。',
                draw_terminal,
            ),
            '打开提交包里的产品文件夹，双击启动本地.command。第一次运行会创建 Mac 专用 Python 环境，并安装所需依赖；这一步需要联网。',
        ),
        (
            custom_frame(
                3, total, '如何找到启动文件', '产品文件夹内保留 README、Web 页面与独立演示库',
                '如果 Mac 阻止双击运行，进入产品文件夹打开终端，执行 bash 启动本地.command。依赖安装完成后，以后再次双击即可。',
                draw_finder,
            ),
            '如果 Mac 阻止双击运行，进入产品文件夹打开终端，执行 bash 启动本地.command。依赖安装完成后，以后再次双击即可。',
        ),
        (
            custom_frame(
                4, total, '打开本地产品', '使用 127.0.0.1:8000 访问四端',
                '终端出现本机地址后，浏览器打开 127.0.0.1:8000。用提交说明里的虚构账号登录社区、养老公司、服务员或顾客端。',
                draw_login,
            ),
            '终端出现本机地址后，浏览器打开 127.0.0.1:8000。用提交说明里的虚构账号登录社区、养老公司、服务员或顾客端。',
        ),
        (
            custom_frame(
                5, total, '社区与老人', '合同、资格、补贴、自主选人',
                '社区端先登记公司和合同，再核定老人资格、发放补贴；顾客端只看到有效签约公司和可选服务员，按项目与时段提交预约。',
                lambda c, d: draw_two_screens(
                    c, d, ASSETS / 'community-contracts.png', ASSETS / 'customer-book.png',
                    '社区：公司入驻与合同', '老人：跨公司自主选人',
                ),
            ),
            '社区端先登记公司和合同，再核定老人资格、发放补贴；顾客端只看到有效签约公司和可选服务员，按项目与时段提交预约。',
        ),
        (
            custom_frame(
                6, total, '服务员上门留痕', '当天地址打卡，结束后合影',
                '服务员确认订单后，在预约当天填写实际地址并允许浏览器定位再打卡。结束后必须征得老人同意、上传合影并确认，系统才会按该订单完成一次扣款。',
                lambda c, d: draw_two_screens(
                    c, d, ASSETS / 'worker-checkin.png', ASSETS / 'worker-photo.png',
                    '开始：地址与定位', '结束：合影与授权',
                ),
            ),
            '服务员确认订单后，在预约当天填写实际地址并允许浏览器定位再打卡。结束后必须征得老人同意、上传合影并确认，系统才会按该订单完成一次扣款。',
        ),
        (
            custom_frame(
                7, total, '账本、结算与停止', '先核对明细，再导出结算依据',
                '公司可以查看服务账本、生成员工酬金结算并导出 CSV；社区生成公司结算。使用结束后关闭启动终端即可停止服务，演示数据会保留在本机。',
                lambda c, d: draw_two_screens(
                    c, d, ASSETS / 'company-settle.png', ASSETS / 'community-ledger.png',
                    '公司：员工酬金结算', '社区：服务币账本',
                ),
            ),
            '公司可以查看服务账本、生成员工酬金结算并导出 CSV；社区生成公司结算。使用结束后关闭启动终端即可停止服务，演示数据会保留在本机。',
        ),
    ]
    return values


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if mode in ('all', 'project'):
        make_video('颐养通_项目介绍.mp4', project_scenes(), WORK / 'project', rate=236)
    if mode in ('all', 'mac'):
        make_video('颐养通_Mac本地启动与使用.mp4', mac_scenes(), WORK / 'mac', rate=190)
    report = {
        'width': W, 'height': H, 'fps': 25,
        'project': probe(OUT / '颐养通_项目介绍.mp4'),
        'mac': probe(OUT / '颐养通_Mac本地启动与使用.mp4'),
    }
    (WORK / 'video-report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
