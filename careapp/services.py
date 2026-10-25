"""订单、凭证、虚拟币账本与双层结算。金额均为百分之一服务币。"""
import functools
import math
from datetime import datetime,timedelta
from flask import g,request,current_app
from .db import get_db,now_str


class Problem(Exception):
    def __init__(self,message,status=400):
        self.message=message;self.status=status


def require(test,message,status=400):
    if not test:
        raise Problem(message,status)


def atomic(fn):
    @functools.wraps(fn)
    def wrap(*a,**kw):
        db=get_db();db.execute('BEGIN IMMEDIATE')
        try:
            out=fn(*a,**kw)
            db.commit()
            return out
        except Exception:
            db.rollback()
            raise
    return wrap


def body():
    return request.get_json(silent=True) or {}


def integer(v,minimum=0,maximum=100000000):
    require(not isinstance(v,bool),'请输入有效数字')
    try:
        n=int(str(v))
    except (TypeError,ValueError):
        raise Problem('请输入有效整数')
    require(minimum<=n<=maximum,'数字超出可用范围')
    return n


def day(v):
    try:
        return datetime.strptime(str(v),'%Y-%m-%d').date().isoformat()
    except ValueError:
        raise Problem('日期格式应为 YYYY-MM-DD')


def text(v,limit=500):
    return str(v or '').strip()[:limit]


def coordinates(d):
    try:
        lat,lng,acc=float(d['lat']),float(d['lng']),float(d['accuracy'])
    except (KeyError,TypeError,ValueError):
        raise Problem('请允许浏览器定位，需提供有效坐标和精度')
    require(all(math.isfinite(x) for x in (lat,lng,acc)) and -90<=lat<=90 and -180<=lng<=180 and 0<=acc<=1000,'定位无效或精度超过1000米，请重新定位')
    return lat,lng,acc


def scope(alias='o'):
    u=g.user
    key={'community':'community_id','admin':'company_id','worker':'worker_id','customer':'customer_id'}[u['role']]
    value=u['company_id'] if u['role']=='admin' else u['id']
    return f'{alias}.{key}=?',[value]


ORDER_SQL='''SELECT o.*,i.name item_name,w.name worker_name,w.phone worker_phone,c.name customer_name,
 c.phone customer_phone,co.name company_name,o.customer_lat lat,o.customer_lng lng,o.duration_minutes minutes
 FROM orders o JOIN service_items i ON i.id=o.item_id JOIN users w ON w.id=o.worker_id
 JOIN users c ON c.id=o.customer_id LEFT JOIN companies co ON co.id=o.company_id'''


def order(oid):
    clause,params=scope()
    row=get_db().execute(ORDER_SQL+' WHERE o.id=? AND '+clause,[oid]+params).fetchone()
    require(row is not None,'订单不存在或无权访问',404)
    return dict(row)


def log(oid,action,detail=''):
    get_db().execute('INSERT INTO order_logs(order_id,actor,action,detail,created_at) VALUES(?,?,?,?,?)',
                     (oid,f'{g.user["role"]}:{g.user["id"]} {g.user["name"]}',action,detail,now_str()))


def active_contract(community,company,date):
    return get_db().execute('''SELECT * FROM contracts c WHERE community_id=? AND company_id=?
      AND start_date<=? AND end_date>=? AND NOT EXISTS(SELECT 1 FROM contract_events e
      WHERE e.contract_id=c.id AND e.action='terminate') ORDER BY id DESC LIMIT 1''',
      (community,company,date,date)).fetchone()


