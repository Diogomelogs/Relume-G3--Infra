from datetime import datetime, timezone

from relluna.core.document_memory import (
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    ArtefatoBruto,
    MediaType,
    OriginType,
    Layer2EvidenceBaseModel,
    ProvenancedString,
    ConfidenceState,
)

from relluna.services.context_inference.document_taxonomy.signals import extract_document_signals
from relluna.services.context_inference.document_taxonomy.rules.engine import infer_document_type


def _dm_with_ocr(text: str) -> DocumentMemory:
    return DocumentMemory(
        version="v0.1.0",
        layer0=Layer0Custodia(
            documentid="doc",
            contentfingerprint="3" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="a1",
                    tipo="original",
                    uri="/tmp/x.pdf",
                    metadados_nativos={},
                    logs_ingestao=[],
                )
            ],
        ),
        layer2=Layer2EvidenceBaseModel(
            texto_ocr_literal=ProvenancedString(
                valor=text,
                fonte="ocr",
                metodo="stub",
                estado=ConfidenceState.confirmado,
                confianca=1.0,
            )
        ),
    )


def test_rule_nota_fiscal_wins_over_recibo_when_danfe_present():
    dm = _dm_with_ocr("DANFE Nota Fiscal eletrônica CHAVE DE ACESSO 123 R$ 10,00")
    signals = extract_document_signals(dm)
    res = infer_document_type(signals)

    assert res is not None
    assert res.doc_type.value == "nota_fiscal"
    assert res.confidence >= 0.85
    assert len(res.lastro) >= 1
    assert res.lastro[0].path == "layer2.texto_ocr_literal.valor"


def test_rule_documento_identidade_detects_rg_cpf():
    dm = _dm_with_ocr("Carteira de Identidade RG 12.345.678 CPF 123.456.789-00")
    signals = extract_document_signals(dm)
    res = infer_document_type(signals)

    assert res is not None
    assert res.doc_type.value == "identidade"
    assert len(res.lastro) >= 1


def test_rule_recibo_detects_recibo_keywords():
    dm = _dm_with_ocr("Recibo de pagamento referente à transação X")
    signals = extract_document_signals(dm)
    res = infer_document_type(signals)

    assert res is not None
    assert res.doc_type.value == "recibo"
    assert len(res.lastro) >= 1


def test_no_match_returns_none():
    dm = _dm_with_ocr("Texto genérico sem marcadores claros")
    signals = extract_document_signals(dm)
    res = infer_document_type(signals)

    # Pode retornar None se realmente não casou
    # (este texto tende a não casar; se casar no futuro, ajuste o texto)
    assert res is None
