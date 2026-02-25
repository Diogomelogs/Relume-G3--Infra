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


def test_search_read_models_text_empty_query_returns_empty():
    hits = search_read_models_text([{"documentid": "a", "texto": "x"}], "")
    assert hits == []