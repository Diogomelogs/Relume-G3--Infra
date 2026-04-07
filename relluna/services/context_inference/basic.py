from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple

from relluna.services.context_inference.document_taxonomy.signals import extract_document_signals
from relluna.services.context_inference.document_taxonomy.rules.engine import infer_document_type

from relluna.core.document_memory import DocumentMemory, MediaType
from relluna.core.document_memory.layer3 import (
    Layer3Evidence,
    PageContextClassification,
    ProbatoryEvent,
    SemanticEntity,
)
from relluna.core.document_memory.types_basic import (
    ConfidenceState,
    EvidenceRef,
    InferredString,
    InferenceMeta,
)

_SOURCE = "rules"
_METHOD = "taxonomy_rules_v3"
_BUILDER_VERSION = "probatory_event_builder_v7"

_CANONICAL_PRIORITY_TYPES = {
    "atestado_medico": 0.97,
    "parecer_medico": 0.96,
    "laudo_medico": 0.93,
    "receituario": 0.92,
    "documento_composto": 0.90,
    "prontuario": 0.90,
    "relatorio_medico": 0.89,
    "recibo": 0.82,
}

_HARD_NON_PERSON = {
    "uso oral continuo",
    "uso oral contínuo",
    "medicamentos ou substâncias",
    "medicamentos ou substancias",
    "estado de sao paulo",
    "estado de são paulo",
    "identificação do comprador",
    "identificacao do comprador",
    "identificação do fornecedor",
    "identificacao do fornecedor",
}


def _ocr_text(dm: DocumentMemory) -> str:
    if dm.layer2 is None:
        return ""
    o = getattr(dm.layer2, "texto_ocr_literal", None)
    if o is None:
        return ""
    if isinstance(o, str):
        return o
    if isinstance(o, dict):
        return str(o.get("valor") or "")
    return str(getattr(o, "valor", "") or "")


def _load_signal_json(dm: DocumentMemory, key: str) -> Any:
    if dm.layer2 is None:
        return None
    sig = dm.layer2.sinais_documentais.get(key)
    if not sig or not getattr(sig, "valor", None):
        return None
    try:
        return json.loads(sig.valor)
    except Exception:
        return None


def _canonical(dm: DocumentMemory) -> Dict[str, Any]:
    data = _load_signal_json(dm, "entities_canonical_v1")
    return data if isinstance(data, dict) else {}


def _page_evidence(dm: DocumentMemory) -> List[Dict[str, Any]]:
    data = _load_signal_json(dm, "page_evidence_v1") or []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _trim_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip(" -:|,.;")
    cleaned = re.sub(
        r"(?i)\s+\b(nascimento|sexo|rghc|rg|cpf|idade|data|hora|prontu[aá]rio|conv[eê]nio|plano|prestador|servi[cç]o|especialidade)\b.*$",
        "",
        cleaned,
    ).strip()
    return cleaned or None


def _looks_like_person(value: Optional[str]) -> bool:
    value = _trim_name(value)
    if not value:
        return False
    low = value.lower()
    if any(x in low for x in _HARD_NON_PERSON):
        return False
    if re.search(
        r"\b(?:medicamentos?|subst[âa]ncias?|emitente|fornecedor|comprador|identifica[cç][aã]o|estado)\b",
        low,
    ):
        return False
    if len(value.split()) < 2:
        return False
    if len(value.split()) > 8:
        return False
    if re.search(r"\d", value):
        return False
    return True


def _page_rank(page_item: Dict[str, Any]) -> int:
    taxonomy = ((page_item.get("page_taxonomy") or {}).get("value") or "").lower()
    if taxonomy in {"atestado_medico", "parecer_medico", "laudo_medico", "documento_medico"}:
        return 0
    if taxonomy in {"documento_composto"}:
        return 1
    if taxonomy in {"formulario_administrativo"}:
        return 3
    return 2


