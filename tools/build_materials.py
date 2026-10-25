"""本地生成参赛 PPTX 与独立 HTML。需要 python-pptx、Pillow。"""
from pathlib import Path
import base64
import csv
import html
import json

from PIL import Image, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'data/competition-build'
OUT = ROOT / 'deliverables/competition'
ASSETS = WORK / 'assets'
SAMPLE = json.loads((WORK / 'sample.json').read_text())
ORDERS = SAMPLE['orders']
ORDER = ORDERS[0]['order']
DAY = SAMPLE['date']
FONT = 'PingFang SC'
FONT_PATH = next(Path('/System/Library/AssetsV2').glob('**/PingFang.ttc'))
C = dict(blue='2563EB', navy='183456', ink='20344C', muted='60748C', teal='158579',
         pale='EEF4FF', paper='F6F9FD', white='FFFFFF', line='D7E2EF', amber='AE6815')
prs = Presentation()
prs.slide_width = Inches(13.333333)
prs.slide_height = Inches(7.5)
prs.core_properties.title = '颐养通｜社区养老服务协同与结算依据'
prs.core_properties.subject = '比赛项目介绍：客户、服务、产品、交付与商业方案'
prs.core_properties.author = '颐养通项目'
prs.core_properties.keywords = '居家养老,公司订阅,个人免费,社区免费,演示样例'
warnings = []


def rgb(value):
    return RGBColor.from_string(C.get(value, value))


def shape(s, x, y, w, h, fill='white', kind=MSO_SHAPE.RECTANGLE, stroke=None, radius=False):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else kind,
                            Inches(x), Inches(y), Inches(w), Inches(h))
    if fill:
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(fill)
    else:
        sh.fill.background()
    if stroke:
        sh.line.color.rgb = rgb(stroke)
        sh.line.width = Pt(1)
    else:
        sh.line.fill.background()
    if radius:
        sh.adjustments[0] = 0.12
    return sh


def line(s, x1, y1, x2, y2, color='line', width=1.2):
    sh = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    sh.line.color.rgb = rgb(color)
    sh.line.width = Pt(width)
    return sh


def wrapped(value, width, size):
    font = ImageFont.truetype(str(FONT_PATH), round(size * 96 / 72))
    lines = []
    for raw in value.split('\n'):
        current = ''
        for char in raw:
            if current and font.getlength(current + char) > width * 96:
                lines.append(current)
                current = char
            else:
                current += char
        lines.append(current)
    return lines


def text(s, value, x, y, w, h, size=20, color='ink', bold=False, align='left', font=FONT):
    t = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = t.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    lines = wrapped(value, w - 0.03, size)
    if len(lines) * size * 1.18 / 72 > h + 0.04:
        warnings.append(f'{len(prs.slides)}: {value[:22]} 预计高度超出 ({len(lines)}行/{h}in)')
    for i, part in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = part
        p.alignment = {'left': PP_ALIGN.LEFT, 'center': PP_ALIGN.CENTER, 'right': PP_ALIGN.RIGHT}[align]
        p.space_before = Pt(0)
        p.space_after = Pt(0)
        p.line_spacing = 1.15
        p.font.name = font
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = rgb(color)
        for r in p.runs:
            r.font.name = font
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = rgb(color)
            ea = OxmlElement('a:ea')
            ea.set('typeface', FONT)
            r._r.get_or_add_rPr().append(ea)
    return t


def home(s, x, y, size, color='blue', heart=True):
    line(s, x, y + size * .38, x + size * .5, y, color, 3)
    line(s, x + size * .5, y, x + size, y + size * .38, color, 3)
    line(s, x + .12 * size, y + .3 * size, x + .12 * size, y + .92 * size, color, 3)
    line(s, x + .12 * size, y + .92 * size, x + .88 * size, y + .92 * size, color, 3)
    line(s, x + .88 * size, y + .92 * size, x + .88 * size, y + .3 * size, color, 3)
    if heart:
        shape(s, x + .33 * size, y + .44 * size, .34 * size, .3 * size, color, MSO_SHAPE.HEART)


def base(title, sub='', dark=False):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb('navy' if dark else 'white')
    color = 'white' if dark else 'navy'
    text(s, title, .65, .49, 12.0, .66, 29, color, True)
    if sub:
        text(s, sub, .68, 1.22, 11.95, .48, 15.5, 'line' if dark else 'muted')
    line(s, .68, 7.04, 12.65, 7.04, 'muted' if dark else 'line', .7)
    text(s, '颐养通 · 社区养老服务协同与结算依据', .68, 7.16, 7.5, .2, 9.5, 'line' if dark else 'muted')
    text(s, f'{len(prs.slides):02d} / 13', 11.4, 7.14, 1.25, .25, 11, 'line' if dark else 'muted', align='right', font='Arial')
    return s


def note(s, value):
    s.notes_slide.notes_text_frame.text = value


