# Diagnostico Tecnico e de Produto do Pipeline Relluna

Data da analise: 2026-04-07

## Resumo executivo

O projeto ja expressa uma proposta de produto forte: transformar documentos medicos e correlatos em uma `DocumentMemory` com cadeia de custodia, extracao deterministica, inferencia contextual, normalizacao e read models de timeline/entidades. A intencao arquitetural aparece em camadas: Layer0 para custodia, Layer1 para artefatos, Layer2 para fatos observaveis, Layer3 para inferencias, Layer4 para normalizacao canonica, Layer5 para derivados/read models e Layer6 para indexacao/otimizacao.

O fluxo principal real hoje passa pela API em `relluna/services/ingestion/api.py`, nao pelo pipeline legado em `relluna/core/full_pipeline.py`. A API faz ingestao, salva arquivo local em `.uploads`, cria `DocumentMemory`, escolhe modo de processamento (`fast`, `standard`, `forensic`) e roda uma sequencia de extratores e inferencias: `extract_basic`, decomposicao/OCR de PDF, analise por pagina, consolidacao de entidades canonicas, sementes de timeline, inferencia Layer3, normalizacao Layer4 e Layer5.

O alinhamento com o produto e parcial. O pipeline ja tem componentes para auditoria e lastro (`processingevents`, `custodychain`, `EvidenceRef`, `bbox`, `snippet`, `review_state`), mas a confiabilidade ainda depende de heuristicas regex/textuais e de muitos fallbacks. Em especial, a timeline final so nasce de `entities_canonical_v1` e cobre poucos tipos/eventos clinicos. Documentos com datas relevantes mas sem tipo canonico esperado podem ficar sem timeline util.

Os principais riscos tecnicos sao: multiplos contratos de `DocumentMemory`, duplicacao de pipelines e read models, regra solta de taxonomia aparentemente quebrada, reprocessamento duplicado no caminho de escalonamento, storage/Layer5 ainda fake, repositorio com `.venv`, `.env`, uploads e caches versionados, e persistencia dividida entre stores diferentes. Os principais riscos de produto sao: classificacao errada de documentos compostos, confusao entre data de nascimento e data do documento, falso positivo de CID/CRM/pessoa, eventos estimados tratados perto de eventos observados, e uma timeline que pode parecer mais conclusiva do que a evidencia permite.

## Arquivos centrais lidos

- `relluna/services/ingestion/api.py`: ponto de entrada FastAPI e orquestrador real do pipeline de ingestao/processamento.
- `relluna/core/document_memory/__init__.py`: contrato interno atualmente importado como `DocumentMemory`.
- `relluna/core/document_memory/models_v0_2_0.py`: contrato canonico v0.2.0 alternativo, mas nao e o unico contrato usado.
- `relluna/core/document_memory/layer0.py`: custodia, integridade, eventos de processamento e cadeia de custodia.
- `relluna/core/document_memory/layer1.py`: artefatos, tipo de midia e origem.
- `relluna/core/document_memory/layer2.py`: evidencias deterministicas e `sinais_documentais`.
- `relluna/core/document_memory/layer3.py`: inferencias contextuais, entidades semanticas, classificacoes de pagina e eventos probatorios.
- `relluna/core/document_memory/layer4_canonical.py`: normalizacao canonica de datas, local, entidades e tags.
- `relluna/services/deterministic_extractors/basic.py`: extrator basico por midia e entrada do caminho deterministico.
- `relluna/services/pdf_decomposition/decompose_pdf.py`: estrategia native/hybrid/OCR para PDFs, subdocumentos e texto literal.
- `relluna/services/page_extraction/page_pipeline.py`: analise por pagina, anchors, signal zones, page evidence e extracao de entidades basicas/clinicas.
- `relluna/services/page_extraction/page_entity_extractors.py`: regexes administrativas e pessoas.
- `relluna/services/page_extraction/page_clinical_extractors.py`: regexes clinicas, CID, CRM, atendimento, especialidade e prestador.
- `relluna/services/entities/entities_canonical_v1.py`: consolidacao multi-pagina de paciente, prestador, CIDs, data documental e tipo documental.
- `relluna/services/deterministic_extractors/entities_hard_v2.py`: extracao hard de CPF/CNPJ/CRM/CID/datas/afastamento.
- `relluna/services/deterministic_extractors/timeline_seed_v2.py`: geracao de sementes de timeline a partir de `entities_canonical_v1`.
- `relluna/services/context_inference/basic.py`: inferencia Layer3, classificacao documental e eventos probatorios.
- `relluna/core/normalization.py`: promocao para Layer4.
- `relluna/services/derivatives/layer5.py`: derivados placeholder e read models `timeline_v1` e `entity_summary_v1`.
- `relluna/services/read_model/timeline_builder.py`: endpoint `/documents/{documentid}/timeline`, independente do read model de Layer5.
- `relluna/infra/mongo_store.py` e `relluna/infra/mongo/document_store.py`: persistencia com duas abordagens diferentes.
- `debug_run_pipeline.py`, `debug_profile_pipeline.py`, `tools/debug_pipeline_trace.py`: scripts de debug que documentam o fluxo esperado por etapas.

