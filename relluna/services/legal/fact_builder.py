from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from relluna.domain.legal_fields import CanonicalExtraction, TimelineFact


def _to_iso(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception:
        return None


def build_facts(extractions: List[CanonicalExtraction]) -> List[TimelineFact]:
    facts: List[TimelineFact] = []

    for ext in extractions:
        fdict = {f.name: f for f in ext.fields}

        for field_name, fact_type in [
            ("Data_Nascimento", "data_nascimento"),
            ("Data_Admissao", "data_admissao"),
            ("Data_Demissao", "data_demissao"),
            ("DIB", "dib_beneficio"),
            ("DCB", "dcb_beneficio"),
            ("Data_Documento", "data_documento_medico"),
            ("Data_ASO", "data_aso"),
            ("Data_Entrega_EPI", "data_entrega_epi"),
            ("Internacao_Inicio", "internacao_inicio"),
            ("Internacao_Fim", "internacao_fim"),
            ("Afastamento_Inicio", "afastamento_inicio"),
            ("Afastamento_Fim_Estimado", "afastamento_fim_estimado"),
        ]:
            fld = fdict.get(field_name)
            if fld and fld.value:
                raw_value = fld.normalized_value or fld.value
                iso = _to_iso(str(raw_value)) or (str(raw_value) if isinstance(raw_value, str) and len(str(raw_value)) == 10 and str(raw_value)[4] == "-" else None)
                if iso:
                    facts.append(
                        TimelineFact(
                            fact_type=fact_type,
                            date_iso=iso,
                            value=fld.value,
                            document_id=ext.document_id,
                            doc_type=ext.doc_type,
                            anchor=fld.anchor,
                            metadata={"field_name": field_name},
                            confidence=fld.confidence,
                            assertion_level=fld.assertion_level,
                            provenance_status=fld.provenance_status,
                            review_state=fld.review_state,
                            source_signal=fld.source_signal,
                            source_path=fld.source_path,
                        )
                    )

    facts.sort(key=lambda x: (x.date_iso, x.fact_type))
    return facts