def photo(s, name, x, y, w, h, border=True):
    p = ASSETS / name
    iw, ih = Image.open(p).size
    ratio = min(w / iw, h / ih)
    pw, ph = iw * ratio, ih * ratio
    px, py = x + (w - pw) / 2, y + (h - ph) / 2
    if border:
        shape(s, px - .035, py - .035, pw + .07, ph + .07, 'paper', stroke='line', radius=True)
    s.shapes.add_picture(str(p), Inches(px), Inches(py), width=Inches(pw), height=Inches(ph))


def bullet(s, title, detail, x, y, w=3.8, color='blue'):
    text(s, title, x, y, w, .42, 21, color, True)
    text(s, detail, x, y + .55, w, 1.05, 17, 'muted')


def card(s, title, detail, x, y, w, h=1.5, fill='pale'):
    shape(s, x, y, w, h, fill, radius=True)
    text(s, title, x+.22, y+.2, w-.44, .42, 21, 'blue', True)
    text(s, detail, x+.22, y+.75, w-.44, h-.88, 16, 'muted')


def rows(s, headers, records, x, y, widths, row_h=.55, size=16):
    for n, row in enumerate([headers]+records):
        xx=x
        for value, w in zip(row, widths):
            shape(s, xx, y+n*row_h, w, row_h-.015, 'navy' if n==0 else ('paper' if n%2 else 'white'))
            text(s, str(value), xx+.14, y+n*row_h+.13, w-.26, row_h-.16, size, 'white' if n==0 else 'ink', n==0)
            xx+=w


# 1. A concrete service and buyer.
s=base('',dark=True)
home(s,.76,.55,.5,'white')
text(s,'颐养通',.75,1.65,7.3,.9,50,'white',True)
text(s,'让每笔养老服务\n有记录、有依据、能对账',.78,2.95,7.3,1.65,32,'white',True)
text(s,'为居家养老服务公司提供预约、履约与结算工具。',.8,5.04,7.15,.65,18,'line')
shape(s,.8,6.01,7.25,.62,'blue',radius=True)
text(s,'公司付费 · 个人与社区免费使用平台',1,6.16,6.9,.35,19,'white',True)
for i,(a,b) in enumerate([('社区签约','高龄补贴入账'),('老人选人','跨签约公司预约'),('上门留痕','地址打卡＋结束合影'),('双层结算','公司对账＋员工酬金')]):
    yy=1.68+i*1.22
    shape(s,8.62,yy,3.83,1,'white',radius=True)
    text(s,a,8.87,yy+.16,3.3,.35,22,'blue',True)
    text(s,b,8.87,yy+.61,3.3,.28,14,'muted')
note(s,'项目定位：给居家养老服务公司提供可接单的本地软件配置、培训与结算交付服务。平台仅向公司收费；社区与个人免费使用平台。上门服务用服务币消费，服务本身并非免费。全部样例为虚构，无真实客户、充值或履约。')

# 2. Real workflow hypotheses, with explicit validation status.
s=base('服务谁，解决哪笔账', '目标买方：有固定服务员、社区合作和持续上门订单的居家养老服务公司。')
shape(s,.68,1.98,3.27,4.72,'pale',radius=True)
text(s,'谁会付钱',.98,2.25,2.7,.45,22,'blue',True)
text(s,'公司负责人\n运营与财务主管',.98,3.07,2.69,1.4,27,'navy',True)
text(s,'购买结果：\n把上门服务转成\n可核验的结算明细。',.98,5.03,2.7,1.2,18,'muted')
for i,(title,problem,value) in enumerate([
    ('公司与社区对账','补贴、消费、服务凭证分散','用同一订单串联账本与凭证'),
    ('员工服务与酬金','谁上门、做了哪单、怎么算','保留打卡合影及酬金快照'),
    ('老人选择与信任','可选服务人员和价格不直观','展示签约公司、服务员与报价')]):
    yy=2.08+i*1.47
    text(s,title,4.48,yy,7.7,.45,23,'navy',True)
    text(s,problem,4.48,yy+.57,3.8,.54,17,'muted')
    text(s,value,8.7,yy+.57,3.82,.68,19,'blue',True)
    if i<2:line(s,4.48,yy+1.27,12.55,yy+1.27)
text(s,'待验证：访谈负责人，核对真实台账，并完成一期试用；当前不声称已有付费客户或提效数据。',4.48,6.6,8.0,.28,11,'muted')
note(s,'需求来自社区养老协同和公司结算场景，尚未用真实客户访谈验证。本次比赛展示可运行产品与样例交付；下一步用目标公司的现有台账验证需求及付费意愿。')

