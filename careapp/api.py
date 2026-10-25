"""四端接口，所有写操作使用 SQLite 串行事务。"""
import csv
import hashlib
import io
import secrets
import sqlite3
from datetime import date,datetime
from PIL import Image,ImageOps,UnidentifiedImageError
from flask import Blueprint,g,jsonify,request,current_app,send_file,Response
from werkzeug.security import generate_password_hash
from .auth import auth_required,public
from .db import get_db,now_str,HASH_METHOD
from .services import (Problem,require,atomic,body,integer,day,text,coordinates,scope,order,log,
                       active_contract,ledger,conflicts,schedule,create_order,settlement_entry,pending_entries,ORDER_SQL)

bp=Blueprint('api',__name__,url_prefix='/api')


@bp.get('/catalog')
@auth_required()
def catalog():
    db=get_db();today=date.today().isoformat()
    if g.user['role']=='customer':
        community=g.user['community_id']
    elif g.user['role']=='community':
        community=g.user['id']
    else:
        community=request.args.get('community_id',type=int)
    companies=[dict(r) for r in db.execute('SELECT * FROM companies WHERE active=1')
               if (not community or active_contract(community,r['id'],today)) and
               (g.user['role']!='admin' or r['id']==g.user['company_id'])]
    ids=[x['id'] for x in companies]
    workers=[{k:r[k] for k in ('id','name','phone','company_id','address')} for r in db.execute("SELECT * FROM users WHERE role='worker' AND active=1") if r['company_id'] in ids]
    items=[dict(r) for r in db.execute('SELECT * FROM service_items WHERE active=1') if r['company_id'] in ids]
    return jsonify(companies=companies,workers=workers,items=items)


@bp.get('/orders')
@auth_required()
def orders():
    clause,p=scope();extra=''
    for arg,col in [('from','sched_start'),('to','sched_start'),('status','status')]:
        val=request.args.get(arg)
        if val:
            if arg=='status':
                extra+=' AND o.status=?';p.append(val)
            else:
                extra+=' AND substr(o.'+col+',1,10)'+('>=?' if arg=='from' else '<=?');p.append(day(val))
    rows=[dict(r) for r in get_db().execute(ORDER_SQL+' WHERE '+clause+extra+' ORDER BY o.sched_start DESC,o.id DESC',p)]
    for r in rows:
        if g.user['role']=='customer':
            r.pop('worker_pay_cents',None)
    return jsonify(orders=rows)


@bp.post('/orders')
@auth_required('customer','admin')
@atomic
def book():
    d=body();cid=g.user['id'] if g.user['role']=='customer' else integer(d.get('customer_id'))
    return jsonify(ok=True,id=create_order(d,cid))


@bp.get('/orders/<int:oid>')
@auth_required()
def details(oid):
    o=order(oid)
    logs=[dict(r) for r in get_db().execute('SELECT * FROM order_logs WHERE order_id=? ORDER BY id',(oid,))]
    proof=get_db().execute('SELECT id,sha256,created_at,consent FROM proofs WHERE id=?',(o['proof_id'],)).fetchone()
    if g.user['role']=='customer':
        o.pop('worker_pay_cents',None)
    return jsonify(order=o,logs=logs,proof=dict(proof) if proof else None)


@bp.post('/orders/<int:oid>/confirm')
@auth_required('worker')
@atomic
def confirm(oid):
    o=order(oid);require(o['status']=='pending','订单已处理',409)
    get_db().execute("UPDATE orders SET status='confirmed',updated_at=? WHERE id=?",(now_str(),oid));log(oid,'确认上门')
    return jsonify(ok=True)


@bp.post('/orders/<int:oid>/checkin')
@auth_required('worker')
@atomic
def checkin(oid):
    o=order(oid);d=body()
    require(o['status']=='confirmed' and not o['checkin_at'],'需先确认，且不能重复打卡',409)
    require(o['sched_start'][:10]==date.today().isoformat(),'仅可为当天预约打卡')
    require(active_contract(o['community_id'],o['company_id'],date.today().isoformat()),'社区合同已失效，请联系社区')
    lat,lng,acc=coordinates(d);addr=text(d.get('address'),300)
    require(len(addr)>=4,'请填写本次实际打卡地址')
    stamp=now_str()
    get_db().execute('''UPDATE orders SET checkin_at=?,checkin_address=?,checkin_lat=?,checkin_lng=?,checkin_accuracy=?,
      legacy=0,updated_at=? WHERE id=?''',(stamp,addr,lat,lng,acc,stamp,oid))
    log(oid,'开始服务打卡',f'{addr}；WGS84 {lat},{lng}；精度{acc}米；服务器时间{stamp}')
    return jsonify(ok=True,checkin_at=stamp)


