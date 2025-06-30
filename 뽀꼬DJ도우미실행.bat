@echo off
setlocal
set "BASEDIR=%~dp0"
set "PYDIR=%BASEDIR%python"
REM PYTHONPATH 줄은 남겨도 되고 지워도 됩니다 (site 모듈이 경로를 읽어 줌)
set "PYTHONPATH=%BASEDIR%site-packages"
"%PYDIR%\python.exe" "%BASEDIR%run_app.py"