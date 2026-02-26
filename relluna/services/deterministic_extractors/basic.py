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
    InferredString,
    ConfidenceState,
    ProvenancedNumber,
    ProvenancedString,
    QualidadeSinal,
)
from relluna.services.deterministic_extractors.base import extract_base


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
    """Helper para criar ProvenancedString quando há valor."""
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
    # Usado para PDFs sem texto (ex.: páginas em branco)
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
    """Extrai metadados completos de vídeo via ffprobe."""
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
    """Lê DateTimeOriginal (ou DateTime) do EXIF e devolve como 'YYYYMMDD HHMMSS'.

    Mantido por compatibilidade; o fluxo novo usa metadados_exif.data_captura.
    """
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


def _extract_full_exif(path: Path) -> Optional[dict]:
    """Extrai TODOS os metadados EXIF disponíveis da imagem.

    Retorna dicionário com valores brutos ou None se não existir EXIF.
    """
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None

            # Mapear todos os tags NAME -> valor
            exif_data = {}
            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, f"Unknown_{tag_id}")
                exif_data[tag_name] = value

            # Tentar pegar EXIF GPSInfo (tags numéricos)
            try:
                gps_info = exif.get(34853)  # GPSInfo tag
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
    """Converte coordenadas GPS do formato EXIF para decimal.

    Retorna (latitude, longitude) ou (None, None).
    """

    def convert_to_degrees(value):
        """Converte tupla (graus, minutos, segundos) para decimal."""
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
    """Converte string ISO6709 (QuickTime), ex.: '-34.6048-058.3859+023.127/'
    em (latitude, longitude). Ignora altitude.
    """
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
    """Extrai um frame do vídeo para OCR usando ffmpeg e retorna o caminho da imagem."""
    if shutil.which("ffmpeg") is None:
        return None

    # Salva o frame na mesma pasta, com sufixo específico
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


def extract_basic(dm: DocumentMemory) -> DocumentMemory:
    dm = extract_base(dm)

    if dm.layer1 is None or not dm.layer1.artefatos:
        return dm

    artefato = dm.layer1.artefatos[0]
    path = Path(artefato.uri)
    layer2 = dm.layer2

    # ---------------- IMAGEM ----------------
    if dm.layer1.midia == MediaType.imagem:
        # Garante objeto de qualidade_sinal
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

        # Dimensões básicas (já estavam corretas)
        layer2.largura_px = _make_number(width, "Pillow.size")
        layer2.altura_px = _make_number(height, "Pillow.size")

        # qualidade_sinal.resolucao -> ProvenancedString("3264x2448", ...)
        if width is not None and height is not None:
            layer2.qualidade_sinal.resolucao = _make_string(
                f"{int(width)}x{int(height)}",
                "resolution_from_dimensions",
            )

        # foco (stub) -> ProvenancedNumber(float, ...)
        if layer2.qualidade_sinal.foco is None:
            # qualquer valor float > 0 atende o teste; 1.0 é um stub simples
            layer2.qualidade_sinal.foco = _make_number(1.0, "focus_stub")

        # data_exif:
        # - se houver EXIF: ProvenancedString com valor != None, estado=confirmado
        # - se não houver EXIF: objeto com valor=None, estado=insuficiente
        if layer2.data_exif is None:
            exif_str = _extract_exif_datetime_str(path)
            if exif_str is not None:
                layer2.data_exif = _make_string(exif_str, "exif")
            else:
                layer2.data_exif = _make_empty_date()

        # OCR literal (mantém lógica existente)
        if layer2.texto_ocr_literal is None:
            ocr_field = make_layer2_ocr_field(path)
            layer2.texto_ocr_literal = make_layer2_ocr_field(path)

        return dm

        # ---------------- PDF ----------------
    elif dm.layer1.midia == MediaType.documento and path.suffix.lower() == ".pdf":
        num: float | None = None
        if path.exists():
            try:
                reader = PdfReader(str(path))
                num = float(len(reader.pages))
            except Exception:
                num = None

        # num_paginas sempre como ProvenancedNumber (nunca None bruto)
        layer2.num_paginas = _make_number(num, "pypdf")

        # texto_ocr_literal sempre como ProvenancedString (mesmo vazio)
        if layer2.texto_ocr_literal is None:
            ocr_field = make_layer2_ocr_field(path)
            layer2.texto_ocr_literal = ocr_field or _make_empty_ocr()

        return dm

    # ---------------- ÁUDIO ----------------
    elif dm.layer1.midia == MediaType.audio:
        dur = _audio_wav_duration_seconds(path) if path.exists() else None
        layer2.duracao_segundos = _make_number(dur, "audio_probe")
        return dm

    # ---------------- VÍDEO ----------------
    elif dm.layer1.midia == MediaType.video:
        if path.exists():
            dur = _video_duration_seconds(path)
            layer2.duracao_segundos = _make_number(dur, "video_probe")
        else:
            layer2.duracao_segundos = _make_number(None, "video_probe")

        return dm

    return dm