@bp.post('/orders/<int:oid>/complete')
@auth_required('worker')
@atomic
def complete(oid):
    o=order(oid)
    require(o['status']=='confirmed' and o['checkin_at'] and not o['paid'],'完成前须确认并打卡，且不能重复完成',409)
    require(request.form.get('consent')=='1','请确认合影已征得老人同意')
    f=request.files.get('photo');require(f is not None,'请上传服务结束后与老人的合影')
    try:
        img=Image.open(f.stream)
        require(img.format in ('JPEG','PNG','WEBP'),'仅支持 JPG、PNG、WebP')
        require(128<=img.width<=10000 and 128<=img.height<=10000 and img.width*img.height<=25000000,'照片尺寸应至少128像素，且不超过2500万像素')
        img.load();img=ImageOps.exif_transpose(img).convert('RGB');img.thumbnail((2000,2000))
        output=io.BytesIO();img.save(output,format='JPEG',quality=88);data=output.getvalue()
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError):
        raise Problem('照片无法解码，请更换有效照片')
    stamp=now_str();sha=hashlib.sha256(data).hexdigest()
    pid=get_db().execute('''INSERT INTO proofs(order_id,filename,sha256,actor,consent,created_at,content)
      VALUES(?,?,?,?,1,?,?)''',(oid,secrets.token_hex(16)+'.jpg',sha,g.user['id'],stamp,data)).lastrowid
    tx=ledger(o['customer_id'],-o['price_cents'],'consumption',text(request.form.get('note')) or f'订单#{oid}服务扣款',f'order:{oid}',o['company_id'],oid)
    get_db().execute("UPDATE orders SET status='completed',paid=1,completed_at=?,proof_id=?,updated_at=? WHERE id=?",(stamp,pid,stamp,oid))
    settlement_entry(o,'service',tx)
    log(oid,'完成服务',f'合影凭证#{pid}；SHA256 {sha}；扣除{o["price_cents"]/100:.2f}服务币')
    return jsonify(ok=True,proof_id=pid)


@bp.get('/orders/<int:oid>/photo')
@auth_required()
def photo(oid):
    o=order(oid)
    r=get_db().execute('SELECT content FROM proofs WHERE id=?',(o['proof_id'],)).fetchone()
    require(r is not None,'暂无合影凭证',404)
    res=send_file(io.BytesIO(r[0]),mimetype='image/jpeg',download_name=f'order-{oid}.jpg')
    res.headers['Cache-Control']='no-store';res.headers['X-Content-Type-Options']='nosniff'
    return res


@bp.post('/orders/<int:oid>/cancel')
@auth_required('customer','admin','community')
@atomic
def cancel(oid):
    o=order(oid);reason=text(body().get('reason'));require(reason,'请填写取消或退款原因')
    require(o['status']!='cancelled','订单已取消',409)
    if o['paid']:
        require(g.user['role']=='community','已扣款订单由社区核实退款',403)
        require(not o['legacy'] and o['proof_id'],'历史订单保留原始账务，不可自动退款')
        tx=ledger(o['customer_id'],o['price_cents'],'refund',reason,f'refund:{oid}',o['company_id'],oid)
        settlement_entry(o,'refund',tx,-1)
    else:
        require(not o['checkin_at'] or g.user['role'] in ('admin','community'),'服务已开始，请联系公司核实')
    get_db().execute("UPDATE orders SET status='cancelled',refunded=?,updated_at=? WHERE id=?",(1 if o['paid'] else 0,now_str(),oid))
    log(oid,'退款冲正' if o['paid'] else '取消订单',reason)
    return jsonify(ok=True)


@bp.post('/orders/<int:oid>/exception')
@auth_required('worker')
@atomic
def exception(oid):
    o=order(oid);note=text(body().get('reason'))
    require(o['status'] in ('pending','confirmed'),'当前状态不能上报异常');require(note,'请说明异常')
    get_db().execute("UPDATE orders SET status='exception',exception_note=?,updated_at=? WHERE id=?",(note,now_str(),oid));log(oid,'上报异常',note)
    return jsonify(ok=True)


