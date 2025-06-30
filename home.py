#!/usr/bin/env python
# home.py ― Streamlit 메인 페이지 (v2025-06-27)
#   • sidebar에 단계별 페이지 바로가기 버튼
#   • 필수 CSV 존재 여부·Python 패키지·환경 변수 점검
#   • 첫 실행 시 안내 메시지·리소스 링크 제공

from __future__ import annotations
import os
from pathlib import Path
import importlib
import streamlit as st

###############################################################################
# 1. 페이지 설정 & 기본 정보
###############################################################################
st.set_page_config(page_title="Poco Music DJ Toolkit", page_icon="🎶", layout="wide")
st.title("🎶 Poco Music DJ Toolkit – 홈")

with st.expander("ℹ️ 프로젝트 개요", expanded=True):
    st.markdown(
        """
        이 앱은 **탱고·발스·밀롱가 DJ**를 위한 올-인-원 워크플로우입니다.

        | 단계 | 페이지 | 주요 기능 |
        |------|--------|----------|
        | ① | **자동 태그 정리 (CSV) 생성** | 음악 폴더 → `music_library_full.csv` 자동 생성 |
        | ② | **음악 필터링 & 탄다 구성** | 다중 필터 + BPM·장르 태그 보정 & 탄다 빌더 |
        | ③ | **탄다 스케줄러** | ZIP/JSON/M3U 불러오기 + 편집|
        | ④ | **AI 탄다 의견** | AI 기반 탄다 피드백 |
        """,
        unsafe_allow_html=True,
    )

###############################################################################
# 2. Sidebar – 단계별 페이지 바로가기
###############################################################################
st.sidebar.header("📑 페이지 바로가기")

PAGES = [
    ("pages/1_자동태그정리파일생성(csv).py", "① 자동 태그 정리(csv) 생성", "🎼"),
    ("pages/2_음악필터링.py",              "② 음악 필터링 🎛️",       "🎛️"),
    ("pages/3_탄다스케줄러.py",            "③ 탄다 스케줄러 📅",     "📅"),
   ]

for path, label, icon in PAGES:
    if Path(path).exists():
        st.sidebar.page_link(path, label=f"{icon} {label}")
    else:
        st.sidebar.write(f"❌ `{Path(path).name}` 를 찾을 수 없습니다")


###############################################################################
# 4. 첫-사용자 안내
###############################################################################
if not st.session_state.get("first_visit_done"):
    st.success("🎉 앱이 로드되었습니다. 왼쪽 메뉴에서 ① 단계부터 순서대로 진행하세요!")
    st.session_state.first_visit_done = True
