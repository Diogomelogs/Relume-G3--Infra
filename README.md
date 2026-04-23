# Relume-G3--Infra

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
