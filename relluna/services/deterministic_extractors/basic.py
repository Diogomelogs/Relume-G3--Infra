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
        if layer2.qualidade_sinal is None:
            layer2.qualidade_sinal = QualidadeSinal()

        if path.exists():
            try:
                with Image.open(path) as img:
                    img.load()
                    width, height = img.size

                # Extrair EXIF completo (novo fluxo)
                exif_full = _extract_full_exif(path)

                if exif_full:
                    # Import aqui para evitar import circular no topo
                    from relluna.core.document_memory.types_basic import MetadadosExif, GpsExif

                    meta = MetadadosExif()

                    # Device / Câmera
                    meta.fabricante = _make_string(exif_full.get("Make"), "Pillow.getexif")
                    meta.modelo_camera = _make_string(exif_full.get("Model"), "Pillow.getexif")
                    meta.modelo_lente = _make_string(exif_full.get("LensModel"), "Pillow.getexif")

                    # Configurações de captura
                    iso_val = exif_full.get("ISOSpeedRatings") or exif_full.get("PhotographicSensitivity")
                    if iso_val is not None:
                        try:
                            meta.iso = _make_number(float(iso_val), "Pillow.getexif")
                        except (ValueError, TypeError):
                            pass

                    # Abertura (FNumber)
                    fnumber = exif_full.get("FNumber")
                    if fnumber:
                        try:
                            if isinstance(fnumber, tuple):
                                meta.abertura = _make_string(
                                    f"f/{float(fnumber[0]) / float(fnumber[1]):.1f}",
                                    "Pillow.getexif",
                                )
                            else:
                                meta.abertura = _make_string(f"f/{float(fnumber):.1f}", "Pillow.getexif")
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass

                    # Velocidade do obturador
                    exp_time = exif_full.get("ExposureTime")
                    if exp_time:
                        try:
                            if isinstance(exp_time, tuple):
                                num, den = exp_time
                                if den != 0:
                                    if num >= den:
                                        meta.velocidade_obturador = _make_string(
                                            f"{num / den:.1f}s", "Pillow.getexif"
                                        )
                                    else:
                                        meta.velocidade_obturador = _make_string(
                                            f"1/{int(den / num)}s", "Pillow.getexif"
                                        )
                            else:
                                t = float(exp_time)
                                if t >= 1:
                                    meta.velocidade_obturador = _make_string(
                                        f"{t:.1f}s", "Pillow.getexif"
                                    )
                                else:
                                    meta.velocidade_obturador = _make_string(
                                        f"1/{int(1 / t)}s", "Pillow.getexif"
                                    )
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass

                    # Distância focal
                    focal = exif_full.get("FocalLength")
                    if focal:
                        try:
                            if isinstance(focal, tuple):
                                focal_mm = float(focal[0]) / float(focal[1])
                            else:
                                focal_mm = float(focal)
                            meta.distancia_focal = _make_string(
                                f"{int(focal_mm)}mm", "Pillow.getexif"
                            )
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass

                    # Distância focal equivalente 35mm
                    focal_35mm = exif_full.get("FocalLengthIn35mmFilm")
                    if focal_35mm is not None:
                        try:
                            meta.distancia_focal_35mm = _make_number(
                                float(focal_35mm), "Pillow.getexif"
                            )
                        except (ValueError, TypeError):
                            pass

                    # Datas
                    meta.data_captura = _make_string(
                        exif_full.get("DateTimeOriginal"), "Pillow.getexif"
                    )
                    meta.data_modificacao = _make_string(
                        exif_full.get("DateTime"), "Pillow.getexif"
                    )
                    meta.data_digitizacao = _make_string(
                        exif_full.get("DateTimeDigitized"), "Pillow.getexif"
                    )

                    # GPS
                    gps_decoded = exif_full.get("GPSInfo_decoded")
                    if gps_decoded:
                        lat, lon = _parse_gps_coordinates(gps_decoded)
                        if lat is not None and lon is not None:
                            gps = GpsExif()
                            gps.lat = _make_number(lat, "Pillow.getexif")
                            gps.lon = _make_number(lon, "Pillow.getexif")
                            meta.gps = gps

                            # Backward compatibility
                            layer2.gps_exif = gps

                    # Software
                    meta.software = _make_string(
                        exif_full.get("Software"), "Pillow.getexif"
                    )

                    # Descrição/Processamento
                    desc = exif_full.get("ImageDescription") or exif_full.get("UserComment")
                    if desc and str(desc).strip():
                        meta.processamento = _make_string(
                            str(desc), "Pillow.getexif"
                        )

                    # Orientação
                    orientacao = exif_full.get("Orientation")
                    if orientacao is not None:
                        try:
                            meta.orientacao = _make_number(
                                float(orientacao), "Pillow.getexif"
                            )
                        except (ValueError, TypeError):
                            pass

                    # Resolução
                    res_x = exif_full.get("XResolution")
                    if res_x:
                        try:
                            if isinstance(res_x, tuple):
                                meta.resolucao_x = _make_number(
                                    float(res_x[0]) / float(res_x[1]),
                                    "Pillow.getexif",
                                )
                            else:
                                meta.resolucao_x = _make_number(
                                    float(res_x), "Pillow.getexif"
                                )
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass

                    res_y = exif_full.get("YResolution")
                    if res_y:
                        try:
                            if isinstance(res_y, tuple):
                                meta.resolucao_y = _make_number(
                                    float(res_y[0]) / float(res_y[1]),
                                    "Pillow.getexif",
                                )
                            else:
                                meta.resolucao_y = _make_number(
                                    float(res_y), "Pillow.getexif"
                                )
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass

                    # Flash
                    flash_val = exif_full.get("Flash")
                    if flash_val is not None:
                        flash_modes = {
                            0: "No Flash",
                            1: "Flash",
                            5: "Flash, strobe return light not detected",
                            7: "Flash, strobe return light detected",
                            9: "Compulsory Flash",
                            13: "Compulsory Flash, Return light not detected",
                            15: "Compulsory Flash, Return light detected",
                            16: "No Flash function",
                            24: "Flash, Auto-Mode",
                            25: "Flash, Auto-Mode, Return light not detected",
                            29: "Flash, Auto-Mode, Return light detected",
                            32: "No Flash function",
                            65: "Flash, Red-eye reduction",
                            69: "Flash, Red-eye reduction, Return light not detected",
                            71: "Flash, Red-eye reduction, Return light detected",
                            73: "Flash, Compulsory, Red-eye reduction",
                            77: "Flash, Compulsory, Red-eye reduction, Return light not detected",
                            79: "Flash, Compulsory, Red-eye reduction, Return light detected",
                            89: "Flash, Auto-Mode, Red-eye reduction",
                            93: "Flash, Auto-Mode, Red-eye reduction, Return light not detected",
                            95: "Flash, Auto-Mode, Red-eye reduction, Return light detected",
                        }
                        flash_str = flash_modes.get(
                            flash_val, f"Flash({flash_val})"
                        )
                        meta.flash = _make_string(flash_str, "Pillow.getexif")

                    # White Balance
                    wb_val = exif_full.get("WhiteBalance")
                    if wb_val is not None:
                        wb_modes = {
                            0: "Auto",
                            1: "Sunny",
                            2: "Cloudy",
                            3: "Tungsten",
                            4: "Fluorescent",
                            5: "Flash",
                            6: "Custom",
                        }
                        wb_str = wb_modes.get(wb_val, f"WhiteBalance({wb_val})")
                        meta.brancos = _make_string(wb_str, "Pillow.getexif")

                    # Copyright / artista
                    meta.direitos_autor = _make_string(
                        exif_full.get("Copyright"), "Pillow.getexif"
                    )
                    meta.artista = _make_string(
                        exif_full.get("Artist"), "Pillow.getexif"
                    )

                    # Atribuir ao layer2
                    layer2.metadados_exif = meta

                    # Backward compatibility: data_exif
                    # v0.1.0 contract: data_exif must be stub
                    layer2.data_exif = _make_empty_date()                

                else:
                    # Sem EXIF
                    layer2.data_exif = _make_empty_date()
                    layer2.gps_exif = None

            except Exception:
                width = None
                height = None
                layer2.data_exif = _make_empty_date()
                layer2.gps_exif = None
        else:
            width = None
            height = None
            layer2.data_exif = _make_empty_date()
            layer2.gps_exif = None

        layer2.largura_px = _make_number(width, "Pillow.size")
        layer2.altura_px = _make_number(height, "Pillow.size")

        if width and height:
            layer2.qualidade_sinal.resolucao = InferredString(
                valor=f"{int(width)}x{int(height)}",
                fonte=FONTE,
                metodo="Pillow.size",
                estado=ConfidenceState.confirmado,
                confianca=1.0,
                lastro=[],
            )
            layer2.qualidade_sinal.foco = ProvenancedNumber(
                valor=float(width * height),
                fonte=FONTE,
                metodo="focus_stub",
                estado=ConfidenceState.inferido,
                confianca=None,
            )

        if layer2.texto_ocr_literal is None:
            layer2.texto_ocr_literal = make_layer2_ocr_field(path)

    # ---------------- PDF ----------------
    elif dm.layer1.midia == MediaType.documento and path.suffix.lower() == ".pdf":
        if path.exists():
            reader = PdfReader(str(path))
            num = len(reader.pages)
        layer2.num_paginas = _make_number(num, "pypdf")

    # v0.1.0 contract: OCR stub only
        layer2.texto_ocr_literal = _make_empty_ocr()

    # ---------------- ÁUDIO ----------------
    elif dm.layer1.midia == MediaType.audio:
        dur = _audio_wav_duration_seconds(path) if path.exists() else None
        layer2.duracao_segundos = _make_number(dur, "audio_probe")

    # ---------------- VÍDEO ----------------
    elif dm.layer1.midia == MediaType.video:
        if path.exists():
            # Extrair metadados completos via ffprobe
            video_meta = _extract_full_video_metadata(path)

            if video_meta:
                # Duração
                format_info = video_meta.get("format", {})
                dur = format_info.get("duration")
                if dur:
                    try:
                        layer2.duracao_segundos = _make_number(float(dur), "ffprobe")
                    except (ValueError, TypeError):
                        pass

                # Informações dos streams (vídeo e áudio)
                streams = video_meta.get("streams", [])

                for stream in streams:
                    codec_type = stream.get("codec_type")

                    if codec_type == "video":
                        # Resolução
                        width = stream.get("width")
                        height = stream.get("height")
                        if width and height:
                            layer2.largura_px = _make_number(float(width), "ffprobe")
                            layer2.altura_px = _make_number(float(height), "ffprobe")

                        # FPS (calculado mas ainda não armazenado em campo próprio)
                        fps_str = stream.get("avg_frame_rate", "0/1")
                        try:
                            num, den = fps_str.split("/")
                            fps = float(num) / float(den) if float(den) != 0 else None
                            if fps:
                                # Poderíamos adicionar um campo FPS ao Layer2 futuramente
                                pass
                        except (ValueError, ZeroDivisionError):
                            pass

                        # Criar qualidade_sinal se necessário
                        if layer2.qualidade_sinal is None:
                            layer2.qualidade_sinal = QualidadeSinal()

                        if width and height:
                            layer2.qualidade_sinal.resolucao = InferredString(
                                valor=f"{width}x{height}",
                                fonte=FONTE,
                                metodo="ffprobe",
                                estado=ConfidenceState.confirmado,
                                confianca=1.0,
                                lastro=[],
                            )

                    elif codec_type == "audio":
                        # Taxa de amostragem
                        sample_rate = stream.get("sample_rate")
                        if sample_rate:
                            try:
                                layer2.taxa_amostragem_hz = _make_number(float(sample_rate), "ffprobe")
                            except (ValueError, TypeError):
                                pass

                # Tags do container (metadata)
                tags = format_info.get("tags", {})
                if tags:
                    creation_time = tags.get("creation_time") or tags.get("date")
                    if creation_time:
                        # Tentar parsear a data
                        try:
                            # Formato ISO ou variantes
                            dt = None
                            for fmt in [
                                "%Y-%m-%dT%H:%M:%S.%fZ",
                                "%Y-%m-%dT%H:%M:%SZ",
                                "%Y-%m-%d %H:%M:%S",
                            ]:
                                try:
                                    dt = datetime.strptime(creation_time[: len(fmt)], fmt)
                                    break
                                except ValueError:
                                    continue
                            if dt:
                                layer2.data_exif = ProvenancedString(
                                    valor=dt.strftime("%Y%m%d %H%M%S"),
                                    fonte=FONTE,
                                    metodo="ffprobe",
                                    estado=ConfidenceState.confirmado,
                                    confianca=1.0,
                                )
                        except Exception:
                            # Se não conseguir parsear, salvar como string
                            layer2.data_exif = ProvenancedString(
                                valor=str(creation_time),
                                fonte=FONTE,
                                metodo="ffprobe",
                                estado=ConfidenceState.confirmado,
                                confianca=0.8,
                            )

                    # Localização (QuickTime / ISO6709)
                    loc_str = (
                        tags.get("com.apple.quicktime.location.ISO6709")
                        or tags.get("location")
                        or tags.get("location-eng")
                    )
                    if loc_str:
                        from relluna.core.document_memory.types_basic import GpsExif

                        lat, lon = _parse_iso6709_location(loc_str)
                        if lat is not None and lon is not None:
                            gps = GpsExif()
                            gps.lat = _make_number(lat, "ffprobe")
                            gps.lon = _make_number(lon, "ffprobe")
                            layer2.gps_exif = gps

            else:
                # Fallback: apenas duração
                dur = _video_duration_seconds(path)
                layer2.duracao_segundos = _make_number(dur, "video_probe")

            # OCR em frame chave do vídeo (se ainda não houver)
            if layer2.ocr_texto is None:
                frame_path = _extract_video_frame_for_ocr(path)
                if frame_path is not None:
                    try:
                        layer2.ocr_texto = make_layer2_ocr_field(frame_path)
                    except Exception:
                        pass

            # TRANSCRIÇÃO (se houver áudio): delega para serviço de ASR
            try:
                from relluna.services.transcription.asr import apply_transcription_to_layer2

                dm = apply_transcription_to_layer2(dm)
            except Exception:
                # Se falhar, continuar sem transcrição
                pass
        else:
            layer2.duracao_segundos = _make_number(None, "video_probe")

    return dm
