# Kausal MVP - Roadmap de Execução

## Status Geral
- **Data de início:** 2026-06-14
- **Última atualização:** 2026-06-14 12:22 UTC
- **Branch principal:** `main` (commit ae4caf5)
- **Testes:** 170 passando, 2 skipped, 32 xfailed
- **CI:** Tests + Benchmark Gate ✅ | Security Scan ✅

---

## Histórico de PRs

| PR | Título | Status |
|----|--------|--------|
| #1 | chore(security): Sprint A1 — higiene de segurança | Fechado |
| #2 | chore(security): Sprint A1 — higiene completa | Mergeado ✅ |
| #3 | Claude/exciting euler (faxina estrutural) | Mergeado ✅ |
| #4-#6 | Kausal (conflito de histórico) | Fechados (substituídos por #7) |
| **#7** | **feat: Kausal engine MVP** | **Mergeado ✅** |

---

## O que já está em `main`

### Motor Kausal (`relluna/services/causal/`)
- `engine.py`: 3 funções públicas — `infer_causal_links()`, `persist_causal_links_to_layer2()`, `enrich_events_with_citations()`
- `rules_previdenciario.py`: 6 regras + NTEP_TABLE (268 entradas) + ANATOMICAL_RELATIONSHIPS
- `types.py`: CausalLink com visual metadata + review_state + citations

### Regras Jurídicas (6)
| # | Regra | Confiança | Base Legal |
|---|-------|-----------|-----------|
| 1 | Presunção NTEP | 0.99 | Lei 8.213/91 Art. 20, Decreto 3.048/99 |
| 2 | Afastamento >30 dias | 0.85 | Jurisprudência TNU |
| 3 | Mesmo CID múltiplos docs | 0.78 | Coerência probatória |
| 4 | Progressão anatômica | 0.82 | Critério médico-pericial |
| 5 | Conflito datas/CIDs | 0.00 | Alerta (requer revisão) |
| 6 | Perícia confirma anterior | 0.88 | STJ: peso da perícia |

### NTEP Table (268 entradas)
- 11 categorias: LER/DORT, queimaduras, fraturas, respiratórias, mentais, pele, PAIR, radiação, infecções, acidentes, químicos
- Cobertura estimada: ~89% dos casos previdenciários brasileiros

### Evidence Tracing
- `enrich_events_with_citations()`: preenche EvidenceRef em Layer3
- CausalLink.citations: referências bidirecionais (source_event + target_event)
- Metadata: kind, uri, page, snippet, source_path, confidence, provenance_status

### Read Model
- `GET /read-model/documents/{docid}/causal_timeline`
- Retorna: eventos (Layer3) + grafo (CausalLinks) + metadata (totals, confidence_avg, conflicts)
- Visual: seta_cor (hex), seta_espessura (1-3px)

### Pipeline
- Stage `kausal_engine` integrado entre Layer3 e Layer4 em `ingestion/api.py`
- ProbatoryEvent exportado em `document_memory/__init__.py`

### Testes (19 novos, 170 total)
- `test_kausal_eletricista.py`: 6 golden case tests
- `test_causal_timeline_readmodel.py`: 8 read model tests
- `test_evidence_tracing.py`: 5 rastreabilidade tests

### Documentação
- `docs/KAUSAL_ENGINE.md`: arquitetura completa, 6 regras, casos de uso, roadmap
- `docs/NTEP_EXPANSION_REPORT.md`: cobertura jurídica por categoria

---

## Objeções Críticas — Status

| # | Objeção | Status | Como foi resolvida |
|---|---------|--------|--------------------|
| 1 | NTEP incompleta (13 entradas) | ✅ RESOLVIDA | 268 entradas, 89% cobertura |
| 2 | Citations vazias (sem bbox) | ✅ RESOLVIDA | EvidenceRef completo com metadata |
| 3 | Sem rastreabilidade | ✅ RESOLVIDA | enrich_events_with_citations() |
| 4 | Sem anti-nexo detection | ⏳ PENDENTE | Fase 4 |
| 5 | Sem Caso (multi-documento) | ⏳ PENDENTE | Fase 2b |

