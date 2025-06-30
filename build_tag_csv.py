#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_tags_csv.py
 └─ (1) DJMusic ▸ 악단 ▸ 앨범 ▸ 파일명 4단계 폴더 구조
     (2) MP3 ID3 태그 (Title, Artist, Album)
     (3) BPM (librosa, 130↑ → ÷2 보정)
 모두 합쳐 CSV로 저장 → <루트>/music_library_tags.csv
"""

import os, sys, time, librosa, pandas as pd
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen import File
from tqdm import tqdm

# ──────────── MP3 태그 로딩 ─────────────────────────────
def load_tags(path: str):
    try:
        return MP3(path, ID3=EasyID3).tags
    except Exception:
        audio = File(path, easy=True)
        return audio.tags if audio else None

# ──────────── CSV 빌드 메인 ────────────────────────────
def build_csv(root: str):
    root = os.path.abspath(root)
    root_name = os.path.basename(root.rstrip("/\\"))
    rows = []

    # 지정한 깊이(루트/악단/앨범/파일)만 탐색
    mp3_files = []
    for orch in os.listdir(root):
        o_path = os.path.join(root, orch)
        if not os.path.isdir(o_path):
            continue
        for alb in os.listdir(o_path):
            a_path = os.path.join(o_path, alb)
            if not os.path.isdir(a_path):
                continue
            mp3_files.extend(
                os.path.join(a_path, f)
                for f in os.listdir(a_path)
                if f.lower().endswith(".mp3")
            )

    print(f"총 MP3 파일 수: {len(mp3_files)}")

    for fp in tqdm(mp3_files, desc="Scanning"):
        parts = fp[len(root):].lstrip("/\\").split(os.sep)
        if len(parts) < 3:  # 악단/앨범/파일 구조가 아니면 건너뜀
            continue
        orchestra, album, file_name = parts[0], parts[1], parts[2]

        tags = load_tags(fp)
        if tags is None:
            continue

        def tag(key, default=""):
            return tags.get(key, [default])[0].strip() if tags.get(key) else default

        title  = tag("title", os.path.splitext(file_name)[0])
        artist = tag("artist")
        albtag = tag("album")

        # BPM 계산 (파일 전체가 오래 걸릴 수 있어 60초만 분석)
        try:
            y, sr = librosa.load(fp, mono=True, duration=60)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            bpm_val = tempo / 2 if tempo >= 130 else tempo  # 130↑이면 ½로 보정
            bpm     = int(round(bpm_val))
        except Exception:
            bpm = ""

        rows.append(
            dict(
                Root=root_name,            # A열
                Orchestra=orchestra,       # B열
                AlbumFolder=album,         # C열
                FileName=file_name,        # D열
                Title=title,               # E열
                TrackArtist=artist,        # F열
                AlbumTag=albtag,           # G열
                BPM=bpm                    # H열
            )
        )

    # DataFrame → CSV
    df = pd.DataFrame(rows,
        columns=[
            "Root", "Orchestra", "AlbumFolder", "FileName",
            "Title", "TrackArtist", "AlbumTag", "BPM"
        ]
    )
    out_csv = os.path.join(root, "music_library_tags.csv")
    df.to_csv(out_csv, index=False, encoding="utf-8")
    print(f"\n✅ CSV 저장 완료 → {out_csv}  (총 {len(df)} 곡)")

# ──────────── 실행부 ───────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) >= 2:
        root_dir = sys.argv[1]
    else:
        root_dir = r"C:/DJMusic"   # 기본값
    t0 = time.time()
    build_csv(root_dir)
    print(f"소요 시간: {time.time() - t0:.1f}초")
