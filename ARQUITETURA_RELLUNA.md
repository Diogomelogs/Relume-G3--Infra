# Arquitetura Relluna

Data: 2026-04-07

## Objetivo

A Relluna transforma documentos médicos e correlatos em uma `DocumentMemory` auditável para uso médico-jurídico.

O foco técnico atual é preservar cadeia de custódia, extrair evidências determinísticas, gerar inferências contextuais controladas e expor read models úteis sem confundir fatos observados com eventos inferidos.

Este documento descreve o fluxo real do código atual. Não descreve a arquitetura ideal futura.

## Componentes Principais

| Área | Arquivos principais | Papel real |
| --- | --- | --- |
| Ingestion/API | `relluna/services/ingestion/api.py` | Ponto de entrada real do produto. Faz ingestão, deduplicação, persistência local, execução de pipeline e endpoints de leitura. |
| Contrato de memória | `relluna/core/document_memory/*` | Define `DocumentMemory` e camadas Layer0 a Layer6. Ainda há contratos legados e compatibilidade parcial. |
| Extração básica | `relluna/services/deterministic_extractors/basic.py` | Preenche Layer2 com sinais determinísticos por mídia. Em PDF, não faz OCR textual completo; delega decomposição/OCR ao pipeline de PDF. |
| PDF e páginas | `relluna/services/pdf_decomposition/decompose_pdf.py`, `relluna/services/page_extraction/page_pipeline.py` | Decompõe PDF, gera páginas normalizadas, spans/layout e `page_evidence_v1`. |
| Entidades canônicas | `relluna/services/entities/entities_canonical_v1.py` | Consolida sinais de página em `entities_canonical_v1` dentro de Layer2. |
| Timeline seed | `relluna/services/deterministic_extractors/timeline_seed_v2.py` | Converte `entities_canonical_v1` em sementes temporais `timeline_seed_v2`. |
| Inferência contextual | `relluna/services/context_inference/basic.py` | Popula Layer3 com classificação, entidades semânticas e `eventos_probatorios`. |
| Normalização | `relluna/core/normalization.py`, `relluna/services/correlation/layer4.py` | Promove data, local, entidades e tags para Layer4. |
| Derivados/Layer5 | `relluna/services/derivatives/layer5.py` | Gera derivados placeholder e read models `timeline_v1` e `entity_summary_v1`. |
| Read models públicos | `relluna/services/read_model/timeline_builder.py`, `relluna/services/read_model/*` | Expõe timeline pública por documento e busca/listagem parcial. |
| Benchmark | `relluna/services/benchmark/medical_legal.py`, `scripts/benchmark_runner.py`, `tests/golden/*` | Avalia casos médico-jurídicos goldens e gera `BENCHMARK_MEDICO_JURIDICO.md`. |

## Fluxo Real de Ingestão

O caminho principal é a API em `relluna/services/ingestion/api.py`.

### `/ingest`

1. Recebe arquivo via `UploadFile`.
2. Rejeita arquivo sem nome, vazio e HEIC.
3. Calcula SHA-256 do conteúdo.
4. Procura documento existente pelo fingerprint.
5. Se houver duplicata, retorna o `documentid` existente e não cria nova memória.
6. Salva o arquivo em `.uploads` com prefixo do hash.
7. Detecta `MediaType` e `OriginType`.
8. Cria `DocumentMemory` com:
   - Layer0: hash, custódia, metadados de ingestão, `processingevents`.
   - Layer1: artefato original local.
9. Para imagem, tenta rodar checagem NSFW e salva o resultado em `metadados_nativos` quando disponível.
10. Persiste com `relluna.infra.mongo_store.save`.

Observação: o campo legado `blob_uri` aponta para caminho local em `.uploads`, não para blob remoto real. As respostas de ingestão também expõem `artifact_uri`, `local_file_uri`, `storage_kind="local_file"`, `storage_state="local_file_persisted"` e `is_remote_blob=false` para evitar leitura enganosa de persistência remota.

### `/extract/{documentid}`