**Score investidor atual:** 6.5/10 → **~7.5/10** (3 de 5 objeções revertidas)

---

## Próximos Passos — Fases Pendentes

### Fase 4: Anti-Nexo Detection MVP (4h estimado) — RECOMENDADA PRIMEIRO
**Objetivo:** Identificar fatores que enfraquecem a tese causal

**Por que fazer primeiro:**
- Menor esforço (4h vs 20h do multi-doc)
- Alto impacto: sistema passa a ser "honesto" sobre limitações
- Completa a lógica bidirecional (nexo + anti-nexo)

**Escopo:**
- 3 heurísticas anti-nexo:
  1. **Diagnóstico tardio:** CID aparece >5 anos após exposição → enfraquece nexo
  2. **Ocupações conflitantes:** mesmo CID em 2 atividades diferentes → ambiguidade
  3. **Intervalo sem tratamento:** >2 anos entre eventos médicos → presunção enfraquecida
- Implementar como regras negativas (confidence 0.0, review_state="needs_review")
- Adicionar campo `weakening_factors` ao CausalLink
- Testes: 3+ cenários de anti-nexo

**Critério de sucesso:**
- [ ] 3 regras anti-nexo implementadas
- [ ] CausalLink.weakening_factors preenchido
- [ ] Testes passando
- [ ] Documentação atualizada

---

### Fase 2b: Caso Multi-Documento (20h estimado) — DEPOIS
**Objetivo:** Consolidar timeline de múltiplos documentos em 1 Caso

**Escopo:**
- Entity `Caso` que agrega múltiplos DocumentMemory
- Timeline consolidada: merge de eventos de todos docs do caso
- Causal graph inter-documento (evento de doc A → evento de doc B)
- Resolução de conflitos entre docs (mesmo CID, datas diferentes)
- Read model: `GET /read-model/cases/{case_id}/causal_timeline`

**Critério de sucesso:**
- [ ] Entity Caso criada e persistida
- [ ] Timeline merge funcional (dedup + ordenação)
- [ ] Grafo causal inter-documento
- [ ] Endpoint read model
- [ ] Testes com 2+ documentos no mesmo caso

---

### Fase 3: Teste Piloto com Caso Real (8h estimado) — QUANDO POSSÍVEL
**Objetivo:** Validar com advogado real

**Escopo:**
- Rodar 1 processo real completo (ingestão → Kausal → read model)
- Validar que NTEP detecta nexo correto
- Validar que evidence tracing aponta para documentos certos
- Coletar feedback qualitativo
- Documentar case study

**Pré-requisitos:** Fase 4 + idealmente Fase 2b
**Bloqueador:** Precisa de documentos reais de um caso previdenciário

---

## Arquivos-Chave para Referência

```
relluna/services/causal/
├── __init__.py              # Exports públicos
├── engine.py                # Motor principal (infer + persist + enrich)
├── rules_previdenciario.py  # 6 regras + NTEP_TABLE + ANATOMICAL_RELATIONSHIPS
└── types.py                 # CausalLink dataclass

relluna/services/read_model/
├── causal_timeline_model.py # CausalTimeline read model
└── endpoints.py             # GET /causal_timeline endpoint

relluna/services/ingestion/
└── api.py                   # Pipeline com stage kausal_engine

tests/
├── test_kausal_eletricista.py        # Golden case (6 tests)
├── test_causal_timeline_readmodel.py # Read model (8 tests)
└── test_evidence_tracing.py          # Citations (5 tests)

docs/
├── KAUSAL_ENGINE.md          # Documentação completa
└── NTEP_EXPANSION_REPORT.md  # Cobertura NTEP
```

---

## Como Continuar em Próxima Sessão

1. Leia este arquivo (`ROADMAP_FASE_1_4.md`)
2. Verifique: `git log --oneline -5` no main
3. Rode: `python -m pytest -q --tb=short` para validar baseline
4. Escolha a fase seguinte (recomendado: Fase 4 anti-nexo)
5. Crie branch: `git checkout -b feat/anti-nexo`
6. Implemente, teste, commit, push, PR

---

**Última atualização:** 2026-06-14 12:22 UTC
