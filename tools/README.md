# 参赛材料生成工具（可选）

这些工具用于 Mac 本地制作和核验参赛交付，普通启动无需安装材料工具依赖。

1. 用项目虚拟环境运行 `python tools/build_demo.py`，在忽略目录 `data/competition-build/` 生成独立虚构库、模拟定位及插画凭证、样例 JSON 与 CSV。它不会修改日常运行的 `data/care-mac-demo.db`。
2. 产品在 macOS 使用 `启动本地.command`，在 Windows 使用 `start_windows.bat`。两者分别创建 `.venv-mac` 或 `.venv-win` 并调用同一个 `server.py`。
3. 可选浏览器核验：将样例库复制到 `browser-demo.db`，用 `CARE_DB` 指向副本、`CARE_PORT=8001 CARE_NO_BROWSER=1` 启动服务；安装 Node Playwright 后运行 `node tools/verify_browser.cjs`。仅操作一次性的副本，该脚本会修改预约时钟和模拟位置，以核验打卡流程并截图到 `assets/`。
4. 在单独材料工具环境安装 `python-pptx` 和 `Pillow`，运行 `python tools/build_materials.py`，生成 13 页可编辑 PPTX 和独立 HTML。使用 Mac 的中文字体及上一步截图。通过 LibreOffice / PowerPoint 导出同名 PDF；用 Chrome 打印 HTML 为 `样例交付.pdf`。
5. 运行 `python tools/build_cover.py`，生成 1600×1200 的 JPG、PNG 封面。标题与人物均放在中央裁剪安全区，两种格式都小于 10 MB。
6. 在 macOS 上运行 `python tools/build_videos.py`，使用系统中文语音、Pillow 和 ffmpeg 生成项目介绍视频与 Mac 启动使用视频，并附同名 SRT 字幕。视频为 1280×720 H.264 + AAC。
7. 运行 `python tools/build_package.py`，生成 ZIP。打包采用文件清单，仅加入单独样例库，检查没有会话、密钥、日志、环境与 Git 历史。

`verify_browser.cjs` 是可选效果核验，不适合作为普通启动步骤，也不对真实老人或真实数据库运行。生成器的服务记录、图片、定位和充值均是模拟数据，不能作为真实履约证明。视频中的系统语音仅用于比赛演示。
