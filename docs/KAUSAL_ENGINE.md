# Kausal Engine — Motor de Nexo Causal Previdenciário

## Visão Geral

**Kausal** é o motor determinístico que transforma uma timeline de eventos médicos em um **grafo de nexo causal** auditável e justificável para o domínio jurídico-previdenciário brasileiro.

Enquanto a timeline temporal responde **"quando?"**, Kausal responde **"por quê?"**: qual evento causou qual outro, com qual confiança, e por qual regra jurídica.

## Principios

1. **Determinístico, não mágico**: 100% das hipóteses de nexo vêm de regras explícitas baseadas em Lei 8.213/91, Decreto 3.048/99 e jurisprudência (TNU, STJ).
2. **Rastreável**: cada aresta causal aponta para a página exata dos dois eventos que a geraram.
3. **Revisável**: o advogado sempre pode questionar, confirmar ou descartar uma hipótese (review_state).
4. **Honesto sobre incerteza**: confiança 0.99 para presunção legal, 0.85 para afastamento prolongado, etc.

## Arquitetura

### Input: Eventos Probatórios (Layer3)

```python
ProbatoryEvent(
    event_id="evt_001",
    event_type="acidente",
    date_iso="2024-06-15T10:30:00Z",
    entities={"cid": "T20.0", "provider_activity": "eletricista"},
    citations=[EvidenceRef(path="page:2/doc:CAT", bbox=...)]
)
```

### Process: 6 Regras Jurídicas

Cada regra é uma hipótese de nexo com:
- **Base legal**: Lei/artigo que a sustenta
- **Condição**: quando dispara
- **Confiança base**: 0.0–1.0
- **Explicação**: justificativa em linguagem natural

#### 1. Presunção Legal NTEP (conf: 0.99)

```
IF (atividade, CID) está na tabela CEREST
THEN "Presunção legal automática"

Exemplo: Eletricista + T20 (queimadura elétrica)
Legal: Lei 8.213/91 Art. 20, Decreto 3.048/99
```

#### 2. Afastamento Prolongado (conf: 0.85)

```
IF evento_a → evento_b (afastamento)
   AND intervalo > 30 dias
THEN "Perda de capacidade presume nexo"

Legal: Jurisprudência dominante TNU
```

#### 3. Mesmo CID em Múltiplos Documentos (conf: 0.78)

```
IF CID_a[:3] == CID_b[:3] em docs diferentes
   E data_a < data_b
THEN "Diagnóstico estável, validado"

Semântica: não é causalidade, é coerência/continuidade
```

#### 4. Progressão Anatômica (conf: 0.82)

```
IF (CID_a, CID_b) em ANATOMICAL_RELATIONSHIPS
   E cronologia preservada
THEN "Evolução de lesão confirmada"

Exemplo: Queimadura (T20) → Síndrome fibromiálgica (M79)
```

#### 5. ALERTA: Conflito de Datas/CIDs (conf: 0.0)

```
IF mesmo CID com datas > 60 dias apart
THEN "⚠ CONFLITO: requer revisão humana"

Semântica: reduz confiança total, marca para revisão
```

#### 6. Perícia Confirma Anterior (conf: 0.88)

```
IF perícia posterior tem CID compatível com evento anterior
THEN "Perícia reforça nexo original"

Legal: STJ: perícia contemporânea tem peso, posterior que confirma também
```

### Output: CausalLink

```python
CausalLink(
    event_a_id="evt_001",
    event_b_id="evt_002",
    link_type="presuncao_legal",
    confidence=0.99,
    rule_id="rule_presuncao_ntep",
    rule_explanation="Presunção legal: eletricista + T20 está em NTEP (Lei 8.213/91 Art. 20)",
    citations=[...],
    review_state="auto",  # ou "needs_review", "human_confirmed"
    visual_color="#22c55e",  # verde (forte)
    visual_thickness=3
)
```

Persistido em: `Layer2.sinais_documentais["causal_link_v1"]` (JSON)

## Fluxo no Pipeline

```
/ingest → Layer0 + Layer1
    ↓
/extract → Layer2
    ↓
/infer_context
    Step 1: infer_layer3 → ProbatoryEvent[]
    
    Step 2: [NOVO] infer_causal_links()
            Para cada par (evt_a, evt_b):
              - Aplica 6 regras
              - Cria CausalLink se conf > 0.5
    
    Step 3: persist_causal_links_to_layer2()
            Salva em sinais_documentais["causal_link_v1"]
    
    Step 4: apply_layer4()
            Consolida grafo para visualização
    
    Step 5: apply_layer5()
            Read model: causal_timeline_v1
```

## Casos de Uso

### 1. Previdenciário: Acidente Laboral + Sequela

**Documentos**: CAT, Atestado, Perícia

**Timeline**:
- T+0: CAT: Queda de 3m em construção (S72.0)
- T+5: Atestado: Fratura fêmur com lesão vascular (S73.1)
- T+30: Perícia INSS: Confir ma sequela permanente

**Kausal detecta**:
- S72 (fratura) → S73 (luxação/vascular) = progressão anatômica (conf: 0.82)
- Perícia confirma anterior (conf: 0.88)
- **Resultado**: Nexo provado com 2 regras independentes ✓

### 2. Alertas: Conflito Documental

**Documentos**: Receita médica, Atestado contraditório

**Conflito**:
- Receita (01/03): Prescreve antibiótico para bronquite (J20)
- Atestado (10/03): Afirma fratura de bacia (S32) desde 28/02

