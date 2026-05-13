from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from .preprocess import build_image_variants, build_pdf_variants, read_image, render_pdf_page, split_rg_page
from .validators import (
    DOCUMENT_PATTERNS,
    count_document_hits,
    document_structure_score,
    evaluate_text_quality,
    normalize_spaces,
)


class DocType(Enum):
    NATIVE_PDF = "native_pdf"
    SCANNED_PDF = "scanned_pdf"
    IMAGE = "image"


class OCRStatus(Enum):
    APPROVED = "approved"
    REVIEW = "review"
    REJECTED = "rejected"


@dataclass
class OCRResult:
    text: str
    doc_type: DocType
    pages: int
    engine: str
    confidence: float | None
    status: OCRStatus
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    candidates: list[dict] = field(default_factory=list)

    def to_dict(self):
        data = asdict(self)
        data["doc_type"] = self.doc_type.value
        data["status"] = self.status.value
        return data


class OCRModule:
    SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}

    DOCUMENT_KEYWORDS = [
        "registro geral",
        "cpf",
        "nome",
        "data de nascimento",
        "secretaria da segurança",
        "secretaria da seguranca",
        "instituto de identificação",
        "instituto de identificacao",
        "carteira de identidade",
        "data de expedição",
        "data de expedicao",
        "doc origem",
        "número de controle",
        "numero de controle",
        "nit",
        "salário contribuição",
        "salario contribuicao",
        "origem do vínculo",
        "origem do vinculo",
        "cnis",
        "filiação",
        "filiacao",
    ]

    def __init__(
        self,
        lang: str = "por+eng",
        work_dir: str = ".ocr_work",
        enable_easyocr: bool = False,
        enable_paddleocr: bool = False,
    ):
        self.lang = lang
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.enable_easyocr = enable_easyocr
        self.enable_paddleocr = enable_paddleocr
        self._easy_reader = None
        self._paddle_reader = None

    def _get_easy_reader(self):
        if not self.enable_easyocr:
            return None
        if self._easy_reader is not None:
            return self._easy_reader
        try:
            import easyocr

            self._easy_reader = easyocr.Reader(["pt", "en"], gpu=False, verbose=False)
            return self._easy_reader
        except Exception:
            return None

    def _get_paddle_reader(self):
        if not self.enable_paddleocr:
            return None
        if self._paddle_reader is not None:
            return self._paddle_reader
        try:
            from paddleocr import PaddleOCR

            self._paddle_reader = PaddleOCR(use_textline_orientation=True, lang="pt")
            return self._paddle_reader
        except Exception:
            return None

    def extract(self, file_path: str | Path) -> OCRResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")
        if path.suffix.lower() not in self.SUPPORTED:
            raise ValueError(f"Formato não suportado: {path.suffix}")

        doc_type = self._detect_type(path)

        if doc_type == DocType.NATIVE_PDF:
            return self._extract_native_pdf(path)
        if doc_type == DocType.SCANNED_PDF:
            return self._extract_scanned_pdf(path)
        return self._extract_image(path)

    def _probe_native_pdf_text(self, path: Path) -> dict:
        doc = fitz.open(path)

        page_texts: list[str] = []
        page_blocks: list[str] = []
        image_count = 0

        for page in doc:
            page_texts.append(page.get_text("text") or "")
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (b[1], b[0]))
            for block in blocks:
                txt = (block[4] or "").strip()
                if txt:
                    page_blocks.append(txt)
            image_count += len(page.get_images(full=True))

        page_count = doc.page_count
        doc.close()

        raw_text = "\n".join(page_texts)
        blocks_text = "\n\n".join(page_blocks)
        lower = raw_text.lower()

        clean_text_len = sum(1 for c in raw_text if c.isalnum())
        avg_chars = clean_text_len / max(page_count, 1)
        keyword_hits = sum(1 for kw in self.DOCUMENT_KEYWORDS if kw in lower)

        return {
            "page_count": page_count,
            "raw_text": raw_text,
            "blocks_text": blocks_text,
            "clean_text_len": clean_text_len,
            "avg_chars": avg_chars,
            "keyword_hits": keyword_hits,
            "image_count": image_count,
            "structured_hits": count_document_hits(raw_text),
        }

    def _detect_type(self, path: Path) -> DocType:
        if path.suffix.lower() != ".pdf":
            return DocType.IMAGE

        probe = self._probe_native_pdf_text(path)

        if probe["avg_chars"] >= 80:
            return DocType.NATIVE_PDF

        if probe["keyword_hits"] >= 2 and probe["clean_text_len"] >= 40:
            return DocType.NATIVE_PDF

        if probe["structured_hits"] >= 2 and probe["clean_text_len"] >= 35:
            return DocType.NATIVE_PDF

        lower = probe["raw_text"].lower()
        if "registro geral" in lower and "nome" in lower and (
            "cpf" in lower or "data de nascimento" in lower
        ):
            return DocType.NATIVE_PDF

        if probe["image_count"] > 0 and probe["avg_chars"] < 35:
            return DocType.SCANNED_PDF

        if probe["clean_text_len"] >= 60:
            return DocType.NATIVE_PDF

        return DocType.SCANNED_PDF

    def _extract_native_pdf(self, path: Path) -> OCRResult:
        probe = self._probe_native_pdf_text(path)
        text = probe["blocks_text"] if probe["blocks_text"].strip() else probe["raw_text"]

        decision = evaluate_text_quality(text, confidence=99.0)
        decision = self._semantic_adjust(text, decision)

        return OCRResult(
            text=normalize_spaces(text),
            doc_type=DocType.NATIVE_PDF,
            pages=probe["page_count"],
            engine="pymupdf_blocks",
            confidence=99.0,
            status=OCRStatus(decision.status),
            reasons=decision.reasons,
            warnings=[],
            metrics=decision.to_dict()["metrics"],
            candidates=[],
        )

    def _extract_scanned_pdf(self, path: Path) -> OCRResult:
        candidates: list[OCRResult] = []

        via_ocrmypdf = self._extract_scanned_pdf_via_ocrmypdf(path)
        if via_ocrmypdf is not None:
            candidates.append(via_ocrmypdf)

        via_pages = self._extract_scanned_pdf_by_pages(path, previous=via_ocrmypdf)
        candidates.append(via_pages)

        return max(candidates, key=self._result_sort_key)

    def _extract_scanned_pdf_via_ocrmypdf(self, path: Path) -> OCRResult | None:
        if shutil.which("ocrmypdf") is None:
            return None

        with tempfile.TemporaryDirectory(prefix="ocrpdf_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            out_pdf = tmpdir_path / "out.pdf"
            sidecar = tmpdir_path / "out.txt"

            cmd = [
                "ocrmypdf",
                "--rotate-pages",
                "--deskew",
                "--clean",
                "--oversample",
                "300",
                "--skip-text",
                "-l",
                self.lang,
                "--sidecar",
                str(sidecar),
                str(path),
                str(out_pdf),
            ]

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=1800,
                    check=False,
                )
            except Exception:
                return None

            if proc.returncode != 0:
                return None

            text = sidecar.read_text(encoding="utf-8", errors="ignore") if sidecar.exists() else ""
            cleaned = normalize_spaces(text)
            alnum = sum(1 for c in cleaned if c.isalnum())
            if alnum < 25:
                return None

            decision = evaluate_text_quality(cleaned, confidence=78.0)
            decision = self._semantic_adjust(cleaned, decision)

            return OCRResult(
                text=cleaned,
                doc_type=DocType.SCANNED_PDF,
                pages=self._count_pdf_pages(path),
                engine="ocrmypdf",
                confidence=78.0,
                status=OCRStatus(decision.status),
                reasons=decision.reasons,
                warnings=[],
                metrics=decision.to_dict()["metrics"],
                candidates=[],
            )

    def _extract_scanned_pdf_by_pages(self, path: Path, previous: OCRResult | None = None) -> OCRResult:
        doc = fitz.open(path)

        page_texts: list[str] = []
        page_candidates: list[dict] = []
        page_confidences: list[float] = []
        warnings = list(previous.warnings) if previous else []
        inherited_reasons = list(previous.reasons) if previous else []

        for idx, page in enumerate(doc, start=1):
            img = render_pdf_page(page, dpi=300)
            best = self._best_pdf_candidate(img)

            page_texts.append(best["text"])
            if best["confidence"] is not None:
                page_confidences.append(best["confidence"])

            page_candidates.append(
                {
                    "page": idx,
                    "engine": best["engine"],
                    "variant": best["variant"],
                    "psm": best["psm"],
                    "confidence": best["confidence"],
                    "status": best["decision"]["status"],
                    "score": best["decision"]["metrics"]["score"],
                    "document_score": best["decision"]["metrics"].get("document_score", 0),
                    "reasons": best["decision"]["reasons"],
                }
            )

        doc.close()

        merged = "\n\n".join(t for t in page_texts if t.strip())
        avg_conf = round(sum(page_confidences) / len(page_confidences), 2) if page_confidences else None
        decision = evaluate_text_quality(merged, avg_conf)
        decision = self._semantic_adjust(merged, decision)

        return OCRResult(
            text=normalize_spaces(merged),
            doc_type=DocType.SCANNED_PDF,
            pages=len(page_candidates),
            engine="tesseract_pdf_fallback",
            confidence=avg_conf,
            status=OCRStatus(decision.status),
            reasons=sorted(set(inherited_reasons + decision.reasons)),
            warnings=warnings,
            metrics=decision.to_dict()["metrics"],
            candidates=page_candidates,
        )

    def _extract_image(self, path: Path) -> OCRResult:
        img = read_image(path)
        best = self._best_image_candidate(img)
        status = OCRStatus(best["decision"]["status"])

        warnings: list[str] = []
        if status == OCRStatus.REJECTED:
            warnings.append("ocr_rejeitado_por_qualidade")
        if best["decision"]["metrics"].get("document_score", 0) == 0:
            warnings.append("sem_campos_estruturados_detectados")

        return OCRResult(
            text=normalize_spaces(best["text"]),
            doc_type=DocType.IMAGE,
            pages=1,
            engine=best["engine"],
            confidence=best["confidence"],
            status=status,
            reasons=best["decision"]["reasons"],
            warnings=warnings,
            metrics=best["decision"]["metrics"],
            candidates=best["all_candidates"],
        )

    def _evaluate_page_regions(self, img, *, is_image: bool = False) -> dict:
        warnings: list[str] = []
        cards = split_rg_page(img, lang=self.lang)
        if len(cards) >= 2:
            warnings.append("layout_rg_split_detected")
            regions = cards
        else:
            regions = [{"name": "page", "image": img, "masked_image": None}]

        region_results: list[dict] = []
        for region in regions:
            if is_image:
                best = self._best_image_candidate(region["image"], masked_img=region.get("masked_image"))
            else:
                best = self._best_pdf_candidate(region["image"], masked_img=region.get("masked_image"))
            best["region"] = region["name"]
            region_results.append(best)

        ordered = sorted(region_results, key=self._region_sort_key, reverse=True)

        if len(cards) >= 2:
            selected = [
                result
                for result in ordered
                if result["region"] != "page"
                and (
                    result["decision"]["metrics"].get("document_score", 0) >= 6
                    or result["decision"]["status"] != "rejected"
                    or result["decision"]["metrics"].get("structured_hits", 0) >= 1
                )
            ]
            if not selected and ordered:
                selected = [ordered[0]]
        else:
            selected = [ordered[0]] if ordered else []

        merged_text = self._merge_region_texts(selected)
        avg_conf = self._average_confidence(selected)
        merged_decision = evaluate_text_quality(merged_text, avg_conf)
        merged_decision = self._semantic_adjust(merged_text, merged_decision)

        return {
            "merged_text": normalize_spaces(merged_text),
            "confidence": avg_conf,
            "engine": selected[0]["engine"] if selected else "unknown",
            "warnings": warnings,
            "candidates": self._serialize_candidates(ordered),
            "decision": merged_decision.to_dict(),
        }

    def _select_variant_plan(self, variants: dict, *, has_masked: bool) -> tuple[list[tuple[str, object]], tuple[int, ...]]:
        if has_masked:
            preferred = ["masked_adaptive", "masked_gray", "adaptive", "gray", "otsu"]
            psms = (6, 11)
            limit = 4
        else:
            preferred = ["adaptive", "gray", "sharp_otsu", "otsu", "no_tables", "inverted"]
            psms = (6, 11)
            limit = 4
        items = [(name, variants[name]) for name in preferred if name in variants][:limit]
        if not items:
            items = list(variants.items())[:limit]
        return items, psms

    def _best_pdf_candidate(self, img, *, masked_img=None) -> dict:
        variants = build_pdf_variants(img, masked_img=masked_img)
        variant_items, psms = self._select_variant_plan(variants, has_masked=masked_img is not None)
        all_candidates = []

        for variant_name, frame in variant_items:
            for psm in psms:
                text, conf = self._run_tesseract(frame, psm=psm)
                decision = evaluate_text_quality(text, conf)
                decision = self._semantic_adjust(text, decision)
                all_candidates.append({
                    "engine": f"tesseract:{variant_name}:psm{psm}",
                    "variant": variant_name,
                    "psm": psm,
                    "text": text,
                    "confidence": conf,
                    "decision": decision.to_dict(),
                })

        all_candidates = self._maybe_add_paddle_candidate(img, all_candidates)
        best = max(all_candidates, key=self._candidate_sort_key)
        best["all_candidates"] = self._serialize_candidates(all_candidates)
        return best

    def _best_image_candidate(self, img, *, masked_img=None) -> dict:
        variants = build_image_variants(img, masked_img=masked_img)
        variant_items, psms = self._select_variant_plan(variants, has_masked=masked_img is not None)
        all_candidates = []

        for variant_name, frame in variant_items:
            for psm in psms:
                text, conf = self._run_tesseract(frame, psm=psm)
                decision = evaluate_text_quality(text, conf)
                decision = self._semantic_adjust(text, decision)
                all_candidates.append({
                    "engine": f"tesseract:{variant_name}:psm{psm}",
                    "variant": variant_name,
                    "psm": psm,
                    "text": text,
                    "confidence": conf,
                    "decision": decision.to_dict(),
                })

        if self.enable_easyocr:
            all_candidates = self._maybe_add_easyocr_candidate(img, all_candidates)
        all_candidates = self._maybe_add_paddle_candidate(img, all_candidates)

        best = max(all_candidates, key=self._candidate_sort_key)
        best["all_candidates"] = self._serialize_candidates(all_candidates)
        return best

    def _maybe_add_easyocr_candidate(self, img, all_candidates: list[dict]) -> list[dict]:
        best = max(all_candidates, key=self._candidate_sort_key)
        metrics = best["decision"]["metrics"]
        if metrics.get("score", 0) >= 72 and metrics.get("document_score", 0) >= 8:
            return all_candidates
        reader = self._get_easy_reader()
        if reader is None:
            return all_candidates
        try:
            results = reader.readtext(img, detail=1, paragraph=True)
        except Exception:
            return all_candidates
        easy_text = "\n".join(item[1] for item in results).strip()
        easy_conf = round((sum(item[2] for item in results) / len(results)) * 100, 2) if results else None
        easy_decision = evaluate_text_quality(easy_text, easy_conf)
        easy_decision = self._semantic_adjust(easy_text, easy_decision)
        all_candidates.append({"engine": "easyocr", "variant": "raw", "psm": None, "text": easy_text, "confidence": easy_conf, "decision": easy_decision.to_dict()})
        return all_candidates

    def _maybe_add_paddle_candidate(self, img, all_candidates: list[dict]) -> list[dict]:
        if not self.enable_paddleocr:
            return all_candidates
        best = max(all_candidates, key=self._candidate_sort_key)
        metrics = best["decision"]["metrics"]
        if metrics.get("score", 0) >= 72 and (metrics.get("confidence") or 0) >= 60 and metrics.get("document_score", 0) >= 8:
            return all_candidates
        reader = self._get_paddle_reader()
        if reader is None:
            return all_candidates
        try:
            result = reader.ocr(img)
        except Exception:
            return all_candidates
        texts, confs = [], []
        if result and result[0]:
            for line in result[0]:
                texts.append(line[1][0])
                confs.append(line[1][1] * 100)
        text = "\n".join(texts).strip()
        conf = round(sum(confs) / len(confs), 2) if confs else None
        decision = evaluate_text_quality(text, conf)
        decision = self._semantic_adjust(text, decision)
        all_candidates.append({"engine": "paddleocr", "variant": "raw", "psm": None, "text": text, "confidence": conf, "decision": decision.to_dict()})
        return all_candidates

    def _candidate_sort_key(self, item: dict):
        decision = item["decision"]
        status_rank = {"approved": 3, "review": 2, "rejected": 1}[decision["status"]]
        conf = item["confidence"] if item["confidence"] is not None else -1
        structured = self._structured_score(item["text"])
        doc_score = decision["metrics"].get("document_score", 0)
        text_len = len(normalize_spaces(item["text"]))
        return (status_rank, structured, doc_score, decision["metrics"]["score"], conf, text_len)

    def _result_sort_key(self, result: OCRResult):
        status_rank = {"approved": 3, "review": 2, "rejected": 1}[result.status.value]
        conf = result.confidence if result.confidence is not None else -1
        structured = self._structured_score(result.text)
        score = result.metrics.get("score", 0)
        text_len = len(normalize_spaces(result.text))
        return (status_rank, structured, result.metrics.get("document_score", 0), score, conf, text_len)

    def _serialize_candidates(self, candidates: list[dict]) -> list[dict]:
        ordered = sorted(candidates, key=self._candidate_sort_key, reverse=True)
        return [
            {
                "engine": candidate["engine"],
                "variant": candidate.get("variant"),
                "psm": candidate.get("psm"),
                "confidence": candidate["confidence"],
                "status": candidate["decision"]["status"],
                "score": candidate["decision"]["metrics"]["score"],
                "document_score": candidate["decision"]["metrics"].get("document_score", 0),
                "reasons": candidate["decision"]["reasons"],
            }
            for candidate in ordered
        ]

    def _structured_score(self, text: str) -> float:
        return document_structure_score(text)

    def _semantic_adjust(self, text: str, decision):
        lowered = normalize_spaces(text).lower()
        hits = 0
        for kw in self.DOCUMENT_KEYWORDS:
            if kw in lowered:
                hits += 1
        for pattern in DOCUMENT_PATTERNS.values():
            if re.search(pattern, lowered, flags=re.UNICODE):
                hits += 1

        metrics = decision.metrics
        document_score = getattr(metrics, "document_score", 0)

        if hits >= 2 and decision.status == "rejected" and document_score >= 10:
            decision.status = "review"

        if hits >= 4 and decision.status == "review" and metrics.confidence and metrics.confidence >= 55:
            decision.status = "approved"

        if document_score == 0 and metrics.confidence is not None and metrics.confidence < 45:
            decision.status = "rejected"

        return decision

    def _region_sort_key(self, item: dict):
        d = item["decision"]
        metrics = d["metrics"]
        status_rank = {"approved": 3, "review": 2, "rejected": 1}[d["status"]]
        conf = item["confidence"] if item["confidence"] is not None else -1
        is_split_card = 1 if str(item.get("region", "")).startswith("card_") else 0
        return (status_rank, is_split_card, metrics.get("structured_hits", 0), metrics.get("document_score", 0.0), metrics.get("score", 0.0), conf)

    def _result_sort_key(self, result: OCRResult):
        status_rank = {"approved": 3, "review": 2, "rejected": 1}[result.status.value]
        structured = result.metrics.get("structured_hits", 0)
        document_score = result.metrics.get("document_score", 0.0)
        conf = result.confidence if result.confidence is not None else -1
        score = result.metrics.get("score", 0.0)
        return (status_rank, structured, document_score, score, conf)

    def _merge_region_texts(self, regions: list[dict]) -> str:
        chunks = []
        seen = set()
        ordered = sorted(regions, key=lambda item: (item["decision"]["metrics"].get("document_score", 0.0), item["decision"]["metrics"].get("structured_hits", 0), item["decision"]["metrics"].get("score", 0.0)), reverse=True)
        for item in ordered:
            text = normalize_spaces(item.get("text", ""))
            if not text:
                continue
            signature = text[:120]
            if signature in seen:
                continue
            seen.add(signature)
            chunks.append(text)
        return "\n\n".join(chunks)

    def _average_confidence(self, candidates: list[dict]) -> float | None:
        values = [c["confidence"] for c in candidates if c["confidence"] is not None]
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    def _run_tesseract(self, frame, psm: int) -> tuple[str, float | None]:
        cfg = f"--oem 3 --psm {psm}"
        pil = Image.fromarray(frame)

        data = pytesseract.image_to_data(
            pil,
            lang=self.lang,
            config=cfg,
            output_type=pytesseract.Output.DICT,
            timeout=12,
        )

        lines: dict[tuple[int, int, int], list[str]] = defaultdict(list)
        confs: list[float] = []
        n = len(data.get("text", []))

        block_nums = data.get("block_num", [0] * n)
        par_nums = data.get("par_num", [0] * n)
        line_nums = data.get("line_num", [0] * n)

        for i in range(n):
            token = (data["text"][i] or "").strip()
            try:
                score = float(data["conf"][i])
            except Exception:
                score = -1.0

            if token:
                key = (block_nums[i], par_nums[i], line_nums[i])
                lines[key].append(token)
            if score >= 0:
                confs.append(score)

        text = "\n".join(" ".join(tokens) for _, tokens in sorted(lines.items())).strip()
        avg_conf = round(sum(confs) / len(confs), 2) if confs else None
        return text, avg_conf

    def _count_pdf_pages(self, path: Path) -> int:
        doc = fitz.open(path)
        count = doc.page_count
        doc.close()
        return count

    def save_artifacts(
        self,
        source_path: str | Path,
        result: OCRResult,
        out_dir: str | Path = "tests/artifacts",
    ):
        src = Path(source_path)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = src.stem.replace(" ", "_")
        txt_file = out_dir / f"{stem}.txt"
        json_file = out_dir / f"{stem}.json"

        txt_file.write_text(result.text or "", encoding="utf-8")
        json_file.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
