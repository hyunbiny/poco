# pages/1_자동태그정리파일생성(csv).py
# ─────────────────────────────────────────────────────────────────────────────
# ① 자동 태그 정리 (CSV) 생성 ― build_tag_csv.py → scrap.py → bpm.py
#   + 마지막에 music_library_full.csv 통합본 저장
# ─────────────────────────────────────────────────────────────────────────────
import os, sys, subprocess, shutil
from pathlib import Path
from collections import deque

import pandas as pd
import streamlit as st

APP_DIR   = Path(__file__).parent.parent
CSV_NAMES = [
    "music_library_tags.csv",
    "music_library_tags_updated.csv",
    "music_library_tags_bpm.csv",
    "music_library_full.csv",   # 통합본도 동기화
]

st.set_page_config(page_title="자동 태그 정리(csv) 생성", page_icon="🎼", layout="wide")
st.title("① 자동 태그 정리 (CSV) 생성")

# ─────────────  음악 폴더 경로  ────────────────────────────────────────────
default_root = Path("C:/DJMUSIC")
audio_root = Path(
    st.text_input("🎼 음악 폴더 경로 ", value=st.session_state.get("audio_root", default_root))
).expanduser().resolve()

if audio_root.exists():
    st.session_state.audio_root = str(audio_root)
    st.success(f"사용 음악 폴더: {audio_root}")
else:
    st.error("❗️ 지정한 폴더가 존재하지 않습니다.")
    st.stop()

st.divider()

# ─────────────  단계 선택  ────────────────────────────────────────────────
ALL_STEPS = {
    "폴더 → CSV 태그 정리 (build_tag_csv.py)": [sys.executable, "build_tag_csv.py", str(audio_root)],
    "tango.info 태그 보강 (scrap.py)"        : [sys.executable, "scrap.py"],
    "BPM 계산 (bpm.py)"                     : [sys.executable, "bpm.py", "--audio-root", str(audio_root)],
}
labels  = list(ALL_STEPS.keys())
checked = st.multiselect("실행할 단계 선택", labels, default=labels)

st.caption(
    "build → scrap → bpm 순으로 실행해 `music_library_tags_bpm.csv` 를 만든 뒤\n"
    "**music_library_full.csv**(통합본)을 자동 저장합니다."
)

if not checked:
    st.warning("실행할 단계를 하나 이상 선택해 주세요.")
    st.stop()

run_btn = st.button("🚀 선택한 단계 실행")

# ─────────────  CSV 동기화 함수  ──────────────────────────────────────────
def sync_csv():
    for n in CSV_NAMES:
        ap, mp = APP_DIR / n, audio_root / n
        if ap.exists() and not mp.exists():
            shutil.copy2(ap, mp)
        elif mp.exists() and not ap.exists():
            shutil.copy2(mp, ap)

# ─────────────  ★ 통합 CSV 생성 함수  ────────────────────────────────────
def make_full_csv():
    bpm_path = APP_DIR / "music_library_tags_bpm.csv"
    upd_path = APP_DIR / "music_library_tags_updated.csv"
    if not (bpm_path.exists() and upd_path.exists()):
        st.warning("통합 CSV 생성: BPM CSV 또는 updated CSV 가 없습니다.")
        return

    df_bpm = pd.read_csv(bpm_path)
    df_upd = pd.read_csv(upd_path)

    # tango.info 에서 가져올 열 매핑
    col_map = {
        "RecordingYear": ["RecordingYear", "Year", "RecYear"],
        "Genre"        : ["Genre"],
        "Vocalist"     : ["Vocalist"],
        "Leader"       : ["Leader"],
    }
    real_cols = {k: next((c for c in v if c in df_upd.columns), None)
                 for k, v in col_map.items()}
    avail = [c for c in real_cols.values() if c]

    # 병합용 서브 DF
    cols_for_merge = ["FileName", "Orchestra"] + avail
    if "RecordingDate" in df_upd.columns:
        cols_for_merge.append("RecordingDate")
    upd_sub = df_upd[cols_for_merge]

    # FileName + Orchestra 기준 병합
    df_full = pd.merge(
        df_bpm, upd_sub,
        on=["FileName", "Orchestra"],
        how="left",
        suffixes=("", "_upd"),
    )

    # 열별 NaN 보강 / 신규 열 생성
    for logical, real in real_cols.items():
        if not real:                         # 해당 컬럼 없음
            continue
        upd_col = f"{real}_upd" if real in df_bpm.columns else real
        if upd_col not in df_full.columns:
            continue
        if logical not in df_full.columns:
            df_full.rename(columns={upd_col: logical}, inplace=True)
        else:
            df_full[logical] = df_full[logical].fillna(df_full[upd_col])
            if upd_col != logical:
                df_full.drop(columns=upd_col, inplace=True)

    # RecordingDate → RecordingYear 파생 (남은 NaN 포함)
    if "RecordingDate" in df_full.columns:
        rec_year = pd.to_numeric(
            df_full["RecordingDate"].astype(str).str[:4], errors="coerce"
        )
        if "RecordingYear" in df_full.columns:
            df_full["RecordingYear"] = df_full["RecordingYear"].fillna(rec_year)
        else:
            df_full["RecordingYear"] = rec_year

    out = APP_DIR / "music_library_full.csv"
    df_full.to_csv(out, index=False)
    shutil.copy2(out, audio_root / out.name)
    st.success(f"🎉 통합 CSV 저장 완료 → {out.name}")

# ─────────────  실행 루프  ────────────────────────────────────────────────
if run_btn:
    with st.status("진행 중 …", expanded=True) as stat:
        env = os.environ.copy()
        env["PYTHONUTF8"]       = "1"
        env["PYTHONIOENCODING"] = "utf-8"   # UnicodeEncodeError 방지

        for idx, lbl in enumerate(checked, 1):
            cmd = ALL_STEPS[lbl]
            st.markdown(f"<span style='color:#28a745'>Step {idx}/{len(checked)} ▶ {' '.join(cmd)}</span>",
                        unsafe_allow_html=True)

            block, last, line_no = st.empty(), deque(maxlen=10), 0
            try:
                with subprocess.Popen(cmd, cwd=APP_DIR,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, encoding="utf-8", errors="replace",
                                      env=env) as p:
                    for line in p.stdout:
                        line_no += 1
                        last.append(line.rstrip())
                        if line_no % 3 == 0:
                            block.code("\n".join(last), language="bash")
                    p.communicate()
                    if p.returncode:
                        raise subprocess.CalledProcessError(p.returncode, cmd)
            except subprocess.CalledProcessError:
                block.code("\n".join(last), language="bash")
                st.error(f"❌ {lbl} 실패 – 이후 단계 중단")
                stat.update(label="실패", state="error")
                st.stop()

            block.code("\n".join(last), language="bash")
            sync_csv()

        # 통합 CSV 생성 → 동기화
        make_full_csv()
        sync_csv()

        stat.update(label="✅ 모든 단계 완료!", state="complete")
        st.success("🎉 music_library_tags_bpm.csv & music_library_full.csv 생성이 끝났습니다.")