## Arquitetura atual em linguagem simples

O sistema recebe um arquivo e cria uma memoria estruturada chamada `DocumentMemory`.

Essa memoria e organizada em camadas:

- Layer0: identidade, hash, custodia, eventos de processamento e prontidao juridica.
- Layer1: artefato original e metadados de midia/origem.
- Layer2: fatos observaveis e deterministas, como OCR, dimensoes, numero de paginas, spans, entidades hard e sinais documentais em JSON serializado.
- Layer3: inferencias contextuais, classificacao de documento, entidades semanticas e eventos probatorios.
- Layer4: normalizacao canonica, como data canonica, periodo, local, entidades e tags.
- Layer5: derivados e read models para frontend.
- Layer6: embeddings/indexacao, ainda pouco integrado no fluxo real da API.

O ponto de entrada de produto e a API:

- `/ingest`: cria `DocumentMemory` minima com Layer0/Layer1 e persiste.
- `/extract/{documentid}`: roda extracao deterministica e sinais de pagina.
- `/infer_context/{documentid}`: roda timeline seeds, Layer3, Layer4 e Layer5.
- `/process`: faz ingestao, extracao e inferencia em uma chamada.
- `/documents/{documentid}/timeline`: gera uma timeline por documento a partir de `timeline_seed_v2` ou `timeline_seed_v1`.

Ha tambem pipelines em `relluna/core/*_pipeline.py`, mas eles parecem legados ou usados por testes antigos. O fluxo mais atual esta concentrado em `relluna/services/ingestion/api.py` e nos servicos em `relluna/services`.

## Fluxo principal do pipeline

1. Upload/ingestao

`relluna/services/ingestion/api.py` recebe `UploadFile`, calcula SHA-256, deduplica por `layer0.contentfingerprint`, grava o arquivo em `.uploads`, cria `Layer0` e `Layer1` e salva via `relluna/infra/mongo_store.py`. Para imagens, tenta registrar resultado NSFW em `metadados_nativos`.

2. Decisao de modo

`_collect_preflight_signals` e `_decide_processing_mode` avaliam midia, PDF, quantidade de paginas, texto nativo e rotacao. O modo pode ser:

- `fast`: PDF simples com texto nativo.
- `standard`: caminho default e PDFs sem texto nativo.
- `forensic`: audio/video ou PDF rotacionado.

3. Extracao deterministica inicial

`relluna/services/deterministic_extractors/basic.py` garante `Layer2`, extrai dimensoes/EXIF/OCR para imagens, numero de paginas para PDFs, duracao simples para audio/video e, para PDF, delega OCR textual completo para `decompose_pdf_into_subdocuments`.

4. Decomposicao/OCR de PDF

`relluna/services/pdf_decomposition/decompose_pdf.py` tenta texto nativo com `pypdf`, decide estrategia `native`, `hybrid` ou `ocr`, normaliza paginas com PyMuPDF/Tesseract quando necessario, gera `normalized_pages_v1`, `ocr_pages_v1`, `layout_spans_v1`, `subdocuments_v1` e popula `layer2.texto_ocr_literal`.

5. Analise por pagina

`relluna/services/page_extraction/page_pipeline.py` usa `split_document_by_page`, extratores administrativos e clinicos, taxonomia de pagina, anchors e signal zones para gerar `page_evidence_v1`. Esse e um dos blocos mais importantes para auditoria porque tenta conectar valores a pagina, bbox, snippet e source_path.

6. Extracao juridica

`relluna/services/legal/legal_pipeline.py` e atualmente um hook de compatibilidade que nao grava sinais interpretativos em Layer2. Isso e bom conceitualmente, porque classificacao juridica/contextual deve ficar em Layer3, mas o nome da etapa pode sugerir mais do que ela faz.

7. Consolidacao canonica de entidades

`relluna/services/entities/entities_canonical_v1.py` consolida `page_evidence_v1` e `layout_spans_v1` em um sinal Layer2 chamado `entities_canonical_v1`. Ele escolhe paciente, mae, prestador, CRM, CIDs, data documental, tipo documental e, para atestados, internacao/afastamento.

Observacao: apesar do nome "canonical", esse sinal fica em Layer2. Ele e semanticamente mais rico do que um fato bruto, entao existe uma tensao de fronteira Layer2/Layer3.

8. Sementes de timeline

`relluna/services/deterministic_extractors/timeline_seed_v2.py` le `entities_canonical_v1` e gera `timeline_seed_v2`. Para `atestado_medico`, prioriza internacao e afastamento. Para `parecer_medico`, usa data documental e eventualmente CIDs. Datas de nascimento e datas candidatas genericas sao marcadas para nao entrar na timeline.

9. Inferencia Layer3

