📘 Relluna Labs — Infraestrutura G3 (2025–2027)

Do analógico ao presente. Preservando memórias, conectando gerações.

Visão Geral

A Relluna Labs é um ecossistema dedicado a transformar memórias analógicas e digitais em presença, narrativa e continuidade.
Nosso propósito é possibilitar que famílias, criadores, instituições, escolas e empresas possam:

Digitalizar memórias analógicas

Organizar fotos, vídeos e áudios

Catalogar automaticamente com IA

Criar linhas do tempo narrativas

Compartilhar acervos, histórias e reluminações

Este repositório documenta a infraestrutura G4, que estabelece a base técnica do projeto para operação real em ambiente cloud, com arquitetura mínima, enxuta e totalmente funcional.

Objetivo da Infraestrutura

A fase G3 tem como foco:

✔ Tornar a Relluna funcional e pública

Permitir que usuários possam realmente fazer upload, processar mídias, gerar contexto com IA e acessar suas memórias em uma timeline viva.

✔ Criar a base para o ecossistema completo

Esta infraestrutura estabelece a fundação para:

Relluna Scan (digitalização assistida)

Relluna Cloud (álbum em nuvem + IA)

Relluna Atlas (catalogação profunda para B2B e acervos institucionais)

Relluna Moments / Reluminações (narrativas emocionais)

Integração com dispositivos físicos (dock multimídia, leitores magnéticos, etc.)

✔ Criar documentação, governança e prova de anterioridade

Incluindo arquitetura, fluxo, estrutura de dados e APIs.

Arquitetura do G3

A infraestrutura utiliza uma combinação de serviços cloud e IA moderna, garantindo escalabilidade e um fluxo contínuo entre upload, processamento e consumo dos dados.

Componentes Principais
Componente	Tecnologia	Função
API Relluna	FastAPI (Python) + Azure App Service	Core da aplicação. Recebe uploads, processa mídias, gera metadados e comunica com bancos e storages.
Armazenamento de Mídia	Azure Blob Storage	Guarda fotos, vídeos e áudios enviados pelos usuários.
Banco de Dados	MongoDB Atlas	Armazena registros da timeline, dados de processamento e metadados.
IA de Visão Computacional	Azure Vision	Extrai tags, descrições, rostos, elementos e contexto visual.
IA de Linguagem	OpenAI GPT / Azure OpenAI	Constrói narrativas curtas, legendas e interpretações.
Frontend G3 Web	Next.js 14	Interface mínima funcional com upload, timeline e detalhe de mídia.
Integração Código–Infra	GitHub + GitHub Actions	Deploy contínuo automatizado.
Observabilidade	Kudu / Azure Monitor	Logs, métricas e inspeção da aplicação.
Fluxo Operacional G3
Fluxo mínimo:

Upload

Usuário envia foto/vídeo/áudio via web

Arquivo é versionado e enviado ao Blob Storage

Processamento

Azure Vision extrai descrição, objetos, tags e contexto

OpenAI gera narrativa curta (opcional)

Metadados são gravados no MongoDB Atlas

Timeline

Dados são exibidos em ordem cronológica

Usuário acessa o detalhe de cada mídia

Reluminação (opcional)

IA compila momentos especiais em formato narrativo

Priorizado para fases G4–G5

Rotas da API
POST /upload

Recebe upload de mídia e gera versão Blob.

POST /process

Aplica Vision e organiza metadados.

GET /timeline?user_id=

Retorna timeline viva do usuário.

POST /narrate

Gera narrativa emocional (modo inicial).

GET /health

Verificação da integridade da API.

Documentação completa:
/docs (Swagger UI automaticamente gerado)

Estrutura de Arquivos do Repositório
root/
│
├── api/main.py             # API FastAPI principal
├── requirements.txt        # Dependências
├── scripts/                # Ferramentas internas
├── tools/                  # Utilitários e funções auxiliares
├── frontend/ (opcional)    # G3 Web App (outro repositório)
└── README.md               # Este documento

Prova de Anterioridade — Projeto Relluna

Este repositório e suas versões armazenam:

Documentação técnica

Arquitetura do produto

Estrutura de banco e dados

Fluxos operacionais

Interface mínima G3

Interações com IA

APIs e endpoints

Essa documentação funciona como prova de anterioridade, importante para:

Registro de marca

Proteção intelectual

Histórico de desenvolvimento

Comprovação de autoria

Defesa contra plágio ou disputas

Escopo da Prova

A prova inclui:

Estrutura e narrativa do ecossistema Relluna

Arquitetura e fluxo G0 → G3

Pitch inicial, visão de longo prazo e roadmap conceitual

Modelos de dados

Funções de IA (Vision / Narrate)

Desenho das rotas da API

Processos de digitalização

Propostas de uso B2C, B2B e Institucional

Próximas Fases
G4 – Experiência e Estética

Home refinada

Timeline emocional (linha de vida)

Carrossel de Reluminações

Interface mobile-first

Estética marinha/esmeralda

Micro animações respirantes

G5 – Relluna Scan

Digitalização assistida

Orientação de enquadramento

Correções automáticas

Captura multi-dispositivo

G6 – Relluna Atlas

Catalogação avançada

Redes de relações

Mapa cruzado de acervos

Pesquisas semânticas

Licença e Direitos

Todo o código, documentação, fluxos, modelos e arquitetura pertencem à Relluna Labs.
É proibida a utilização comercial, parcial ou total, sem autorização formal.

Contato

Relluna Labs - preservação
Founder: Diogo D'Melo
E-mail: diogomelogs@gmail.com

🌙 Relluna – Do analógico ao presente.
