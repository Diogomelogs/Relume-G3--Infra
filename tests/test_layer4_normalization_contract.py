from datetime import datetime, timezone
from relluna.core.document_memory import (
    DocumentMemory,
    ConfidenceState,
    Layer3Evidence,
    Layer4SemanticNormalization,
    ProvenancedDatetime,
    ProvenancedString,
)
from relluna.core.normalization import normalize_to_layer4


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _base_dm():
    return DocumentMemory(
        version="v0.1.0",
        layer0=dict(
            documentid="doc-123",
            contentfingerprint="d" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="test",
        ),
        layer1=None,
        layer2=None,
        layer3=None,
        layer4=None,
        layer5=None,
        layer6=None,
    )


def _layer3_with_temporal(value: str, confidence: float) -> Layer3Evidence:
    return Layer3Evidence(
        estimativa_temporal=ProvenancedDatetime(
            valor=datetime.fromisoformat(value),
            fonte="inferida",
            metodo="regex",
            estado=ConfidenceState.inferido,
            confianca=confidence,
            lastro=[],
        )
    )


# ---------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------

def test_layer4_is_always_created():
    """
    Layer4 deve SEMPRE existir após normalização,
    mesmo sem qualquer evidência ou inferência.
    """
    dm = _base_dm()
    out = normalize_to_layer4(dm)

    assert out.layer4 is not None
    assert isinstance(out.layer4, Layer4SemanticNormalization)


def test_layer4_does_not_invent_date():
    """
    Sem evidência temporal, Layer4 NÃO deve inventar data.
    """
    dm = _base_dm()
    out = normalize_to_layer4(dm)

    assert out.layer4.data_canonica is None


def test_layer4_prefers_layer3_temporal_estimate():
    """
    Quando Layer3 fornece estimativa temporal,
    ela deve ser promovida para Layer4 como data canônica.
    """
    dm = _base_dm()
    dm.layer3 = _layer3_with_temporal("2001-05-20", 0.85)

    out = normalize_to_layer4(dm)

    assert out.layer4.data_canonica is not None
    assert isinstance(out.layer4.data_canonica, datetime)
    assert out.layer4.data_canonica.year == 2001


def test_layer4_generates_period_label():
    """
    A partir de uma data canônica, Layer4 deve gerar
    um rótulo temporal humano (ex: ano, década).
    """
    dm = _base_dm()
    dm.layer3 = _layer3_with_temporal("1994-08-01", 0.9)

    out = normalize_to_layer4(dm)

    assert out.layer4.periodo is not None
    assert isinstance(out.layer4.periodo, str)
    assert "1994" in out.layer4.periodo


def test_layer4_entities_are_propagated_not_created():
    """
    Layer4 não cria entidades novas.
    Ela apenas consolida ou propaga informações existentes.
    """
    dm = _base_dm()
    dm.layer3 = Layer3Evidence(
        tipo_evento=ProvenancedString(
            valor="documento_identidade",
            fonte="inferida",
            metodo="rules",
            estado=ConfidenceState.inferido,
            confianca=0.9,
            lastro=[],
        )
    )

    out = normalize_to_layer4(dm)

    assert isinstance(out.layer4.entidades, list)


def test_layer4_tags_always_exist():
    """
    Tags devem sempre existir (lista vazia é aceitável).
    O front nunca deve lidar com None.
    """
    dm = _base_dm()
    out = normalize_to_layer4(dm)

    assert out.layer4.tags is not None
    assert isinstance(out.layer4.tags, list)


def test_layer4_does_not_mutate_previous_layers():
    """
    Layer4 NÃO pode modificar Layer0–3.
    """
    dm = _base_dm()
    dm.layer3 = _layer3_with_temporal("2010-01-01", 0.8)

    snapshot = dm.model_dump()
    out = normalize_to_layer4(dm)
    out_dump = out.model_dump()

    for layer in ["layer0", "layer1", "layer2", "layer3"]:
        assert out_dump[layer] == snapshot[layer]


def test_layer4_contract_is_strict():
    """
    Layer4 deve rejeitar campos fora do contrato canônico.
    Isso garante evolução controlada do schema.
    """
    dm = _base_dm()
    out = normalize_to_layer4(dm)

    data = out.layer4.model_dump()
    allowed_keys = {"data_canonica", "periodo", "local_canonico", "entidades", "tags", "relacoes_temporais"}

    assert set(data.keys()) == allowed_keys