1. Lê o documento do `mongo_store`.
2. Valida como `DocumentMemory`.
3. Executa `_run_extract_pipeline`.
4. Persiste o resultado.
5. Retorna `to_contract(dm)`.

O pipeline de extração decide entre modos `fast`, `standard` e `forensic`. O modo é escolhido por sinais de preflight, tipo de mídia, PDF, quantidade de páginas, texto nativo e rotação.

O fluxo real usa estágios como:

- `extract_basic`.
- `decompose_pdf_into_subdocuments`, quando aplicável.
- `apply_page_analysis`.
- `apply_legal_extraction`.
- `apply_entities_canonical_v1`.

O caminho `fast` pode escalar para `standard` se a qualidade extraída for baixa.

Para PDFs escaneados sem texto nativo, `decompose_pdf_into_subdocuments` usa OCR. Antes do OCR pesado, `page_strategy_v1` classifica cada página como `native_text`, `ocr_light`, `ocr_heavy` ou `image_only` a partir de sinais baratos de texto nativo e imagens do PDF. A normalização de orientação não tenta mais múltiplas rotações por OCR por padrão; mantém a orientação renderizada, registra `ocr_warnings_v1` e emite `ProcessingEvent(status="warning")` quando opera em modo limitado. Chamadas de Tesseract têm timeout operacional para evitar travamento silencioso e permitir erro estruturado na API/UI.

### `/infer_context/{documentid}`

1. Exige que Layer2 exista.
2. Executa `seed_timeline_v2`.
3. Executa `infer_layer3`.
4. Executa `apply_layer4`.
5. Garante Layer4 se ela ainda não existir.
6. Executa `apply_layer5`.
7. Atualiza `juridicalreadinesslevel`.
8. Persiste e retorna `to_contract(dm)`.

Sequência real:

```text
Layer2 sinais -> timeline_seed_v2 -> Layer3.eventos_probatorios -> Layer4 -> Layer5
```

### `/process`

Combina `/ingest`, `_run_extract_pipeline` e `_run_infer_pipeline` em uma única chamada.

### `/documents/{documentid}/timeline`

Lê o documento persistido e retorna `build_document_timeline_read_model(dm)`.

Este endpoint é a fonte pública atual da timeline por documento.

### `/documents/{documentid}/case`

Lê o documento persistido e retorna uma visão mínima de caso por documento.

Esse endpoint não cria uma nova fonte semântica. Ele apenas consolida superfícies já existentes:

- timeline pública de `relluna/services/read_model/timeline_builder.py`;
- `entity_summary_v1` e `review_items_v1` derivados de Layer5;
- `legal_canonical_fields_v1` e `case_engine` para campos/fatos/alertas jurídicos compatíveis.

Regra de compatibilidade: a timeline continua tendo sua própria fonte pública em `/documents/{documentid}/timeline`. O endpoint de caso apenas a embute para reduzir round-trips de UI e consumo de produto.

## Camadas

### Layer0: Custódia

Contém identidade do documento, fingerprint, timestamp de ingestão, agente, metadados do arquivo, cadeia de custódia, provas de integridade, eventos de processamento e nível de prontidão jurídica.

Regra de domínio: Layer0 não deve conter inferência clínica ou jurídica.

Observabilidade operacional: `processingevents` deve registrar os estágios críticos do pipeline com `duration_ms`. Quando o estágio for por página, o evento deve carregar `page_index`; quando houver warning, deve carregar `warning_code`; quando houver fallback ou modo degradado, deve explicitar `fallback` e/ou `degraded_mode`. Isso se aplica ao wrapper de estágios da API e aos subestágios de página como normalização e OCR.

### Layer1: Artefatos

Contém a mídia, origem e lista de artefatos. No fluxo atual, o artefato original normalmente aponta para arquivo local em `.uploads`.

Regra de domínio: Layer1 descreve artefatos e origem, não interpreta conteúdo.

### Layer2: Evidência Determinística

Contém fatos observáveis e sinais determinísticos:

