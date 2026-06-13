# Relluna

A Relluna transforma documentos médicos e correlatos (atestados, receituários, laudos, pareceres) em uma `DocumentMemory` auditável para uso médico-jurídico: cadeia de custódia, evidência determinística com lastro (página, snippet, bbox), inferência controlada e timeline probatória revisável por humanos.

## Arquitetura em uma linha

```text
/ingest → preflight → extração (PDF/OCR/páginas) → entidades canônicas
       → timeline seed → inferência (Layer3) → normalização (Layer4)
       → read models (Layer5) → MongoDB
```

O ponto de entrada vivo do produto é a API FastAPI em `relluna/services/ingestion/api.py`. Detalhes em [docs/ARQUITETURA_RELLUNA.md](docs/ARQUITETURA_RELLUNA.md).

## Estrutura do repositório

| Caminho | Papel |
| --- | --- |
| `relluna/core/` | Contratos da `DocumentMemory` (Layer0–Layer6) e normalização |
| `relluna/services/` | Pipeline real: ingestão/API, decomposição de PDF, extratores determinísticos, inferência contextual, derivados e read models |
| `relluna/infra/` | MongoDB, Azure Blob, segredos |
| `frontend/` | Protótipo navegável estático servido em `/demo` (dados mockados) |
| `tests/` | Suite de testes + goldens médico-jurídicos |
| `scripts/benchmark_runner.py` | Benchmark auditável que gera `BENCHMARK_MEDICO_JURIDICO.md` |
| `docs/` | Arquitetura, plano e diagnóstico do pipeline |

## Configuração de desenvolvimento

1. Clone o repositório
2. Copie `.env.example` para `.env` e preencha com suas credenciais
3. Crie ambiente virtual: `python -m venv .venv && source .venv/bin/activate`
4. Instale dependências do sistema: `tesseract-ocr`, `poppler-utils`, `ffmpeg`
5. Instale dependências: `pip install -e ".[dev]" && pip install -r requirements-dev.txt`
6. Instale pre-commit hooks: `pre-commit install`

**Atenção:** o arquivo `.env` JAMAIS deve ser commitado. O pre-commit hook bloqueia commits que contenham segredos detectáveis.

## Comandos principais

```bash
make test            # suite de testes (APP_ENV=test)
make lint            # ruff em relluna, tests, scripts e tools
make benchmark       # gera BENCHMARK_MEDICO_JURIDICO.md
make benchmark-gate  # falha em regressão semântica crítica (usado no CI)
make api             # sobe a API local em :8000
```

Com Docker: `docker compose -f docker-compose.dev.yml up` (Mongo + API).

## Demo frontend

Protótipo navegável estático em `frontend/`, servido pela rota `/demo` da API local:

```bash
make api
# abra http://localhost:8000/demo
```

Princípios do protótipo:

- usa dados mockados plausíveis e explicitamente não representa integração real com auth, billing ou persistência;
- preserva a semântica do domínio Relluna: custódia, evidência determinística, inferência controlada, revisão humana e timeline pública;
- qualquer métrica exibida usa o benchmark interno atual do checkout local ou permanece rotulada como demo.

## Estado atual (honesto)

- Funciona de ponta a ponta: ingestão, decomposição de PDF com estratégia de OCR por página, entidades canônicas com lastro, timeline probatória e read models persistidos no Mongo.
- Ainda não existe: geração real de derivados binários (thumbnail/preview — listas ficam vazias por contrato), worker assíncrono com fila, frontend integrado à API e autenticação/multiusuário.
- Integrações externas (Azure OpenAI, Azure Blob) são opcionais e degradam de forma explícita quando ausentes.
