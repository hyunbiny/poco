# pages/2_음악필터링.py
# ────────────────────────────────────────────────────────────────
# ② 음악 필터링 & 탄다 구성  ― music_library_full.csv 하나만 사용
#   · 곡 순서 편집 + 탄다 종류/이름 지정 (+평균 BPM 자동 태그)
#   · “3단계로 보내기” 버튼 → 세션에 tanda 목록 저장
# ────────────────────────────────────────────────────────────────
from __future__ import annotations
from pathlib import Path
import io, json, zipfile

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="음악 필터링", page_icon="🎛️", layout="wide")
st.title("② 음악 필터링 🎛️")

# ─────────── 세션 초기화 ──────────────────────────────────────────
for k, v in {
    "current_tanda": [],
    "current_tanda_type": "탱고",
    "tanda_groups": [],
}.items():
    st.session_state.setdefault(k, v)

# ─────────── 파일 업로드 ─────────────────────────────────────────
filter_box = st.sidebar.container()
filter_box.header("🎚️  필터")
st.sidebar.markdown("---")
st.sidebar.header("📂 CSV 업로드")

csv_default = Path("music_library_full.csv")
csv_file = st.sidebar.file_uploader("music_library_full.csv", type=["csv"])
if not csv_file and csv_default.exists():
    csv_file = csv_default.open("rb")

if not csv_file:
    st.error("music_library_full.csv 파일이 필요합니다.")
    st.stop()

audio_root = Path(
    st.sidebar.text_input("🎧 음악 폴더 루트", "C:/DJMUSIC")
).expanduser().resolve()

# ─────────── CSV 로드 & 기본 열 보강 ─────────────────────────────
df = pd.read_csv(csv_file)
for c, d in {"Genre": "", "BPM": np.nan, "RecordingYear": np.nan,
             "AlbumFolder": "", "AlbumTag": ""}.items():
    df[c] = df.get(c, d)

if df["RecordingYear"].isna().all() and "RecordingDate" in df.columns:
    df["RecordingYear"] = pd.to_numeric(df["RecordingDate"].astype(str).str[:4],
                                        errors="coerce")

# ─────────── 1. 필터 UI ─────────────────────────────────────────
with filter_box:
    orch_sel  = st.selectbox("악단",  ["(all)"] + sorted(df["Orchestra"].dropna().unique()))
    yrs       = df["RecordingYear"].dropna()
    y_min,y_max = (1900,2025) if yrs.empty else (int(yrs.min()),int(yrs.max()))
    y_range   = st.slider("녹음 연도", y_min, y_max, (y_min, y_max))
    genre_sel = st.selectbox("장르",   ["(all)", "tango", "vals", "milonga"])
    bpms      = df["BPM"].dropna()
    b_min,b_max = (0,250) if bpms.empty else (int(bpms.min()),int(bpms.max()))
    b_range   = st.slider("BPM 범위", b_min, b_max, (b_min,b_max))
    album_col = "AlbumFolder" if df["AlbumFolder"].notna().any() else "AlbumTag"
    album_sel = st.selectbox("앨범", ["(all)"] + sorted(df[album_col].dropna().unique()))

# ─────────── 2. 필터링 ──────────────────────────────────────────
f = df.copy()
if orch_sel!="(all)": f=f[f["Orchestra"]==orch_sel]
full_year = y_range==(y_min,y_max)
f=f[f["RecordingYear"].between(*y_range)|(full_year & f["RecordingYear"].isna())]
if genre_sel!="(all)": f=f[f["Genre"].str.lower()==genre_sel]
full_bpm=b_range==(b_min,b_max)
f=f[f["BPM"].between(*b_range)|(full_bpm & f["BPM"].isna())]
if album_sel!="(all)": f=f[f[album_col]==album_sel]

# ─────────── 3. 결과 테이블 ✔ 선택 ──────────────────────────────
st.subheader(f"🎵 필터 결과 — {len(f)}곡")
def mk_path(r:pd.Series)->str:
    parts=[audio_root,r["Orchestra"],r["AlbumFolder"],r["FileName"]]
    return str(Path(*[p for p in parts if pd.notna(p) and str(p).strip()]))

f=f.copy(); f["Path"]=f.apply(mk_path,axis=1)
table=f[["Title","Orchestra","RecordingYear","Genre","BPM"]].copy(); table.insert(0,"✔",False)
edited=st.data_editor(table,hide_index=True,use_container_width=True,
                      column_config={"✔":st.column_config.CheckboxColumn(required=False)},
                      key="tracks_select")
sel_df=f[edited["✔"]].copy()

# ─────────── 4. 선택 곡 순서 조정 ───────────────────────────────
ordered_paths=[]
if not sel_df.empty:
    st.markdown("#### ✏️ 선택 곡 순서 조정")
    seq=sel_df.reset_index(drop=True)[["Path","Title","Orchestra"]]
    seq["순서"]=range(1,len(seq)+1)
    seq_edit=st.data_editor(seq,column_config={
        "순서":st.column_config.NumberColumn(min_value=1,max_value=len(seq),step=1)},
        hide_index=True,key="order_editor")
    ordered_paths=seq_edit.sort_values("순서",kind="stable")["Path"].tolist()