@bp.post('/orders/<int:oid>/reschedule')
@auth_required('admin','worker')
@atomic
def reschedule(oid):
    o=order(oid);d=body()
    require(o['status'] in ('pending','confirmed','exception') and not o['checkin_at'],'已开始的服务不可改期')
    start,end=schedule(d.get('sched_start'),o['duration_minutes'])
    require(active_contract(o['community_id'],o['company_id'],start.date().isoformat()),'改期日期无有效合同')
    require(not conflicts(o['worker_id'],start,end,oid),'改期时段冲突',409)
    get_db().execute("UPDATE orders SET sched_start=?,sched_end=?,status='pending',updated_at=? WHERE id=?",(start.strftime('%Y-%m-%d %H:%M'),end.strftime('%Y-%m-%d %H:%M'),now_str(),oid))
    log(oid,'改期',start.strftime('%Y-%m-%d %H:%M'))
    return jsonify(ok=True)


@bp.get('/people')
@auth_required('admin','community')
def people():
    db=get_db()
    if g.user['role']=='community':
        rows=db.execute("SELECT * FROM users WHERE role='customer' AND community_id=?",(g.user['id'],))
    else:
        rows=db.execute("SELECT * FROM users WHERE role='worker' AND company_id=?",(g.user['company_id'],))
    return jsonify(people=[dict(public(r),active=r['active'],lat=r['lat'],lng=r['lng']) for r in rows])


@bp.post('/people')
@auth_required('admin','community')
@atomic
def save_person():
    d=body();db=get_db();pid=d.get('id')
    role='customer' if g.user['role']=='community' else 'worker'
    fields=dict(name=text(d.get('name'),80),address=text(d.get('address'),300),active=integer(d.get('active',1),0,1))
    require(fields['name'],'姓名不能为空')
    for key,lo,hi in [('lat',-90,90),('lng',-180,180)]:
        if d.get(key) not in (None,''):
            val=float(d[key]);require(math_isfinite(val) and lo<=val<=hi,'坐标无效');fields[key]=val
    if role=='customer':
        fields['subsidy_eligible']=integer(d.get('subsidy_eligible',0),0,1)
    if pid:
        key='community_id' if role=='customer' else 'company_id'
        value=g.user['id'] if role=='customer' else g.user['company_id']
        r=db.execute(f'SELECT id FROM users WHERE id=? AND role=? AND {key}=?',(integer(pid),role,value)).fetchone()
        require(r is not None,'无权修改该人员',403)
        db.execute('UPDATE users SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',list(fields.values())+[pid])
    else:
        phone=text(d.get('phone'),30);require(phone.isdigit() and 5<=len(phone)<=15,'账号应为5至15位数字')
        pwd=d.get('password','');require(len(pwd)>=6,'初始密码至少6位')
        fields.update(phone=phone,password_hash=generate_password_hash(pwd,method=HASH_METHOD),role=role,created_at=now_str(),
          community_id=g.user['id'] if role=='customer' else None,company_id=g.user['company_id'] if role=='worker' else None)
        pid=db.execute('INSERT INTO users('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',list(fields.values())).lastrowid
    if d.get('reset_password'):
        pwd=d['reset_password'];require(len(pwd)>=6,'密码至少6位')
        db.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(pwd,method=HASH_METHOD),pid));db.execute('DELETE FROM sessions WHERE user_id=?',(pid,))
    return jsonify(ok=True,id=pid)


def math_isfinite(val):
    import math
    return math.isfinite(val)


@bp.get('/companies')
@auth_required('community')
def companies():
    return jsonify(companies=[dict(r) for r in get_db().execute('SELECT id,name,active FROM companies')])


@bp.post('/companies')
@auth_required('community')
@atomic
def new_company():
    d=body();name=text(d.get('name'),100);phone=text(d.get('phone'),20);pwd=d.get('password','')
    require(name and phone.isdigit() and 5<=len(phone)<=15 and len(pwd)>=6,'请填写公司名、有效账号和至少6位密码')
    db=get_db();uid=db.execute("INSERT INTO users(phone,password_hash,role,name,created_at) VALUES(?,?,'admin',?,?)",
      (phone,generate_password_hash(pwd,method=HASH_METHOD),name+'管理员',now_str())).lastrowid
    cid=db.execute('INSERT INTO companies(admin_id,name,created_at) VALUES(?,?,?)',(uid,name,now_str())).lastrowid
    db.execute('UPDATE users SET company_id=? WHERE id=?',(cid,uid))
    return jsonify(ok=True,id=cid)