`relluna/services/context_inference/basic.py` classifica o tipo documental, gera entidades semanticas regex e cria `eventos_probatorios` a partir de `timeline_seed_v2`. Os eventos recebem `event_id`, `event_type`, `title`, `description`, `date_iso`, `entities`, `citations`, `confidence`, `review_state` e `provenance_status`.

10. Normalizacao Layer4

`relluna/core/normalization.py` promove uma data para `layer4.data_canonica`, periodo, local, entidades e tags. A data vem de temporalidades de Layer3, EXIF ou primeiro candidato em `page_evidence_v1`.

11. Layer5 e read models

`relluna/services/derivatives/layer5.py` cria derivados placeholder (`generated://...`, `https://local.blob/fake`) e gera `read_models.timeline_v1` e `entity_summary_v1`. Em paralelo, `relluna/services/read_model/timeline_builder.py` tem outro read model usado pelo endpoint `/documents/{documentid}/timeline`, mais simples e baseado diretamente em `timeline_seed_v2`.

## Modulos mais importantes e papeis

- `relluna/services/ingestion/api.py`: orquestracao real do produto, endpoints, decisao adaptativa, tracking de etapas.
- `relluna/core/document_memory/*`: contrato de dados e fronteiras entre custodia, fatos, inferencias, normalizacao e derivados.
- `relluna/services/deterministic_extractors/basic.py`: extracao inicial especifica por midia.
- `relluna/services/pdf_decomposition/decompose_pdf.py`: OCR/decomposicao de PDF, essencial para documentos escaneados.
- `relluna/services/page_extraction/page_pipeline.py`: construcao de evidencia auditavel por pagina.
- `relluna/services/page_extraction/page_entity_extractors.py`: entidades administrativas.
- `relluna/services/page_extraction/page_clinical_extractors.py`: entidades clinicas.
- `relluna/services/entities/entities_canonical_v1.py`: consolidacao multi-pagina e fonte principal da timeline atual.
- `relluna/services/deterministic_extractors/timeline_seed_v2.py`: transformacao de entidades canonicas em sementes temporais.
- `relluna/services/context_inference/basic.py`: classificacao contextual e eventos probatorios.
- `relluna/core/normalization.py`: normalizacao Layer4.
- `relluna/services/derivatives/layer5.py`: read models ricos e derivados placeholder.
- `relluna/services/read_model/*`: busca/listagem/read-models de frontend, ainda parcialmente desconectados do fluxo de escrita.
- `relluna/infra/mongo_store.py`: persistencia async usada pela API.

## Gargalos, acoplamentos e duplicacoes

### Gargalos

- OCR de PDF em `decompose_pdf_into_subdocuments.py` pode ser caro: renderiza paginas, roda orientacao/OCR com Tesseract e cria imagens temporarias.
- `fast` pode escalar para `standard` depois de ja executar `extract_basic`, `apply_page_analysis`, `apply_legal_extraction` e `apply_entities_canonical_v1`, duplicando trabalho.
- `page_pipeline.py` faz muita coisa em um arquivo grande: normalizacao, scoring, resolucao de pessoas, anchors, signal zones, taxonomia e payload final.
- Tesseract/PyMuPDF/ffmpeg/whisper sao dependencias externas com degradacao silenciosa em alguns pontos.

### Acoplamentos excessivos

- `entities_canonical_v1.py`, `timeline_seed_v2.py`, `context_inference/basic.py` e `layer5.py` dependem de chaves JSON dentro de `layer2.sinais_documentais`. Isso cria acoplamento por string e torna refactors arriscados.
- `DocumentMemory` tem contratos paralelos: `relluna/core/document_memory/__init__.py`, `models.py` e `models_v0_2_0.py`. O import principal usa o contrato em `__init__.py`, enquanto o canonic v0.2.0 existe separado.
- A API mistura ingestao, persistencia, decisao de pipeline, execucao, erro e retorno de contrato no mesmo arquivo.
- O read model da timeline existe em pelo menos dois caminhos: `services/read_model/timeline_builder.py` e `services/derivatives/layer5.py`.

### Duplicacoes

- Datas sao extraidas em `entities_hard_v2.py`, `page_pipeline.py`, `timeline/date_extractor.py` e `entities_canonical_v1.py`.
- Entidades de pessoa/CRM/CID aparecem em `page_entity_extractors.py`, `page_clinical_extractors.py`, `entities_hard_v2.py`, `entities_canonical_v1.py` e `context_inference/basic.py`.
- Timeline aparece em `deterministic_extractors/timeline_seed.py`, `timeline_seed_v2.py`, `services/timeline/*`, `read_model/timeline_builder.py`, `read_model/timeline_read_model.py` e `derivatives/layer5.py`.
- Persistencia Mongo aparece em `infra/mongo_store.py`, `infra/mongo/document_store.py`, `infra/mongo_indexes.py` e `infra/mongo/indexes.py`.

### Pontos frageis

