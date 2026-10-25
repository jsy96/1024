"""本地账号和角色鉴权。"""
import functools
import secrets
from flask import Blueprint,g,jsonify,request
from werkzeug.security import check_password_hash,generate_password_hash
from .db import HASH_METHOD,get_db,now_str

bp=Blueprint('auth',__name__)


def auth_required(*roles):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a,**kw):
            token=request.headers.get('Authorization','').removeprefix('Bearer ').strip() if hasattr(str,'removeprefix') else request.headers.get('Authorization','').replace('Bearer ','',1).strip()
            row=get_db().execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE token=?',(token,)).fetchone()
            if not row or not row['active']:
                return jsonify(error='请先登录有效账号'),401
            if roles and row['role'] not in roles:
                return jsonify(error='无权访问'),403
            g.user=dict(row);g.token=token
            return fn(*a,**kw)
        return wrap
    return deco


def public(u):
    return {k:u[k] for k in ('id','phone','role','name','address','company_id','community_id','balance_cents','subsidy_eligible')}


@bp.post('/api/login')
def login():
    d=request.get_json(silent=True) or {}
    u=get_db().execute('SELECT * FROM users WHERE phone=?',(d.get('phone'),)).fetchone()
    if not u or not u['active'] or not check_password_hash(u['password_hash'],d.get('password','')):
        return jsonify(error='账号或密码错误'),401
    token=secrets.token_hex(32)
    get_db().execute('INSERT INTO sessions VALUES(?,?,?)',(token,u['id'],now_str()));get_db().commit()
    return jsonify(token=token,**public(u))


@bp.get('/api/me')
@auth_required()
def me():
    return jsonify(public(g.user))


@bp.post('/api/logout')
@auth_required()
def logout():
    get_db().execute('DELETE FROM sessions WHERE token=?',(g.token,));get_db().commit()
    return jsonify(ok=True)


@bp.post('/api/auth/change-password')
@auth_required()
def change_password():
    d=request.get_json(silent=True) or {}
    if not check_password_hash(g.user['password_hash'],d.get('old_password','')):
        return jsonify(error='原密码不正确'),400
    if len(d.get('new_password',''))<6:
        return jsonify(error='新密码至少6位'),400
    db=get_db()
    db.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(d['new_password'],method=HASH_METHOD),g.user['id']))
    db.execute('DELETE FROM sessions WHERE user_id=? AND token!=?',(g.user['id'],g.token));db.commit()
    return jsonify(ok=True)
