#!/usr/bin/env python
# scrap.py – tango.info 태그 스크래퍼  (RecordingDate 컬럼-추가판)
# 2025-06-24

from __future__ import annotations
import argparse, re, sys, time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from tqdm import tqdm


##############################################################################
# 경로와 HTTP 세션
##############################################################################
CSV_IN  = Path("music_library_tags.csv")
CSV_OUT = Path("music_library_tags_updated.csv")

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0 Safari/537.36"
})


##############################################################################
# 유틸
##############################################################################
def similarity(a: str, b: str) -> float:
    """token_set_ratio (0~1) – 단어 순서·불용어에 둔감."""
    return fuzz.token_set_ratio(a or "", b or "") / 100.0


def clean_title(t: str) -> str:
    """‘01 La Cumparsita (Tango)’ → ‘La Cumparsita’ 처럼 정리."""
    t = re.sub(r"^\s*\d+\s+", "", t)        # 번호 제거
    t = re.sub(r"\([^)]*\)", "", t)         # 괄호 제거
    return t.strip()


##############################################################################
# tango.info work 검색 → TIWC 링크 하나
##############################################################################
def find_tiwc_link(work_query: str) -> str | None:
    url    = "https://tango.info/search"
    params = {"q": work_query, "c": "work"}

    try:
        r = S.get(url, params=params, timeout=15)
        r.raise_for_status()
    except requests.RequestException:
        return None

    a = BeautifulSoup(r.text, "lxml").select_one(
        "table.listing tbody a[href^='/T']"
    )
    return f"https://tango.info{a['href']}" if a else None


##############################################################################
# TIWC 페이지 → Performance 행 하나 파싱
##############################################################################
_DATE_FULL = re.compile(r"\b(19|20)\d{2}-\d{2}-\d{2}\b")
_DATE_YEAR = re.compile(r"\b(19|20)\d{2}\b")

def parse_performance(tiwc_url: str,
                      orchestra_hint: str,
                      vocalist_hint: str | None = None
                      ) -> tuple[str, str, str] | None:
    """return (recording_date, genre, vocalist) 또는 None"""
    try:
        r = S.get(tiwc_url, timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        return None

    rows = BeautifulSoup(r.text, "lxml").select("table.listing tbody tr")
    best, best_score = None, -1.0

    for tr in rows:
        tds = [td.get_text(strip=True) for td in tr.select("td")]
        if len(tds) < 7:
            continue

        genre_cell, orch_name, vocalist, date_cell = tds[2], tds[3], tds[4], tds[6]

        score = 0.7 * similarity(orch_name, orchestra_hint) + \
                0.3 * similarity(vocalist, vocalist_hint)

        if score <= best_score:
            continue

        m_full = _DATE_FULL.search(date_cell)
        m_year = _DATE_YEAR.search(date_cell)
        rec_date = ""
        if m_full:
            rec_date = m_full.group(0)          # YYYY-MM-DD
        elif m_year:
            rec_date = m_year.group(0)          # YYYY

        best = (rec_date, genre_cell.capitalize(), vocalist or "inst")
        best_score = score

    return best


##############################################################################
# 행 보강
##############################################################################
def enrich_row(row: pd.Series) -> pd.Series:
    row = row.copy()  # SettingWithCopy 경고 방지

    title          = clean_title(row["Title"])
    orchestra_hint = row["Orchestra"]
    vocalist_hint  = row.get("TrackArtist", "")

    tiwc = find_tiwc_link(title)
    if not tiwc:
        row["ScrapNote"] = "no-work"
        return row

    perf = parse_performance(tiwc, orchestra_hint, vocalist_hint)
    if not perf:
        row["ScrapNote"] = "no-perf"
        return row

    rec_date, genre, vocalist = perf
    row["RecordingDate"] = rec_date
    row["Genre"]         = genre
    row["Vocalist"]      = vocalist
    row["Leader"]        = orchestra_hint
    row["ScrapNote"]     = "✓"
    return row


##############################################################################
# 메인
##############################################################################
def main() -> None:
    ap = argparse.ArgumentParser(description="tango.info 태그 자동 보강기")
    ap.add_argument("--single", metavar="TITLE",
                    help="제목이 포함된 첫 트랙만 테스트")
    args = ap.parse_args()

    if not CSV_IN.exists():
        sys.exit(f"❌ {CSV_IN} not found")

    df = pd.read_csv(CSV_IN)

    # 새 컬럼 확보
    for col in ("RecordingDate", "Genre", "Vocalist", "Leader", "ScrapNote"):
        if col not in df.columns:
            df[col] = ""

    if args.single:
        mask = df["Title"].str.contains(args.single, case=False, regex=False)
        if mask.sum() == 0:
            sys.exit("❌ 해당 제목 없음")
        idx = mask.idxmax()
        print(f"🎧 TEST » {df.at[idx,'Title']} | {df.at[idx,'Orchestra']}")
        df.loc[idx] = enrich_row(df.loc[idx])
    else:
        for idx in tqdm(df.index, desc="Tracks", unit="trk"):
            df.loc[idx] = enrich_row(df.loc[idx])

    df.to_csv(CSV_OUT, index=False)
    print(f"✅ Saved → {CSV_OUT}")


if __name__ == "__main__":
    main()
