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



def _has_media_evidence(dm: DocumentMemory) -> bool:
    """
    Verifica se existe algum sinal mínimo em layer2
    para mídias não-documento (dimensão ou duração).
    """
    if dm.layer2 is None:
        return False


    l2 = dm.layer2
    midia = dm.layer1.midia


    if midia == MediaType.imagem:
        return any(
            [
                getattr(l2, "largura_px", None) is not None,
                getattr(l2, "altura_px", None) is not None,
                getattr(l2, "data_exif", None) is not None,
                getattr(l2, "qualidade_sinal", None) is not None,
            ]
        )


    if midia in (MediaType.audio, MediaType.video):
        return getattr(l2, "duracao_segundos", None) is not None


    return False



def infer_layer3(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer1 is None:
        return dm


    midia = dm.layer1.midia


    # ---------- MÍDIAS NÃO-DOCUMENTO ----------
    # Só cria Layer3 se houver alguma evidência em layer2
    if midia in (MediaType.imagem, MediaType.video, MediaType.audio):
        if not _has_media_evidence(dm):
            return dm


        l3 = Layer3Evidence()
        meta = InferenceMeta(engine=_SOURCE)
        lastro = [EvidenceRef(path="layer1.midia")]


        # Para os testes, basta distinguir imagem/áudio/vídeo; imagem já cobre o contrato.
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


    # ---------- DOCUMENTO ----------
    if not _has_any_evidence_for_document(dm):
        # NÃO criar layer3 quando não há lastro textual
        return dm


    text = _ocr_text(dm)
    inferred = _infer_document_tipo_from_ocr(text, dm)
    if inferred is None:
        return dm


    l3 = Layer3Evidence()
    meta = InferenceMeta(engine=_SOURCE)
    lastro = [EvidenceRef(path="layer2.texto_ocr_literal.valor")]


    l3.tipo_documento = InferredString(
        valor=inferred,
        fonte=_SOURCE,
        metodo=_METHOD,
        estado=ConfidenceState.inferido,
        confianca=0.85,
        lastro=lastro,
        meta=meta,
    )


    l3.tipo_evento = InferredString(
        valor=inferred.value if hasattr(inferred, 'value') else inferred,
        fonte=_SOURCE,
        metodo=_METHOD,
        estado=ConfidenceState.inferido,
        confianca=0.85,
        lastro=lastro,
        meta=meta,
    )


    dm.layer3 = l3
    return dm
