#!/usr/bin/env python
# bpm.py – 라이브러리 BPM 채우기 (2025-06-25)

from __future__ import annotations
import argparse, re, sys, unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import librosa
from rapidfuzz import process, fuzz
from tqdm import tqdm

##############################################################################
# 기본 경로
##############################################################################
CSV_IN  = Path("music_library_tags.csv")
CSV_OUT = Path("music_library_tags_bpm.csv")
FAILLOG = Path("bpm_failures.log")

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".wav", ".ogg"}

##############################################################################
# BPM 범위 테이블
##############################################################################
GENRE_RANGES: Dict[str, Tuple[int, int]] = {
    "tango":   (55, 95),
    "vals":    (55, 95),   # 발스 / 왈츠
    "waltz":   (55, 95),
    "milonga": (85, 130),
}

##############################################################################
# 문자열 유틸
##############################################################################
def slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text)

def strip_track_number(stem: str) -> str:
    return re.sub(r"^\s*\d+\s*[-_. ]\s*", "", stem).strip()

def base_title_from_stem(stem: str) -> str:
    return re.split(r"[-–—]", strip_track_number(stem), maxsplit=1)[0].strip()

clean_parentheses = re.compile(r"\([^)]*\)")

def slug_candidates(title: str) -> List[str]:
    t0 = title.strip()
    t1 = clean_parentheses.sub("", t0).strip()
    t2 = t0.split(" -")[0].strip()
    t3 = t1.split(" -")[0].strip()
    uniques = {t for t in (t0, t1, t2, t3) if t}
    return [slugify(t) for t in uniques]

##############################################################################
# 오디오 파일 인덱스
##############################################################################
def build_audio_index(root: Path, debug: bool=False) -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    all_files = [p for p in root.rglob("*") if p.suffix.lower() in AUDIO_EXTS]

    if debug:
        print(f"🔍  오디오 파일 인덱싱 중 …\n   → {len(all_files):,} 개 파일 인덱스 완료")

    for p in all_files:
        stem = p.stem
        keys = {slugify(stem), slugify(base_title_from_stem(stem))}
        for k in keys:
            index[k] = p     # 중복 slug ⇒ 마지막 값 유지

    return index

##############################################################################
# BPM 계산 + 보정
##############################################################################
def detect_bpm(filepath: Path) -> float | None:
    try:
        y, sr = librosa.load(str(filepath), mono=True)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_f = float(np.atleast_1d(tempo)[0])
        return round(tempo_f, 1)
    except Exception:
        return None

def normalise_genre(raw: str) -> str:
    raw = (raw or "").lower().strip()
    if not raw:
        return "tango"
    if "milonga" in raw:
        return "milonga"
    if any(k in raw for k in ("vals", "valse", "waltz")):
        return "vals"
    return "tango"

def adjust_bpm(bpm: float, genre_key: str) -> Tuple[float, bool]:
    lo, hi = GENRE_RANGES.get(genre_key, GENRE_RANGES["tango"])
    adj_bpm = bpm
    # 너무 느리면 ×2, 너무 빠르면 ÷2 을 반복
    while adj_bpm < lo and adj_bpm > 1:
        adj_bpm *= 2
    while adj_bpm > hi:
        adj_bpm /= 2
    adj_bpm = round(adj_bpm, 1)
    changed = not np.isclose(adj_bpm, bpm)
    # 범위 여전히 벗어나면 실패 → 원본 유지
    if adj_bpm < lo or adj_bpm > hi:
        return bpm, False
    return adj_bpm, changed