- dimensões de imagem;
- EXIF;
- duração de áudio/vídeo;
- número de páginas;
- OCR literal quando aplicável;
- `page_evidence_v1`;
- `page_unit_v1`;
- `subdocument_unit_v1`;
- `document_relation_graph_v1`;
- `entities_canonical_v1`;
- `timeline_seed_v2`.

Observação importante: `entities_canonical_v1` e `timeline_seed_v2` vivem hoje em `layer2.sinais_documentais`, mas já têm conteúdo semântico/canônico. Isso é uma compatibilidade temporária e uma fronteira arquitetural a ser corrigida com cuidado. A resolução de data documental, paciente, mãe e prestador começa a ser extraída para componentes puros (`DocumentDateResolver` e `PeopleResolver`), mantendo o shape legado e adicionando `semantic_resolution_v1` com `confidence`, `reason` e `evidence_refs`. No fluxo de pessoas, cabeçalhos fortes como `Paciente:` e `Nome:` podem confirmar paciente mesmo com nome curto de 2 tokens quando há `bbox` exato ou quando o `page_text` preserva o header real; sem `bbox`, o resultado permanece como `text_fallback` e o filtro continua conservador fora desse contexto forte.

Os sinais críticos `page_evidence_v1`, `page_unit_v1`, `subdocument_unit_v1`, `document_relation_graph_v1`, `entities_canonical_v1` e `timeline_seed_v2` possuem schemas versionados em `relluna/services/evidence/signals.py`. A leitura e a escrita validam esses schemas sem quebrar documentos antigos: payloads legados válidos em JSON seguem como fallback, e falhas de JSON/schema geram `signal_validation_warnings_v1`.

Para segmentação epistemicamente segura, `page_unit_v1` trata cada página como unidade autônoma com candidatos, evidências, warnings e uncertainties próprios. `subdocument_unit_v1` agrega apenas páginas com `subdoc_id` comum e preserva o estado `observed`, `inferred` ou `unknown` dos campos consolidados. `document_relation_graph_v1` explicita quando a ligação entre subdocumentos é `same_patient`, `same_provider`, `same_episode`, `same_document_continuation`, `conflict` ou `unknown`, em vez de assumir colapso global implícito.

Como bridge mínima para uso jurídico por caso, `entities_canonical_v1` também projeta `legal_canonical_fields_v1`. Esse sinal não reativa o extrator jurídico regex antigo; ele reaproveita apenas campos já consolidados no fluxo real e marca cada campo com `assertion_level` (`observed`, `inferred`, `estimated`), `provenance_status`, `review_state` e origem da evidência. Assim, datas e papéis resolvidos continuam utilizáveis pelo `case_engine` sem misturar fato observado com campo inferido ou estimado.

Na resolução de pessoas, `page_pipeline` tenta extrair `patient_name`, `mother_name` e `provider_name` do texto e dos spans, gera `anchors` e `signal_zones`, e `entities_canonical_v1` consolida isso via `semantic_resolution_v1.people`. Prefixos honoríficos como `Sr(a).` no paciente são tratados como ruído de cabeçalho, enquanto a deduplicação entre papéis compara uma identidade normalizada para evitar colisões simples como `ANA LIMA` versus `DRA ANA LIMA`.

### Layer3: Inferência Contextual

Contém inferências:

- `tipo_documento`;
- `tipo_evento`;
- `entidades_semanticas`;
- `classificacoes_pagina`;
- `eventos_probatorios`.

`Layer3.eventos_probatorios` é gerado principalmente a partir de `timeline_seed_v2`, que por sua vez nasce primeiro de `subdocument_unit_v1` e `page_unit_v1`; `entities_canonical_v1` permanece apenas como fallback compatível. Cada evento deve carregar data, tipo, título, descrição, entidades, citações, confiança, revisão, status de proveniência e o estado epistemológico explícito (`observed`, `inferred` ou `unknown`).