# 3. Four roles.
s=base('四个角色，共用一条服务记录', '社区管准入和补贴，老人自主选人，公司管服务，员工留下履约凭证。')
for i,(role,title,desc,out) in enumerate([
    ('社区','签约入驻 · 资格核定','登记公司与合同，发放高龄补贴','结算给公司有据可查'),
    ('老人','自主选公司 · 自主选服务员','看项目报价、预约时段、查询服务币','个人免费使用平台'),
    ('服务员','确认上门 · 开始打卡 · 结束合影','记录实际地址与定位、上传结束合影','本人服务与酬金可追溯'),
    ('公司','管理人员项目 · 核算酬金','处理订单与异常，导出员工结算明细','公司是平台付费客户')]):
    yy=1.98+i*1.16
    shape(s,.7,yy,1.68,.94,'blue' if i!=2 else 'teal',radius=True)
    text(s,role,.84,yy+.28,1.4,.4,22,'white',True,'center')
    text(s,title,2.78,yy+.04,6.15,.4,21,'navy',True)
    text(s,desc,2.78,yy+.55,6.0,.36,16,'muted')
    text(s,out,9.38,yy+.27,3.02,.49,18,'blue',True)
    if i<3:line(s,2.76,yy+1.03,12.5,yy+1.03)
note(s,'演示已实现四类角色及公司、社区、员工、顾客的访问范围控制。顾客没有固定服务员绑定，可选择所在社区有效签约公司的服务员。公司订阅与老人服务币分开核算。')

# 4. Actual product screens.
s=base('先签约，再让老人自己选', '本地产品实拍：社区登记合同，顾客在有效签约公司中选择服务员和服务项目。')
text(s,'01  社区：公司签约入驻',.76,1.97,5.75,.43,21,'blue',True)
text(s,'02  老人：跨公司自主选人',6.88,1.97,5.75,.43,21,'teal',True)
photo(s,'community-contracts.png',.76,2.65,5.7,3.83)
photo(s,'customer-book.png',6.88,2.65,5.7,3.83)
text(s,'预约价格、酬金和地址固定保存；校验合同期、工作时段、服务员冲突和可预约余额。',.77,6.59,11.8,.32,14,'muted')
note(s,'截图来自当前独立虚构样例库，没有使用线上或真实老人数据。预约支持按时薪与时长报价，并为未完成订单预留额度，防止同一余额重复预约。')

# 5. Frontline journey and transparency.
s=base('让骑电瓶车的服务员，从容跑好一天', '按预约顺序估算路线、天气、午餐和电量；后续逐步把顾客可见的服务进度接入订单。')
shape(s,.72,1.98,6.05,4.65,'paper',radius=True)
text(s,'次日行程预览',1.0,2.24,3.8,.42,21,'navy',True)
text(s,'11/26 · 8小时 · 3户',4.74,2.29,1.66,.28,12,'muted',align='right')
stops=[('08:30','王秀英家','助浴 90 分钟','2.4 km'),('11:10','陈桂芳家','助洁 60 分钟','4.8 km'),('15:00','周明德家','陪医 120 分钟','6.1 km')]
for i,(tm,who,task,dist) in enumerate(stops):
    yy=2.9+i*1.12
    shape(s,1.02,yy,.52,.52,'blue' if i<2 else 'teal',kind=MSO_SHAPE.OVAL)
    text(s,str(i+1),1.03,yy+.08,.5,.32,17,'white',True,'center')
    text(s,tm,1.78,yy-.01,1.0,.34,17,'blue',True)
    text(s,who,2.76,yy-.01,1.84,.34,18,'navy',True)
    text(s,task,2.76,yy+.42,2.55,.3,14,'muted')
    text(s,dist,5.55,yy+.08,1.02,.3,15,'navy',True,'right')
    if i<2:line(s,1.28,yy+.55,1.28,yy+1.08,'line',2)
text(s,'按订单时间和位置排序，自动预留路途、午餐与准备时间。',1.01,6.19,5.45,.28,12,'muted')
for i,(title,detail,mark) in enumerate([
    ('路线与距离','高德骑行路线可选；\n无 Key 时使用距离估算','13.3 km'),
    ('天气与安全','雨雪降温自动降速，\n提醒雨具、防滑与续航','小雨 18℃'),
    ('中餐与电量','跨午餐自动留时；\n估算载重、温度和里程耗电','午休 12:00')]):
    yy=1.99+i*1.46
    shape(s,7.02,yy,5.43,1.2,'pale' if i!=1 else 'paper',radius=True)
    text(s,title,7.29,yy+.17,2.15,.38,19,'blue',True)
    text(s,detail,9.28,yy+.13,2.76,.72,14,'muted')
    text(s,mark,7.29,yy+.67,1.72,.27,13,'teal',True)
shape(s,7.02,6.26,5.43,.37,'navy',radius=True)
text(s,'当前可查次日行程；自动推送提醒列为下一阶段。',7.2,6.31,5.08,.25,12,'white',True)
note(s,'产品已有按日期查看的电瓶车行程估算：根据预约时间排序，估算骑行、天气影响、午餐占用、续航和冲突。高德骑行路线和天气需要联网。用户提出提前一天自动提醒，比赛版先展示可查询的次日行程，系统推送列为下一阶段，不声称已经自动发送。')

