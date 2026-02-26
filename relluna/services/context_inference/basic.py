# relluna/services/context_inference/basic.py


from __future__ import annotations


from typing import Optional
from relluna.services.context_inference.document_taxonomy.signals import extract_document_signals
from relluna.services.context_inference.document_taxonomy.rules.engine import infer_document_type



from relluna.core.document_memory import DocumentMemory, MediaType
from relluna.core.document_memory.layer3 import Layer3Evidence
from relluna.core.document_memory.types_basic import (
    ConfidenceState,
    EvidenceRef,
    InferredString,
    InferenceMeta,
)


_SOURCE = "rules"
_METHOD = "taxonomy_rules"



def _ocr_text(dm: DocumentMemory) -> str:
    """
    Retorna OCR literal (string) se existir, senão "".
    Pode vir como ProvenancedString, dict ou str.
    """
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



def _has_any_evidence_for_document(dm: DocumentMemory) -> bool:
    """
    Para documentos: só inferir se houver evidência (ex.: OCR não-vazio).
    """
    return bool(_ocr_text(dm).strip())



def _infer_document_tipo_from_ocr(text: str, dm: DocumentMemory) -> Optional[str]:
    """
    Usa o engine de taxonomia para inferir tipo do documento a partir de signals.
    Fallback para regra simples se o engine não retornar resultado.
    """
    signals = extract_document_signals(dm)
    
    # Garante que o OCR atual seja usado
    signals.ocr_text = text
    signals.has_text = bool(text)
    
    # Usa o engine de regras (ReciboRule, DocumentoIdentidadeRule, NotaFiscalRule, etc)
    result = infer_document_type(signals)
    if result:
        return result.doc_type.value
    
    # Fallback para compatibilidade com testes existentes
    if "recibo" in text.lower():
        return "recibo"
    return None

def infer_layer3(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer1 is None:
        return dm

    midia = dm.layer1.midia

    # =====================================================
    # -------- NÃO DOCUMENTO (imagem / áudio / vídeo) ----
    # =====================================================
    if midia in (MediaType.imagem, MediaType.video, MediaType.audio):
        if dm.layer2 is None:
            return dm

        l2 = dm.layer2
        has_signal = False

        if midia == MediaType.imagem:
            has_signal = any([
                getattr(l2, "largura_px", None) is not None,
                getattr(l2, "altura_px", None) is not None,
                getattr(l2, "data_exif", None) is not None,
            ])

        elif midia in (MediaType.audio, MediaType.video):
            has_signal = getattr(l2, "duracao_segundos", None) is not None

        if not has_signal:
            return dm

        l3 = Layer3Evidence()
        meta = InferenceMeta(engine=_SOURCE)
        lastro = [EvidenceRef(path="layer1.midia")]

        l3.tipo_evento = InferredString(
            valor=midia.value,
            fonte=_SOURCE,
            metodo=_METHOD,
            estado=ConfidenceState.inferido,
            confianca=0.9,
            lastro=lastro,
            meta=meta,
        )

        dm.layer3 = l3
        return dm

    # =====================================================
    # ------------------- DOCUMENTO -----------------------
    # =====================================================

    text = _ocr_text(dm)
    if not text or not text.strip():
        return dm

    signals = extract_document_signals(dm)
    signals.ocr_text = text
    signals.has_text = True

    result = infer_document_type(signals)

    # ---------- Fallback médico estruturado ----------
    if result is None:
        upper_text = text.upper()

        if "PARECER" in upper_text and "CID:" in upper_text:
            inferred_valor = "parecer_medico"
            confidence = 0.95
        else:
            return dm
    else:
        inferred = result.doc_type
        inferred_valor = inferred.value if hasattr(inferred, "value") else str(inferred)
        confidence = result.confidence

    l3 = Layer3Evidence()
    meta = InferenceMeta(engine=_SOURCE)
    lastro = [EvidenceRef(path="layer2.texto_ocr_literal.valor")]

    l3.tipo_documento = InferredString(
        valor=inferred_valor,
        fonte=_SOURCE,
        metodo=_METHOD,
        estado=ConfidenceState.inferido,
        confianca=confidence,
        lastro=lastro,
        meta=meta,
    )

    l3.tipo_evento = InferredString(
        valor=inferred_valor,
        fonte=_SOURCE,
        metodo=_METHOD,
        estado=ConfidenceState.inferido,
        confianca=confidence,
        lastro=lastro,
        meta=meta,
    )

    # =====================================================
    # ------------- REGEX ENTIDADES TRANSVERSAL ----------
    # =====================================================

    import re
    from relluna.core.document_memory.types_basic import SemanticEntity

    entidades: list[SemanticEntity] = []

    def _add(tipo, valor):
        entidades.append(
            SemanticEntity(
                tipo=tipo,
                valor=valor,
                fonte="regex",
                confianca=0.9,
            )
        )

    # CPF
    for m in re.findall(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", text):
        _add("cpf", m)

    # CNPJ
    for m in re.findall(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", text):
        _add("cnpj", m)

    # Valor monetário
    for m in re.findall(r"R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}", text):
        _add("valor_monetario", m)

    # Datas simples
    for m in re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text):
        _add("data_textual", m)

    # CID médico
    for m in re.findall(r"\b[A-Z]\d{2}\.\d\b", text):
        _add("cid", m)

    # CRM
    for m in re.findall(r"CRM\s*\d+\s*[A-Z]{2}", text):
        _add("crm", m)

    if entidades:
        l3.entidades_semanticas = entidades

    dm.layer3 = l3
    return dm