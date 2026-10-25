"""Mac 本地 SQLite；保留旧订单，账本和凭证只追加。"""
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flask import g
from werkzeug.security import generate_password_hash

BASE = str(Path(__file__).resolve().parent.parent)
HASH_METHOD = 'pbkdf2:sha256:600000'


def now_str():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def load_config():
    return json.loads((Path(BASE) / 'config.json').read_text())


def db_path():
    return os.environ.get('CARE_DB', str(Path(BASE) / 'data/care-mac-demo.db'))


def connect(path=None):
    c = sqlite3.connect(path or db_path(), timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA journal_mode=WAL')
    return c


def get_db():
    if 'db' not in g:
        g.db = connect()
    return g.db


def close_db(e=None):
    c = g.pop('db', None)
    if c is not None:
        c.rollback()  # Every successful mutation explicitly commits.
        c.close()


SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('admin','community','worker','customer')), name TEXT NOT NULL,
 address TEXT NOT NULL DEFAULT '',lat REAL,lng REAL,worker_id INTEGER,admin_id INTEGER,is_super INTEGER DEFAULT 0,
 balance_cents INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,
 company_id INTEGER,community_id INTEGER,subsidy_eligible INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS service_items(
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,minutes INTEGER NOT NULL,price_cents INTEGER NOT NULL,
 unit_price_cents INTEGER NOT NULL DEFAULT 0,worker_pay_cents INTEGER NOT NULL DEFAULT 0,active INTEGER DEFAULT 1,company_id INTEGER);
