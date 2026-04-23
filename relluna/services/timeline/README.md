# Politica de Timeline Legada

Data: 2026-04-09

## Fonte oficial atual

A timeline oficial do produto converge para:

1. `Layer3.eventos_probatorios` como fonte primária semântica.
2. `relluna/services/read_model/timeline_builder.py` como superfície pública.
3. `timeline_seed_v2` apenas como fallback compatível para documentos legados.

Regra: o diretório `relluna/services/timeline/*` não é a fonte oficial da timeline pública.

## Classificação dos arquivos

| Arquivo | Classificação | Política |
| --- | --- | --- |
| `date_anchor.py` | legado | helper antigo de ancoragem; manter apenas como referência/compatibilidade |
| `date_extractor.py` | legado | extrator simplificado, fora do pipeline oficial atual |
| `event_builder.py` | wrapper compatível | mantido com wrapper `build_events` para não quebrar o caminho paralelo |
| `timeline_attach.py` | morto | grava em `layer6.timeline_events`, fora da fonte oficial |
| `timeline_builder.py` | legado | builder simplificado, duplicado em relação ao read model oficial |
| `timeline_pipeline.py` | wrapper compatível | pipeline paralelo antigo; não participa do fluxo real da API |

## Regra de manutenção

- Não remover abruptamente sem cobertura e sem documentação.
- Não promover novos consumidores para `relluna/services/timeline/*`.
- Qualquer uso novo de timeline deve apontar para `Layer3.eventos_probatorios` e para `relluna/services/read_model/timeline_builder.py`.
