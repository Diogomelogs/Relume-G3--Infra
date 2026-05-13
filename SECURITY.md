# Política de Segurança da Relluna

## Reportar vulnerabilidades

Se você encontrou uma vulnerabilidade na Relluna, envie email para diogomelogs@gmail.com com:
- Descrição da vulnerabilidade
- Passos para reproduzir
- Impacto potencial

Compromisso de resposta em até 48h e divulgação responsável.

## Práticas de segurança

A Relluna trata dados sensíveis (documentos médicos, jurídicos, dados pessoais sob LGPD).

- Segredos gerenciados via Azure Key Vault em produção
- Nenhum segredo versionado (`.gitignore` enforced + pre-commit detect-secrets)
- CI executa gitleaks em cada push
- Rotação trimestral de credenciais recomendada
- Princípio do menor privilégio em identidades de aplicação
- Dados em trânsito via TLS 1.2+
- Dados em repouso criptografados (Azure Storage e MongoDB Atlas)

## Conformidade

- LGPD (Lei 13.709/2018) — dados pessoais sensíveis (art. 11, saúde)
- Resolução CNJ 615/2025 — princípios de IA no judiciário
