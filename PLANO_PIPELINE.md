# Plano de Execucao em Fases do Pipeline Relluna

Data: 2026-04-07

Escopo: plano operacional baseado em `DIAGNOSTICO_PIPELINE.md`. Este documento nao altera codigo; organiza a execucao para aumentar confiabilidade, reduzir regressao semantica e preparar evolucao do produto.

## Fase 1: quick wins de baixo risco

### Objetivo

Reduzir riscos imediatos de manutencao, seguranca e confiabilidade sem mudar o comportamento central do pipeline. A prioridade e explicitar placeholders, remover ambiguidade perigosa e criar testes de caracterizacao antes de qualquer refatoracao maior.

### Arquivos afetados

- `.gitignore`
- `DIAGNOSTICO_PIPELINE.md`
- `PLANO_PIPELINE.md`
- `relluna/services/context_inference/document_taxonomy/rules.py`
- `relluna/services/derivatives/layer5.py`
- `relluna/services/read_model/timeline_builder.py`
- `tests/test_document_taxonomy_rules.py`
- `tests/test_layer4_normalization_contract.py`
- novos testes em `tests/test_pipeline_reliability_*.py`

### Risco

Baixo, se a fase for limitada a documentacao, higiene de repositorio, testes e pequenas correcoes defensivas sem alterar contratos publicos. O maior cuidado e nao remover arquivos versionados sensiveis sem uma decisao explicita de historico/segredos, porque isso pode exigir limpeza de Git e rotacao de credenciais.

### Esforco estimado

1 a 3 dias.

### Criterio de sucesso