def _best_candidate_from_pages(dm: DocumentMemory, field: str) -> Optional[str]:
    items = _page_evidence(dm)
    candidates: List[Tuple[float, str]] = []

    for item in items:
        people = item.get("people") or {}
        raw = people.get(field)
        value = _trim_name(raw)
        if not _looks_like_person(value):
            continue

        conf_key = field.replace("_name", "_confidence")
        conf = float(people.get(conf_key) or 0.0)
        score = conf - (_page_rank(item) * 0.03)
        if field == "provider_name":
            admin = item.get("administrative_entities") or {}
            if admin.get("crm"):
                score += 0.05

        candidates.append((score, value))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _infer_document_tipo_from_ocr(text: str, dm: DocumentMemory) -> Optional[Tuple[str, float]]:
    canonical = _canonical(dm)
    canonical_doc_type = canonical.get("document_type")

    # Prioridade forte do canônico consolidado
    if canonical_doc_type in _CANONICAL_PRIORITY_TYPES:
        return canonical_doc_type, _CANONICAL_PRIORITY_TYPES[canonical_doc_type]

    upper_text = (text or "").upper()

    if "ATESTADO" in upper_text and ("CID" in upper_text or "CRM" in upper_text):
        return "atestado_medico", 0.97
    if "PARECER" in upper_text and "CRM" in upper_text:
        return "parecer_medico", 0.95
    if "RECEITU" in upper_text and "CRM" in upper_text:
        return "receituario", 0.92
    if "LAUDO" in upper_text and ("CRM" in upper_text or "EXAME" in upper_text):
        return "laudo_medico", 0.90

    signals = extract_document_signals(dm)
    signals.ocr_text = text
    signals.has_text = bool(text)

    result = infer_document_type(signals)
    if result:
        # Evitar regressão para identidade quando já existe forte semântica documental.
        if result.doc_type.value == "identidade" and canonical_doc_type in {
            "documento_composto",
            "receituario",
            "laudo_medico",
            "prontuario",
            "relatorio_medico",
        }:
            return canonical_doc_type, 0.88
        return result.doc_type.value, result.confidence

    if "RECEITU" in upper_text:
        return "receituario", 0.90
    if "RECIBO" in upper_text:
        return "recibo", 0.75

    return None