- `relluna/services/context_inference/document_taxonomy/rules.py` parece conter codigo quebrado ou rascunho: usa `@dataclass` sem import visivel nesse arquivo e possui um `return RuleResult(...)` em nivel de modulo. O caminho principal importa `rules/engine.py`, nao esse arquivo, mas o arquivo solto e um risco de manutencao.
- `relluna/core/document_memory/models.py` contem uma segunda definicao de `DocumentMemory` com `...`, parecendo legado quebrado. Pode nao ser usado, mas e um risco de import futuro.
- `relluna/services/forensics/layer6.py` busca `datacanonica`, mas o modelo canonico usa `data_canonica` com alias de validacao, nao necessariamente atributo `datacanonica`.
- `relluna/core/canonical_pipeline.py` tenta setar `fonte_data_canonica` em `Layer4SemanticNormalization`, cujo modelo usa `extra="forbid"`. Dependendo da execucao, isso pode falhar. Esse pipeline parece legado, mas testes o exercitam.
- `relluna/services/derivatives/layer5.py` grava URIs fake (`generated://...`, `https://local.blob/fake`) e `persistence_state="stored"`, o que e perigoso para auditoria se exposto como persistencia real.
- O repositorio esta versionando `.env`, `.venv`, uploads, `.uploads`, caches, artefatos e possiveis documentos sensiveis. Isso e um risco operacional, juridico e de seguranca.

## Riscos de classificacao e regressao semantica

### Classificacao errada de documento

- `entities_canonical_v1._determine_document_type` usa marcadores globais no texto inteiro (`ATESTADO`, `CID`, `CRM`, `PARECER`, `RECEITU`). Em documentos compostos, uma pagina pode contaminar o tipo do documento inteiro.
- `context_inference/basic.py` tem uma trava anti-regressao para evitar trocar tipos medicos por `identidade`, mas a classificacao ainda depende de heuristicas e prioridade canonica.
- `page_taxonomy` e `document_taxonomy` existem em paralelo, o que pode gerar divergencia entre tipo por pagina, tipo canonico e tipo Layer3.

### Extracao errada de entidades

- Pessoa: nomes de paciente, mae e prestador sao inferidos por regex, linhas vizinhas e scoring. Ha listas de falsos positivos conhecidas, mas o risco permanece em OCR ruidoso ou layouts pouco padronizados.
- Prestador: `provider_name` pode confundir cidade, instituicao, especialidade ou texto administrativo. O codigo contem filtros explicitos para exemplos como "sao paulo" e "medicamentos ou substancias", indicando historico de falso positivo.
- CID: regexes podem capturar padroes alfanumericos que nao sao CID. Ha filtros de contexto, mas `page_clinical_extractors.py` ainda faz extracao ampla e `context_inference/basic.py` usa regex simples para entidades semanticas.
- Datas: ha risco recorrente de confundir data de nascimento com data do documento. O codigo ja possui penalidades e warnings (`document_date_looks_like_birth_date`), mas a Layer4 ainda pode pegar o primeiro candidato de `page_evidence_v1` se nao houver temporalidade/EXIF.
- Afastamento: `entities_canonical_v1.py` calcula fim estimado a partir de duracao. Isso e util, mas deve ser destacado como inferido/estimado no produto; nao deve aparecer como fato observado.

### Regressao semantica

- A decisao de manter `entities_canonical_v1` em `Layer2.sinais_documentais` aumenta risco de Layer2 conter informacao semantica/contextual. Isso contradiz parcialmente a fronteira "Layer2 factual, Layer3 inferencial".
- Mudancas em uma chave de sinal (`page_evidence_v1`, `layout_spans_v1`, `entities_canonical_v1`, `timeline_seed_v2`) podem quebrar multiplas etapas downstream sem erro de tipo.
- O endpoint `/documents/{documentid}/timeline` usa `timeline_seed_v2` diretamente e pode divergir de `layer5.read_models.timeline_v1`, que usa `Layer3.eventos_probatorios` e tem mais contexto.
- Alguns testes usam contratos antigos (`version="v0.1.0"`, hashes invalidos, Layer4 com aliases antigos), o que pode mascarar incompatibilidades reais entre v0.1.0 e v0.2.0.

## Avaliacao de alinhamento com a proposta do produto

### O que esta alinhado

- A arquitetura por camadas e adequada para um produto juridico/operacional.
- Layer0 tem hash, custodia e processing events, o que sustenta auditabilidade.
- Layer2 separa muitos fatos deterministas e registra fonte/metodo/confianca.
- `page_evidence_v1` tenta preservar pagina, bbox, snippet e source path, que sao essenciais para revisao e navegacao em evidencia.
- `timeline_seed_v2` e `eventos_probatorios` ja modelam `review_state`, `provenance_status`, `confidence` e citacoes.
- O pipeline reconhece que estimativas e inferencias precisam ser marcadas, nao apenas jogadas como fatos.

### O que ainda nao esta alinhado