**Kausal detecta**:
- Mesma pessoa, CIDs incompatíveis, datas conflitantes
- Marca para revisão: "⚠ CONFLITO: J20 em 01/03 vs S32 em 28/02"
- Review_state = "needs_review"
- **Resultado**: Advogado revisará documentos, identificará falsificação

### 3. Nexo Técnico Epidemiológico (NTEP)

**Documentos**: Prontuário ocupacional, Atestado LER

**Caso**: Operador de caixa com LER (M17)

**Kausal detecta**:
- Atividade ("operador_caixa") + CID M17 em NTEP
- **Presunção legal**: não precisa provar cronologia
- Conf: 0.99
- **Resultado**: Nexo automático, pericias posteriores confirmam

## Frontend Integration

### Visualização

Grafo de eventos com setas causais:

```
15/01/2024 ──────► ACIDENTE
     │             (CAT, p.2)
     │
     ├─→ [seta verde, espessura 3]
     │   Presunção NTEP (conf: 0.99)
     │
20/01/2024 ──────► LESÃO
                   (Atestado, p.1)
     │
     └─→ [seta amarela, espessura 2]
         Progressão (conf: 0.82)

01/04/2024 ──────► PERÍCIA
                   (INSS, p.3)
```

**Clica na seta**: abre painel mostrando:
- Tipo de nexo + regra + explicação
- Documento A (esquerda) com bbox do trecho relevante
- Documento B (direita) com bbox do trecho relevante
- Botões: ✓ Confirmar / ? Questionar

### Read Model

`/documents/{docid}/causal_timeline` retorna:

```json
{
  "grafo": [
    {
      "event_a_id": "evt_001",
      "event_b_id": "evt_002",
      "link_type": "presuncao_legal",
      "confidence": 0.99,
      "seta_cor": "#22c55e",
      "seta_espessura": 3,
      "rule_explanation": "..."
    }
  ],
  "eventos": [...]
}
```

## Guia de Extensão

### Adicionar Nova Regra

1. **Definir em `rules_previdenciario.py`**:

```python
def rule_nova_hipotese(event_a, event_b, canonical):
    # Lógica da condição
    return True

RULE_NOVA = KausalRule(
    rule_id="rule_nova_hipotese",
    name="Nova Hipótese",
    description="Quando dispara",
    confidence_base=0.80,
    condition=rule_nova_hipotese,
    explanation_template="Explicação: {param1}",
    legal_basis="Lei X Art. Y"
)

KAUSAL_RULES.append(RULE_NOVA)
```

2. **Testar com golden case**:

```python
def test_kausal_nova_hipotese():
    dm = create_dm_with_pattern()
    links = infer_causal_links(dm)
    assert any(l.rule_id == "rule_nova_hipotese" for l in links)
```

3. **Documentar base legal** em docstring

### Ajustar Confiança por Contexto

Regras aplicam confiança base, mas é possível ajustar pós-hoc:

```python
# Na persistência, aumentar confiança se múltiplas regras concordam
for link in links:
    confirmadores = len([l for l in links 
                        if l.event_a_id == link.event_a_id 
                        and l.confidence > 0.5])
    if confirmadores > 1:
        link.confidence += 0.05  # Boost por concordância
```

## Validação & Qualidade

### Benchmark

Golden cases no benchmark (test_kausal_eletricista.py):

1. **Presunção NTEP**: Eletricista + queimadura elétrica
2. **Progressão Anatômica**: Queimadura → Síndrome fibromiálgica
3. **Perícia Confirma**: INSS confirma diagnóstico anterior
4. **Conflito**: Documentos contraditórios sinalizam revisão

### Métricas

- **Cobertura**: % de pares de eventos com ≥1 regra disparada
- **Confiança média**: avg(confidence) entre links válidos
- **Conflitos detectados**: % de pares flagged para revisão
- **Regressions**: benchmark deve passar a cada iteração

## Limitações & Roadmap

### MVP (Atual)

✅ 6 regras determinísticas
✅ Presunção NTEP com tabela
✅ Detecção de conflitos
✅ Rastreabilidade completa

❌ Não detecta causalidades raras (só NTEP official)
❌ Frontend não renderiza ainda
❌ Multi-documento não agregado

### v0.2

- Expandir tabela NTEP (hoje: 13 atividades, objetivo: 50+)
- Agregar causas em Caso (multi-documento)
- Anti-nexo: detectar o que enfraquece a tese

### v0.3

- LLM como redator de explicações (nunca criador de nexo)
- Integração com perícias: sugerir alvo de perícia baseado em gaps

## Referências Legais

1. **Lei 8.213/1991**: Lei de Benefícios da Previdência Social
   - Art. 19: Definição de acidente
   - Art. 20: Doenças ocupacionais equiparadas
   - Art. 21: Acidentes por equiparação

2. **Decreto 3.048/1999**: Regulamento da Previdência Social
   - Detalha tabela de doenças por atividade

3. **CEREST**: Centro de Referência em Saúde do Trabalhador
   - Tabela NTEP (Nexo Técnico Epidemiológico Previdenciário)

4. **Jurisprudência**:
   - Súmula 442 (STF): Sequelas óbvias não requerem prova de nexo
   - Decisões TNU: Afastamento prolongado presume nexo
   - STJ: Perícia contemporânea tem peso máximo

## Contato & Dúvidas

Documentação: `/docs/KAUSAL_ENGINE.md`
Código: `relluna/services/causal/`
Testes: `tests/test_kausal_*.py`