Regra de utilidade jurídica: todo evento probatório deve expor `provenance_status`, `review_state` e `confidence`. Quando houver evidência exata, a citação deve carregar `page`, `snippet` e `bbox`; quando a evidência não for exata, o evento deve ficar explicitamente marcado como `inferred` ou `estimated`.

Regra de domínio: evento inferido não deve ser tratado como observado.

### Layer4: Normalização Canônica

Contém projeções normalizadas:

- `data_canonica`;
- `periodo`;
- `local_canonico`;
- `entidades`;
- `tags`;
- `relacoes_temporais`.

O normalizador real em `relluna/core/normalization.py` busca temporalidade em Layer3, depois EXIF, depois `entities_canonical_v1.document_date` e só então cai para resolução a partir de `page_evidence_v1`, evitando candidatos que pareçam data de nascimento. Como defesa de compatibilidade, a promoção para `data_canonica` também rejeita valores temporais que coincidam com uma data marcada como nascimento em `page_evidence_v1` ou em `entities_canonical_v1.quality.warnings`, mesmo se um payload legado contaminado já trouxer essa data em `document_date`.

### Layer5: Derivados e Read Models

`relluna/services/derivatives/layer5.py` cria:

- derivados placeholder (`generated://...`);
- `storage_uris` vazio enquanto não houver backend real;
- `persistence_state="placeholder_not_persisted"`;
- `read_models.timeline_v1`;
- `read_models.entity_summary_v1`;
- `read_models.review_items_v1`.

Regra atual: `generated://...` representa derivado placeholder não persistido. O contrato não deve afirmar blob remoto nem `stored` sem backend real. Isso deve permanecer explícito em documentação/testes até a migração terminar.

### Política de revisão humana

A revisão humana deve reaproveitar a semântica já produzida pelo pipeline, não criar uma trilha paralela de decisão.

O read model `review_items_v1` em `relluna/services/derivatives/layer5.py` projeta itens revisáveis a partir de:

- `entities_canonical_v1.semantic_resolution_v1.people`;
- `entities_canonical_v1.semantic_resolution_v1.document_date`;
- `entities_canonical_v1.clinical.cids`;
- `Layer3.eventos_probatorios`;
- `timeline_consistency_v1`, quando houver divergência entre `timeline_seed_v2` e `Layer3.eventos_probatorios`.

Cada item de revisão deve expor:

- `item_type`;
- `field`;
- `value`;
- `confidence`;
- `review_state`;
- `provenance_status`;
- `reason`;
- `evidence_refs`;
- `source_signal`;
- `suggested_action`.

Regra operacional: `review_items_v1` deve destacar explicitamente fallback textual, eventos inferidos ou estimados sem bbox exato e conflitos entre fontes. O frontend pode priorizar a fila por `review_state` e `suggested_action`, mas a fonte de verdade continua sendo a semântica já consolidada em Layer2/Layer3.

### Layer6: Otimização

Layer6 é usado para embeddings e indexação em componentes como `semantic_pipeline` e `forensics/layer6.py`.

Ele ainda não é o centro do fluxo real da API de ingestão/processamento.

## Timeline

Há dois caminhos relevantes:

### Fonte pública atual

`relluna/services/read_model/timeline_builder.py`

O endpoint `/documents/{documentid}/timeline` usa:

1. `Layer3.eventos_probatorios`, como fonte primária inequívoca da timeline pública;
2. `timeline_seed_v2`, apenas como fallback compatível para documentos antigos;
3. `timeline_seed_v1`, como fallback legado.

Ele preserva compatibilidade do contrato legado e enriquece a superfície pública com campos de produto:

- `event_id`;
- `date`;
- `label`;
- `event_type`;
- `evidence_ref`.
- `title`;
- `description`;
- `confidence`;
- `review_state`;
- `provenance_status`;
- `assertion_level`;
- `entities`;
- `citations`;
- `artifact_uri`;
- `evidence_navigation`.

Além da lista de eventos, o read model expõe `subdocuments`, `relations` e `inconsistencies` para tornar visíveis conflitos e vínculos `unknown` entre blocos documentais heterogêneos.

O resumo público também expõe métricas consolidadas:

