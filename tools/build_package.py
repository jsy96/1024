"""打包 Mac 本地产品和参赛材料；只使用独立生成的虚构样例库。"""
from pathlib import Path
import shutil
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'data/competition-build'
OUT = ROOT / 'deliverables/competition'
STAGE = WORK / 'package-1024'
TITLE = '颐养通参赛材料'
ZIP = OUT / '颐养通_参赛提交包.zip'


def build():
    expected = ['颐养通_比赛项目介绍.pptx','颐养通_比赛项目介绍.pdf',
                '样例交付.html','样例交付.pdf','提交与演示说明.md',
                '颐养通_作品封面_4x3.jpg','颐养通_作品封面_4x3.png',
                '颐养通_项目介绍.mp4','颐养通_项目介绍.srt',
                '颐养通_Mac本地启动与使用.mp4','颐养通_Mac本地启动与使用.srt',
                '样例订单明细.csv','样例服务币账本.csv',
                '样例结算_社区公司_1.csv','样例结算_社区公司_2.csv',
                '样例结算_公司员工_3.csv','样例结算_公司员工_4.csv']
    for name in expected:
        assert (OUT/name).is_file(), f'缺少材料 {name}'
    assert (WORK/'competition-demo.db').is_file(), '先运行 build_demo.py'
    shutil.rmtree(STAGE, ignore_errors=True)
    material = STAGE / TITLE
    product = material / '产品'
    product.mkdir(parents=True)
    for name in expected:
        shutil.copy2(OUT/name,material/name)
    for name in ['careapp','web','tests','tools']:
        shutil.copytree(ROOT/name,product/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store'))
    for name in ['README.md','requirements.txt','config.json','secrets.example.json','server.py','启动本地.command','start_windows.bat','.gitignore']:
        shutil.copy2(ROOT/name,product/name)
    (product/'data').mkdir()
    # Online backup captures a consistent DB even if a demo viewer is open.
    src = sqlite3.connect(WORK/'competition-demo.db')
    dst = sqlite3.connect(product/'data/care-mac-demo.db')
    src.backup(dst)
    src.close()
    assert dst.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]==0
    assert dst.execute('SELECT COUNT(*) FROM orders').fetchone()[0]==3
    assert not dst.execute('PRAGMA foreign_key_check').fetchone()
    dst.execute('PRAGMA journal_mode=DELETE')
    dst.close()
    with zipfile.ZipFile(ZIP,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(material.rglob('*')):
            if path.is_file():
                archive.write(path,path.relative_to(STAGE))
    with zipfile.ZipFile(ZIP) as archive:
        assert archive.testzip() is None
        names=archive.namelist()
        assert len([n for n in names if n.endswith('.db')])==1
        assert len([n for n in names if n.endswith('.mp4')])==2
        assert len([n for n in names if n.endswith('.srt')])==2
        assert len([n for n in names if '作品封面_4x3.' in n])==2
        assert any(n.endswith('/start_windows.bat') for n in names)
        forbidden=['/.git/','/.venv','/__pycache__/','/secrets.json','.log','.pid','deploy','cloudbase','start.bat','sw.js']
        assert not [n for n in names if any(x in n for x in forbidden)]
    print(f'已生成 {ZIP.name}：{len(names)} 个文件，{ZIP.stat().st_size/1024/1024:.2f} MB')


if __name__=='__main__':
    build()
