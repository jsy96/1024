"""颐养通 Mac 本地演示应用。"""
import sqlite3
from pathlib import Path
from flask import Flask,jsonify,send_from_directory
from werkzeug.exceptions import HTTPException
from .db import BASE,close_db,init_db,load_config
from .services import Problem


def create_app():
    app=Flask(__name__,static_folder=None)
    app.config.update(APP_CONF=load_config(),MAX_CONTENT_LENGTH=8*1024*1024)
    app.json.ensure_ascii=False
    init_db(app);app.teardown_appcontext(close_db)
    from .auth import bp as auth
    from .api import bp as api
    app.register_blueprint(auth);app.register_blueprint(api)

    @app.errorhandler(Problem)
    def problem(e):
        return jsonify(error=e.message),e.status

    @app.errorhandler(sqlite3.IntegrityError)
    def integrity(e):
        return jsonify(error='记录重复或关联无效，原始记录已保留'),409

    @app.errorhandler(ValueError)
    def invalid(e):
        return jsonify(error='输入格式不正确，请检查数字、日期和选项'),400

    @app.errorhandler(HTTPException)
    def http(e):
        return jsonify(error='上传内容超过8MB' if e.code==413 else e.description),e.code

    @app.get('/api/meta')
    def meta():
        return jsonify(version='1024',**app.config['APP_CONF'])

    @app.get('/api/health')
    def health():
        from .db import get_db
        return jsonify(ok=True,users=get_db().execute('SELECT COUNT(*) FROM users').fetchone()[0],mode='mac-local')

    @app.get('/')
    def index():
        return send_from_directory(Path(BASE)/'web','index.html')

    @app.get('/<path:p>')
    def assets(p):
        res=send_from_directory(Path(BASE)/'web',p)
        res.headers['Cache-Control']='no-cache'
        return res
    return app
