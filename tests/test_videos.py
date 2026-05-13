#!/usr/bin/env python3
import sys
from pathlib import Path
import hashlib
from datetime import datetime, UTC
import pytest
from relluna.core.basic_pipeline import run_basic_pipeline
from relluna.core.document_memory import DocumentMemory, Layer0Custodia as Layer0, Layer1, MediaType, OriginType, ArtefatoBruto

pytestmark = pytest.mark.xfail(
    reason="script legado de teste manual; depende de fixture video_path não definida",
    run=False,
    strict=False,
)

def test_video(video_path: str):
    p = Path(video_path)
    if not p.exists():
        print(f"❌ {p.name} não existe")
        return
    
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    
    dm = DocumentMemory(
        layer0=Layer0(
            documentid=p.stem[:20],
            contentfingerprint=digest,
            ingestiontimestamp=datetime.now(UTC).isoformat(),
            ingestionagent="batch_test"
        ),
        layer1=Layer1(
            midia=MediaType.video,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(
                id="video_main",
                tipo="original",
                uri=str(p),
                nome=p.name,
                mimetype="video/mp4",
                tamanho_bytes=p.stat().st_size
            )]
        )
    )
    
    print(f"📹 {p.name}")
    dm = run_basic_pipeline(dm)
    
    res = getattr(dm.layer2.video_metadata, 'resolucao', 'N/A')
    dur = getattr(dm.layer2.video_metadata, 'duracao', 'N/A')
    
    # Fix None seguro
    literal = getattr(dm.layer2, 'transcricao_literal', None)
    text = (getattr(literal, 'valor', '') or 'None')[:80] if literal else 'None'
    segs = len(getattr(dm.layer2, 'transcricao_segmentada', []))
    
    print(f"   FFProbe: {res} ({dur}s)")
    print(f"   Whisper: {text}...")
    print(f"   Segments: {segs}")
    print()

if __name__ == "__main__":
    for path in sys.argv[1:]:
        test_video(path)
