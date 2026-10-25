"""构造独立、全为虚构的参赛样例。使用项目 Python 环境运行。"""
import csv
import io
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'data' / 'competition-build'
OUT = ROOT / 'deliverables' / 'competition'
ASSETS = WORK / 'assets'
DB = WORK / 'competition-demo.db'
sys.path.insert(0, str(ROOT))


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(exist_ok=True)
    # Only the dedicated generated fixture is replaced, never the user's local DB.
    for suffix in ('', '-wal', '-shm'):
        Path(str(DB) + suffix).unlink(missing_ok=True)
    os.environ['CARE_DB'] = str(DB)
    from careapp import create_app
    from careapp.db import get_db
    app = create_app()
    app.testing = True

    font_path = next(Path('/System/Library/AssetsV2').glob('**/PingFang.ttc'))
    image = Image.new('RGB', (960, 600), '#eef4ff')
    draw = ImageDraw.Draw(image)
    f = lambda n: ImageFont.truetype(str(font_path), n)
    draw.rounded_rectangle((25, 25, 935, 575), radius=28, fill='#ffffff', outline='#b9cae5', width=3)
    draw.text((70, 58), '演示合影占位', font=f(48), fill='#183456')
    # Geometric people are deliberately recognizable as an illustration.
    for x, color in [(290, '#2563eb'), (610, '#158579')]:
        draw.ellipse((x-56, 166, x+56, 278), fill='#f1d9bd')
        draw.rounded_rectangle((x-88, 292, x+88, 430), radius=38, fill=color)
    draw.text((70, 466), '虚构数据 / 模拟定位 / 不是真实履约照片', font=f(32), fill='#9a5b13')
    draw.text((70, 518), '仅演示上传、授权查看和结算关联流程', font=f(25), fill='#60748c')
    photo_path = ASSETS / '演示合影占位.png'
    image.save(photo_path)
    photo_bytes = photo_path.read_bytes()

    def login(phone, password='123456'):
        client = app.test_client()
        r = client.post('/api/login', json={'phone': phone, 'password': password})
        assert r.status_code == 200, r.json
        client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer ' + r.json['token']
        return client, r.json

    def post(client, path, data=None, files=None):
        r = client.post('/api' + path, json=data) if files is None else client.post('/api' + path, data=files)
        assert r.status_code == 200, (path, r.status_code, r.json)
        return r.json

    community, com = login('13900000000', 'community123')
    company1, co1 = login('13900000001', 'admin123')
    company2, co2 = login('13900000002', 'admin123')
    worker1, w1 = login('13800001001')
    worker3, w3 = login('13800001003')
    customer1, u1 = login('13800002001')
    customer2, u2 = login('13800002002')
    date = datetime.now().date().isoformat()
    post(community, '/credits', {'kind': 'subsidy', 'amount_cents': 20000,
         'reference': 'DEMO-202610-高龄补贴', 'note': '虚构演示：社区高龄资格核定及发放清单',
         'customer_ids': [u1['id'], u2['id']]})
    post(community, '/credits', {'kind': 'recharge', 'amount_cents': 10000,
         'reference': 'DEMO-CZ-001', 'note': '虚构演示：充值凭据CZ001；未发生真实收款',
         'customer_ids': [u1['id']]})
    catalog = customer1.get('/api/catalog').json
    by_item = {(i['company_id'], i['name']): i['id'] for i in catalog['items']}
    tomorrow = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    cases = [(customer1, worker1, w1, '上门助浴', 90, 9),
             (customer1, worker1, w1, '居家助洁', 60, 14),
             (customer2, worker3, w3, '陪同就医', 120, 9)]
    orders = []
    for customer, worker, w, name, minutes, hour in cases:
        oid = post(customer, '/orders', {'worker_id': w['id'],
            'item_id': by_item[w['company_id'], name], 'duration_minutes': minutes,
            'sched_start': tomorrow.replace(hour=hour).strftime('%Y-%m-%d %H:%M'),
            'note': '虚构演示订单；由样例工具模拟当天履约，不代表真实服务'})['id']
        post(worker, f'/orders/{oid}/confirm')
        # Deliberately simulated clock fixture. Never bypasses checks in product UI.
        start = tomorrow.replace(year=datetime.now().year, month=datetime.now().month, day=datetime.now().day, hour=hour)
        with app.app_context():
            db = get_db()
            db.execute('UPDATE orders SET sched_start=?,sched_end=? WHERE id=?',
                       (start.strftime('%Y-%m-%d %H:%M'), (start+timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M'), oid))
            db.commit()
        post(worker, f'/orders/{oid}/checkin', {'address': '江岸区中山大道100号（虚构演示地址）',
              'lat': 30.5938, 'lng': 114.3065, 'accuracy': 10})
        post(worker, f'/orders/{oid}/complete', files={'consent': '1',
             'note': '演示模拟：插画占位图，无真实合影或实际服务',
             'photo': (io.BytesIO(photo_bytes), 'demo-placeholder.png')})
        orders.append(community.get(f'/api/orders/{oid}').json)

    batches = []
    for client, target, ref in [(community, {'company_id': co1['company_id']}, 'DEMO-SQ-001'),
                                (community, {'company_id': co2['company_id']}, 'DEMO-SQ-002'),
                                (company1, {'worker_id': w1['id']}, 'DEMO-YG-001'),
                                (company2, {'worker_id': w3['id']}, 'DEMO-YG-002')]:
        params = dict(target, from_date=date, to_date=date)
        preview = post(client, '/batches/preview', params)
        bid = post(client, '/batches', dict(params, reference=ref,
                   entry_ids=[e['id'] for e in preview['entries']]))['id']
        data = client.get(f'/api/batches/{bid}').json
        batches.append(data)
        kind = '社区公司' if data['batch']['kind'] == 'company' else '公司员工'
        (OUT / f'样例结算_{kind}_{bid}.csv').write_bytes(client.get(f'/api/batches/{bid}/export.csv').data)

    ledger = community.get('/api/ledger').json['ledger']
    with app.app_context():
        db = get_db()
        customers = [dict(r) for r in db.execute("SELECT id,name,balance_cents FROM users WHERE role='customer'")]
        db.execute('DELETE FROM sessions')
        db.commit()
        assert not db.execute('PRAGMA foreign_key_check').fetchone()
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    sample = {'date': date, 'simulation': True,
              'notice': '全为虚构演示数据；定位及履约时间经过工具模拟，插画占位不是真实服务合影。无真实充值、服务或资金兑付。',
              'orders': orders, 'ledger': ledger, 'batches': batches, 'customers': customers}
    (WORK / 'sample.json').write_text(json.dumps(sample, ensure_ascii=False, indent=2))
    with (OUT / '样例订单明细.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['数据说明','订单','社区','公司','老人','服务员','服务项目','预约开始','分钟','服务币','酬金核算单位','打卡时间','打卡地址','完成时间','合影凭证','SHA256'])
        for d in orders:
            o, p = d['order'], d['proof']
            writer.writerow(['虚构演示/模拟定位/插画占位',o['id'],'江城示范社区',o['company_name'],o['customer_name'],o['worker_name'],o['item_name'],o['sched_start'],o['duration_minutes'],o['price_cents']/100,o['worker_pay_cents']/100,o['checkin_at'],o['checkin_address'],o['completed_at'],p['id'],p['sha256']])
    with (OUT / '样例服务币账本.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['数据说明','流水','老人','类型','服务币变动','订单','业务单号','依据','时间'])
        for l in reversed(ledger):
            writer.writerow(['虚构演示',l['id'],l['customer_name'],l['kind'],l['delta_cents']/100,l['order_id'],l['reference'],l['note'],l['created_at']])
    print(f'已构造独立样例：{len(orders)}笔完成订单、{len(batches)}个双层结算批次，DB={DB}')


if __name__ == '__main__':
    build()
