from __future__ import annotations

def extract_named_entities_pt(text: str):
    # Import lazy: spacy pode não estar instalado no ambiente
    try:
        import spacy
    except Exception:
        return []

    try:
        nlp = spacy.load("pt_core_news_sm")
    except Exception:
        return []

    doc = nlp(text or "")
    return [{"texto": ent.text, "label": ent.label_} for ent in doc.ents]