# 6. Evidence.
s=base('从“点完成”到留下可核验凭证', '服务开始前地址打卡；结束后提交与老人合影，缺少任一项就不能完成扣款。')
photo(s,'worker-checkin.png',.75,1.96,5.68,3.58)
photo(s,'worker-photo.png',6.88,1.96,5.68,3.58)
for x,title,detail in [(.8,'开始：地址＋定位＋时间','WGS84 坐标、定位精度、服务器打卡时间'),(6.88,'结束：合影＋授权＋时间','照片授权访问、SHA256、服务器完成时间')]:
    text(s,title,x,5.76,5.65,.42,20,'blue',True)
    text(s,detail,x,6.29,5.67,.35,14,'muted')
note(s,'截图中的定位为自动化模拟，图片是标明演示用途的几何插画，不是真实履约证明。系统校验图片文件与流程必填项，不能自动证明服务真实发生、识别人脸或验证拍摄时间。社区与公司仍须核验。')

# 7. Virtual ledger using generated data.
s=base('充值、补贴、消费，每笔都能查', '服务币是内部结算记账单位；保留原始流水，差错以退款或冲正追加处理。')
text(s,'陈桂芳的演示账户',.78,2.0,5.3,.45,23,'navy',True)
parts=[('期初额度','600'),('社区补贴','+200'),('充值记账','+100'),('两笔服务','−180'),('当前余额','720')]
for i,(a,b) in enumerate(parts):
    xx=.77+i*2.43
    shape(s,xx,2.74,2.19,1.29,'pale' if i<4 else 'blue',radius=True)
    text(s,a,xx+.18,2.94,1.85,.36,16,'muted' if i<4 else 'white')
    text(s,b,xx+.18,3.39,1.85,.45,27,'navy' if i<4 else 'white',True)
rows(s,['流水动作','可查询的依据','对账用途'],[
    ['补贴 / 充值','批次号、凭据、操作人、时间','查明服务币从哪里来'],
    ['服务消费','订单、公司、服务员、打卡、合影','查明服务币花在哪里'],
    ['退款 / 冲正','原记录引用、原因、新流水','保留原账，形成负数调整']],.8,4.4,[2.15,5.5,4.1],.50,15)
text(s,'所有数值均为虚构样例。服务币与人民币的兑付规则由合同约定；充值记录不代表系统已实际收款。',.8,6.59,11.8,.32,12,'muted')
note(s,'样例账户：期初600、社区补贴200、充值记账100，两笔已留存演示凭证的服务扣除120和60，剩余720服务币。充值没有真实收款；系统保存线下凭据或业务依据。发放批次、订单完成、退款和冲正均防止重复。')

# 8. Two settlements.
s=base('一份履约记录，支持两层结算', '社区核对公司服务净额，公司核算员工酬金；两层分别防止重复计入。')
rows(s,['订单 / 公司','服务项目','服务币','酬金单位'],[
    ['#1 安心养老','助浴 · 90分钟','120.00','67.50'],
    ['#2 安心养老','助洁 · 60分钟','60.00','40.00'],
    ['#3 康乐养老','陪医 · 120分钟','120.00','80.00']],.8,2.05,[3.65,4.25,2.0,2.0],.58,17)
card(s,'社区 → 养老公司','安心：180 服务币；康乐：120 服务币\n合计 300 服务币，附订单与凭证明细。',.8,4.82,5.75,1.69)
card(s,'养老公司 → 员工','王秀英：107.50；赵春梅：80.00\n合计 187.50 酬金核算单位，按约定兑付。',6.88,4.82,5.65,1.69)
note(s,'样例数据真实从产品API产生，但全部业务均为模拟。4个结算依据批次分别对应2家公司和2名员工。服务币和酬金核算单位不是人民币。结算单只提供核算依据，不表示已经结账、发薪或转账。已结算订单如退款，系统追加负数调整，进入后续批次。')

# 9. The actual sellable delivery.
s=base('可以接的一单：公司养老服务数字化配置', '交付给一家养老公司：能用的本地产品、操作培训，以及一份可逐单追溯的结算样例。')
for i,(n,title,desc) in enumerate([
    ('01','安装与初始化','Mac 安装、公司人员与项目\n社区合同、老人资格及补贴'),
    ('02','预约到履约演示','自主选人、改期与异常处理\n开始定位打卡、结束合影'),
    ('03','结算明细与交接','结算 CSV、逐笔服务账本\nPPT、HTML 与操作说明')]):
    xx=.78+i*4.14
    shape(s,xx,2.12,3.87,3.67,'paper',radius=True)
    text(s,n,xx+.25,2.41,3.3,.75,36,'blue',True)
    text(s,title,xx+.25,3.36,3.32,.52,23,'navy',True)
    text(s,desc,xx+.25,4.24,3.32,1.13,16,'muted')
