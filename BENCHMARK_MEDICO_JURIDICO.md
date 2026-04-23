# Benchmark medico-juridico auditavel

Gerado em: `2026-04-23T18:39:28.862119+00:00`
Casos avaliados: **11**
Score geral: **88.94/100**

## Score por eixo

| Eixo | Score |
| --- | ---: |
| entidades | 91.21 |
| eventos | 81.82 |
| evidencia | 91.67 |
| confiabilidade | 98.16 |
| utilidade_juridica | 81.82 |

## Métricas explícitas

| Métrica | Score |
| --- | ---: |
| utilidade_juridica | 81.82 |
| ancoragem_evidencia | 91.67 |
| revisao_humana | 78.79 |
| consistencia_timeline | 90.91 |

## Casos

| Caso | Score | Entidades | Eventos | Evidencia | Confiabilidade | Utilidade juridica | Regressões |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 001_atestado_afastamento | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 0 |
| 002_parecer_cid | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 0 |
| 003_regressao_data_nascimento | 54.46 | 80.00 | 0.00 | 100.00 | 92.31 | 0.00 | 5 |
| 004_receituario_vs_atestado | 96.00 | 80.00 | 100.00 | 100.00 | 100.00 | 100.00 | 1 |
| 005_documento_composto | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 0 |
| 006_paciente_vs_mae | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 0 |
| 007_prestador_falso_positivo | 87.00 | 60.00 | 100.00 | 75.00 | 100.00 | 100.00 | 4 |
| 008_cid_espurio | 93.33 | 83.33 | 100.00 | 83.33 | 100.00 | 100.00 | 3 |
| 009_evento_inferido_sem_lastro_exato | 87.50 | 100.00 | 100.00 | 50.00 | 87.50 | 100.00 | 3 |
| 010_divergencia_seed_layer3 | 60.00 | 100.00 | 0.00 | 100.00 | 100.00 | 0.00 | 1 |
| 011_evento_estimado_com_explicacao | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 | 0 |

## Métrica de consistência

- timeline_consistency_score: **90.91/100**

## Regressões explícitas

- `003_regressao_data_nascimento` [critical] entidades: Campo crítico `document_date` divergente: esperado `2024-03-05`.
- `003_regressao_data_nascimento` [critical] eventos: Evento obrigatório ausente: `document_issue_date` em `2024-03-05`.
- `003_regressao_data_nascimento` [critical] eventos: Evento proibido presente: `document_issue_date` em `1980-01-20`.
- `003_regressao_data_nascimento` [critical] confiabilidade: Data documental usa data proibida `1980-01-20`, provável data de nascimento.
- `003_regressao_data_nascimento` [major] confiabilidade: `entity:document_date` exige revisão humana, mas não expõe review_state.
- `004_receituario_vs_atestado` [critical] entidades: Tipo documental divergente: esperado `receituario`.
- `007_prestador_falso_positivo` [critical] entidades: Campo crítico `provider` divergente: esperado `DR. GUSTAVO LEAL`.
- `007_prestador_falso_positivo` [critical] entidades: Campo `provider` contém valor proibido `SAO PAULO`.
- `007_prestador_falso_positivo` [major] evidencia: Lastro incompleto para `entity:provider`; exige página, snippet e bbox.
- `007_prestador_falso_positivo` [major] confiabilidade: `entity:provider` exige revisão humana, mas não expõe review_state.
- `008_cid_espurio` [critical] entidades: Campo `cids` contém valor proibido `ABC12`.
- `008_cid_espurio` [major] evidencia: Lastro incompleto para `entity:cids`; exige página, snippet e bbox.
- `008_cid_espurio` [major] confiabilidade: `entity:cids:1` exige revisão humana, mas não expõe review_state.
- `009_evento_inferido_sem_lastro_exato` [major] evidencia: Lastro incompleto para `entity:document_date`; exige página, snippet e bbox.
- `009_evento_inferido_sem_lastro_exato` [major] evidencia: Lastro incompleto para `event:parecer_emitido`; exige página, snippet e bbox.
- `009_evento_inferido_sem_lastro_exato` [major] confiabilidade: `entity:document_date` não distingue observado/inferido/estimado.
- `010_divergencia_seed_layer3` [critical] eventos: Evento obrigatório ausente: `document_issue_date` em `2024-10-21`.

## Estrutura proposta

- Entidades: paciente, prestador, mãe, CID e data documental como campos críticos, com valor esperado e lastro.
- Eventos: timeline com tipos jurídicos úteis, data, título, descrição, entidades vinculadas e estado observado/inferido/estimado.
- Evidência: cada entidade/evento relevante deve apontar página, snippet, bbox e caminho lógico da fonte.
- Confiabilidade: distinção explícita entre observado, inferido e estimado, confiança numérica e revisão humana quando necessário.
- Utilidade jurídica: penaliza eventos sem descrição, sem entidades críticas, sem estado de revisão ou sem relevância para advogado.
