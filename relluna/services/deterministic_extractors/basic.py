from __future__ import annotations

from pathlib import Path
from typing import Optional
from datetime import datetime
import contextlib
import json
import re
import shutil
import subprocess
import wave

from PIL import Image, ExifTags
from pypdf import PdfReader

from relluna.services.ocr import make_layer2_ocr_field

from relluna.core.document_memory import (
    DocumentMemory,
    MediaType,
    ConfidenceState,
    ProvenancedNumber,
    ProvenancedString,
    QualidadeSinal,
)

from relluna.services.deterministic_extractors.base import extract_base
from relluna.services.deterministic_extractors.pdf_layout import extract_pdf_layout_spans
from relluna.services.deterministic_extractors.entities_hard_v2 import extract_hard_entities_v2
from relluna.services.deterministic_extractors.structured_block import extract_structured_contract_block

FONTE = "deterministic_extractors.basic"


def _make_number(valor: Optional[float], metodo: str) -> ProvenancedNumber:
    if valor is not None:
        return ProvenancedNumber(
            valor=float(valor),
            fonte=FONTE,
            metodo=metodo,
            estado=ConfidenceState.confirmado,
            confianca=1.0,
        )
    return ProvenancedNumber(
        valor=None,
        fonte=FONTE,
        metodo=metodo,
        estado=ConfidenceState.insuficiente,
        confianca=None,
    )


def _make_string(valor: Optional[str], metodo: str) -> Optional[ProvenancedString]:
    if valor is not None and str(valor).strip():
        return ProvenancedString(
            valor=str(valor),
            fonte=FONTE,
            metodo=metodo,
            estado=ConfidenceState.confirmado,
            confianca=1.0,
        )
    return None


def _make_empty_date() -> ProvenancedString:
    return ProvenancedString(
        valor=None,
        fonte=FONTE,
        metodo="exif",
        estado=ConfidenceState.insuficiente,
        confianca=None,
    )


def _make_empty_ocr() -> ProvenancedString:
    return ProvenancedString(
        valor=None,
        fonte=FONTE,
        metodo="ocr_stub",
        estado=ConfidenceState.insuficiente,
        confianca=None,
    )


def _audio_wav_duration_seconds(path: Path) -> Optional[float]:
    try:
        with contextlib.closing(wave.open(str(path), "rb")) as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate == 0:
                return None
            return frames / float(rate)
    except Exception:
        return None


def _video_duration_seconds(path: Path) -> Optional[float]:
    if shutil.which("ffprobe") is None:
        return None
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        data = json.loads(out.decode("utf-8"))
        dur_str = data.get("format", {}).get("duration")
        return float(dur_str) if dur_str else None
    except Exception:
        return None


def _extract_full_video_metadata(path: Path) -> Optional[dict]:
    if shutil.which("ffprobe") is None:
        return None
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,bit_rate,format_name",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels",
            "-show_entries",
            "format_tags=creation_time,location,location-eng,com.apple.quicktime.location.ISO6709",
            "-of",
            "json",
            str(path),
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
        return json.loads(out.decode("utf-8"))
    except Exception:
        return None


def _extract_exif_datetime_str(path: Path) -> Optional[str]:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None

            dt_tag = None
            for tag_id, tag_name in ExifTags.TAGS.items():
                if tag_name == "DateTimeOriginal":
                    dt_tag = tag_id
                    break
            if dt_tag is None:
                dt_tag = 306  # DateTime

            raw = exif.get(dt_tag)
            if not raw:
                return None

            raw_str = str(raw)
            try:
                dt = datetime.strptime(raw_str, "%Y:%m:%d %H:%M:%S")
                return dt.strftime("%Y%m%d %H%M%S")
            except ValueError:
                return raw_str
    except Exception:
        return None
    return None


def _extract_full_exif(path: Path) -> Optional[dict]:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None

            exif_data: dict = {}
            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, f"Unknown_{tag_id}")
                exif_data[tag_name] = value

            try:
                gps_info = exif.get(34853)  # GPSInfo
                if gps_info:
                    from PIL.ExifTags import GPSTAGS

                    gps_data = {}
                    for key in gps_info.keys():
                        decode = GPSTAGS.get(key, key)
                        gps_data[decode] = gps_info[key]
                    exif_data["GPSInfo_decoded"] = gps_data
            except Exception:
                pass

            return exif_data
    except Exception:
        return None


def _parse_gps_coordinates(gps_data: dict) -> tuple[Optional[float], Optional[float]]:
    def convert_to_degrees(value):
        if not value:
            return None
        try:
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)
        except (TypeError, ValueError, IndexError):
            return None

    if not gps_data:
        return None, None

    try:
        lat = gps_data.get("GPSLatitude")
        lat_ref = gps_data.get("GPSLatitudeRef", "N")
        lon = gps_data.get("GPSLongitude")
        lon_ref = gps_data.get("GPSLongitudeRef", "E")

        if lat and lon:
            lat_dec = convert_to_degrees(lat)
            lon_dec = convert_to_degrees(lon)

            if lat_dec is not None and lon_dec is not None:
                if lat_ref == "S":
                    lat_dec = -lat_dec
                if lon_ref == "W":
                    lon_dec = -lon_dec
                return lat_dec, lon_dec
    except Exception:
        pass

    return None, None


