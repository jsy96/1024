"""Mac / Windows 本地入口，仅监听 http://127.0.0.1:8000。"""
import os
import threading
import webbrowser
from careapp import create_app

app=create_app()
if __name__=='__main__':
    port=int(os.environ.get('CARE_PORT','8000'))
    if not os.environ.get('CARE_NO_BROWSER'):
        threading.Timer(1.2,lambda:webbrowser.open(f'http://127.0.0.1:{port}')).start()
    app.run(host='127.0.0.1',port=port,debug=False,threaded=True)