- A timeline ainda e estreita: cobre melhor `atestado_medico` e `parecer_medico`, mas nao parece robusta para prontuarios longos, laudos, receitas, recibos de saude, notas fiscais, historicos hospitalares ou documentos compostos complexos.
- A saida de produto esta fragmentada entre contrato da API, endpoint de timeline e `layer5.read_models`.
- A Layer5 afirma persistencia/derivados que nao parecem reais.
- A fronteira Layer2/Layer3 ainda esta borrada pelo uso de `entities_canonical_v1` e `timeline_seed_v2` como sinais em Layer2.
- O repositorio versiona dados sensiveis e ambiente, o que e incompatvel com um produto juridico/medico em producao.
- Nao ha evidencia clara de uma fila/worker real; o `worker` no `docker-compose.dev.yml` e placeholder. Processos pesados de OCR/ASR rodam no caminho da API.

## Incertezas

- Nao executei os scripts de debug para evitar processamento pesado e possiveis escritas temporarias; li `debug_run_pipeline.py`, `debug_profile_pipeline.py`, `tools/debug_pipeline_trace.py` e `trace_pipeline.txt` para entender o fluxo.
- Nao confirmei a saude atual da suite de testes. Pela leitura, ha sinais de contratos legados e arquivos suspeitos, mas o diagnostico aqui prioriza arquitetura/produto.
- Nao esta totalmente claro se o produto final deve usar `layer5.read_models.timeline_v1` ou o endpoint `/documents/{documentid}/timeline` como fonte de verdade da timeline.
- Nao esta claro se `models_v0_2_0.py` deve substituir `relluna/core/document_memory/__init__.py` como contrato unico.

## Oportunidades

- Consolidar um contrato unico de `DocumentMemory` v0.2.0 e migrar aliases antigos para uma camada de compatibilidade explicita.
- Transformar `sinais_documentais` criticos em modelos tipados ou ao menos schemas versionados por sinal.
- Definir uma unica fonte de verdade para timeline: provavelmente `Layer3.eventos_probatorios` + read model derivado.
- Separar orquestracao da API em um service de pipeline para viabilizar worker assicrono.
- Criar um modulo de "evidence graph" para conectar entidade/evento a pagina, bbox, snippet, artefato e hash.
- Adicionar avaliacao quantitativa de qualidade: taxa de eventos com bbox, taxa de entidades essenciais ausentes, quantidade de warnings e diferencas entre tipo por pagina/documento.
- Introduzir fixtures/goldens clinicos reais anonimizados para regressao semantica.
- Adicionar UI/estado de revisao humana para itens `review_recommended` e `needs_review`.

## Plano priorizado

### Correcoes rapidas

- Remover/ignorar do versionamento `.venv`, `.env`, `.uploads`, `uploads`, `uploads_test_ui`, caches e artefatos sensiveis; rotacionar qualquer segredo que tenha sido versionado.
- Corrigir ou remover `relluna/services/context_inference/document_taxonomy/rules.py` se for arquivo morto/quebrado.
- Marcar claramente `Layer5` como placeholder ou remover `persistence_state="stored"` e URIs fake ate haver persistencia real.
- Escolher um endpoint/read model de timeline como fonte publica e documentar que o outro e legado.
- Adicionar teste de regressao para nao promover `birth_date` como `document_date` ou `data_canonica`.
- Adicionar teste de regressao para documento composto com RG + atestado/parecer, evitando classificacao global incorreta.
- Adicionar teste de smoke do fluxo real `/process` com PDF textual pequeno e com PDF OCR, cobrindo `entities_canonical_v1`, `timeline_seed_v2`, `layer3.eventos_probatorios` e Layer5.
- Registrar nos eventos de processamento quando uma etapa foi pulada por falta de dependencia externa, em vez de silenciosamente retornar vazio.

### Refatoracao estrutural

- Extrair de `ingestion/api.py` um `PipelineOrchestrator` testavel, deixando a API apenas como transporte.
- Consolidar `DocumentMemory` em um contrato unico v0.2.0 e criar migradores explicitos para documentos v0.1.0.
- Tipar `page_evidence_v1`, `entities_canonical_v1` e `timeline_seed_v2` com Pydantic ou schemas JSON versionados.
- Separar `page_pipeline.py` em componentes menores: split, anchors, people resolver, clinical resolver, taxonomy, quality.
- Unificar extratores de datas, pessoas, CID/CRM/CPF e remover duplicacoes entre hard/page/canonical/context.
- Mover consolidacao semantica de `entities_canonical_v1` para Layer3 ou renomear/modelar como sinal intermediario "consolidated evidence" com fronteira explicita.
- Substituir reprocessamento `fast -> standard` por pipeline incremental que nao repita etapas ja feitas.
- Unificar stores Mongo e nomes de colecao (`document_memory`, `document_memories`, read model) em uma camada de repositorio.
- Separar processamento pesado em worker/fila, com estados de job e retry.

### Melhorias de produto

