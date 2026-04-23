# AGENTS.md

## Produto
A Relluna é uma plataforma de inteligência médico-jurídica para advogados.
O objetivo central é transformar documentos médicos em eventos probatórios auditáveis, com evidência navegável e confiança explícita.

## Verdades do domínio
- Nunca tratar evento inferido como observado.
- Nunca tratar data de nascimento como data documental.
- Nunca expor persistência fake como se fosse persistência real.
- Sempre priorizar evidência com documento, página, snippet e bbox.
- A timeline pública deve convergir para uma única fonte de verdade.
- Enquanto a migração não terminar, qualquer compatibilidade temporária deve ser explicitada em documentação e testes.

## Estado atual do projeto
Leia antes de começar qualquer tarefa:
- DIAGNOSTICO_PIPELINE.md
- PLANO_PIPELINE.md
- BENCHMARK_MEDICO_JURIDICO.md
- ARQUITETURA_RELLUNA.md, quando existir no checkout

## Prioridade atual
Estamos na Fase 1:
1. criar base de benchmark e testes de caracterização;
2. remover ambiguidades perigosas;
3. documentar política da timeline;
4. impedir regressões semânticas críticas.

## Regras de trabalho
- Para qualquer tarefa complexa, planeje antes de codar.
- Faça diffs pequenos e revisáveis.
- Não faça refatoração ampla sem antes estabilizar com testes.
- Atualize documentação junto com o código.
- Ao alterar comportamento, adicione ou atualize testes.
- Ao encontrar código legado/quebrado, marque explicitamente como legado ou corrija com cobertura mínima.
- Não introduza dependências novas sem justificativa.

## Áreas críticas
- relluna/services/ingestion/api.py
- relluna/services/page_extraction/page_pipeline.py
- relluna/services/entities/entities_canonical_v1.py
- relluna/services/deterministic_extractors/timeline_seed_v2.py
- relluna/services/context_inference/basic.py
- relluna/services/derivatives/layer5.py
- relluna/services/read_model/timeline_builder.py

## O que significa "feito"
Uma tarefa só está pronta quando:
1. o código compila;
2. os testes relevantes passam;
3. a documentação foi atualizada;
4. não há regressão óbvia no benchmark;
5. o resultado foi resumido com arquivos alterados, risco e validação executada.

## Comandos esperados
- Setup: make setup
- Testes: make test
- Benchmark: make benchmark
- API local: make api
- Lint: make lint