- `total_events`;
- `needs_review_count`;
- `anchored_events`;
- `timeline_consistency_score`;
- `warnings`.

Esse caminho preserva compatibilidade de contrato: os campos legados permanecem, mas a fonte primária passa a ser `Layer3.eventos_probatorios` quando disponível.

`Layer5.read_models.timeline_v1` deve convergir para a mesma política: usar `Layer3.eventos_probatorios` como fonte preferencial e reutilizar o read model público apenas como bridge de compatibilidade quando o documento legado ainda só tiver `timeline_seed_v2`/`timeline_seed_v1`.

### Política de fonte oficial

A fonte oficial da timeline do produto é:

1. `Layer3.eventos_probatorios` como fonte primária semântica.
2. `relluna/services/read_model/timeline_builder.py` como projeção pública por documento.
3. `timeline_seed_v2` apenas como fallback compatível para documentos legados ou incompletos.

O diretório `relluna/services/timeline/*` não é a fonte oficial atual. Ele contém código legado, wrappers compatíveis e caminhos mortos que devem permanecer documentados até a limpeza final, mas não devem receber novos consumidores de produto.

### Fonte de compatibilidade

`timeline_seed_v2` não foi removido. Ele continua sendo gerado, validado e usado como fallback para documentos antigos ou incompletos.

Motivo: Layer3 tem mais contexto e carrega campos necessários para produto médico-jurídico:

- título;
- descrição;
- entidades vinculadas;
- citações;
- confiança;
- estado de revisão;
- status de proveniência;
- regra de derivação.

### Verificação de consistência

Enquanto a migração não termina, `timeline_builder.py` compara `timeline_seed_v2` com `Layer3.eventos_probatorios` em:

- contagem de eventos;
- datas principais.

Regra operacional: divergência entre a timeline pública derivada de Layer3 e o fallback legado não pode ficar silenciosa. O read model público deve zerar `timeline_consistency_score` e expor `warnings` estruturados quando houver diferença de contagem ou de datas principais.

Quando há divergência, emite warning estruturado:

```text
timeline_seed_v2_layer3_divergence
```

O benchmark também expõe `timeline_consistency_score`.

## Read Models

### Timeline pública por documento

Arquivo: `relluna/services/read_model/timeline_builder.py`

Uso real: endpoint `/documents/{documentid}/timeline`.

Fonte primária atual: `Layer3.eventos_probatorios`.

Fallbacks compatíveis: `timeline_seed_v2` e, em último caso, `timeline_seed_v1`.

Regra de consistência: `timeline_seed_v2` continua existindo para documentos legados, mas não substitui `Layer3` quando os eventos probatórios estiverem disponíveis.

### Timeline Layer5

Arquivo: `relluna/services/derivatives/layer5.py`

Read model: `layer5.read_models["timeline_v1"]`.

Fonte atual: `Layer3.eventos_probatorios`.

Status: serve como superfície rica paralela e deve permanecer semanticamente alinhado ao endpoint público principal.

### Entity summary

Arquivo: `relluna/services/derivatives/layer5.py`

Read model: `layer5.read_models["entity_summary_v1"]`.

### Painel e busca

Arquivos principais:

- `relluna/services/read_model/models.py`
- `relluna/services/read_model/projector.py`
- `relluna/services/read_model/store.py`
- `relluna/services/read_model/text_search.py`
- `relluna/services/read_model/endpoints.py`

Regra atual: o painel usa um único schema consolidado em `DocumentReadModel`. Ele combina:

- `doc_type`, `date_canonical`, `period_label`, `tags` e `entities` de Layer4;
- `entity_summary_v1`, `timeline_v1` e `review_items_v1` de Layer5;
- a relação operacional com a timeline pública via endpoint `/documents/{documentid}/timeline`.

O read model do painel deve expor, no mínimo:

- tipo documental;
- data canônica;
- tags semânticas;
- entidades resumidas;
- resumo executivo curto;
- indicadores de confiança;
- `needs_review_count`;
- referência para a timeline pública.