- Definir taxonomia de eventos da timeline por dominios: internacao, consulta, laudo, receita, exame, afastamento, alta, encaminhamento, compra/pagamento, protocolo administrativo.
- Exibir na timeline o nivel de lastro: `exact bbox`, `snippet only`, `inferred`, `estimated`, `needs_review`.
- Diferenciar visualmente evento observado de evento estimado, principalmente `afastamento_fim_estimado`.
- Criar tela/contrato de revisao humana para confirmar ou corrigir paciente, prestador, data documental, CIDs e eventos.
- Gerar um dossie auditavel por documento: hash, artefato, paginas, anchors, eventos, citacoes e warnings de qualidade.
- Agregar timeline multi-documento por pessoa/caso, com deduplicacao de eventos e conflitos temporais.
- Adicionar explicacoes de "por que este evento entrou na timeline" com citacoes navegaveis.
- Introduzir pontuacao de prontidao juridica baseada em criterios objetivos, nao apenas etapa alcancada.
- Criar goldens anonimizados por tipo documental e medir regressao semantica por entidade/evento, nao apenas por validade de schema.

## Aprofundamento: confiabilidade do pipeline

### Onde documentos medicos podem ser classificados incorretamente

- `relluna/services/entities/entities_canonical_v1.py::_determine_document_type` decide por marcadores globais no texto inteiro: `ATESTADO + CID/CRM`, `PARECER + CRM`, `RECEITU`. Em PDF composto, um recibo/anexo/RG na mesma memoria pode herdar tipo medico do documento vizinho ou o inverso.
- `relluna/services/context_inference/basic.py::_infer_document_tipo_from_ocr` tambem usa marcadores globais e depois cai para `document_taxonomy.rules.engine`. A trava anti-regressao evita alguns casos de `identidade`, mas nao resolve colisao entre `atestado_medico`, `parecer_medico`, `laudo_medico`, `receituario` e `documento_composto`.
- `relluna/services/page_extraction/page_taxonomy.py` classifica pagina, mas o tipo final do documento e escolhido em outro modulo. Isso cria risco de desacordo entre `page_taxonomy`, `entities_canonical_v1.document_type` e `layer3.tipo_documento`.
- `relluna/services/context_inference/document_taxonomy/rules/engine.py` hoje carrega regras default apenas para nota fiscal, identidade e recibo. Isso deixa documentos medicos dependentes de heuristicas espalhadas em `entities_canonical_v1.py` e `context_inference/basic.py`, nao de uma taxonomia medica formal.
- `relluna/services/context_inference/document_taxonomy/rules.py` parece arquivo quebrado/legado e pode confundir manutencao, porque o caminho correto usa `rules/engine.py`. Se alguem importar esse arquivo por engano, ha risco de erro em runtime.
- `relluna/services/deterministic_extractors/timeline_seed_v2.py` so especializa bem `atestado_medico` e `parecer_medico`. Se a classificacao vier como `laudo_medico`, `receituario` ou `documento_composto`, a timeline cai para emissao generica ou fica vazia.

### Onde pode confundir paciente, prestador e mae

- `relluna/services/page_extraction/page_pipeline.py::_infer_patient_name`, `_infer_provider_name` e `_infer_mother_name` usam regex, candidatos por linha, scores e filtros negativos. Isso e pragmatico, mas sensivel a OCR ruidoso, quebra de linha e cabecalhos.
- `relluna/services/page_extraction/page_entity_extractors.py::_infer_mother_name_fallback` pega a linha seguinte a marcadores como `mae`/`filiacao`. Em formularios com layout colunar ou texto OCR desordenado, pode capturar outro campo administrativo.
- `relluna/services/page_extraction/page_clinical_extractors.py::_infer_provider_name_fallback` procura nomes perto de `CRM` e tambem padroes `Dr/Dra`. Pode confundir prestador com paciente se ambos aparecem no mesmo bloco, especialmente quando o CRM esta em rodape/cabecalho institucional.
- `relluna/services/entities/entities_canonical_v1.py::_pick_best_patient`, `_pick_best_provider` e `_pick_best_mother` escolhem candidatos por score e pagina. A consolidacao multi-pagina pode escolher um nome de pagina administrativa em vez da pagina clinica quando confidence/bbox favorecem o candidato errado.
- `relluna/services/context_inference/basic.py::_best_candidate_from_pages` reaplica selecao de pessoas como fallback. Isso duplica decisao de pessoa ja feita em `entities_canonical_v1`, aumentando chance de divergencia entre evento, resumo de entidades e Layer4.
- A semantica de labels nao e totalmente uniforme: anchors usam `patient`, `mother`, `provider`, enquanto `entities_hard_v2` procura `patient_name`, `mother_name`, `provider_name` via `_find_person`. Essa diferenca reduz a chance de encontrar bbox/anchor correto e empurra o sistema para fallback textual.

### Onde ha fallback ou regressao silenciosa