_iso6709_re = re.compile(
    r"^(?P<lat>[+-]\d+\.\d+)(?P<lon>[+-]\d+\.\d+)(?P<alt>[+-]\d+\.\d+)?/$"
)


def _parse_iso6709_location(value: str) -> tuple[Optional[float], Optional[float]]:
    if not value:
        return None, None
    m = _iso6709_re.match(value.strip())
    if not m:
        return None, None
    try:
        lat = float(m.group("lat"))
        lon = float(m.group("lon"))
        return lat, lon
    except (TypeError, ValueError):
        return None, None


def _extract_video_frame_for_ocr(path: Path) -> Optional[Path]:
    if shutil.which("ffmpeg") is None:
        return None

    out_path = path.with_suffix(".frame_ocr.jpg")
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out_path),
        ]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
        if out_path.exists():
            return out_path
    except Exception:
        return None

    return None


def _populate_pdf_structural_signals(dm: DocumentMemory) -> DocumentMemory:
    """
    Para PDFs, este extractor deve produzir apenas sinais estruturais baratos e determinísticos.
    O OCR textual principal do PDF deve ficar concentrado em decompose_pdf_into_subdocuments()
    para evitar trabalho duplicado.
    """
    try:
        dm = extract_pdf_layout_spans(dm)
    except Exception:
        pass

    try:
        dm = extract_hard_entities_v2(dm)
    except Exception:
        pass

    try:
        dm = extract_structured_contract_block(dm)
    except Exception:
        pass

    return dm


def extract_basic(dm: DocumentMemory) -> DocumentMemory:
    dm = extract_base(dm)

    if dm.layer1 is None or not dm.layer1.artefatos:
        return dm

    artefato = dm.layer1.artefatos[0]
    path = Path(artefato.uri)
    layer2 = dm.layer2

    # ─── IMAGEM ────────────────────────────────────────────────────────────────
    if dm.layer1.midia == MediaType.imagem:
        if layer2.qualidade_sinal is None:
            layer2.qualidade_sinal = QualidadeSinal()

        width: float | None = None
        height: float | None = None

        if path.exists():
            try:
                with Image.open(path) as img:
                    img.load()
                    width, height = img.size
            except Exception:
                pass

        layer2.largura_px = _make_number(width, "Pillow.size")
        layer2.altura_px = _make_number(height, "Pillow.size")

        if width is not None and height is not None:
            layer2.qualidade_sinal.resolucao = _make_string(
                f"{int(width)}x{int(height)}",
                "resolution_from_dimensions",
            )

        if layer2.qualidade_sinal.foco is None:
            layer2.qualidade_sinal.foco = _make_number(1.0, "focus_stub")

        if layer2.data_exif is None:
            exif_str = _extract_exif_datetime_str(path)
            if exif_str is not None:
                layer2.data_exif = _make_string(exif_str, "exif")
            else:
                layer2.data_exif = _make_empty_date()

        if layer2.texto_ocr_literal is None:
            ocr_field = make_layer2_ocr_field(path)
            layer2.texto_ocr_literal = ocr_field

        return dm

    # ─── PDF / DOCUMENTO ───────────────────────────────────────────────────────
    elif dm.layer1.midia == MediaType.documento and path.suffix.lower() == ".pdf":
        num: float | None = None
        if path.exists():
            try:
                reader = PdfReader(str(path))
                num = float(len(reader.pages))
            except Exception:
                num = None

        layer2.num_paginas = _make_number(num, "pypdf")

        # IMPORTANTE:
        # Não popular texto_ocr_literal aqui para PDF.
        # O OCR textual completo será gerado em decompose_pdf_into_subdocuments(),
        # evitando duplicidade de OCR no caminho standard/forensic.
        dm = _populate_pdf_structural_signals(dm)

        return dm

    # ─── DOCUMENTO NÃO PDF ─────────────────────────────────────────────────────
    elif dm.layer1.midia == MediaType.documento:
        if layer2.texto_ocr_literal is None and path.exists():
            ocr_field = make_layer2_ocr_field(path)
            layer2.texto_ocr_literal = ocr_field or _make_empty_ocr()
        return dm

    # ─── ÁUDIO ─────────────────────────────────────────────────────────────────
    elif dm.layer1.midia == MediaType.audio:
        dur = _audio_wav_duration_seconds(path) if path.exists() else None
        layer2.duracao_segundos = _make_number(dur, "audio_probe")
        return dm

    # ─── VÍDEO ─────────────────────────────────────────────────────────────────
    elif dm.layer1.midia == MediaType.video:
        if path.exists():
            dur = _video_duration_seconds(path)
            layer2.duracao_segundos = _make_number(dur, "video_probe")
        else:
            layer2.duracao_segundos = _make_number(None, "video_probe")
        return dm

    return dm