@bp.get('/contracts')
@auth_required('community','admin')
def contracts():
    key='c.community_id' if g.user['role']=='community' else 'c.company_id'
    value=g.user['id'] if g.user['role']=='community' else g.user['company_id']
    rows=[dict(r) for r in get_db().execute('''SELECT c.*,co.name company_name,u.name community_name,
      EXISTS(SELECT 1 FROM contract_events e WHERE e.contract_id=c.id AND e.action='terminate') terminated
      FROM contracts c JOIN companies co ON co.id=c.company_id JOIN users u ON u.id=c.community_id WHERE '''+key+'=? ORDER BY c.id DESC',(value,))]
    return jsonify(contracts=rows)


@bp.post('/contracts')
@auth_required('community')
@atomic
def sign():
    d=body();cid=integer(d.get('company_id'));start=day(d.get('start_date'));end=day(d.get('end_date'));number=text(d.get('number'),100)
    require(start<=end and number,'请填写有效合同编号及日期')
    require(get_db().execute('SELECT 1 FROM companies WHERE id=? AND active=1',(cid,)).fetchone(),'公司不存在')
    get_db().execute('INSERT INTO contracts(community_id,company_id,number,start_date,end_date,created_at) VALUES(?,?,?,?,?,?)',
      (g.user['id'],cid,number,start,end,now_str()))
    return jsonify(ok=True)


@bp.post('/contracts/<int:cid>/terminate')
@auth_required('community')
@atomic
def terminate(cid):
    c=get_db().execute('SELECT * FROM contracts WHERE id=? AND community_id=?',(cid,g.user['id'])).fetchone()
    require(c is not None,'合同不存在',404);reason=text(body().get('reason'));require(reason,'请填写终止原因')
    require(not get_db().execute("SELECT 1 FROM contract_events WHERE contract_id=? AND action='terminate'",(cid,)).fetchone(),'合同已终止',409)
    get_db().execute("INSERT INTO contract_events(contract_id,action,actor,reason,created_at) VALUES(?,'terminate',?,?,?)",(cid,g.user['id'],reason,now_str()))
    return jsonify(ok=True)


@bp.get('/items')
@auth_required('admin')
def items():
    return jsonify(items=[dict(r) for r in get_db().execute('SELECT * FROM service_items WHERE company_id=?',(g.user['company_id'],))])