- `relluna/services/ingestion/api.py::_read_pdf_preflight`, `_find_existing_by_fingerprint`, NSFW e outros blocos capturam excecoes e seguem sem registrar sempre um evento de warning. Isso pode transformar falha de preflight em decisao de pipeline errada.
- `relluna/services/deterministic_extractors/basic.py::_populate_pdf_structural_signals` engole falhas de layout, hard entities e structured block com `except Exception: pass`. O downstream recebe menos sinais sem saber se foi ausencia real ou falha tecnica.
- `relluna/services/ocr/service.py` retorna metodos como `native_failed`, `image_ocr_unavailable`, `docx_failed` e `xlsx_failed`, mas nem sempre isso vira `processingevents` ou metrica de qualidade agregada.
- `relluna/services/transcription/asr.py` retorna sem transcrever quando `opts.enabled` e falso ou dependencia falta; para produto, isso precisa aparecer como etapa pulada/degradada, nao como documento sem audio relevante.
- `relluna/services/page_extraction/page_text_splitter.py` retorna lista vazia se nao consegue carregar JSON de sinais. `apply_page_analysis` entao gera `page_evidence_v1` vazio sem necessariamente falhar.
- `relluna/core/normalization.py::_load_signal_json` retorna `None` em erro de parse. Um JSON invalido em `page_evidence_v1` ou `entities_canonical_v1` pode virar simplesmente ausencia de data/entidades.
- `relluna/services/read_model/timeline_builder.py::_load_signal_json` tambem suprime erro de parse; endpoint de timeline pode voltar vazio sem diferenciar "sem evento" de "sinal corrompido".
- `fast -> standard` em `relluna/services/ingestion/api.py` pode reexecutar etapas e sobrescrever sinais. Isso e uma regressao silenciosa se a segunda passagem perde informacao que a primeira tinha produzido.

### Onde faltam testes automatizados

- Ha testes para regras simples de `nota_fiscal`, `identidade` e `recibo` em `tests/test_document_taxonomy_rules.py`, mas nao encontrei cobertura equivalente para `atestado_medico`, `parecer_medico`, `laudo_medico`, `receituario`, `prontuario` e `documento_composto`.
- Ha testes de contrato de Layer3/Layer4/read model, mas nao vi testes direcionados para confusao paciente vs mae vs prestador no caminho `page_pipeline -> entities_canonical_v1 -> context_inference`.
- Nao vi teste especifico garantindo que `birth_date` nunca vira `document_date`, `timeline_seed_v2` ou `Layer4.data_canonica` quando ha apenas data de nascimento.
- Nao vi teste garantindo que `afastamento_fim_estimado` sempre preserve `provenance_status="inferred"` ou equivalente ate o read model.
- Nao vi teste de documento composto com duas paginas de tipos diferentes garantindo que o tipo global seja `documento_composto` ou que eventos sejam segmentados por subdocumento.
- Nao vi teste de corrupcao de sinal JSON em `sinais_documentais` validando que o pipeline registra warning em vez de retornar vazio.
- Nao vi teste de "dependencia externa ausente" para Tesseract, PyMuPDF, ffmpeg ou whisper com expectativa explicita de degraded/warning.
- Nao vi teste de equivalencia entre `/documents/{documentid}/timeline` e `layer5.read_models.timeline_v1`; hoje eles podem divergir por desenho.

### Partes muito acopladas e dificeis de evoluir

- `relluna/services/page_extraction/page_pipeline.py` concentra regex, heuristica de pessoa, anchors, confidence, review state, signal zone, payload e escrita do sinal. Evoluir uma parte sem regressao exige testes muito finos.
- `entities_canonical_v1.py` depende de `page_evidence_v1` e `layout_spans_v1` por formato implicito. Qualquer mudanca em labels, snippets, bbox ou page taxonomy afeta paciente, prestador, data documental e tipo de documento.
- `timeline_seed_v2.py` depende de shape interno de `entities_canonical_v1`. Isso torna a timeline uma extensao rigida do consolidator, nao um consumidor tipado de eventos/fatos.
- `context_inference/basic.py` mistura classificacao, regex de entidades, evento probatorio, titulos/descricoes e fallback de pessoas. A evolucao para LLM, regras medicas ou revisao humana ficara mais dificil se essa unidade crescer.
- `Layer5` depende de `Layer3.eventos_probatorios` e de `entities_canonical_v1`; o endpoint de timeline depende diretamente de `timeline_seed_v2`. Isso cria dois contratos de consumo para a mesma finalidade.
- A API em `ingestion/api.py` acopla transporte HTTP, storage local, preflight, decisao de pipeline, execucao e persistencia. Isso dificulta testar modo adaptativo e falhas de etapa sem subir FastAPI/Mongo.

## TESTES_PRIORITARIOS

