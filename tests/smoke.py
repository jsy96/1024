"""运行：.venv-mac/bin/python tests/smoke.py；临时库，不修改当前演示数据。"""
import io
import os
import sqlite3
import sys
import tempfile
from datetime import datetime,timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from werkzeug.security import generate_password_hash


def run():
 with tempfile.TemporaryDirectory() as work:
    os.environ['CARE_DB']=str(Path(work)/'test.db')
    from careapp import create_app
    from careapp.db import get_db,HASH_METHOD,now_str
    app=create_app();app.testing=True
    checks=0
    def check(condition,message):
        nonlocal checks
        assert condition,message
        checks+=1
    def login(phone,pwd='123456'):
        c=app.test_client();r=c.post('/api/login',json={'phone':phone,'password':pwd})
        assert r.status_code==200,r.json
        c.environ_base['HTTP_AUTHORIZATION']='Bearer '+r.json['token']
        return c,r.json
    com,cu=login('13900000000','community123')
    admin,au=login('13900000001','admin123');admin2,au2=login('13900000002','admin123')
    worker,wu=login('13800001001');worker2,wu2=login('13800001003');customer,u=login('13800002001')
    check(app.test_client().get('/api/orders').status_code==401,'unauth denied')
    check(customer.get('/api/people').status_code==403,'role isolation')
    catalog=customer.get('/api/catalog').json
    check(len(catalog['companies'])==2,'cross company catalog')
    items={r['company_id']:r for r in catalog['items']}
    now=datetime.now();start=now.replace(hour=8,minute=0,second=0,microsecond=0)+timedelta(days=1)
    def book(w=wu,start_at=start):
        return customer.post('/api/orders',json={'worker_id':w['id'],'item_id':items[w['company_id']]['id'],
          'sched_start':start_at.strftime('%Y-%m-%d %H:%M'),'duration_minutes':60})
    r=book();check(r.status_code==200,'book first company');oid=r.json['id']
    r2=book(wu2);check(r2.status_code==200,'customer independently chooses second company');oid2=r2.json['id']
    check(book().status_code==409,'conflict blocked')
    check(admin2.get(f'/api/orders/{oid}').status_code==404,'company order isolation')
    check(worker2.post(f'/api/orders/{oid}/confirm').status_code==404,'worker order isolation')
    check(worker.post(f'/api/orders/{oid}/confirm').status_code==200,'confirm')
    check(worker.post(f'/api/orders/{oid}/checkin',json={'address':'测试地址','lat':30.6,'lng':114.3,'accuracy':10}).status_code==400,'future checkin blocked')
    # Simulate the appointment clock by moving only this test order's schedule to today.
    with app.app_context():
        db=get_db();db.execute('UPDATE orders SET sched_start=?,sched_end=? WHERE id=?',
          (now.strftime('%Y-%m-%d %H:%M'),(now+timedelta(hours=1)).strftime('%Y-%m-%d %H:%M'),oid));db.commit()
    check(worker.post(f'/api/orders/{oid}/complete').status_code==409,'missing checkin denied')
    for bad in ({'lat':float('nan'),'lng':114,'accuracy':10},{'lat':30,'lng':114,'accuracy':2000}):
        check(worker.post(f'/api/orders/{oid}/checkin',json={'address':'测试服务地址',**bad}).status_code==400,'invalid coordinates denied')
    geo={'address':'演示服务地址100号','lat':30.6,'lng':114.3,'accuracy':10}
    check(worker.post(f'/api/orders/{oid}/checkin',json=geo).status_code==200,'checkin')
    check(worker.post(f'/api/orders/{oid}/checkin',json=geo).status_code==409,'duplicate checkin denied')
    check(worker.post(f'/api/orders/{oid}/reschedule',json={'sched_start':start.strftime('%Y-%m-%d %H:%M')}).status_code==400,'started reschedule denied')
    check(customer.post(f'/api/orders/{oid}/cancel',json={'reason':'test'}).status_code==400,'customer cannot cancel started service')
    check(worker.post(f'/api/orders/{oid}/complete',data={'consent':'1'}).status_code==400,'missing photo denied')
    check(worker.post(f'/api/orders/{oid}/complete',data={'consent':'1','photo':(io.BytesIO(b'bad'),'bad.jpg')}).status_code==400,'bad photo denied')
    pic=io.BytesIO();Image.new('RGB',(320,240),'#dbeafe').save(pic,format='PNG');image=pic.getvalue()
    balance=customer.get('/api/me').json['balance_cents']
    def complete_once():
        c=app.test_client();c.environ_base['HTTP_AUTHORIZATION']=worker.environ_base['HTTP_AUTHORIZATION']
        return c.post(f'/api/orders/{oid}/complete',data={'consent':'1','photo':(io.BytesIO(image),'demo.png')}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:complete_once(),range(2)))
    check(sorted(results)==[200,409],'concurrent completion only once')
    o=customer.get(f'/api/orders/{oid}').json['order']
    check(customer.get('/api/me').json['balance_cents']==balance-o['price_cents'],'deduct exactly once')
    check(customer.get(f'/api/orders/{oid}/photo').status_code==200,'owner accesses proof')
    check(admin2.get(f'/api/orders/{oid}/photo').status_code==404,'other company proof denied')
    check(app.test_client().get(f'/api/orders/{oid}/photo').status_code==401,'private proof')
    sub={'kind':'subsidy','amount_cents':10000,'reference':'2026-test','note':'虚构补贴依据','customer_ids':[u['id']]}
    check(com.post('/api/credits',json=sub).status_code==200,'subsidy')
    check(com.post('/api/credits',json=sub).status_code==409,'duplicate subsidy blocked')
    check(admin.post('/api/credits',json=sub).status_code==403,'company cannot issue community credits')
    lid=next(l['id'] for l in com.get('/api/ledger').json['ledger'] if l['kind']=='subsidy')
    check(com.post(f'/api/ledger/{lid}/reverse',json={'reason':'演示冲正'}).status_code==200,'credit reversal')
    check(com.post(f'/api/ledger/{lid}/reverse',json={'reason':'重复'}).status_code==409,'duplicate reversal blocked')
    # An invalid recipient rolls back the entire batch.
    b=customer.get('/api/me').json['balance_cents']
    invalid={**sub,'reference':'rollback','customer_ids':[u['id'],99999]}
    check(com.post('/api/credits',json=invalid).status_code==403,'invalid recipient rejected')
    check(customer.get('/api/me').json['balance_cents']==b,'batch rollback is atomic')
    date=now.date().isoformat();period={'from_date':date,'to_date':date}
    for c,who in [(com,{'company_id':wu['company_id']}),(admin,{'worker_id':wu['id']})]:
        p=c.post('/api/batches/preview',json={**period,**who});check(p.status_code==200 and len(p.json['entries'])==1,'proof-backed preview')
        entries=[e['id'] for e in p.json['entries']]
        create={**period,**who,'entry_ids':entries,'reference':'demo'}
        br=c.post('/api/batches',json=create);check(br.status_code==200,'settlement creation')
        bid=br.json['id'];check(c.get(f'/api/batches/{bid}/export.csv').status_code==200,'settlement export')
        check(c.post('/api/batches',json=create).status_code==409,'duplicate settlement prevented')
        check(admin2.get(f'/api/batches/{bid}').status_code==404,'batch isolation')
    check(admin.post('/api/batches/preview',json={**period,'worker_id':wu2['id']}).status_code==403,'payout scope isolation')
    check(com.post(f'/api/orders/{oid}/cancel',json={'reason':'演示退款核实'}).status_code==200,'refund after settlement appends adjustment')
    check(com.post(f'/api/orders/{oid}/cancel',json={'reason':'重复'}).status_code==409,'duplicate refund denied')
    refund=com.post('/api/batches/preview',json={**period,'company_id':wu['company_id']}).json
    check(refund['total_cents']==-o['price_cents'] and len(refund['entries'])==1,'negative adjustment next batch')
    with app.app_context():
        db=get_db();db.execute('UPDATE users SET subsidy_eligible=0 WHERE id=?',(u['id'],));db.commit()
    check(com.post('/api/credits',json={**sub,'reference':'ineligible'}).status_code==400,'ineligible subsidy rejected')
    # Append-only invariants and balance reconciliation.
    with app.app_context():
        db=get_db()
        for tbl in ['ledger','proofs','settlement_entries','batches','batch_lines','order_logs','contracts']:
            try:db.execute(f'DELETE FROM {tbl}');raise AssertionError(tbl+' mutable')
            except sqlite3.IntegrityError:db.rollback();checks+=1
        for row in db.execute("SELECT id,balance_cents FROM users WHERE role='customer'"):
            check(row['balance_cents']==db.execute('SELECT COALESCE(SUM(delta_cents),0) FROM ledger WHERE customer_id=?',(row['id'],)).fetchone()[0],'balance equals immutable ledger')
        check(not list(db.execute('PRAGMA foreign_key_check')),'FK integrity')
    create_app() # migration/seed can run repeatedly, without duplicating ledger.
    check(customer.get('/api/me').json['balance_cents']==balance,'restarting preserves balance after refunds')
    registered=com.post('/api/companies',json={'name':'待签约测试公司','phone':'13900000009','password':'test123'}).json['id']
    create_app()
    check(registered not in [c['id'] for c in customer.get('/api/catalog').json['companies']],'restart does not automatically admit registered companies')
    contracts=com.get('/api/contracts').json['contracts']
    contract=next(c for c in contracts if c['company_id']==wu2['company_id'])
    check(com.post(f'/api/contracts/{contract["id"]}/terminate',json={'reason':'测试终止'}).status_code==200,'terminate by append-only event')
    check(book(wu2,start+timedelta(days=2)).status_code==400,'terminated contract blocks booking')
    create_app()
    check(wu2['company_id'] not in [c['id'] for c in customer.get('/api/catalog').json['companies']],'restart preserves terminated contract')
    # Logout must revoke the token.
    check(customer.post('/api/logout').status_code==200 and customer.get('/api/me').status_code==401,'logout revokes session')
    print(f'通过 {checks} 项业务与权限检查（含并发重复完成）')


if __name__=='__main__':run()
