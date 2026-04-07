#!/usr/bin/env python3
from pathlib import Path
from PIL import Image
import sys

sys.path.insert(0, '.')

try:
    from relluna.services.deterministic_extractors.basic import (
        _extract_exif_all,
        _extract_video_metadata_ffprobe,
    )
except Exception:
    def _extract_exif_all(p): return {}
    def _extract_video_metadata_ffprobe(p): return {}

files = [
    "uploads_test_ui/IMG_0153.jpg",
    "uploads_test_ui/IMG_2746.jpg",
    "uploads_test_ui/IMG_8231.MOV"
]

for f in files:
    p = Path(f)

    if not p.exists():
        print(f"❌ {f} missing")
        continue

    print(f"\n✅ {p.name}")
    print(f"  SIZE: {p.stat().st_size/1024/1024:.1f}MB")

    suffix = p.suffix.lower()

    # ---------------- IMAGEM ----------------
    if suffix in [".jpg", ".jpeg", ".png", ".webp", ".heic"]:
        try:
            print(f"  DIMS: {Image.open(p).size}")
        except Exception as e:
            print("  DIMS ERROR:", e)

        print(f"  EXIF: {_extract_exif_all(p)}")

    # ---------------- VÍDEO ----------------
    elif suffix in [".mov", ".mp4", ".m4v"]:
        print("  DIMS: N/A (vídeo)")
        print(f"  VIDEO META: {_extract_video_metadata_ffprobe(p)}")

    else:
        print("  Tipo não tratado")

print("\n🎉 TESTE FINALIZADO")