- `test_atestado_medico_generates_clinical_timeline`: OCR com `ATESTADO`, `CRM`, `CID`, internacao e afastamento deve gerar `internacao_inicio`, `internacao_fim`, `afastamento_inicio` e `afastamento_fim_estimado`, com confidence/review/provenance coerentes.
- `test_parecer_medico_with_cid_generates_parecer_and_condition_events`: parecer com CRM, CID e data documental deve gerar `parecer_emitido` e `registro_condicao_clinica`.
- `test_receituario_does_not_become_atestado`: texto com `RECEITUARIO`, CRM e medicamentos nao deve ser classificado como `atestado_medico` so por conter CRM.
- `test_documento_composto_preserves_page_types`: PDF simulado com pagina de RG e pagina de atestado deve preservar page taxonomy e evitar tipo global enganoso sem sinalizar composicao.
- `test_birth_date_not_used_as_document_date`: texto com `Data de nascimento` e sem data de emissao nao deve preencher `entities_canonical_v1.document_date`, `timeline_seed_v2` nem `layer4.data_canonica` como fato documental.
- `test_patient_mother_provider_disambiguation`: fixture com `Nome paciente`, `Nome da mae`, `Prestador` e `CRM` deve consolidar cada papel corretamente e manter anchors/source_path.
- `test_provider_not_city_or_specialty`: textos com `Sao Paulo`, `medico clinico`, `servico` e `especialidade` nao devem virar `provider.name`.
- `test_cid_false_positive_context`: tokens como `S30` em endereco/cidade ou ruído OCR nao devem virar CID clinico.
- `test_corrupt_signal_json_records_warning`: `page_evidence_v1` ou `entities_canonical_v1` com JSON invalido deve produzir warning/processing event, nao timeline vazia silenciosa.
- `test_fast_to_standard_escalation_does_not_erase_signals`: escalonamento do modo `fast` para `standard` deve preservar ou substituir explicitamente sinais com evento de processamento auditavel.
- `test_timeline_endpoint_matches_layer5_read_model_policy`: definir e testar se `/documents/{id}/timeline` deve refletir `timeline_seed_v2` ou `Layer3.eventos_probatorios`; o comportamento precisa ser unico e documentado.
- `test_missing_ocr_dependency_is_degraded_not_empty`: simular Tesseract indisponivel e exigir estado `warning/degraded` rastreavel.

## Sequencia minima de refatoracao sem quebrar compatibilidade

1. Adicionar testes de caracterizacao antes de refatorar: criar fixtures pequenas em texto/DM para os casos de `TESTES_PRIORITARIOS`, sem depender de OCR real. O objetivo e congelar o comportamento esperado de produto.
2. Introduzir modelos Pydantic opcionais para `page_evidence_v1`, `entities_canonical_v1` e `timeline_seed_v2`, mantendo serializacao atual em `Layer2.sinais_documentais["..."].valor` para compatibilidade.
3. Criar helpers centralizados `load_signal_json_typed` e `write_signal_json` que registrem warning em `processingevents` quando parse/validacao falhar. Manter os nomes de chaves atuais.
4. Extrair de `page_pipeline.py` um `PeopleResolver` puro, testavel por string/lista de spans, sem mudar o payload final de `page_evidence_v1`.
5. Extrair de `entities_canonical_v1.py` um `DocumentTypeResolver` puro que recebe page taxonomy + texto + entidades e retorna tipo, confidence, lastro e motivo. Inicialmente escrever o resultado no mesmo `entities_canonical_v1.document_type`.
6. Criar uma camada de adaptador `TimelineSource` que consome `timeline_seed_v2` e produz `Layer3.eventos_probatorios`. O endpoint antigo pode continuar lendo seeds, mas deve ganhar teste/nota de deprecacao.
7. Unificar gradualmente o read model publico para usar `Layer3.eventos_probatorios`/`layer5.read_models.timeline_v1`, mantendo `/documents/{id}/timeline` como wrapper compativel.
8. Separar `PipelineOrchestrator` de `ingestion/api.py` sem mudar endpoints. A API chama o orchestrator; testes passam a exercitar o orchestrator diretamente.
9. Depois que os testes estiverem verdes, mover `entities_canonical_v1` para uma fronteira semantica explicita: ou Layer3, ou um `Layer2ConsolidatedEvidence` bem documentado. Enquanto isso, manter alias de leitura da chave antiga.
10. Por fim, limpar contratos legados (`models.py`, pipelines antigos, timeline duplicada) em etapas pequenas, sempre mantendo adaptadores para documentos ja persistidos.

## Conclusao

O pipeline esta no caminho certo conceitualmente: ele ja separa custodia, extracao, inferencia, normalizacao e read model, e ja carrega lastro suficiente para evoluir para um produto juridico/operacional auditavel. O proximo salto nao e adicionar mais regex isolada; e consolidar contrato, fonte de verdade da timeline, fronteira factual/inferencial e mecanismos de revisao/qualidade. Sem isso, o sistema pode produzir uma timeline plausivel, mas ainda fragil diante de documentos compostos, OCR ruidoso e exigencia juridica de rastreabilidade.
