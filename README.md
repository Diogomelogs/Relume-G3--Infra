# Relume-G3--Infra

## Configuração de desenvolvimento

1. Clone o repositório
2. Copie `.env.example` para `.env` e preencha com suas credenciais
3. Crie ambiente virtual: `python -m venv .venv && source .venv/bin/activate`
4. Instale dependências: `pip install -e ".[dev]" && pip install -r requirements-dev.txt`
5. Instale pre-commit hooks: `pre-commit install`
6. Rode os testes: `make test`

**Atenção:** o arquivo `.env` JAMAIS deve ser commitado. O pre-commit hook bloqueia commits que contenham segredos detectáveis.

## Demo frontend

O repositório agora inclui um protótipo navegável estático em `frontend/`, servido localmente pela rota `/demo`.

Princípios do protótipo:

- usa dados mockados plausíveis e explicitamente não representa integração real com auth, billing ou persistência;
- preserva a semântica do domínio Relluna: custódia, evidência determinística, inferência controlada, revisão humana e timeline pública;
- qualquer métrica exibida usa o benchmark interno atual do checkout local ou permanece rotulada como demo.

Para visualizar com a API local:

```bash
make api
```

Depois abra:

```text
http://localhost:8000/demo
```