@bp.post('/items')
@auth_required('admin')
@atomic
def save_item():
    d=body();minutes=integer(d.get('minutes'),15,480);unit=integer(d.get('unit_price_cents'),1,1000000)
    pay=integer(d.get('worker_pay_cents'),0,1000000);name=text(d.get('name'),80);require(name,'服务名不能为空')
    db=get_db();values=[name,minutes,unit*minutes//60,unit,pay,integer(d.get('active',1),0,1)]
    if d.get('id'):
        cur=db.execute('UPDATE service_items SET name=?,minutes=?,price_cents=?,unit_price_cents=?,worker_pay_cents=?,active=? WHERE id=? AND company_id=?',values+[integer(d['id']),g.user['company_id']]);require(cur.rowcount,'项目不存在',404)
    else:
        db.execute('INSERT INTO service_items(name,minutes,price_cents,unit_price_cents,worker_pay_cents,active,company_id) VALUES(?,?,?,?,?,?,?)',values+[g.user['company_id']])
    return jsonify(ok=True)


@bp.get('/ledger')
@auth_required('community','admin','customer')
def get_ledger():
    key={'community':'community_id','admin':'company_id','customer':'customer_id'}[g.user['role']]
    value=g.user['company_id'] if g.user['role']=='admin' else g.user['id']
    rows=[dict(r) for r in get_db().execute('''SELECT l.*,u.name customer_name,a.name actor_name,
      EXISTS(SELECT 1 FROM ledger r WHERE r.reversal_of=l.id) reversed FROM ledger l
      JOIN users u ON u.id=l.customer_id LEFT JOIN users a ON a.id=l.actor WHERE l.'''+key+'=? ORDER BY l.id DESC',(value,))]
    return jsonify(ledger=rows)


@bp.post('/credits')
@auth_required('community')
@atomic
def credit():
    d=body();kind=d.get('kind');require(kind in ('subsidy','recharge'),'请选择补贴或充值')
    amount=integer(d.get('amount_cents'),1,100000000);ref=text(d.get('reference'),100);note=text(d.get('note'))
    ids=d.get('customer_ids');require(isinstance(ids,list) and 1<=len(ids)<=500,'请勾选1至500名老人');require(ref and note,'请填写业务单号和依据说明')
    ids=list(dict.fromkeys(integer(x,1) for x in ids));db=get_db()
    prefix=f'credit:{g.user["id"]}:{ref}:'
    require(not db.execute('SELECT 1 FROM ledger WHERE substr(reference,1,?)=?',(len(prefix),prefix)).fetchone(),'该业务批次已入账，请查询原记录',409)
    for uid in ids:
        u=db.execute("SELECT * FROM users WHERE id=? AND community_id=? AND role='customer' AND active=1",(uid,g.user['id'])).fetchone()
        require(u is not None,'包含其他社区或已停用人员',403)
        require(kind!='subsidy' or u['subsidy_eligible'],'补贴只可发给已核定资格的老人')
        ledger(uid,amount,kind,note,f'credit:{g.user["id"]}:{ref}:{uid}')
    return jsonify(ok=True,count=len(ids))


@bp.post('/ledger/<int:lid>/reverse')
@auth_required('community')
@atomic
def reverse(lid):
    r=get_db().execute('SELECT * FROM ledger WHERE id=? AND community_id=?',(lid,g.user['id'])).fetchone()
    require(r is not None,'流水不存在',404);require(r['kind'] in ('subsidy','recharge'),'仅补贴或充值可从此冲正，消费请从订单退款')
    require(not get_db().execute('SELECT 1 FROM ledger WHERE reversal_of=?',(lid,)).fetchone(),'已冲正',409)
    note=text(body().get('reason'));require(note,'请说明冲正原因')
    ledger(r['customer_id'],-r['delta_cents'],'reversal',note,f'reversal:{lid}',reversal=lid)
    return jsonify(ok=True)


def batch_params(d):
    role=g.user['role'];kind='company' if role=='community' else 'worker'
    company=integer(d.get('company_id'),1) if role=='community' else g.user['company_id']
    worker=integer(d.get('worker_id'),1) if kind=='worker' else None
    community=g.user['id'] if kind=='company' else None
    if worker:
        require(get_db().execute("SELECT 1 FROM users WHERE id=? AND company_id=? AND role='worker'",(worker,company)).fetchone(),'无权结算该员工',403)
    if community:
        require(get_db().execute('SELECT 1 FROM contracts WHERE company_id=? AND community_id=?',(company,community)).fetchone(),'未与该公司签约',403)
    start=day(d.get('from_date'));end=day(d.get('to_date'));require(start<=end,'日期范围无效')
    return kind,company,community,worker,start,end


@bp.post('/batches/preview')
@auth_required('community','admin')
def preview():
    args=batch_params(body());rows=pending_entries(*args)
    total=sum(r['amount_cents' if args[0]=='company' else 'pay_cents'] for r in rows)
    return jsonify(entries=rows,total_cents=total,kind=args[0])


@bp.post('/batches')
@auth_required('community','admin')
@atomic
def make_batch():
    d=body();args=batch_params(d);rows=pending_entries(*args);kind,company,community,worker,start,end=args
    require(rows,'该期间无待结算记录',409)
    # Preview's exact ids prevents a stale screen from silently adding new items.
    require(sorted(integer(x,1) for x in d.get('entry_ids',[]))==sorted(r['id'] for r in rows),'待结算记录已变化，请重新预览',409)
    ref=text(d.get('reference'),100);require(ref,'请填写结算依据单号')
    total=sum(r['amount_cents' if kind=='company' else 'pay_cents'] for r in rows)
    db=get_db();bid=db.execute('''INSERT INTO batches(kind,community_id,company_id,worker_id,from_date,to_date,
      total_cents,actor,reference,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
      (kind,community,company,worker,start,end,total,g.user['id'],f'{kind}:{g.user["id"]}:{ref}',now_str())).lastrowid
    for r in rows:
        db.execute('INSERT INTO batch_lines(batch_id,entry_id,kind) VALUES(?,?,?)',(bid,r['id'],kind))
    return jsonify(ok=True,id=bid,total_cents=total)


@bp.get('/batches')
@auth_required('community','admin','worker')
def batches():
    key={'community':'community_id','admin':'company_id','worker':'worker_id'}[g.user['role']]
    val=g.user['company_id'] if g.user['role']=='admin' else g.user['id']
    rows=[dict(r) for r in get_db().execute('''SELECT b.*,co.name company_name,u.name worker_name
      FROM batches b JOIN companies co ON co.id=b.company_id LEFT JOIN users u ON u.id=b.worker_id WHERE b.'''+key+'=? ORDER BY b.id DESC',(val,))]
    return jsonify(batches=rows)


def scoped_batch(bid):
    key={'community':'community_id','admin':'company_id','worker':'worker_id'}[g.user['role']]
    val=g.user['company_id'] if g.user['role']=='admin' else g.user['id']
    b=get_db().execute('SELECT * FROM batches WHERE id=? AND '+key+'=?',(bid,val)).fetchone()
    require(b is not None,'结算批次不存在',404)
    rows=[dict(r) for r in get_db().execute('''SELECT e.*,o.checkin_at,o.checkin_address,o.completed_at,o.proof_id,
       c.name customer_name,w.name worker_name FROM batch_lines bl JOIN settlement_entries e ON e.id=bl.entry_id
       JOIN orders o ON o.id=e.order_id JOIN users c ON c.id=o.customer_id JOIN users w ON w.id=e.worker_id
       WHERE bl.batch_id=? ORDER BY e.id''',(bid,))]
    return dict(b),rows


@bp.get('/batches/<int:bid>')
@auth_required('community','admin','worker')
def batch_details(bid):
    b,rows=scoped_batch(bid);return jsonify(batch=b,entries=rows)


@bp.get('/batches/<int:bid>/export.csv')
@auth_required('community','admin','worker')
def export_batch(bid):
    b,rows=scoped_batch(bid);f=io.StringIO();w=csv.writer(f)
    w.writerow(['结算依据单号','类型','订单','账本流水','老人','服务员','服务币','酬金依据单位','打卡时间','打卡地址','完成时间','合影凭证'])
    def safe(v):
        s=str(v or '');return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s
    for r in rows:
        w.writerow([safe(b['reference']),r['event'],r['order_id'],r['ledger_id'],safe(r['customer_name']),safe(r['worker_name']),
                    f'{r["amount_cents"]/100:.2f}',f'{r["pay_cents"]/100:.2f}',r['checkin_at'],safe(r['checkin_address']),r['completed_at'],r['proof_id']])
    return Response('\ufeff'+f.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="settlement-{bid}.csv"','Cache-Control':'no-store'})


@bp.get('/summary')
@auth_required()
def summary():
    where,p=scope();db=get_db()
    r=dict(db.execute('''SELECT COUNT(*) orders_count,SUM(status='completed') completed_count,
      SUM(status='exception') exception_count,COALESCE(SUM(CASE WHEN status='completed' AND proof_id IS NOT NULL AND refunded=0 THEN price_cents ELSE 0 END),0) service_cents
      FROM orders o WHERE '''+where,p).fetchone())
    r['balance_cents']=g.user['balance_cents']
    if g.user['role']=='customer':
        reserved=db.execute("SELECT COALESCE(SUM(price_cents),0) FROM orders WHERE customer_id=? AND status IN ('pending','confirmed','exception') AND paid=0",(g.user['id'],)).fetchone()[0]
        r['reserved_cents']=reserved;r['available_cents']=g.user['balance_cents']-reserved
    return jsonify(r)


@bp.get('/route')
@auth_required('worker')
def route():
    from .routing import plan_route
    dt=day(request.args.get('date',date.today().isoformat()))
    rows=[dict(r) for r in get_db().execute(ORDER_SQL+" WHERE o.worker_id=? AND substr(o.sched_start,1,10)=? AND o.status IN ('pending','confirmed') ORDER BY o.sched_start",(g.user['id'],dt))]
    return jsonify(plan_route(g.user,rows,current_app.config['APP_CONF'],dt))