def _semantic_entities_from_text(text: str) -> List[SemanticEntity]:
    entidades: List[SemanticEntity] = []

    def _add(tipo: str, valor: str):
        entidades.append(
            SemanticEntity(
                tipo=tipo,
                valor=valor,
                score=0.9,
                lastro=[EvidenceRef(source_path="layer2.texto_ocr_literal.valor")],
                meta=InferenceMeta(engine="regex"),
            )
        )

    for m in re.findall(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", text):
        _add("cpf", m)
    for m in re.findall(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", text):
        _add("cnpj", m)
    for m in re.findall(r"R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}", text):
        _add("valor_monetario", m)
    for m in re.findall(r"\b[A-Z]\d{2}(?:\.\d)?\b", text):
        _add("cid", m)
    for m in re.findall(r"CRM\s*[-:]?\s*\d+\s*[A-Z]{0,2}", text, flags=re.IGNORECASE):
        _add("crm", m.strip())

    return entidades


def _extract_patient_name(dm: DocumentMemory) -> Optional[str]:
    canonical = _canonical(dm)
    name = _trim_name((canonical.get("patient") or {}).get("name"))
    if _looks_like_person(name):
        return name
    return _best_candidate_from_pages(dm, "patient_name")


def _extract_provider_name(dm: DocumentMemory) -> Optional[str]:
    canonical = _canonical(dm)
    name = _trim_name((canonical.get("provider") or {}).get("name"))
    if _looks_like_person(name):
        return name
    return _best_candidate_from_pages(dm, "provider_name")


def _extract_mother_name(dm: DocumentMemory) -> Optional[str]:
    canonical = _canonical(dm)
    name = _trim_name((canonical.get("mother") or {}).get("name"))
    if _looks_like_person(name):
        return name
    return _best_candidate_from_pages(dm, "mother_name")


def _extract_hard_entities(dm: DocumentMemory) -> Dict[str, Any]:
    items = _load_signal_json(dm, "hard_entities_v2") or []
    result: Dict[str, Any] = {
        "cids": [],
        "crms": [],
        "cpfs": [],
        "cnpjs": [],
        "monetary_values": [],
    }
    if not isinstance(items, list):
        return result

    for item in items:
        t = item.get("type")
        if t == "cid":
            result["cids"].append(item.get("value"))
        elif t == "crm":
            crm_str = item.get("value", "")
            uf = item.get("uf") or ""
            result["crms"].append(f"CRM {crm_str} {uf}".strip())
        elif t == "cpf":
            result["cpfs"].append(item.get("value"))
        elif t == "cnpj":
            result["cnpjs"].append(item.get("value"))
        elif t == "valor_monetario":
            result["monetary_values"].append(item.get("value_literal"))

    for k in result:
        result[k] = list(dict.fromkeys(v for v in result[k] if v))
    return result


def _extract_primary_cids(l3: Layer3Evidence, dm: DocumentMemory) -> List[str]:
    canonical = _canonical(dm)
    canonical_cids = [
        item.get("code")
        for item in ((canonical.get("clinical") or {}).get("cids") or [])
        if isinstance(item, dict) and item.get("code")
    ]
    if canonical_cids:
        return canonical_cids
    return [
        e.valor
        for e in (l3.entidades_semanticas or [])
        if getattr(e, "tipo", None) == "cid"
    ]


def _extract_signal_zones_for_page(page_evidence: List[dict], page_no: Optional[int]) -> List[dict]:
    for item in page_evidence:
        if item.get("page") == page_no:
            return [
                z
                for z in (item.get("signal_zones") or [])
                if z.get("signal_zone") == "core_probative"
            ]
    return []


def _confidence_for_event(
    event_type: str,
    doc_tipo: Optional[str],
    has_bbox: bool,
    has_patient: bool,
    has_cids: bool,
    seed_confidence: Optional[float],
) -> float:
    base = seed_confidence or 0.70

    if event_type in {
        "internacao_inicio",
        "internacao_fim",
        "afastamento_inicio",
        "afastamento_fim_estimado",
    }:
        base = max(base, 0.92)
    elif doc_tipo in {
        "parecer_medico",
        "atestado_medico",
        "receituario",
        "laudo_medico",
        "documento_composto",
    }:
        base = max(base, 0.84)
    elif doc_tipo:
        base = max(base, 0.76)

    if has_bbox:
        base = min(base + 0.03, 1.0)
    if has_patient:
        base = min(base + 0.02, 1.0)
    if has_cids and event_type != "birth_date":
        base = min(base + 0.02, 1.0)

    return round(base, 3)


def _review_state(confidence: float) -> str:
    if confidence >= 0.95:
        return "auto_confirmed"
    if confidence >= 0.80:
        return "review_recommended"
    return "needs_review"


_DOC_LABELS: Dict[str, str] = {
    "parecer_medico": "Parecer médico",
    "atestado_medico": "Atestado médico",
    "receituario": "Receituário",
    "laudo_medico": "Laudo médico",
    "prontuario": "Prontuário",
    "relatorio_medico": "Relatório médico",
    "documento_composto": "Documento composto",
    "recibo": "Recibo",
    "birth_date": "Data de nascimento",
    "internacao_inicio": "Início da internação",
    "internacao_fim": "Fim da internação",
    "afastamento_inicio": "Início do afastamento",
    "afastamento_fim_estimado": "Fim estimado do afastamento",
    "document_issue_date": "Data de emissão",
    "parecer_emitido": "Emissão de parecer médico",
    "encaminhamento_clinico": "Encaminhamento clínico",
    "registro_condicao_clinica": "Registro de condição clínica",
}


def _best_provenance_from_citations(citations: List[EvidenceRef]) -> str:
    for c in citations:
        if getattr(c, "bbox", None):
            return "exact"
    for c in citations:
        if getattr(c, "provenance_status", None) == "exact":
            return "exact"
    for c in citations:
        if getattr(c, "snippet", None):
            return "snippet_only"
    return "missing"


def _best_review_state_from_citations(citations: List[EvidenceRef], fallback: str) -> str:
    if any(getattr(c, "bbox", None) for c in citations):
        return "auto_confirmed"
    if any(getattr(c, "provenance_status", None) == "exact" for c in citations):
        return "auto_confirmed"
    return fallback


def _event_title(event_type: Optional[str], provider_name: Optional[str], cids: List[str]) -> str:
    label = _DOC_LABELS.get(event_type or "", (event_type or "Evento").replace("_", " ").capitalize())
    if provider_name and event_type not in {"birth_date"}:
        return f"{label} — {provider_name}"
    if cids:
        return f"{label} ({', '.join(cids[:2])})"
    return label


def _event_description(
    event_type: Optional[str],
    patient_name: Optional[str],
    provider_name: Optional[str],
    cids: List[str],
    date_iso: Optional[str],
    snippet: Optional[str],
) -> str:
    parts: List[str] = []
    parts.append(_DOC_LABELS.get(event_type or "", "Evento documental"))
    if date_iso:
        parts.append(f"em {date_iso}")
    if patient_name:
        parts.append(f"referente a {patient_name}")
    if provider_name and event_type not in {"birth_date"}:
        parts.append(f"por {provider_name}")
    if cids and event_type not in {"birth_date"}:
        parts.append(f"CIDs: {', '.join(cids[:3])}")
    if snippet:
        parts.append(f'Evidência: "{snippet[:160]}"')
    return " | ".join(parts)


def _event_type_from_seed(seed: Dict[str, Any]) -> Optional[str]:
    event_hint = seed.get("event_hint")
    if event_hint:
        return event_hint

    snippet = (seed.get("snippet") or "").lower()
    literal = str(seed.get("date_literal") or "")
    kind = str(seed.get("date_kind") or "").lower()

    if "nascto" in snippet or "nascimento" in snippet:
        return "birth_date"
    if "internado" in snippet and "do dia" in snippet and literal:
        return "internacao_inicio"
    if "ao dia" in snippet and literal:
        return "internacao_fim"
    if "a partir desta data" in snippet:
        return "afastamento_inicio"
    if "afastado" in snippet and "dia(s)" in snippet:
        return "afastamento_fim_estimado"
    if "sao paulo," in snippet or "são paulo," in snippet:
        return "document_issue_date"
    if kind == "textual_pt":
        return "document_issue_date"

    return None


def _event_entities_from_seed(seed: Dict[str, Any], canonical: Dict[str, Any], hard: Dict[str, Any]) -> Dict[str, Any]:
    patient = _trim_name((canonical.get("patient") or {}).get("name"))
    provider = _trim_name((canonical.get("provider") or {}).get("name"))
    mother = _trim_name((canonical.get("mother") or {}).get("name"))

    canonical_cids = [
        item.get("code")
        for item in ((canonical.get("clinical") or {}).get("cids") or [])
        if isinstance(item, dict) and item.get("code")
    ]
    canonical_crm = ((canonical.get("provider") or {}).get("crm") or {}).get("display")

    entities = {
        "patient": patient if _looks_like_person(patient) else None,
        "mother": mother if _looks_like_person(mother) else None,
        "provider": provider if _looks_like_person(provider) else None,
        "cids": list(dict.fromkeys([c for c in (seed.get("cids") or canonical_cids or hard.get("cids") or []) if c])),
        "crms": list(dict.fromkeys([c for c in ([canonical_crm] if canonical_crm else []) + (hard.get("crms") or []) if c])),
        "cpfs": hard.get("cpfs") or [],
        "cnpjs": hard.get("cnpjs") or [],
    }
    if seed.get("duration_days") is not None:
        entities["duration_days"] = seed.get("duration_days")
    return entities


def _build_probatory_events(dm: DocumentMemory, l3: Layer3Evidence) -> List[ProbatoryEvent]:
    seeds = _load_signal_json(dm, "timeline_seed_v2") or []
    if not isinstance(seeds, list) or not seeds:
        return []

    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    hard = _extract_hard_entities(dm)
    canonical = _canonical(dm)

    patient_name = _extract_patient_name(dm)
    provider_name = _extract_provider_name(dm)
    default_doc_tipo = canonical.get("document_type") or getattr(
        getattr(l3, "tipo_documento", None), "valor", None
    )
    base_cids = _extract_primary_cids(l3, dm)
    document_id = dm.layer0.documentid if dm.layer0 else None

    events: List[ProbatoryEvent] = []

    for seed in seeds:
        if not seed.get("include_in_timeline", False):
            continue

        date_iso = seed.get("date_iso")
        if not date_iso:
            continue

        event_type = _event_type_from_seed(seed)
        if not event_type or event_type in {"birth_date", "document_date_candidate"}:
            continue

        page = seed.get("page")
        bbox = seed.get("bbox")
        snippet = seed.get("snippet")
        seed_id = seed.get("seed_id")
        seed_confidence = seed.get("confidence")
        source_path = seed.get(
            "source_path", "layer2.sinais_documentais.timeline_seed_v2"
        )

        core_zones = _extract_signal_zones_for_page(page_evidence, page)
        doc_tipo = seed.get("document_type") or default_doc_tipo

        entities = _event_entities_from_seed(seed, canonical, hard)
        cids = entities.get("cids") or base_cids

        confidence = _confidence_for_event(
            event_type=event_type,
            doc_tipo=doc_tipo,
            has_bbox=bool(bbox),
            has_patient=bool(patient_name),
            has_cids=bool(cids),
            seed_confidence=seed_confidence,
        )
        review_state = _review_state(confidence)

        basis = f"{event_type}|{date_iso}|{page}|{document_id}|{seed_id}"
        event_id = sha256(basis.encode("utf-8")).hexdigest()[:20]

        citations: List[EvidenceRef] = [
            EvidenceRef(
                source_path=source_path,
                page=page,
                bbox=bbox,
                snippet=snippet,
                confidence=seed_confidence,
                provenance_status=seed.get("provenance_status"),
                review_state=seed.get("review_state"),
                note=f"seed_id:{seed_id}" if seed_id else None,
            )
        ]

        for zone in core_zones[:2]:
            citations.append(
                EvidenceRef(
                    source_path="layer2.sinais_documentais.page_evidence_v1",
                    page=zone.get("page"),
                    bbox=zone.get("bbox"),
                    snippet=zone.get("snippet"),
                    confidence=zone.get("confidence"),
                    provenance_status=zone.get("provenance_status"),
                    review_state=zone.get("review_state"),
                    note=f"signal_zone:core_probative|label:{zone.get('label')}",
                )
            )

        event_provenance = _best_provenance_from_citations(citations)
        event_review_state = _best_review_state_from_citations(
            citations, review_state
        )
        event_confidence = (
            confidence if event_provenance != "exact" else max(confidence, 0.95)
        )

        tipo_legado = InferredString(
            valor=event_type,
            fonte=_SOURCE,
            metodo=_BUILDER_VERSION,
            estado=ConfidenceState.inferido,
            confianca=event_confidence,
            lastro=citations[:1],
            meta=InferenceMeta(engine=_SOURCE),
        )

        events.append(
            ProbatoryEvent(
                event_id=event_id,
                event_type=event_type,
                title=_event_title(event_type, provider_name, cids),
                description=_event_description(
                    event_type=event_type,
                    patient_name=patient_name,
                    provider_name=provider_name,
                    cids=cids,
                    date_iso=date_iso,
                    snippet=snippet,
                ),
                date_iso=date_iso,
                entities=entities,
                citations=citations,
                confidence=event_confidence,
                review_state=event_review_state,
                provenance_status=event_provenance,
                derivation_rule=_BUILDER_VERSION,
                tipo_evento=tipo_legado,
                descricao_curta=_event_description(
                    event_type=event_type,
                    patient_name=patient_name,
                    provider_name=provider_name,
                    cids=cids,
                    date_iso=date_iso,
                    snippet=snippet,
                ),
                evidencias_origem=citations,
                justificativa=(
                    "Evento derivado de timeline_seed_v2 com precedência de "
                    "entities_canonical_v1, seleção de signal_zone e "
                    "projeção controlada de entidades."
                ),
                confianca=event_confidence,
                meta=InferenceMeta(engine=_SOURCE),
            )
        )

    return events


_PAGE_LABEL_MAP = {
    "RECEITU": ("pagina_receituario", 0.85),
    "ATESTADO": ("pagina_atestado", 0.85),
    "LAUDO": ("pagina_laudo", 0.80),
    "PARECER": ("pagina_parecer", 0.82),
    "PRONTUARIO": ("pagina_prontuario", 0.78),
    "RELATORIO": ("pagina_relatorio", 0.75),
}


def _classify_page(snippet_blob: str) -> Tuple[str, float]:
    upper = snippet_blob.upper()
    for keyword, (label, conf) in _PAGE_LABEL_MAP.items():
        if keyword in upper:
            return label, conf
    return "pagina_documental", 0.60


def _canonical_tipo_lastro(dm: DocumentMemory, valor: str, confianca: float) -> InferredString:
    return InferredString(
        valor=valor,
        fonte=_SOURCE,
        metodo=_METHOD,
        estado=ConfidenceState.inferido,
        confianca=confianca,
        lastro=[EvidenceRef(source_path="layer2.sinais_documentais.entities_canonical_v1")],
        meta=InferenceMeta(engine=_SOURCE),
    )


def infer_layer3(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer1 is None:
        return dm

    if dm.layer3 is None:
        dm.layer3 = Layer3Evidence()

    midia = dm.layer1.midia

    if midia in (MediaType.imagem, MediaType.video, MediaType.audio):
        if dm.layer2 is None:
            return dm

        l2 = dm.layer2
        if midia == MediaType.imagem:
            has_signal = any(
                [
                    getattr(l2, "largura_px", None) is not None,
                    getattr(l2, "altura_px", None) is not None,
                    getattr(l2, "data_exif", None) is not None,
                ]
            )
        else:
            has_signal = getattr(l2, "duracao_segundos", None) is not None

        if not has_signal:
            return dm

        dm.layer3.tipo_evento = InferredString(
            valor=midia.value,
            fonte=_SOURCE,
            metodo=_METHOD,
            estado=ConfidenceState.inferido,
            confianca=0.9,
            lastro=[EvidenceRef(source_path="layer1.midia")],
            meta=InferenceMeta(engine=_SOURCE),
        )
        if "media_kind_to_tipo_evento" not in dm.layer3.regras_aplicadas:
            dm.layer3.regras_aplicadas.append("media_kind_to_tipo_evento")
        return dm

    text = _ocr_text(dm)
    if not text.strip():
        return dm

    canonical = _canonical(dm)
    canonical_doc_type = canonical.get("document_type")

    doc_tipo_result = _infer_document_tipo_from_ocr(text, dm)
    if doc_tipo_result:
        valor, confidence = doc_tipo_result

        # trava anti-regressão: se o canônico já consolidou tipo documental forte,
        # não aceitar "identidade" sem sinal muito forte.
        if (
            valor == "identidade"
            and canonical_doc_type in {
                "documento_composto",
                "receituario",
                "laudo_medico",
                "prontuario",
                "relatorio_medico",
                "atestado_medico",
                "parecer_medico",
            }
        ):
            valor = canonical_doc_type
            confidence = max(float(confidence or 0.0), 0.88)

        inferred = _canonical_tipo_lastro(dm, valor, confidence)
        dm.layer3.tipo_documento = inferred
        dm.layer3.tipo_evento = inferred
        if "document_taxonomy_rules_v3" not in dm.layer3.regras_aplicadas:
            dm.layer3.regras_aplicadas.append("document_taxonomy_rules_v3")

    entidades = _semantic_entities_from_text(text)
    if entidades:
        dm.layer3.entidades_semanticas = entidades
        if "regex_semantic_entities" not in dm.layer3.regras_aplicadas:
            dm.layer3.regras_aplicadas.append("regex_semantic_entities")

    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    if isinstance(page_evidence, list):
        page_classes: List[PageContextClassification] = []
        for item in page_evidence:
            page = item.get("page")
            if not isinstance(page, int):
                continue

            signal_zones = item.get("signal_zones") or []
            anchors = item.get("anchors") or []

            core_snippets = " ".join(
                str(z.get("snippet") or "")
                for z in signal_zones
                if z.get("signal_zone") == "core_probative"
            )
            anchor_snippets = " ".join(str(a.get("snippet") or "") for a in anchors)
            snippet_blob = core_snippets or anchor_snippets or str(
                item.get("page_text") or ""
            )

            label, conf = _classify_page(snippet_blob)
            if core_snippets:
                conf = min(conf + 0.05, 1.0)

            page_classes.append(
                PageContextClassification(
                    pagina=page,
                    classificacao=label,
                    confianca=conf,
                    taxonomy_source="page_evidence_v1+signal_zones",
                    taxonomy_confidence=conf,
                    evidencias_origem=[
                        EvidenceRef(
                            source_path="layer2.sinais_documentais.page_evidence_v1",
                            page=page,
                            confidence=conf,
                        )
                    ],
                    meta=InferenceMeta(engine=_SOURCE),
                )
            )

        if page_classes:
            dm.layer3.classificacoes_pagina = page_classes
            if "page_context_rules_v2" not in dm.layer3.regras_aplicadas:
                dm.layer3.regras_aplicadas.append("page_context_rules_v2")

    events = _build_probatory_events(dm, dm.layer3)
    if events:
        dm.layer3.eventos_probatorios = events
        if _BUILDER_VERSION not in dm.layer3.regras_aplicadas:
            dm.layer3.regras_aplicadas.append(_BUILDER_VERSION)

    return dm