##############################################################################
# 행 보강
##############################################################################
def enrich_row(row: pd.Series,
               audio_index: Dict[str, Path],
               fuzzy_keys: List[str],
               audio_root: Path,
               debug: bool=False) -> pd.Series:

    row = row.copy()
    title = row["Title"]
    slugs = slug_candidates(title)

    if debug:
        print(f"🎧  TEST BPM » {title}")
        print(f"   – slug candidates   : {slugs}")

    # ── 파일 매칭 ─────────────────────────────────────────────────────────
    path = next((audio_index[s] for s in slugs if s in audio_index), None)

    if path is None:
        match, score, _ = process.extractOne(
            slugify(title), fuzzy_keys, scorer=fuzz.ratio
        )
        if score >= 85:
            path = audio_index[match]
            if debug:
                print(f"   → fuzzy match      : {match} ({score}%)")

    if path is None:
        row["BPM"]     = ""
        row["BPMNote"] = "file-not-found"
        if debug:
            print("   → file             : (미검색)\n")
        return row

    # ── BPM 측정 & 보정 ─────────────────────────────────────────────────
    raw_bpm = detect_bpm(path)
    if raw_bpm is None:
        row["BPM"]     = ""
        row["BPMNote"] = "no-bpm"
        return row

    genre_key = normalise_genre(row.get("Genre", ""))
    adj_bpm, changed = adjust_bpm(raw_bpm, genre_key)

    note_suffix = "(adj)" if changed else "(raw)"
    row["BPM"]     = adj_bpm
    row["BPMNote"] = f"{path.relative_to(audio_root).as_posix()} {note_suffix}"

    if debug:
        print(f"   → file             : {path}")
        print(f"   → detected BPM     : {raw_bpm}  →  adjusted: {adj_bpm}\n")

    return row

##############################################################################
# 메인
##############################################################################
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="음원 BPM 자동 계산기")
    ap.add_argument("--audio-root", required=True, metavar="DIR",
                    help="음악 파일들이 모여 있는 최상위 폴더")
    ap.add_argument("--single", metavar="TITLE",
                    help="제목이 포함된 첫 트랙만 테스트")
    ap.add_argument("--debug", action="store_true",
                    help="slug, 매칭 파일 경로 등을 출력")
    args = ap.parse_args()

    audio_root = Path(args.audio_root).expanduser().resolve()
    if not audio_root.exists():
        sys.exit(f"❌ {audio_root} 이(가) 존재하지 않습니다")

    if not CSV_IN.exists():
        sys.exit(f"❌ {CSV_IN} 을(를) 찾을 수 없습니다")

    # ── 인덱스 ────────────────────────────────────────────────────────────
    audio_index = build_audio_index(audio_root, debug=args.debug)
    fuzzy_keys  = list(audio_index.keys())

    # ── CSV 로드 & 열 준비 ────────────────────────────────────────────────
    df = pd.read_csv(CSV_IN)
    for col in ("BPM", "BPMNote"):
        if col not in df.columns:
            df[col] = ""

    # ── 처리 ────────────────────────────────────────────────────────────
    if args.single:
        mask = df["Title"].str.contains(args.single, case=False, regex=False, na=False)
        if mask.sum() == 0:
            sys.exit("❌ 해당 제목 없음")

        idx = mask.idxmax()
        df.loc[idx] = enrich_row(df.loc[idx], audio_index, fuzzy_keys,
                                 audio_root, debug=args.debug)
    else:
        with FAILLOG.open("w", encoding="utf-8") as flog:
            for idx in tqdm(df.index, desc="BPM", unit="trk"):
                before = df.loc[idx, ["BPM", "BPMNote"]].copy()
                df.loc[idx] = enrich_row(df.loc[idx], audio_index, fuzzy_keys,
                                         audio_root)
                after = df.loc[idx, ["BPM", "BPMNote"]]
                if (after["BPMNote"].startswith("file-not") or
                    after["BPMNote"].startswith("no-bpm")     or
                    after["BPMNote"].startswith("out-of-range")):
                    flog.write(f"{df.loc[idx,'Title']}\t{after['BPMNote']}\n")

    df.to_csv(CSV_OUT, index=False, encoding="utf-8-sig")
    print(f"✅  Done – saved → {CSV_OUT}")
    print(f"⚠️  실패/누락 로그 → {FAILLOG}")