text(s,'交付验收',.82,6.13,1.6,.4,18,'teal',True)
text(s,'能登录四端 → 能预约与留痕 → 能查询原始账本 → 能导出两层结算。',2.6,6.13,9.8,.5,18,'navy',True)
note(s,'收费服务可以由公司采购：本地产品安装、基础配置和培训，再交付首期结算样例。材料已包含独立演示数据库、PPTX/PDF、HTML/PDF和CSV明细，便于评委直接验收。当前是Mac本地演示，未部署到线上。')

# 10. Commercial clarity.
s=base('只向公司收费，先验证订阅意愿', '公司为管理工具与持续服务付费；个人、社区免平台使用费。正式价格尚未确定。')
for x,name,price,detail in [(.8,'小团队','¥299 / 月','每公司 · 不超过10名服务员'),(4.94,'成长团队','¥699 / 月','每公司 · 不超过30名服务员'),(9.08,'更大规模','协商报价','按人员规模与服务需求评估')]:
    shape(s,x,2.15,3.45,2.5,'pale',radius=True)
    text(s,name,x+.24,2.42,2.95,.47,22,'navy',True)
    text(s,price,x+.24,3.15,2.97,.63,29,'blue',True)
    text(s,detail,x+.24,4.03,2.98,.42,13,'muted')
shape(s,.8,5.1,11.72,1.46,'navy',radius=True)
text(s,'待验证的建议报价',1.08,5.35,4.0,.4,22,'white',True)
text(s,'先访谈公司 → 用一期结算表试用 → 核对节省的工作量 → 确认付费与续用意愿。',1.08,5.95,11.05,.4,16,'line')
note(s,'上述人民币价格是用户批准使用的待验证建议，未声称已经收费。按公司订阅、按服务员规模分档；更大规模协商。个人与社区免费使用平台，老人购买上门服务仍消耗服务币。订阅费、服务币补贴、服务消费、员工酬金分开核算；当前没有订阅扣费或真实支付功能。')

# 11. A wider service model without weakening the current workflow.
s=base('让可信服务被更多人看见', '在现有高龄补贴模式之外，逐步开放普通预约与服务员分享名片，让好服务员不依赖 AI 也能受益。')
text(s,'现有：社区补贴模式',.82,1.98,3.46,.38,18,'muted',True)
shape(s,.82,2.52,3.42,3.78,'pale',radius=True)
text(s,'老人',1.08,2.84,2.88,.42,23,'navy',True)
text(s,'按服务币预约与结算\n社区发补贴，公司提供服务\n保留打卡、合影与双层账本',1.08,3.48,2.76,1.55,17,'muted')
text(s,'下一步：普通预约',4.93,1.98,3.46,.38,18,'muted',True)
shape(s,4.93,2.52,3.42,3.78,'paper',radius=True)
text(s,'普通顾客',5.2,2.84,2.88,.42,23,'navy',True)
text(s,'只做预约，线下自行结算\n不发放、不使用服务币\n不进入老人补贴账本',5.2,3.48,2.76,1.55,17,'muted')
text(s,'增长：服务名片',9.04,1.98,3.46,.38,18,'muted',True)
shape(s,9.04,2.52,3.42,3.78,'pale',radius=True)
text(s,'分享链接',9.31,2.84,2.88,.42,23,'navy',True)
text(s,'展示项目、可预约时间与履历\n分享给亲友或社区\n优秀服务员被更多人看见',9.31,3.48,2.76,1.55,17,'muted')
shape(s,.82,6.5,11.64,.32,'navy',radius=True)
text(s,'AI 在后台帮忙：路线、提醒、服务摘要与异常提示；一线服务员只需会用手机。',1.06,6.54,11.12,.24,13,'white',True)
note(s,'普通顾客预约是下一步扩展，不替代社区的补贴与高龄老人服务。普通预约只用平台促成预约，线下自行结算，不发也不扣虚拟服务币，不进入社区补贴账本。分享链接展示服务项目、可预约时间和服务履历；公开范围、评价和可预约范围待试点确认。AI 用于降低服务员使用门槛，例如路线、提醒、摘要和异常提示。')

