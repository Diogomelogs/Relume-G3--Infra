from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

DOCUMENT_PATTERNS = {
    'cpf': r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b',
    'date': r'\b\d{2}/\d{2}/\d{4}\b',
    'rg': r'\b(registro geral|carteira de identidade|identidade|rg)\b',
    'nome': r'\bnome\b',
    'nascimento': r'\bdata de nascimento\b',
    'mae': r'\b(nome da m[ãa]e|filia[cç][aã]o)\b',
    'orgao': r'\b(ssp|secretaria da seguran[çc]a|instituto de identifica[cç][aã]o)\b',
    'cnis': r'\b(cnis|nit|origem do v[íi]nculo|sal[áa]rio contribui[cç][aã]o)\b',
    'rg_number': r'\b\d{2}\.?\d{3}\.?\d{3}-?[0-9xX]\b',
}

@dataclass
class ValidationMetrics:
    total_chars: int
    non_space_chars: int
    word_count: int
    long_word_count: int
    alnum_ratio: float
    alpha_ratio: float
    digit_ratio: float
    single_char_ratio: float
    repeated_symbol_ratio: float
    printable_ratio: float
    line_count: int
    structured_hits: int
    document_score: float
    confidence: float | None
    score: float

@dataclass
class ValidationDecision:
    status: str
    reasons: list[str]
    metrics: ValidationMetrics
    def to_dict(self):
        return asdict(self)


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_spaces(text: str) -> str:
    text = (text or '').replace('\x0c', ' ').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def count_document_hits(text: str) -> int:
    lowered = _strip_accents(normalize_spaces(text).lower())
    hits = 0
    for pattern in DOCUMENT_PATTERNS.values():
        if re.search(_strip_accents(pattern), lowered, flags=re.UNICODE):
            hits += 1
    return hits


def document_structure_score(text: str) -> float:
    lowered = _strip_accents(normalize_spaces(text).lower())
    score = 0.0
    for name, pattern in DOCUMENT_PATTERNS.items():
        p = _strip_accents(pattern)
        if re.search(p, lowered, flags=re.UNICODE):
            score += 10.0
        if name == 'date':
            score += min(len(re.findall(p, lowered, flags=re.UNICODE)), 3) * 2.0
    if score == 0 and len(lowered) > 150:
        score -= 15.0
    line_count = len([line for line in lowered.splitlines() if line.strip()])
    if line_count >= 4:
        score += 4.0
    return round(score, 2)


def evaluate_text_quality(text: str, confidence: float | None) -> ValidationDecision:
    text = normalize_spaces(text)
    total_chars = len(text)
    non_space_chars = len([c for c in text if not c.isspace()])
    words = re.findall(r'\b[\wÀ-ÿ]{1,}\b', text, flags=re.UNICODE)
    long_words = [w for w in words if len(w) >= 3]
    single_words = [w for w in words if len(w) == 1]
    lines = [line for line in text.splitlines() if line.strip()]
    alnum_chars = len(re.findall(r'[0-9A-Za-zÀ-ÿ]', text, flags=re.UNICODE))
    alpha_chars = len(re.findall(r'[A-Za-zÀ-ÿ]', text, flags=re.UNICODE))
    digit_chars = len(re.findall(r'\d', text))
    printable_chars = len([c for c in text if c.isprintable()])
    repeated_symbol_chunks = re.findall(r'([^\w\s])\1{2,}', text)
    weird_symbol_chunks = re.findall(r'[~_^=\\/|]{2,}', text)
    alnum_ratio = _safe_div(alnum_chars, max(non_space_chars, 1))
    alpha_ratio = _safe_div(alpha_chars, max(non_space_chars, 1))
    digit_ratio = _safe_div(digit_chars, max(non_space_chars, 1))
    single_char_ratio = _safe_div(len(single_words), max(len(words), 1))
    repeated_symbol_ratio = _safe_div(len(repeated_symbol_chunks) + len(weird_symbol_chunks), max(len(words), 1))
    printable_ratio = _safe_div(printable_chars, max(total_chars, 1))
    structured_hits = count_document_hits(text)
    document_score = document_structure_score(text)
    reasons = []
    score = 0.0
    if total_chars == 0:
        reasons.append('texto_vazio')
    else:
        score += min(total_chars, 1200) / 1200 * 18
        score += min(len(long_words), 120) / 120 * 16
        score += alnum_ratio * 18
        score += printable_ratio * 8
        score += max(0.0, (1.0 - single_char_ratio)) * 8
        score += max(0.0, (1.0 - min(repeated_symbol_ratio, 1.0))) * 8
        score += min(document_score, 40.0)
        if confidence is not None:
            score += max(0.0, min(confidence, 100.0)) * 0.08
    low_conf = confidence is not None and confidence < 50
    very_low_conf = confidence is not None and confidence < 40
    if total_chars < 25:
        reasons.append('texto_curto')
    if len(long_words) < 5:
        reasons.append('poucas_palavras_boas')
    if alnum_ratio < 0.55:
        reasons.append('muito_ruido')
    if single_char_ratio > 0.30 and len(words) >= 8:
        reasons.append('muitas_palavras_unitarias')
    if repeated_symbol_ratio > 0.10:
        reasons.append('muitos_simbolos_repetidos')
    if printable_ratio < 0.95:
        reasons.append('baixa_printabilidade')
    if low_conf:
        reasons.append('confianca_baixa')
    if structured_hits == 0 and total_chars >= 150:
        reasons.append('sem_estrutura_documental')
    if 'texto_vazio' in reasons:
        status = 'rejected'
    elif very_low_conf and score < 80:
        status = 'rejected'
    elif 'muito_ruido' in reasons or 'muitas_palavras_unitarias' in reasons or score < 45:
        status = 'rejected'
    elif low_conf:
        status = 'review'
    elif score >= 72 and len(long_words) >= 10 and alnum_ratio >= 0.65:
        status = 'approved'
    else:
        status = 'review'
    metrics = ValidationMetrics(total_chars=total_chars, non_space_chars=non_space_chars, word_count=len(words), long_word_count=len(long_words), alnum_ratio=round(alnum_ratio, 4), alpha_ratio=round(alpha_ratio, 4), digit_ratio=round(digit_ratio, 4), single_char_ratio=round(single_char_ratio, 4), repeated_symbol_ratio=round(repeated_symbol_ratio, 4), printable_ratio=round(printable_ratio, 4), line_count=len(lines), structured_hits=structured_hits, document_score=round(document_score, 2), confidence=None if confidence is None else round(confidence, 2), score=round(score, 2))
    return ValidationDecision(status=status, reasons=sorted(set(reasons)), metrics=metrics)