- `DIAGNOSTICO_PIPELINE.md` e `PLANO_PIPELINE.md` existem e refletem o fluxo real.
- Existe uma decisao documentada sobre `.env`, `.venv`, uploads, caches e artefatos sensiveis no versionamento.
- O arquivo legado/quebrado `relluna/services/context_inference/document_taxonomy/rules.py` esta marcado como legado, corrigido ou coberto por teste de import.
- `Layer5` deixa claro quando usa placeholders ou possui teste que impede expor URI fake como persistencia real.
- Ha testes de caracterizacao para pelo menos: `birth_date` nao virar data do documento, `receituario` nao virar `atestado_medico`, e endpoint/read model de timeline com politica documentada.
- A timeline publica usa `Layer3.eventos_probatorios` como fonte primaria, com `timeline_seed_v2` apenas como fallback compatível explicitado em documentacao e testes.
- O payload publico da timeline preserva `review_state` e `provenance_status`, e o resumo expõe `total_events`, `needs_review_count`, `anchored_events`, `timeline_consistency_score` e `warnings`.
- O benchmark medico-juridico possui gate semantico minimo executavel via CLI/CI: casos criticos positivos (`document_date`, documento composto, paciente/mae, timeline util) devem permanecer sem regressao e com score minimo; casos sentinela negativos (`birth_date`, provider falso positivo, CID espurio, divergencia seed/Layer3`) devem continuar detectando regressoes explicitamente.
- Politica temporaria da suite: `make test` deve executar a suite unitaria/de contrato sem falha; testes legados de integracao com OCR real, midia, Azure Blob, Mongo real ou TestClient pesado ficam marcados como `xfail(run=False)` ate receberem fake, timeout explicito ou workflow dedicado.

## Fase 2: estabilizacao do pipeline

### Objetivo

Tornar o fluxo atual observavel e previsivel sem reescrever a arquitetura. A meta e reduzir regressao silenciosa, padronizar warnings/degraded states e cobrir os principais casos de confiabilidade clinica por testes automatizados.

### Arquivos afetados

- `relluna/services/ingestion/api.py`
- `relluna/services/deterministic_extractors/basic.py`
- `relluna/services/pdf_decomposition/decompose_pdf.py`
- `relluna/services/page_extraction/page_text_splitter.py`
- `relluna/services/page_extraction/page_pipeline.py`
- `relluna/services/page_extraction/page_entity_extractors.py`
- `relluna/services/page_extraction/page_clinical_extractors.py`
- `relluna/services/entities/entities_canonical_v1.py`
- `relluna/services/deterministic_extractors/timeline_seed_v2.py`
- `relluna/services/context_inference/basic.py`
- `relluna/core/normalization.py`
- `relluna/services/read_model/timeline_builder.py`
- testes novos ou expandidos em `tests/test_pipeline_reliability_*.py`, `tests/test_document_taxonomy_rules.py`, `tests/test_layer4_normalization_contract.py`, `tests/test_read_model_*`

### Risco

Medio. Embora o objetivo seja estabilizar, algumas mudancas em warnings, fallback e testes podem revelar comportamento atual incorreto. O risco deve ser controlado com testes de caracterizacao e mantendo os nomes existentes de sinais: `page_evidence_v1`, `layout_spans_v1`, `entities_canonical_v1` e `timeline_seed_v2`.

### Esforco estimado

1 a 2 semanas.

### Criterio de sucesso

- Falhas de parse JSON em `sinais_documentais` viram warning/processing event rastreavel, nao ausencia silenciosa.
- Falta de Tesseract, PyMuPDF, ffmpeg ou Whisper aparece como estado degradado quando relevante.
- `fast -> standard` preserva sinais ou registra substituicao explicita.
- Testes cobrem atestado, parecer, receituario, documento composto, confusao paciente/mae/prestador, falso positivo de CID e data de nascimento.
- `/documents/{documentid}/timeline` tem politica definida: reflete `Layer3.eventos_probatorios` como fonte primaria e usa seeds apenas como fallback compatível com warning estruturado em caso de divergencia.
- `Layer4.data_canonica` nao e preenchida a partir de data de nascimento sem lastro de evento/documento.

## Fase 3: refatoracao estrutural

### Objetivo

Reduzir acoplamento e preparar evolucao segura. A fase deve extrair componentes puros, tipar sinais intermediarios e separar orquestracao da API, mantendo compatibilidade com documentos ja persistidos e endpoints existentes.

### Arquivos afetados

- `relluna/services/ingestion/api.py`
- novo modulo sugerido: `relluna/services/orchestration/pipeline_orchestrator.py`
- novo modulo sugerido: `relluna/services/evidence/signals.py`
- novo modulo sugerido: `relluna/services/page_extraction/people_resolver.py`
- novo modulo sugerido: `relluna/services/entities/document_type_resolver.py`
- novo modulo sugerido: `relluna/services/timeline/timeline_source.py`
- `relluna/services/page_extraction/page_pipeline.py`
- `relluna/services/entities/entities_canonical_v1.py`
- `relluna/services/deterministic_extractors/timeline_seed_v2.py`
- `relluna/services/context_inference/basic.py`
- `relluna/services/derivatives/layer5.py`
- `relluna/services/read_model/timeline_builder.py`
- `relluna/core/document_memory/__init__.py`
- `relluna/core/document_memory/models_v0_2_0.py`
- `relluna/core/document_memory/models.py`
- `relluna/infra/mongo_store.py`
- `relluna/infra/mongo/document_store.py`

### Risco

Medio a alto. O risco vem de mexer em fronteiras entre camadas e contratos de dados. A mitigacao e fazer por adaptadores: primeiro introduzir modelos tipados opcionais e wrappers, depois migrar consumidores, e so no final remover/limpar legados.

### Esforco estimado

3 a 6 semanas.

### Criterio de sucesso

- `ingestion/api.py` deixa de conter a logica principal de orquestracao; endpoints continuam compativeis.
- `page_evidence_v1`, `entities_canonical_v1` e `timeline_seed_v2` possuem modelos/schemas tipados e validacao centralizada.
- `PeopleResolver` e `DocumentTypeResolver` sao testaveis sem FastAPI, Mongo ou OCR real.
- O read model publico de timeline tem uma unica fonte de verdade definida, idealmente `Layer3.eventos_probatorios` ou adaptador equivalente.
- Contratos de `DocumentMemory` ficam consolidados ou com migracao/compatibilidade explicita entre v0.1.0 e v0.2.0.
- Stores Mongo ficam unificados em um repositorio/coordenador claro, com nomes de colecao documentados.
- Pipelines legados permanecem como wrappers ou sao marcados/deprecados sem quebrar testes existentes.

## Fase 4: melhorias de produto e observabilidade

### Objetivo

Transformar o pipeline estabilizado em uma base operacional para uso juridico/produto: timeline mais util, revisao humana, dossie auditavel, metricas de qualidade e observabilidade de processamento.

### Arquivos afetados

- `relluna/services/read_model/*`
- `relluna/services/derivatives/layer5.py`
- `relluna/services/timeline/*`
- `relluna/services/forensics/layer6.py`
- `relluna/services/legal/*`
- `relluna/services/ingestion/api.py`
- novo modulo sugerido: `relluna/services/quality/pipeline_metrics.py`
- novo modulo sugerido: `relluna/services/audit/dossier_builder.py` ou expansao de `relluna/services/export/dossier_builder.py`
- `relluna/services/test_ui/router.py`
- `docker-compose.dev.yml`
- possivel worker/fila em novo modulo `relluna/services/worker/*`
- testes e goldens em `tests/data/golden/*` e `tests/test_*_e2e*.py`

### Risco

Medio. Produto e observabilidade tendem a expor inconsistencias que ja existem. O risco de regressao tecnica e menor se Fases 1 a 3 estiverem concluidas, mas o risco de decisao de produto aumenta: e preciso definir taxonomia de eventos, criterios de prontidao juridica e politica de revisao humana.

### Esforco estimado

4 a 8 semanas para uma primeira versao utilizavel; evolucao continua depois disso.

### Criterio de sucesso

- Timeline inclui taxonomia minima de eventos medicos e correlatos: internacao, consulta, laudo, receita, exame, afastamento, alta, encaminhamento, pagamento/recibo e protocolo administrativo.
- Eventos exibem claramente se sao observados, inferidos, estimados ou pendentes de revisao.
- Read model contem contadores de qualidade: total de eventos, eventos com bbox, eventos sem lastro exato, entidades criticas ausentes, warnings e `needs_review_count`.
- Existe dossie auditavel por documento com hash, artefato, paginas, anchors, eventos, citacoes e warnings.
- Existe fluxo de revisao humana para confirmar/corrigir paciente, prestador, data documental, CID e eventos.
- OCR/ASR/processamento pesado pode rodar fora do request HTTP ou pelo menos expor estado de job.
- Logs/processing events permitem responder: qual etapa rodou, qual falhou, qual foi pulada, qual dependencia faltou e qual sinal foi sobrescrito.
- Goldens anonimizados por tipo documental passam em testes de regressao semantica.

## Ordem recomendada de execucao

1. Fechar Fase 1 antes de qualquer refatoracao: testes de caracterizacao e limpeza de riscos obvios.
2. Executar Fase 2 ate cobrir os principais erros clinicos e fallbacks silenciosos.
3. Iniciar Fase 3 apenas quando os testes de confiabilidade estiverem estabilizados.
4. Iniciar Fase 4 em paralelo somente para prototipos de read model/UI, sem depender deles como fonte de verdade ate a Fase 3 consolidar contratos.

## Principio de compatibilidade

Durante todas as fases, manter leitura das chaves atuais em `Layer2.sinais_documentais` e dos campos legados de `DocumentMemory`. Novos modelos tipados devem ser introduzidos como adaptadores, nao como substituicoes abruptas. Endpoints publicos devem permanecer compativeis ate haver uma versao nova documentada.