def ledger(customer,amount,kind,note,reference,company=None,oid=None,reversal=None):
    db=get_db()
    u=db.execute("SELECT * FROM users WHERE id=? AND role='customer'",(customer,)).fetchone()
    require(u is not None,'顾客不存在')
    require(u['balance_cents']+amount>=0,'服务币余额不足，不能完成扣款或冲正')
    return db.execute('''INSERT INTO ledger(customer_id,community_id,company_id,delta_cents,kind,order_id,note,
        actor,reference,reversal_of,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
        (customer,u['community_id'],company,amount,kind,oid,note,g.user['id'],reference,reversal,now_str())).lastrowid


def conflicts(worker,start,end,exclude=0):
    rows=get_db().execute("SELECT id,sched_start,sched_end FROM orders WHERE worker_id=? AND status IN ('pending','confirmed','exception') AND id!=?",(worker,exclude)).fetchall()
    buffer=timedelta(minutes=current_app.config['APP_CONF']['conflict_buffer_min'])
    return [dict(r) for r in rows if start<datetime.strptime(r['sched_end'],'%Y-%m-%d %H:%M')+buffer
            and end>datetime.strptime(r['sched_start'],'%Y-%m-%d %H:%M')-buffer]


def schedule(start,minutes):
    try:
        dt=datetime.strptime(str(start).replace('T',' '),'%Y-%m-%d %H:%M')
    except ValueError:
        raise Problem('请选择有效预约时间')
    require(dt>=datetime.now()-timedelta(minutes=1),'预约时间不能早于现在')
    require(dt<=datetime.now()+timedelta(days=365),'仅支持一年以内的预约')
    end=dt+timedelta(minutes=minutes)
    hours=current_app.config['APP_CONF']['work_hours']
    require(dt.date()==end.date() and dt.strftime('%H:%M')>=hours['start'] and end.strftime('%H:%M')<=hours['end'],'预约需在工作时段内完成')
    return dt,end


def create_order(d,customer):
    db=get_db()
    u=db.execute("SELECT * FROM users WHERE id=? AND role='customer' AND active=1",(customer,)).fetchone()
    require(u is not None,'顾客不存在')
    w=db.execute("SELECT * FROM users WHERE id=? AND role='worker' AND active=1",(integer(d.get('worker_id')),)).fetchone()
    i=db.execute('SELECT * FROM service_items WHERE id=? AND active=1',(integer(d.get('item_id')),)).fetchone()
    require(w is not None and i is not None and w['company_id']==i['company_id'],'请选择同一家公司的服务员和项目')
    if g.user['role']=='admin':
        require(w['company_id']==g.user['company_id'],'无权为其他公司创建订单',403)
    minutes=integer(d.get('duration_minutes',i['minutes']),15,480)
    start,end=schedule(d.get('sched_start'),minutes)
    contract=active_contract(u['community_id'],w['company_id'],start.date().isoformat())
    require(contract is not None,'预约日期内公司未与所在社区有效签约')
    co=db.execute('SELECT active FROM companies WHERE id=?',(w['company_id'],)).fetchone()
    require(co and co[0],'公司已停用')
    require(not conflicts(w['id'],start,end),'该服务员时段冲突，请调整时间（含路途缓冲）',409)
    price=(i['unit_price_cents']*minutes+30)//60
    pay=(i['worker_pay_cents']*minutes+i['minutes']//2)//i['minutes']
    reserved=db.execute("SELECT COALESCE(SUM(price_cents),0) FROM orders WHERE customer_id=? AND status IN ('pending','confirmed','exception') AND paid=0",(customer,)).fetchone()[0]
    require(u['balance_cents']-reserved>=price,'可预约服务币不足（已预约金额会占用额度）')
    oid=db.execute('''INSERT INTO orders(customer_id,worker_id,item_id,sched_start,sched_end,duration_minutes,
        status,price_cents,worker_pay_cents,note,created_at,updated_at,company_id,community_id,contract_id,
        customer_address,customer_lat,customer_lng,legacy) VALUES(?,?,?,?,?,?,'pending',?,?,?,?,?,?,?,?,?,?,?,0)''',
        (customer,w['id'],i['id'],start.strftime('%Y-%m-%d %H:%M'),end.strftime('%Y-%m-%d %H:%M'),minutes,
         price,pay,text(d.get('note')),now_str(),now_str(),w['company_id'],u['community_id'],contract['id'],u['address'],u['lat'],u['lng'])).lastrowid
    log(oid,'预约',f'选择 {w["name"]}；{minutes}分钟；{price/100:.2f}服务币；酬金依据{pay/100:.2f}')
    return oid


def settlement_entry(o,event,tx,sign=1):
    get_db().execute('''INSERT INTO settlement_entries(order_id,company_id,community_id,worker_id,event,
     amount_cents,pay_cents,ledger_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',
     (o['id'],o['company_id'],o['community_id'],o['worker_id'],event,sign*o['price_cents'],sign*o['worker_pay_cents'],tx,now_str()))


def pending_entries(kind,company,community,worker,from_date,to_date):
    q='''SELECT e.*,o.sched_start,o.checkin_at,o.completed_at,o.proof_id,c.name customer_name,w.name worker_name
      FROM settlement_entries e JOIN orders o ON o.id=e.order_id JOIN users c ON c.id=o.customer_id
      JOIN users w ON w.id=e.worker_id WHERE e.company_id=? AND substr(e.created_at,1,10) BETWEEN ? AND ?
      AND NOT EXISTS(SELECT 1 FROM batch_lines bl WHERE bl.entry_id=e.id AND bl.kind=?)'''
    p=[company,from_date,to_date,kind]
    if community:
        q+=' AND e.community_id=?';p.append(community)
    if worker:
        q+=' AND e.worker_id=?';p.append(worker)
    return [dict(r) for r in get_db().execute(q+' ORDER BY e.id',p)]