# ─────────── 5. 미리듣기 ────────────────────────────────────────
if ordered_paths:
    pick=st.selectbox("🎧 미리 듣기",["(none)"]+ordered_paths)
    if pick!="(none)" and Path(pick).is_file():
        st.audio(open(pick,"rb").read(),format="audio/mp3")

# ─────────── 6. 탄다 빌더 ───────────────────────────────────────
st.markdown("---"); st.header("🎛️ 탄다 빌더")
col1,col2=st.columns([0.3,0.7])
with col1:
    st.session_state.current_tanda_type=st.selectbox(
        "탄다 종류",["탱고","발스","밀롱가","꼬르띠나"],
        index=["탱고","발스","밀롱가","꼬르띠나"].index(st.session_state.current_tanda_type))
with col2:
    tanda_name_input=st.text_input("탄다 이름 (비워두면 자동 생성)")

st.button("➕ 현재 곡들을 탄다에 추가",disabled=not ordered_paths,
          on_click=lambda:st.session_state.current_tanda.extend(ordered_paths))

def confirm_tanda():
    if not st.session_state.current_tanda:
        st.warning("곡을 먼저 추가하세요."); return
    tracks_df=f[f["Path"].isin(st.session_state.current_tanda)]
    avg_bpm=tracks_df["BPM"].astype(float).mean(skipna=True)
    bpm_tag=f"{round(avg_bpm):d} BPM" if not np.isnan(avg_bpm) else "BPM?"
    dom_orch=(tracks_df["Orchestra"].mode().iloc[0]
              if not tracks_df["Orchestra"].dropna().empty else "UnknownOrch")
    final_name=(f"{tanda_name_input.strip()} · {bpm_tag}"
                if tanda_name_input.strip()
                else f"{dom_orch} {st.session_state.current_tanda_type} · {bpm_tag}")
    st.session_state.tanda_groups.append({
        "name":final_name,
        "type":st.session_state.current_tanda_type,
        "tracks":st.session_state.current_tanda.copy(),
    })
    st.session_state.current_tanda.clear()

st.button("✅ 현재 탄다 확정",disabled=not st.session_state.current_tanda,
          on_click=confirm_tanda)

# ─────────── 7. 탄다 목록 표시 ─────────────────────────────────
def render_tanda(idx,tg):
    if isinstance(tg,dict):
        name=tg.get("name",f"Tanda {idx}"); ttype=tg.get("type","탱고")
        tracks=tg.get("tracks",[])
    else:  # 구버전 list
        name,ttype,tracks=f"Tanda {idx}","알수없음",tg
    st.write(f"• Tanda {idx} – **{name}** ({ttype}) – {len(tracks)}곡")

st.write("현재 탄다:",st.session_state.current_tanda or "(빈 상태)")
for i,tg in enumerate(st.session_state.tanda_groups,1):
    render_tanda(i,tg)

# ─────────── 8. 저장 / 내보내기  ───────────────────────────────
st.markdown("---"); st.header("💾 저장 및 내보내기")
flat=f["Path"].tolist()
st.download_button("TXT (필터 전체)","\n".join(flat),"tanda_full.txt")
st.download_button("JSON (필터 전체)",json.dumps(flat,ensure_ascii=False,indent=2),
                   "tanda_full.json")

incl_cur=st.checkbox("진행 중 탄다 포함",True)
export_groups=st.session_state.tanda_groups.copy()
if incl_cur and st.session_state.current_tanda:
    export_groups.append({
        "name":"(진행 중)","type":st.session_state.current_tanda_type,
        "tracks":st.session_state.current_tanda,
    })

if export_groups:
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as z:
        for idx,tg in enumerate(export_groups,1):
            if isinstance(tg,dict):
                name,ttype,tracks=tg["name"],tg["type"],tg["tracks"]
            else:
                name,ttype,tracks=f"Tanda {idx}","알수없음",tg
            base=f"tanda_{idx:02d}_{len(tracks)}_{ttype}"
            z.writestr(base+".txt","\n".join(tracks))
            z.writestr(base+".json",json.dumps(tg,ensure_ascii=False,indent=2))
    buf.seek(0)
    st.download_button("📦 ZIP (모든 탄다)",buf,"tandas.zip")

# ▶▶ 3단계로 보내기 (세션 저장)
def to_step3():
    # dict 형으로 통일
    norm=[]
    for tg in export_groups:
        if isinstance(tg,dict):
            norm.append(tg)
        else:
            norm.append({"name":"(이름없음)","type":"알수없음","tracks":tg})
    st.session_state.tandas_for_step3=norm
    st.success("✅ 3단계 페이지에서 바로 불러올 수 있습니다!")

st.button("➡ 3단계로 보내기",disabled=not export_groups,on_click=to_step3)

# ─────────── 9. CSV 다시 저장 ─────────────────────────────────
st.sidebar.markdown("---")
if st.sidebar.button("💾 music_library_full.csv 다시 저장"):
    df.to_csv("music_library_full.csv",index=False)
    st.sidebar.success("music_library_full.csv 로 저장 완료!")
