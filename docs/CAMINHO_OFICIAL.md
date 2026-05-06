# Caminho Oficial do Sistema

Data de referência do checkout: `2026-05-06`

## Fonte de verdade operacional

O caminho vivo do produto passa por `relluna/services/ingestion/api.py`.

Ponto de entrada real:

- `relluna.services.ingestion.api:app`

Fluxo oficial:

1. `/ingest`
2. `/extract/{documentid}`
3. `/infer_context/{documentid}`
4. `/documents/{documentid}`
5. `/documents/{documentid}/timeline`
6. `/documents/{documentid}/case`
7. `/documents/{document_id}/narrative`
8. `/process`

## Endpoints ativos

- `GET /health`
- `POST /ingest`
- `POST /process`
- `POST /extract/{documentid}`
- `POST /infer_context/{documentid}`
- `GET /documents/{documentid}`
- `GET /documents/{document_id}/narrative`
- `GET /documents/{documentid}/timeline`
- `GET /documents/{documentid}/case`
- `GET /read-model/documents`
- `GET /read-model/search`
- `GET /read-model/search_text`
- `GET /test-ui-lab`
- `GET /demo`
- `GET /demo/{asset_path:path}`

## Fluxo real de ingestão ao produto

### Ingestão

Arquivo: `relluna/services/ingestion/api.py`

- Recebe upload
- Calcula SHA-256
- Deduplica por `layer0.contentfingerprint`
- Persiste artefato local em `.uploads`
- Cria `DocumentMemory` com `layer0` e `layer1`

### Extração

Arquivo: `relluna/services/ingestion/api.py`

Estágios efetivamente chamados pelo caminho oficial:

- `extract_basic`
- `decompose_pdf_into_subdocuments`
- `apply_page_analysis`
- `apply_legal_extraction`
- `apply_entities_canonical_v1`
- `apply_transcription_to_layer2`, quando mídia exigir

Seleção de modo:

- `fast`
- `standard`
- `forensic`

### Inferência

Arquivo: `relluna/services/ingestion/api.py`

Estágios efetivamente chamados:

- `seed_timeline_v2`
- `infer_layer3`
- `apply_layer4`
- `apply_layer5`

### Produto / leitura

Arquivos efetivamente usados:

- `relluna/services/read_model/timeline_builder.py`
- `relluna/services/read_model/case_builder.py`
- `relluna/services/read_model/endpoints.py`
- `relluna/services/derivatives/layer5.py`

## Módulos legados ou compatibilidade

Os módulos abaixo não são a fonte oficial do produto e existem apenas para
compatibilidade com código ou testes antigos:

- `relluna/core/basic_pipeline.py`
- `relluna/core/inference_pipeline.py`
- `relluna/core/canonical_pipeline.py`
- `relluna/core/archival_pipeline.py`
- `relluna/core/semantic_pipeline.py`
- `relluna/core/full_pipeline.py`
- `relluna/core/document_memory/models.py`
- `relluna/services/timeline/*`

Regras:

- Não promover novos consumidores para `relluna/core/*_pipeline.py`.
- Não usar `relluna/core/document_memory/models.py` como contrato novo.
- Não usar `relluna/services/timeline/*` como fonte pública da timeline.

## Observações importantes

- `relluna/services/legal/legal_pipeline.py` é um hook compatível e atualmente
  não grava semântica jurídica em `Layer2`.
- `relluna/services/derivatives/layer5.py` ainda controla read models e estado
  de persistência de derivados; essa superfície precisa ser tratada como parte
  do caminho oficial até a migração terminar.
- `relluna/services/read_model/store.py` expõe busca HTTP, mas a persistência
  do read model precisa ser explicitamente conectada ao write path.
