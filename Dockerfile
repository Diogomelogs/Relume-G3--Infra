FROM python:3.12-slim

WORKDIR /app

# Copia TODO o código primeiro
COPY . .

# Instala dependências do projeto
RUN pip install -U pip && pip install .

# Comando padrão: sobe a API
CMD ["uvicorn", "relluna.services.ingestion.api:app", "--host", "0.0.0.0", "--port", "8000"]
