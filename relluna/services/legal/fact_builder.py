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
        ]:
            fld = fdict.get(field_name)
            if fld and fld.value:
                iso = _to_iso(str(fld.value))
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
                        )
                    )

    facts.sort(key=lambda x: (x.date_iso, x.fact_type))
    return facts