CREATE TABLE IF NOT EXISTS orders(
 id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER NOT NULL REFERENCES users(id),
 worker_id INTEGER NOT NULL REFERENCES users(id),item_id INTEGER NOT NULL REFERENCES service_items(id),
 sched_start TEXT NOT NULL,sched_end TEXT NOT NULL,duration_minutes INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','confirmed','completed','exception','cancelled')),
 price_cents INTEGER NOT NULL,worker_pay_cents INTEGER NOT NULL DEFAULT 0,paid INTEGER DEFAULT 0,refunded INTEGER DEFAULT 0,
 note TEXT,exception_type TEXT,exception_note TEXT,payout_id INTEGER,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 company_id INTEGER,community_id INTEGER,contract_id INTEGER,customer_address TEXT,customer_lat REAL,customer_lng REAL,
 checkin_at TEXT,checkin_address TEXT,checkin_lat REAL,checkin_lng REAL,checkin_accuracy REAL,
 completed_at TEXT,proof_id INTEGER,legacy INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS order_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER NOT NULL REFERENCES orders(id),
 actor TEXT NOT NULL,action TEXT NOT NULL,detail TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY AUTOINCREMENT,admin_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
 name TEXT NOT NULL,active INTEGER DEFAULT 1,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS contracts(id INTEGER PRIMARY KEY AUTOINCREMENT,community_id INTEGER NOT NULL REFERENCES users(id),
 company_id INTEGER NOT NULL REFERENCES companies(id),number TEXT NOT NULL,start_date TEXT NOT NULL,end_date TEXT NOT NULL,
 created_at TEXT NOT NULL,UNIQUE(community_id,number));
CREATE TABLE IF NOT EXISTS contract_events(id INTEGER PRIMARY KEY AUTOINCREMENT,contract_id INTEGER NOT NULL REFERENCES contracts(id),
 action TEXT NOT NULL,actor INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER NOT NULL REFERENCES users(id),
 community_id INTEGER NOT NULL REFERENCES users(id),company_id INTEGER REFERENCES companies(id),
 delta_cents INTEGER NOT NULL,kind TEXT NOT NULL,order_id INTEGER REFERENCES orders(id),note TEXT NOT NULL,
 actor INTEGER REFERENCES users(id),reference TEXT UNIQUE NOT NULL,reversal_of INTEGER UNIQUE REFERENCES ledger(id),created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS proofs(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER UNIQUE NOT NULL REFERENCES orders(id),
 filename TEXT UNIQUE NOT NULL,sha256 TEXT NOT NULL,actor INTEGER NOT NULL REFERENCES users(id),
 consent INTEGER NOT NULL CHECK(consent=1),created_at TEXT NOT NULL,content BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS settlement_entries(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER NOT NULL REFERENCES orders(id),
 company_id INTEGER NOT NULL REFERENCES companies(id),community_id INTEGER NOT NULL REFERENCES users(id),worker_id INTEGER NOT NULL REFERENCES users(id),
 event TEXT NOT NULL,amount_cents INTEGER NOT NULL,pay_cents INTEGER NOT NULL,ledger_id INTEGER UNIQUE NOT NULL REFERENCES ledger(id),
 created_at TEXT NOT NULL,UNIQUE(order_id,event));
CREATE TABLE IF NOT EXISTS batches(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL CHECK(kind IN ('company','worker')),
 community_id INTEGER,company_id INTEGER NOT NULL,worker_id INTEGER,from_date TEXT NOT NULL,to_date TEXT NOT NULL,
 total_cents INTEGER NOT NULL,actor INTEGER NOT NULL,reference TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS batch_lines(id INTEGER PRIMARY KEY AUTOINCREMENT,batch_id INTEGER NOT NULL REFERENCES batches(id),
 entry_id INTEGER NOT NULL REFERENCES settlement_entries(id),kind TEXT NOT NULL,UNIQUE(entry_id,kind));
CREATE INDEX IF NOT EXISTS idx_order_worker ON orders(worker_id,sched_start);
CREATE INDEX IF NOT EXISTS idx_ledger_customer ON ledger(customer_id,id);
'''


def init_db(app):
    path = Path(db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    c = connect()
    # Rebuild only the users role constraint, preserving every existing column and id.
    sql = c.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()
    if sql and "'community'" not in sql[0]:
        c.execute('PRAGMA foreign_keys=OFF')
        updated = sql[0].replace('CREATE TABLE users', 'CREATE TABLE users_new', 1).replace(
            "'admin','worker','customer'", "'admin','community','worker','customer'")
        if updated == sql[0]:
            raise RuntimeError('无法识别旧库角色约束，请保留数据库并检查迁移')
        c.execute(updated)
        cols = ','.join('"'+r[1]+'"' for r in c.execute('PRAGMA table_info(users)'))
        c.execute(f'INSERT INTO users_new({cols}) SELECT {cols} FROM users')
        c.execute('DROP TABLE users')
        c.execute('ALTER TABLE users_new RENAME TO users')
        c.commit()
        c.execute('PRAGMA foreign_keys=ON')
    c.executescript(SCHEMA)
    additions = {
        'users': {'company_id':'INTEGER','community_id':'INTEGER','subsidy_eligible':'INTEGER NOT NULL DEFAULT 0'},
        'service_items': {'company_id':'INTEGER'},
        'orders': {'company_id':'INTEGER','community_id':'INTEGER','contract_id':'INTEGER',
                   'customer_address':'TEXT','customer_lat':'REAL','customer_lng':'REAL','checkin_at':'TEXT',
                   'checkin_address':'TEXT','checkin_lat':'REAL','checkin_lng':'REAL','checkin_accuracy':'REAL',
                   'completed_at':'TEXT','proof_id':'INTEGER','legacy':'INTEGER NOT NULL DEFAULT 1'}
    }
    for table, fields in additions.items():
        cols = {r[1] for r in c.execute(f'PRAGMA table_info({table})')}
        for name, typ in fields.items():
            if name not in cols:
                c.execute(f'ALTER TABLE {table} ADD COLUMN {name} {typ}')
    seed_and_migrate(c)
    for table in ('ledger','proofs','order_logs','contracts','contract_events','settlement_entries','batches','batch_lines'):
        for action in ('UPDATE','DELETE'):
            c.execute(f'''CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action}
             BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'记录只可追加，请使用冲正'); END''')
    c.executescript('''
    CREATE TRIGGER IF NOT EXISTS ledger_balance AFTER INSERT ON ledger BEGIN
      UPDATE users SET balance_cents=balance_cents+NEW.delta_cents WHERE id=NEW.customer_id;
    END;
    CREATE TRIGGER IF NOT EXISTS proof_once BEFORE UPDATE ON orders
    WHEN OLD.proof_id IS NOT NULL AND (NEW.proof_id IS NOT OLD.proof_id OR NEW.checkin_at IS NOT OLD.checkin_at
      OR NEW.checkin_address IS NOT OLD.checkin_address OR NEW.checkin_lat IS NOT OLD.checkin_lat
      OR NEW.checkin_lng IS NOT OLD.checkin_lng OR NEW.completed_at IS NOT OLD.completed_at)
    BEGIN SELECT RAISE(ABORT,'履约凭证不可覆盖'); END;
    ''')
    if c.execute('PRAGMA foreign_key_check').fetchone():
        raise RuntimeError('迁移后关联完整性检查失败')
    c.commit()
    c.close()


def seed_and_migrate(c):
    stamp = now_str()
    def user(phone, name, role, pwd='123456', **kw):
        r = c.execute('SELECT id FROM users WHERE phone=?', (phone,)).fetchone()
        if r:
            return r[0]
        keys = ['phone','password_hash','name','role','created_at']+list(kw)
        return c.execute(f'INSERT INTO users({",".join(keys)}) VALUES({",".join("?" for _ in keys)})',
            [phone,generate_password_hash(pwd,method=HASH_METHOD),name,role,stamp]+list(kw.values())).lastrowid
    community = user('13900000000','江城示范社区','community',pwd='community123')
    if not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        user('13900000001','安心养老管理员','admin',pwd='admin123')
    for a in c.execute("SELECT * FROM users WHERE role='admin'").fetchall():
        c.execute('INSERT OR IGNORE INTO companies(admin_id,name,created_at) VALUES(?,?,?)',
                  (a['id'],'安心养老' if a['phone']=='13900000001' else a['name']+'养老公司',stamp))
        cid = c.execute('SELECT id FROM companies WHERE admin_id=?',(a['id'],)).fetchone()[0]
        c.execute('UPDATE users SET company_id=?,is_super=0 WHERE id=?',(cid,a['id']))
        c.execute("UPDATE users SET company_id=? WHERE role='worker' AND admin_id=? AND company_id IS NULL",(cid,a['id']))
    first = c.execute('SELECT id,admin_id FROM companies ORDER BY id LIMIT 1').fetchone()
    c.execute("UPDATE users SET company_id=? WHERE role='worker' AND company_id IS NULL",(first[0],))
    c.execute('UPDATE service_items SET company_id=? WHERE company_id IS NULL',(first[0],))
    second_admin = user('13900000002','康乐养老管理员','admin',pwd='admin123')
    c.execute('INSERT OR IGNORE INTO companies(admin_id,name,created_at) VALUES(?,?,?)',(second_admin,'康乐养老',stamp))
    second = c.execute('SELECT id FROM companies WHERE admin_id=?',(second_admin,)).fetchone()[0]
    c.execute('UPDATE users SET company_id=? WHERE id=?',(second,second_admin))
    user('13800001001','王秀英','worker',company_id=first[0],admin_id=first[1],lat=30.6048,lng=114.2975,address='江汉区解放大道690号')
    user('13800001002','李建国','worker',company_id=first[0],admin_id=first[1],lat=30.5778,lng=114.3155,address='武昌区中南路99号')
    user('13800001003','赵春梅','worker',company_id=second,admin_id=second_admin,lat=30.596,lng=114.31,address='江岸区示范服务站')
    for i,name in enumerate(['陈桂芳','周明德','吴淑兰','刘志远'],1):
        user('1380000200'+str(i),name,'customer',community_id=community,subsidy_eligible=1,
             address='江岸区中山大道'+str(i*100)+'号',lat=30.5928+i*.001,lng=114.3055+i*.001)
    c.execute("UPDATE users SET community_id=? WHERE role='customer' AND community_id IS NULL",(community,))
    # One-time migration: import all historical transactions, reconcile the recorded opening balance.
    if not c.execute("SELECT 1 FROM ledger WHERE reference='migration-complete'").fetchone():
        has_tx = c.execute("SELECT 1 FROM sqlite_master WHERE name='transactions'").fetchone()
        for u in c.execute("SELECT * FROM users WHERE role='customer'").fetchall():
            rows = c.execute('SELECT * FROM transactions WHERE customer_id=? ORDER BY id',(u['id'],)).fetchall() if has_tx else []
            total = sum(r['delta_cents'] for r in rows)
            # ledger_balance is only enabled after this migration.
            opening = u['balance_cents']-total
            if not rows and not u['balance_cents']:
                opening=60000
                c.execute('UPDATE users SET balance_cents=? WHERE id=?',(opening,u['id']))
            c.execute('INSERT INTO ledger(customer_id,community_id,delta_cents,kind,note,reference,created_at) VALUES(?,?,?,?,?,?,?)',
                      (u['id'],u['community_id'],opening,'opening','历史余额承接／虚构演示初始额度',f'opening:{u["id"]}',stamp))
            for t in rows:
                c.execute('INSERT INTO ledger(customer_id,community_id,delta_cents,kind,order_id,note,reference,created_at) VALUES(?,?,?,?,?,?,?,?)',
                    (u['id'],u['community_id'],t['delta_cents'],'legacy_'+t['kind'],t['order_id'],t['note'] or '历史流水',f'legacy:{t["id"]}',t['created_at']))
        u=c.execute("SELECT * FROM users WHERE role='customer' ORDER BY id LIMIT 1").fetchone()
        c.execute('INSERT INTO ledger(customer_id,community_id,delta_cents,kind,note,reference,created_at) VALUES(?,?,0,?,?,?,?)',
                  (u['id'],u['community_id'],'migration','账本迁移标记','migration-complete',stamp))
        c.execute("UPDATE users SET subsidy_eligible=1 WHERE role='customer'")
        c.execute('''UPDATE orders SET company_id=(SELECT company_id FROM users WHERE id=orders.worker_id),
          community_id=(SELECT community_id FROM users WHERE id=orders.customer_id),
          customer_address=(SELECT address FROM users WHERE id=orders.customer_id),
          customer_lat=(SELECT lat FROM users WHERE id=orders.customer_id),
          customer_lng=(SELECT lng FROM users WHERE id=orders.customer_id),legacy=1 WHERE company_id IS NULL''')
    # Only the two fictional demo companies receive seeded contracts/projects.
    # Registered companies must be admitted explicitly by the community.
    for co in c.execute('SELECT id FROM companies WHERE id IN (?,?)',(first[0],second)).fetchall():
        if not c.execute('SELECT 1 FROM contracts WHERE company_id=? AND community_id=?',(co[0],community)).fetchone():
            c.execute('INSERT INTO contracts(community_id,company_id,number,start_date,end_date,created_at) VALUES(?,?,?,?,?,?)',
                      (community,co[0],f'DEMO-{co[0]}','2026-01-01','2030-12-31',stamp))
        if not c.execute('SELECT 1 FROM service_items WHERE company_id=?',(co[0],)).fetchone():
            for name,minutes,unit,pay in [('居家助洁',60,6000,4000),('上门助浴',60,8000,4500),('陪同就医',120,6000,8000)]:
                c.execute('INSERT INTO service_items(name,minutes,price_cents,unit_price_cents,worker_pay_cents,company_id) VALUES(?,?,?,?,?,?)',
                          (name,minutes,unit*minutes//60,unit,pay,co[0]))
