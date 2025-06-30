#!/usr/bin/env python
# run_app.py  ─ Streamlit EXE/ZIP 런처  (2025-06-27, emoji-free, one-file friendly)

import os, sys, socket, time, pathlib, webbrowser, subprocess, threading
from streamlit.web import cli as stcli

# ── 사용자 설정 ───────────────────────────────────────────────
BASE_PORT, MAX_PORT = 8501, 8599         
# 포트 탐색 범위
APP_FILE            = "home.py"           # Streamlit 진입점
WAIT_TIMEOUT        = 10.0                # 브라우저 자동 열기 대기(sec)

# ── 환경변수 ─────────────────────────────────────────────────
os.environ["STREAMLIT_DEV_MODE"]        = "false"
os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
os.environ.setdefault("PYTHONIOENCODING", "utf-8")   # 콘솔 UTF-8 고정

# ── 실행 파일·리소스 경로 ────────────────────────────────────
BASE_DIR = pathlib.Path(getattr(sys, "_MEIPASS",
                                pathlib.Path(__file__).parent))
APP_PATH = (BASE_DIR / APP_FILE)
if not APP_PATH.exists():                        # one-dir 빌드의 _internal 보정
    alt = BASE_DIR / "_internal" / APP_FILE
    if alt.exists():
        APP_PATH = alt

if not APP_PATH.exists():
    sys.exit(f"[ERROR] {APP_FILE} not found. looked at: {APP_PATH}")

# pages/, .streamlit/ 이 _internal 안에 있으면 import 경로 추가
extra = BASE_DIR / "_internal"
if extra.exists():
    sys.path.insert(0, str(extra))

# ── 포트 유틸 ────────────────────────────────────────────────
def port_in_use(p: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", p)) == 0

def find_free_port(lo: int, hi: int) -> int | None:
    for p in range(lo, hi + 1):
        try:
            with socket.socket() as s:
                s.bind(("127.0.0.1", p))
                return p
        except OSError:
            continue
    return None

# ── 브라우저 오픈 스레드 ─────────────────────────────────────
def open_browser_when_ready(port: int):
    deadline = time.time() + WAIT_TIMEOUT
    while time.time() < deadline:
        if port_in_use(port):
            webbrowser.open_new(f"http://localhost:{port}")
            return
        time.sleep(0.25)
    print(f"[WARNING] server did not open within {WAIT_TIMEOUT}s : "
          f"http://localhost:{port}")

# ── 중복 실행 & 포트 선택 ───────────────────────────────────
if port_in_use(BASE_PORT):
    webbrowser.open_new(f"http://localhost:{BASE_PORT}")
    sys.exit(0)

PORT = find_free_port(BASE_PORT, MAX_PORT)
if PORT is None:
    sys.exit(f"[ERROR] no free port between {BASE_PORT} and {MAX_PORT}")

print(f"[INFO] launching Streamlit on http://localhost:{PORT}")

threading.Thread(target=open_browser_when_ready,
                 args=(PORT,), daemon=True).start()

# ── Streamlit 하위 프로세스 실행 (stdout/stderr 그대로 표시) ──
cmd = [
    sys.executable, "-m", "streamlit", "run", str(APP_PATH),
    f"--server.port={PORT}", "--server.headless=true",
]
with subprocess.Popen(cmd, stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT, text=True) as p:
    try:
        for line in p.stdout:
            print(line, end="")          # 하위 프로세스 로그 전달
    finally:
        p.wait()

if __name__ == "__main__":  
    os.chdir(os.path.dirname(__file__))  # 작업 디렉토리를 현재 파일 위치로 설정  
    sys.argv = ["streamlit", "run", "run_app.py", "--server.port=8501", "--global.developmentMode=false"]  
    stcli.main()  