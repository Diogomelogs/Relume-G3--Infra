from __future__ import annotations

import json

from relluna.core.document_memory.layer2 import Layer2Evidence
from relluna.core.document_memory.layer3 import Layer3Evidence
from relluna.core.document_memory.types_basic import ProvenancedString, ConfidenceState


def test_layer2_page_evidence_is_factual_only():
    l2 = Layer2Evidence()
    l2.sinais_documentais["page_evidence_v1"] = ProvenancedString(
        valor=json.dumps([
            {
                "page": 1,
                "date_candidates": [{"value": "01/02/2024", "source_label": "generic_date"}],
                "anchors": [],
            }
        ]),
        fonte="test",
        metodo="unit",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    payload = json.loads(l2.sinais_documentais["page_evidence_v1"].valor)
    assert "doc_subtype" not in payload[0]
    assert "dates" not in payload[0]
    assert "date_candidates" in payload[0]


def test_layer3_supports_contextual_classification_fields():
    l3 = Layer3Evidence()
    l3.tipo_documento = ProvenancedString(valor="laudo_medico", fonte="rules", metodo="taxonomy_rules", estado=ConfidenceState.inferido, confianca=0.9)
    l3.tipo_evento = ProvenancedString(valor="atendimento", fonte="rules", metodo="taxonomy_rules", estado=ConfidenceState.inferido, confianca=0.8)
    l3.transcricao_contextual = ProvenancedString(valor="fala reconhecida", fonte="asr.whisper", metodo="whisper", estado=ConfidenceState.inferido)
    assert l3.tipo_documento.valor == "laudo_medico"
    assert l3.transcricao_contextual.valor == "fala reconhecida"
