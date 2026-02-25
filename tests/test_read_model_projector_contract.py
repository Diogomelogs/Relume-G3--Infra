from datetime import datetime
from relluna.core.document_memory import DocumentMemory, Layer0Custodia, Layer1Artefatos, ArtefatoBruto, MediaType, OriginType
from relluna.services.read_model.projector import project_dm_to_read_model


def _dm_minimo():
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid="doc-1",
            contentfingerprint="hash",
            ingestiontimestamp=datetime.utcnow(),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(id="a1", tipo="raw", uri="file:///tmp/a.pdf")],
        ),
        layer2=None,
        layer3={},
        layer4={
            "date_canonical": "2008-10-22",
            "period_label": "2008-10",
            "tags": ["familia", "viagem"],
            "entities": [{"kind": "pessoa", "label": "mãe"}],
        },
        layer5=None,
        layer6=None,
    )


def test_projector_creates_read_model_minimum():
    dm = _dm_minimo()
    rm = project_dm_to_read_model(dm)

    assert rm.document_id == "doc-1"
    assert rm.media_type == "documento"
    assert rm.title
    assert rm.summary
    assert rm.date_canonical == "2008-10-22"
    assert rm.period_label == "2008-10"
    assert "familia" in rm.tags
    assert any(e.label == "mãe" for e in rm.entities)
    assert rm.search_text  # sempre preenchido


def test_projector_never_invents_date():
    dm = _dm_minimo()
    dm.layer4 = {}  # sem normalização
    rm = project_dm_to_read_model(dm)
    assert rm.date_canonical is None
    assert rm.period_label is None
