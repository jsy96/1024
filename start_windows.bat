@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "VENV_PY=%CD%\.venv-win\Scripts\python.exe"

where py >nul 2>&1
if not errorlevel 1 (
  set "BASE_PY=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 goto :no_python
  set "BASE_PY=python"
)

%BASE_PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 goto :bad_python

if not exist "%VENV_PY%" (
  echo [1/3] 正在创建 Windows 专用 Python 环境...
  %BASE_PY% -m venv ".venv-win"
  if errorlevel 1 goto :venv_error
)

"%VENV_PY%" -c "import flask, requests, PIL" >nul 2>&1
if errorlevel 1 (
  echo [2/3] 首次启动，正在安装依赖。请保持网络连接...
  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 goto :install_error
)

if not exist "data" mkdir "data"
set "CARE_DB=%CD%\data\care-mac-demo.db"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo [3/3] 正在启动颐养通...
echo 浏览器地址：http://127.0.0.1:8000
echo 关闭此窗口或按 Ctrl+C 即可停止服务。
echo.
"%VENV_PY%" server.py
if errorlevel 1 goto :server_error
endlocal
exit /b 0

:no_python
echo 未找到 Python。请安装 Python 3.9 或更新版本，并勾选“Add Python to PATH”。
echo 下载地址：https://www.python.org/downloads/windows/
pause
exit /b 1

:bad_python
echo Python 版本过低。需要 Python 3.9 或更新版本。
pause
exit /b 1

:venv_error
echo 无法创建 .venv-win。请检查当前目录写入权限和 Python 安装。
pause
exit /b 1

:install_error
echo 依赖安装失败。请检查网络连接后重新运行 start_windows.bat。
pause
exit /b 1

:server_error
echo 服务异常退出。请查看上方错误信息。
pause
exit /b 1
