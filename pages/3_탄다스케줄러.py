# pages/3_탄다스케줄러.py
# ────────────────────────────────────────────────────────────────
# ③ 탄다 스케줄러  (AI 의견 버튼 포함)
#   · 기본 7칸, 행·열 가변  · ZIP/JSON/TXT/M3U 불러오기
#   · “💡 AI 의견 받기” 버튼 → GPT-4o-mini 2,000자 내외 한국어 의견
# ────────────────────────────────────────────────────────────────
from __future__ import annotations
import json, io, zipfile, os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from typing import List

# ───── OpenAI 설정 (AI 의견용) ─────────────────────────────────
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

if API_KEY:
    from langchain_openai import ChatOpenAI
    from langchain.schema import SystemMessage, HumanMessage
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4, openai_api_key=API_KEY)

# ───── 페이지 설정 ────────────────────────────────────────────
st.set_page_config(page_title="탄다 스케줄러", page_icon="📅", layout="wide")
st.title("③ 탄다 스케줄러 📅")

DEFAULT_COLS = 7  # 기본 열 수

# ───── 1. 탄다 불러오기 ───────────────────────────────────────
def parse_uploaded(f) -> List[dict]:
    tandas = []
    def txt_to_tanda(name, txt):
        tracks = [ln for ln in txt.splitlines()
                  if ln.strip() and not ln.startswith("#")]
        tandas.append({"name": Path(name).stem, "type": "탱고", "tracks": tracks})

    if f.name.endswith(".zip"):
        with zipfile.ZipFile(f) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                data = z.read(info).decode("utf-8", "ignore")
                if info.filename.endswith(".json"):
                    obj = json.loads(data)
                    tandas.extend(obj if isinstance(obj, list) else [obj])
                else:
                    txt_to_tanda(info.filename, data)
    elif f.name.endswith(".json"):
        obj = json.load(f)
        tandas.extend(obj if isinstance(obj, list) else [obj])
    else:  # txt / m3u
        txt_to_tanda(f.name, f.getvalue().decode("utf-8"))
    return tandas

tandas: List[dict] = st.session_state.get("tandas_for_step3", [])

st.sidebar.header("📂 탄다 파일 업로드 (선택)")
up = st.sidebar.file_uploader("tandas.zip / .json / .txt / .m3u",
                              type=["zip", "json", "txt", "m3u"])
if up:
    tandas = parse_uploaded(up)
    st.session_state.tandas_for_step3 = tandas
    st.sidebar.success(f"불러온 탄다: {len(tandas)}개")

if not tandas:
    st.warning("탄다 데이터가 없습니다. 2단계에서 보내거나 파일을 업로드하세요.")
    st.stop()

# ───── 2. 스케줄 상태 초기화 ───────────────────────────────────
if "max_col" not in st.session_state:
    st.session_state.max_col = DEFAULT_COLS
if "schedule" not in st.session_state:
    st.session_state.schedule = [{"time": "", "slots": [None] * DEFAULT_COLS}]

def sync_len(row):
    diff = st.session_state.max_col - len(row["slots"])
    if diff > 0:
        row["slots"].extend([None] * diff)
    elif diff < 0:
        row["slots"] = row["slots"][:st.session_state.max_col]

def add_row():
    st.session_state.schedule.append({"time": "", "slots": [None] * st.session_state.max_col})

def del_row(idx: int):
    if len(st.session_state.schedule) > 1:
        st.session_state.schedule.pop(idx)

def add_col():
    st.session_state.max_col += 1
    for r in st.session_state.schedule: r["slots"].append(None)

def del_col():
    if st.session_state.max_col > 1:
        st.session_state.max_col -= 1
        for r in st.session_state.schedule: r["slots"].pop()

# ───── 3. 스케줄 편집 UI ──────────────────────────────────────
st.markdown("### 🗓️ 스케줄 편집")
c_add, c_del = st.columns(2)
c_add.button("➕ 열 추가", on_click=add_col)
c_del.button("➖ 열 삭제", on_click=del_col)

for ridx, row in enumerate(st.session_state.schedule):
    sync_len(row)
    cols = st.columns(st.session_state.max_col + 2)  # 시간 + N + 삭제
    row["time"] = cols[0].text_input("시간", row["time"], key=f"time_{ridx}")
    for cidx in range(st.session_state.max_col):
        opts = ["(empty)"] + [f"{i+1}. {t['name']}" for i, t in enumerate(tandas)]
        cur = row["slots"][cidx]
        idx = tandas.index(cur) + 1 if cur in tandas else 0
        sel = cols[cidx + 1].selectbox(f"칸{cidx+1}", opts, index=idx,
                                       key=f"slot_{ridx}_{cidx}")
        row["slots"][cidx] = None if sel == "(empty)" else tandas[int(sel.split('.')[0]) - 1]
    cols[-1].button("❌", key=f"del_{ridx}", on_click=del_row, args=(ridx,))

st.button("➕ 행 추가", on_click=add_row)

# ───── 4. 미리보기 / 트랙 리스트 ──────────────────────────────
st.markdown("---")
st.subheader("📝 스케줄 미리보기")
def lbl(t): return "" if t is None else f"{t['name']} ({len(t['tracks'])}곡)"
for r in st.session_state.schedule:
    st.write(" ‖ ".join([r["time"]] + [lbl(t) or "…" for t in r["slots"]]))

track_list = [trk for r in st.session_state.schedule for t in r["slots"] if t for trk in t["tracks"]]
st.markdown(f"#### 🎧 재생 순서 — {len(track_list)}곡")
for p in track_list: st.write(p)

# ───── 5. 저장 ────────────────────────────────────────────────
def m3u(lst): return "#EXTM3U\n" + "\n".join(lst)
st.download_button("💾 M3U 저장", m3u(track_list), "playlist.m3u", mime="audio/x-mpegurl")
st.download_button("💾 TXT 저장", "\n".join(track_list), "playlist.txt", mime="text/plain")

sched_json=[{"time":r["time"],"slots":[t["name"] if t else None for t in r["slots"]]}
            for r in st.session_state.schedule]
buf=io.StringIO(); json.dump(sched_json, buf, ensure_ascii=False, indent=2)
st.download_button("💾 스케줄 JSON 저장", buf.getvalue(),
                   "tanda_schedule.json", mime="application/json")