Regra de busca: filtros e busca textual devem operar sobre o schema consolidado do painel, não sobre campos legados divergentes. Os filtros prioritários atuais são:

- paciente;
- prestador;
- CID;
- data canônica;
- tipo de evento;
- tags;
- tipo documental.

Fonte: combina `entities_canonical_v1`, `page_evidence_v1`, `hard_entities_v2` e entidades dos eventos Layer3.

### Busca/listagem

Arquivos em `relluna/services/read_model/*`.

Status: existe implementação parcial com store Mongo e rotas de read model. Alguns testes legados ainda precisam de fake/store dedicado para não tocar Mongo real.

## Benchmark

O benchmark médico-jurídico fica em:

- `relluna/services/benchmark/medical_legal.py`;
- `scripts/benchmark_runner.py`;
- `tests/golden/*`;
- relatório gerado `BENCHMARK_MEDICO_JURIDICO.md`.

Ele avalia casos goldens com os eixos:

- entidades;
- eventos;
- evidência;
- confiabilidade;
- utilidade jurídica.

Também expõe:

- `timeline_consistency_score`.

O projetor `project_document_memory(dm)` lê:

- `entities_canonical_v1`;
- `Layer3.eventos_probatorios`;
- warnings de qualidade;
- warning de consistência entre seed e Layer3.

O benchmark não substitui testes unitários. Ele é uma camada de regressão semântica para evitar que mudanças no pipeline pareçam corretas tecnicamente mas quebrem garantias médico-jurídicas.

## Fonte de Verdade

### Hoje

Para a timeline pública:

```text
timeline_seed_v2 -> /documents/{documentid}/timeline
```

`timeline_seed_v2` é a fonte efetiva do endpoint público de timeline.

Para eventos probatórios internos:

```text
timeline_seed_v2 -> Layer3.eventos_probatorios -> layer5.read_models.timeline_v1
```

### Futuro

Fonte desejada para timeline de produto:

```text
Layer3.eventos_probatorios
```

Depois da migração, o endpoint público deve projetar `Layer3.eventos_probatorios` para o shape público compatível ou para uma versão nova do contrato.

### Durante a migração

As duas fontes não podem divergir silenciosamente. Divergências em contagem ou datas devem gerar warning estruturado e penalizar `timeline_consistency_score`.

## Riscos Conhecidos

- Existem contratos legados de `DocumentMemory` e testes antigos ainda marcados como `xfail`.
- `entities_canonical_v1` e `timeline_seed_v2` estão em Layer2, embora carreguem informação semântica/canônica.
- Layer5 ainda usa derivados e storage URIs placeholder.
- A timeline pública ainda é seed-based, enquanto a timeline futura é Layer3-based.
- OCR real, TestClient pesado, Mongo real e Azure Blob real não devem bloquear `make test` até receberem fakes, timeouts ou suíte de integração dedicada.
- Persistência real e persistência fake/local precisam ser explicitadas na UI e nos contratos.

## Política Atual de Testes

`make test` roda a suíte unitária/de contrato e deve passar.

Testes legados de integração com mídia, OCR real, Azure Blob, Mongo real ou pipeline HTTP pesado estão temporariamente marcados como `xfail(run=False)` até serem migrados para:

- fakes determinísticos;
- timeout explícito;
- suíte de integração separada;
- ou goldens atualizados.

`make benchmark` roda o benchmark médico-jurídico e atualiza `BENCHMARK_MEDICO_JURIDICO.md`.

## Direção de Migração

1. Manter compatibilidade do endpoint público atual.
2. Continuar gerando `timeline_seed_v2` como intermediário auditável.
3. Garantir que `Layer3.eventos_probatorios` reflita as seeds sem divergência silenciosa.
4. Criar adaptador único de Layer3 para timeline pública.
5. Trocar a fonte pública para Layer3 quando os contratos e testes estiverem estabilizados.
6. Depreciar `timeline_seed_v2` como fonte pública, mantendo-o como sinal intermediário determinístico.
