from relluna.services.read_model.text_search import search_read_models_text


def test_search_read_models_text_finds_match():
    rms = [
        {"documentid": "a", "texto": "Pagamento de aluguel janeiro 2024", "tags": ["recibo"]},
        {"documentid": "b", "texto": "Foto de paisagem", "tags": ["imagem"]},
    ]

    hits = search_read_models_text(rms, "aluguel janeiro", limit=10)
    assert len(hits) >= 1
    assert hits[0].documentid == "a"
    assert hits[0].score > 0.0


def test_search_read_models_text_matches_patient_cid_and_event_type():
    rms = [
        {
            "document_id": "doc-clinico",
            "title": "Parecer médico",
            "patient": "MARIA SILVA",
            "provider": "DRA ANA LIMA",
            "cids": ["M54.5"],
            "event_types": ["parecer_emitido"],
            "summary": "Documento médico com CID e parecer.",
        },
        {
            "document_id": "doc-outro",
            "title": "Recibo",
            "patient": "JOAO",
            "cids": ["Z00.0"],
            "event_types": ["pagamento_registrado"],
        },
    ]

    hits = search_read_models_text(rms, "maria m54.5 parecer_emitido", limit=10)
    assert len(hits) >= 1
    assert hits[0].documentid == "doc-clinico"


def test_search_read_models_text_empty_query_returns_empty():
    hits = search_read_models_text([{"documentid": "a", "texto": "x"}], "")
    assert hits == []