# 12. Why home care is different.
s=base('上门养老，产品先解决“安全与长期信任”', '服务进入私人家庭，家属会把老人交给一个可以持续联系的人；仅有好评分或一张照片不够。')
for i,(title,detail,metric) in enumerate([
    ('私人家庭边界','进门之前明确身份、地址、老人授权与家属联系人；\n照片只在完成流程中出现，访问范围受控。','授权与范围'),
    ('老人安全','合同准入、项目与工作时间共同校验；\n实际地址打卡、结束合影和异常记录形成时间链。','可追溯'),
    ('长期可信任','尽量保持熟悉的服务员并积累履历；\n透明报价和结算让老人、家属、公司说同一套事实。','连续性'),
    ('人的尊严','不上传无关隐私，不用“AI 识别一张脸”替代人工核验；\n让技术把记录做清楚，把照护留给人。','有温度')]):
    xx=.82+(i%2)*6.05
    yy=1.98+(i//2)*2.05
    shape(s,xx,yy,5.42,1.72,'paper' if i%2==0 else 'pale',radius=True)
    text(s,title,xx+.25,yy+.18,2.86,.4,21,'navy',True)
    text(s,metric,xx+3.7,yy+.2,1.38,.28,12,'blue',True,'right')
    text(s,detail,xx+.25,yy+.72,4.85,.76,14,'muted')
text(s,'与普通到店服务相比，上门服务买的不是一次交易，而是进入家庭之后的安心。',.84,6.4,11.6,.34,16,'blue',True)
note(s,'居家上门服务与一般到店服务不同：进入私人家庭、涉及老人与家属授权、现场安全和长期信任。产品通过合同准入、订单级打卡合影、范围控制和原始记录提高可核验性，但不能代替身份审查、人工核验或紧急救助。照片必须取得老人及必要监护人同意。')

# 13. Demonstration and acceptance.
s=base('评委可以这样验收', '可运行产品＋一份样例交付，围绕真实需求、可用服务、交付价值与商业思路展示。')
for i,(title,desc) in enumerate([
    ('看客户','公司负责人为谁采购、交付什么；社区与个人为何免费。'),
    ('用产品','社区查看合同与补贴；老人选人；服务员打卡及合影。'),
    ('查交付','一笔消费追溯到订单和凭证，双层结算表与账本能对上。'),
    ('问商业','价格标为建议，下一步验证真实公司需求与付费意愿。')]):
    yy=2.03+i*.98
    shape(s,.81,yy,.52,.52,'blue',kind=MSO_SHAPE.OVAL)
    text(s,str(i+1),.82,yy+.08,.5,.34,17,'white',True,'center')
    text(s,title,1.6,yy+.04,2.2,.44,22,'navy',True)
    text(s,desc,4.0,yy+.08,8.3,.45,18,'muted')
line(s,.8,6.15,12.5,6.15)
text(s,'本地体验  http://127.0.0.1:8000',.82,6.38,6.35,.37,18,'blue',True)
text(s,'提交：PPT / PDF / HTML / CSV / 视频 / 封面 / ZIP',6.45,6.42,6.07,.36,14,'muted',align='right')
note(s,'ZIP包含Mac源代码、启动脚本、独立虚构演示库、比赛材料、项目介绍视频、Mac启动视频和4:3封面。不依赖线上部署。首次安装依赖需要网络；定位需Mac与浏览器权限。当前通过64项业务与权限检查及四端浏览器操作核验。演示数据不能当作真实客户、业绩或履约证明。')

OUT.mkdir(parents=True,exist_ok=True)
prs.save(OUT/'颐养通_比赛项目介绍.pptx')
(WORK/'layout-check.json').write_text(json.dumps(warnings,ensure_ascii=False,indent=2))

# Self-contained sample delivery. Only embedded local illustration, no remote assets.
e=lambda v: html.escape(str(v if v is not None else '—'))
m=lambda v:f'{v/100:,.2f}'
image64=base64.b64encode((ASSETS/'演示合影占位.png').read_bytes()).decode()
order_rows=''.join(f'<tr><td>#{d["order"]["id"]}</td><td>{e(d["order"]["company_name"])}<br>{e(d["order"]["worker_name"])}</td><td>{e(d["order"]["customer_name"])}</td><td>{e(d["order"]["item_name"])}<br>{d["order"]["duration_minutes"]}分钟</td><td>{m(d["order"]["price_cents"])}</td><td>{m(d["order"]["worker_pay_cents"])}</td><td>#{d["proof"]["id"]}</td></tr>' for d in ORDERS)
kinds={'opening':'期初额度','migration':'迁移标记','subsidy':'社区补贴','recharge':'充值记账','consumption':'服务消费'}
ledger_rows=''.join(f'<tr><td>#{l["id"]}</td><td>{e(l["customer_name"])}</td><td>{kinds.get(l["kind"],e(l["kind"]))}</td><td class="amount">{m(l["delta_cents"])}</td><td>{e(l["reference"])}</td><td>{e(l["note"])}</td></tr>' for l in reversed(SAMPLE['ledger']) if l['kind']!='migration')
batch_rows=''.join(f'<tr><td>#{b["batch"]["id"]}</td><td>{"社区 → 公司" if b["batch"]["kind"]=="company" else "公司 → 员工"}</td><td>{e(b["batch"]["reference"])}</td><td>{"、".join("#"+str(x["order_id"]) for x in b["entries"])}</td><td class="amount">{m(b["batch"]["total_cents"])}</td><td>{"服务币" if b["batch"]["kind"]=="company" else "酬金单位"}</td></tr>' for b in SAMPLE['batches'])
proofs=''.join(f'<details><summary>订单 #{d["order"]["id"]} 的打卡、合影校验与操作记录</summary><p>实际打卡地址：{e(d["order"]["checkin_address"])}<br>模拟坐标：{e(d["order"]["checkin_lat"])}, {e(d["order"]["checkin_lng"])}；精度 {e(d["order"]["checkin_accuracy"])} 米<br>服务器打卡：{e(d["order"]["checkin_at"])}<br>服务器完成：{e(d["order"]["completed_at"])}<br>凭证 #{d["proof"]["id"]} · SHA256 <code>{e(d["proof"]["sha256"])}</code></p>{"".join("<p class=log>"+e(l["created_at"])+" · "+e(l["action"])+" · "+e(l["detail"])+"</p>" for l in d["logs"])}</details>' for d in ORDERS)
content=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>颐养通 · 样例交付</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#eaf0f8;color:#20344c;font:15px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1100px;margin:24px auto}}.sheet{{background:white;padding:38px 44px;margin-bottom:24px;border-radius:16px}}h1{{font-size:34px;margin:8px 0 14px;line-height:1.3}}h2{{font-size:24px;margin:22px 0 12px}}h3{{font-size:17px;margin:0 0 8px}}p{{margin:8px 0}}.eyebrow{{color:#2563eb;font-weight:700;letter-spacing:.1em}}.muted{{color:#60748c}}.notice{{padding:12px 16px;background:#fff6e9;border-left:4px solid #ae6815;border-radius:6px}}.blue{{background:#eef4ff;border-color:#2563eb}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0}}.card{{padding:18px 20px;background:#f6f9fd;border:1px solid #d7e2ef;border-radius:12px}}.metric{{font-size:32px;font-weight:700;color:#2563eb}}table{{width:100%;border-collapse:collapse;font-size:13px;margin:14px 0}}th{{background:#183456;color:#fff;text-align:left}}td,th{{padding:9px 10px;vertical-align:top;border-bottom:1px solid #d7e2ef}}tr:nth-child(even){{background:#f6f9fd}}.amount{{white-space:nowrap;font-variant-numeric:tabular-nums}}code{{font-size:11px;word-break:break-all}}img{{width:100%;border-radius:10px}}details{{border:1px solid #d7e2ef;border-radius:8px;padding:12px;margin:10px 0}}summary{{cursor:pointer;font-weight:700;color:#2563eb}}.log{{font-size:12px;color:#60748c}}.foot{{border-top:1px solid #d7e2ef;padding-top:12px;margin-top:22px;color:#60748c;font-size:12px}}button{{background:#2563eb;color:white;border:0;padding:10px 16px;border-radius:8px;font:inherit;cursor:pointer}}@media(max-width:700px){{.sheet{{padding:22px 16px}}.grid{{grid-template-columns:1fr}}table{{font-size:11px}}td,th{{padding:6px 4px}}}}@page{{size:A4;margin:12mm}}@media print{{body{{background:white;font-size:11px;line-height:1.45}}main{{margin:0;max-width:none}}.sheet{{padding:0;margin:0;border-radius:0;break-after:page}}.sheet:last-child{{break-after:auto}}h1{{font-size:27px}}h2{{font-size:18px}}.grid{{gap:14px;margin:14px 0}}.card{{padding:12px}}table{{font-size:10px}}td,th{{padding:6px}}.no-print,details{{display:none}}.foot{{font-size:9px;margin-top:14px}}.metric{{font-size:25px}}}}
</style></head><body><main>
<section class="sheet"><p class="eyebrow">YIYANGTONG / SAMPLE DELIVERY 01</p><h1>一笔上门服务，留下可查的交付依据</h1><p class="muted">颐养通 · 社区养老协同与双层结算样例 · {DAY}</p><p class="notice"><strong>虚构演示</strong>：{e(SAMPLE['notice'])}</p>
<div class="grid"><div class="card"><h3>交付给谁 / 交付什么</h3><p>面向居家养老服务公司，交付可运行 Mac 本地产品、人员项目初始化、培训及首期结算明细。</p><p>社区签约入驻并发放高龄服务币补贴，顾客自主选择公司与服务员。只向公司收平台使用费，个人与社区免费。</p><p class="muted">下一阶段提供普通预约与分享名片：普通顾客线下自行结算，不发也不扣服务币；优秀的服务员可被更多人看见。</p></div><div class="card"><h3>当前样例范围</h3><span class="metric">3 单 / 2 家公司 / 4 个结算批次</span><p>订单 → 确认 → 地址定位打卡 → 结束合影 → 服务币扣款 → 双层结算依据。</p><p>电瓶车行程助手按预约估算路线、天气、午餐与电量；自动推送提醒列为下一阶段。</p></div></div>
<h2>01 · 订单与履约清单</h2><table><thead><tr><th>订单</th><th>公司 / 员工</th><th>老人</th><th>项目 / 时长</th><th>服务币</th><th>酬金单位</th><th>凭证</th></tr></thead><tbody>{order_rows}</tbody></table>
<div class="grid"><div><img alt="演示合影占位，不是真实履约照片" src="data:image/png;base64,{image64}"></div><div class="card"><h3>每单必须留下</h3><p>开始前：实际地址、WGS84 经纬度、精度、服务器打卡时间。</p><p>结束后：已征得同意的合影、图片 SHA256、服务器完成时间。</p><p class="muted">样例通过工具模拟预约时间与定位，打卡到完成只反映演示操作时间，不代表实际服务时长。</p></div></div>
<div class="no-print">{proofs}</div><p class="foot">交付文件：样例订单明细.csv、产品内授权可见的订单与凭证。系统不能自动确认服务真实性，需社区与公司核验。</p></section>
<section class="sheet"><p class="eyebrow">SAMPLE DELIVERY 02 / LEDGER</p><h1>补贴、充值、消费逐笔对得上</h1><p class="notice blue">服务币仅为内部结算单位。原账只追加；差错以冲正／退款保留原始记录。服务币兑付规则由社区与公司合同确定。</p>
<div class="grid"><div class="card"><h3>陈桂芳 · 账户核对</h3><p>期初 600 + 社区补贴 200 + 充值记账 100 − 助浴 120 − 助洁 60</p><span class="metric">余额 720.00 服务币</span></div><div class="card"><h3>周明德 · 账户核对</h3><p>期初 600 + 社区补贴 200 − 陪同就医 120</p><span class="metric">余额 680.00 服务币</span></div></div>
<h2>02 · 原始账本样例</h2><table><thead><tr><th>流水</th><th>老人</th><th>类型</th><th>变动</th><th>业务单号</th><th>依据</th></tr></thead><tbody>{ledger_rows}</tbody></table>
<div class="card"><h3>查询与防重规则</h3><p>每笔有编号、操作人、服务器时间、业务单号及原始依据；消费关联订单、公司、员工和合影凭证。</p><p>相同发放批次、同一订单完成扣款、同一冲正均防重。未完成预约占用可预约额度，服务完成时实际扣款。</p><p>已结算订单核实退款后追加退款流水与负数结算调整，纳入后续结算。</p></div><p class="foot">配套：样例服务币账本.csv。充值记录仅演示凭据登记，无真实收款；平台订阅费不记入老人服务币账本。</p></section>
<section class="sheet"><p class="eyebrow">SAMPLE DELIVERY 03 / SETTLEMENT</p><h1>社区对公司，公司对员工</h1><p class="muted">按记账日期筛选原始服务流水，订单和凭证编号随结算明细一起交付。两层结算分别防重复。</p><table><thead><tr><th>批次</th><th>结算层级</th><th>依据单号</th><th>订单</th><th>合计</th><th>单位</th></tr></thead><tbody>{batch_rows}</tbody></table>
<div class="grid"><div class="card"><h3>社区与公司结账依据</h3><p>安心养老：120 + 60 = <strong>180 服务币</strong></p><p>康乐养老：120 = <strong>120 服务币</strong></p><p>合计 <strong>300 服务币</strong>，可查每单打卡与合影。</p></div><div class="card"><h3>公司与员工酬金依据</h3><p>王秀英：67.50 + 40 = <strong>107.50</strong></p><p>赵春梅：80 = <strong>80.00</strong></p><p>合计 <strong>187.50 酬金核算单位</strong>，按公司约定兑付。</p></div></div>
<p class="notice">生成结算依据不代表已经结账、收款、银行转账或发薪。系统没有真实支付、充值收单或订阅扣费功能。</p>
<h2>03 · 公司采购与验收</h2><div class="card"><p><strong>建议订阅，待试点验证：</strong>不超过 10 名员工 ¥299／月／公司；不超过 30 名 ¥699／月／公司；更大规模协商。只向公司收平台费，个人与社区免费使用。</p><p><strong>可接服务：</strong>本地安装 → 公司员工与项目配置 → 社区合同及补贴配置 → 四端培训 → 首期账本及双层结算表。</p><p><strong>交付验收：</strong>四端能登录；能自主选人预约；缺打卡或合影不能完成；原账可查；能生成及导出两层结算。</p></div>
<p class="foot">交付包含产品源码、Mac 启动脚本、独立虚构数据库、PPTX/PDF、HTML/PDF、订单及账本与结算 CSV。首次安装依赖需联网；主业务无需云账号。正式价格与客户需求尚待验证。</p><p class="no-print"><button onclick="window.print()">打印 / 保存为 PDF</button></p></section>
</main></body></html>'''
(OUT/'样例交付.html').write_text(content)
print(f'已生成 {len(prs.slides)} 页PPTX和独立HTML；排版预警 {len(warnings)} 项')
for w in warnings:print(w)
