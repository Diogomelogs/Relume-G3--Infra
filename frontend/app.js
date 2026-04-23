import { benchmark, billing, cases, collections, currentUser, plans, quickActions, settingsSections } from "./data.js";

const app = document.querySelector("#app");

const routeLabels = {
  "/": "Home",
  "/pricing": "Pricing",
  "/about": "About",
  "/contact": "Contact",
  "/login": "Login",
  "/signup": "Signup",
  "/forgot-password": "Recuperar acesso",
  "/invite/token-demo": "Convite",
  "/app": "Biblioteca",
  "/app/billing": "Billing",
  "/app/settings": "Settings",
  "/404": "404",
  "/500": "500",
  "/unauthorized": "Unauthorized",
};

const state = {
  route: normalizeRoute(location.hash.slice(1) || "/"),
  activeCaseId: cases[0].id,
  activeDocId: cases[0].documents[0].id,
  activeCaseTab: "timeline",
  selectedEventId: cases[0].events[0].id,
  selectedPage: 1,
};

window.addEventListener("hashchange", () => {
  state.route = normalizeRoute(location.hash.slice(1) || "/");
  syncRouteSelection();
  render();
});

document.addEventListener("click", (event) => {
  const action = event.target.closest("[data-action]");
  if (!action) return;

  const { action: type, caseId, docId, tab, eventId, page } = action.dataset;

  if (type === "open-case" && caseId) {
    state.activeCaseId = caseId;
    const activeCase = getActiveCase();
    state.activeDocId = activeCase.documents[0]?.id || "";
    state.selectedEventId = activeCase.events[0]?.id || "";
    location.hash = `#/app/cases/${caseId}`;
    return;
  }

  if (type === "open-doc" && caseId && docId) {
    state.activeCaseId = caseId;
    state.activeDocId = docId;
    const activeCase = getActiveCase();
    state.selectedEventId = activeCase.events[0]?.id || "";
    location.hash = `#/app/documents/${docId}`;
    return;
  }

  if (type === "set-tab" && tab) {
    state.activeCaseTab = tab;
    render();
    return;
  }

  if (type === "select-event" && eventId) {
    state.selectedEventId = eventId;
    render();
    return;
  }

  if (type === "select-page" && page) {
    state.selectedPage = Number(page);
    render();
    return;
  }

  if (type === "go" && action.dataset.to) {
    location.hash = `#${action.dataset.to}`;
  }
});

render();

function render() {
  const route = state.route;
  const page = resolvePage(route);

  app.innerHTML = `
    <div class="site-shell">
      ${renderAnnouncement()}
      ${renderChrome(page)}
      <main class="page-frame">
        ${page}
      </main>
    </div>
  `;
  highlightActiveNav();
}

function renderAnnouncement() {
  return `
    <div class="announcement">
      <div>
        <strong>Protótipo navegável premium.</strong>
        Dados mockados plausíveis. Sem integração real com pipeline, auth, billing ou persistência.
      </div>
      <div class="announcement-meta">
        <span>${benchmark.sourceLabel}</span>
        <span>Score ${formatScore(benchmark.score)}</span>
        <span>Timeline ${formatScore(benchmark.timelineConsistencyScore)}</span>
      </div>
    </div>
  `;
}

function renderChrome(page) {
  const inApp = state.route.startsWith("/app");
  return inApp ? renderAppShell() : renderMarketingShell();
}

function renderMarketingShell() {
  return `
    <header class="topbar marketing">
      <a class="brandmark" href="#/">
        <span class="brandmark-orb"></span>
        <span>
          <strong>Relluna</strong>
          <small>Document Memory for medico-legal ops</small>
        </span>
      </a>
      <nav class="nav-links">
        ${navLink("/", "Home")}
        ${navLink("/pricing", "Pricing")}
        ${navLink("/about", "About")}
        ${navLink("/contact", "Contact")}
      </nav>
      <div class="topbar-actions">
        <a class="ghost-link" href="#/login">Entrar</a>
        <a class="button button-primary" href="#/signup">Criar conta</a>
      </div>
    </header>
  `;
}

function renderAppShell() {
  return `
    <header class="topbar appbar">
      <div class="appbar-left">
        <a class="brandmark" href="#/app">
          <span class="brandmark-orb"></span>
          <span>
            <strong>Relluna</strong>
            <small>Workspace demo</small>
          </span>
        </a>
        <div class="command-bar">
          <span class="command-icon">⌘</span>
          <span>Buscar caso, documento, CID ou evento</span>
        </div>
      </div>
      <div class="appbar-right">
        <button class="chip" data-action="go" data-to="/app">Biblioteca</button>
        <button class="chip" data-action="go" data-to="/app/billing">Billing</button>
        <button class="chip" data-action="go" data-to="/app/settings">Settings</button>
        <button class="icon-button" aria-label="Notificações">⟡</button>
        <div class="user-pill">
          <span>${currentUser.initials}</span>
          <div>
            <strong>${currentUser.name}</strong>
            <small>${currentUser.workspace}</small>
          </div>
        </div>
      </div>
    </header>
  `;
}

function resolvePage(route) {
  if (route === "/") return renderHome();
  if (route === "/pricing") return renderPricing();
  if (route === "/about") return renderAbout();
  if (route === "/contact") return renderContact();
  if (route === "/login") return renderAuth("login");
  if (route === "/signup") return renderAuth("signup");
  if (route === "/forgot-password") return renderForgotPassword();
  if (route.startsWith("/invite/")) return renderInvite(route.split("/").pop());
  if (route === "/app") return renderAppDashboard();
  if (route.startsWith("/app/cases/")) {
    state.activeCaseId = route.split("/")[3] || cases[0].id;
    return renderCasePage();
  }
  if (route.startsWith("/app/documents/")) {
    const docId = route.split("/")[3];
    selectDocumentRoute(docId);
    return renderDocumentPage();
  }
  if (route === "/app/billing") return renderBilling();
  if (route === "/app/settings") return renderSettings();
  if (route === "/500") return renderSystemState("500");
  if (route === "/unauthorized") return renderSystemState("unauthorized");
  if (route === "/404") return renderSystemState("404");
  return renderSystemState("404");
}

function renderHome() {
  const featured = cases[0];
  return `
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">Relluna transforma documentos em memória auditável de caso</p>
        <h1>O workspace premium para explorar casos médico-jurídicos com rigor documental.</h1>
        <p class="hero-text">
          Não é só resumo por IA. A Relluna organiza custódia, evidência determinística, inferência controlada
          e timeline pública em uma experiência que times reais conseguem usar com velocidade e confiança.
        </p>
        <div class="hero-actions">
          <a class="button button-primary" href="#/signup">Criar conta</a>
          <a class="button button-secondary" href="#/app">Ver demo do app</a>
        </div>
        <div class="proof-strip">
          <div>
            <strong>${formatScore(benchmark.score)}</strong>
            <span>benchmark interno atual</span>
          </div>
          <div>
            <strong>${formatScore(benchmark.timelineConsistencyScore)}</strong>
            <span>consistência temporal</span>
          </div>
          <div>
            <strong>página · snippet · bbox</strong>
            <span>evidência auditável</span>
          </div>
        </div>
      </div>
      <div class="hero-preview">
        <div class="preview-card">
          <div class="preview-head">
            <span class="pill pill-gold">Demo navegável</span>
            <span class="pill">mock data</span>
          </div>
          <h3>${featured.title}</h3>
          <p>${featured.summary}</p>
          <div class="preview-grid">
            ${featured.stats.map((item) => `<div><strong>${item.value}</strong><span>${item.label}</span></div>`).join("")}
          </div>
          <div class="timeline-preview">
            ${featured.events.map((event) => `
              <article class="timeline-mini ${event.state}">
                <div class="timeline-mini-date">${formatDate(event.date)}</div>
                <div>
                  <strong>${event.title}</strong>
                  <p>${event.description}</p>
                </div>
              </article>
            `).join("")}
          </div>
        </div>
      </div>
    </section>

    <section class="section-block metrics">
      <div class="section-heading">
        <p class="eyebrow">Prova operacional</p>
        <h2>O produto comunica confiança antes de pedir confiança.</h2>
      </div>
      <div class="metric-grid">
        ${benchmark.metrics.map((item) => `
          <article class="metric-card">
            <strong>${formatScore(item.value)}</strong>
            <span>${item.label}</span>
          </article>
        `).join("")}
      </div>
      <p class="benchmark-note">${benchmark.note}</p>
    </section>

    <section class="section-block how-it-works">
      <div class="section-heading">
        <p class="eyebrow">Como funciona</p>
        <h2>Quatro movimentos claros, sem apagar a complexidade do caso.</h2>
      </div>
      <div class="step-grid">
        ${[
          ["1", "Ingestão com custódia", "Cada documento entra com fingerprint, artefato original e rastros de processamento."],
          ["2", "Evidência determinística", "Os sinais observáveis preservam páginas, snippets, bbox e proveniência exata."],
          ["3", "Inferência controlada", "Eventos inferidos continuam explicitamente marcados como inferidos ou estimados."],
          ["4", "Memória navegável de caso", "Timeline pública, revisão humana e documentação pronta para uso médico-jurídico."],
        ].map(([index, title, text]) => `
          <article class="step-card">
            <span>${index}</span>
            <h3>${title}</h3>
            <p>${text}</p>
          </article>
        `).join("")}
      </div>
    </section>

    <section class="section-block teaser">
      <div class="teaser-card">
        <div>
          <p class="eyebrow">Preparado para monetização</p>
          <h2>Pricing enxuto e estrutura pronta para venda.</h2>
          <p>Starter, Pro e Enterprise aparecem como parte natural da narrativa do produto, não como apêndice.</p>
        </div>
        <a class="button button-primary" href="#/pricing">Explorar planos</a>
      </div>
    </section>

    <footer class="footer">
      <div>
        <strong>Relluna</strong>
        <p>Documentos médicos transformados em memória auditável de caso.</p>
      </div>
      <div class="footer-links">
        <a href="#/about">Sobre</a>
        <a href="#/contact">Contato</a>
        <a href="#/login">Entrar</a>
      </div>
    </footer>
  `;
}

function renderPricing() {
  return `
    <section class="page-hero compact">
      <p class="eyebrow">Pricing</p>
      <h1>Planos desenhados para crescer com casos, documentos e revisão humana.</h1>
      <p>Estrutura comercial mockada, coerente com um software premium e explicitamente tratada como demo.</p>
    </section>
    <section class="pricing-grid">
      ${plans.map((plan) => `
        <article class="pricing-card ${plan.featured ? "featured" : ""}">
          <div class="pricing-head">
            <span class="pill ${plan.featured ? "pill-gold" : ""}">${plan.name}</span>
            <strong>${plan.price}</strong>
          </div>
          <p>${plan.blurb}</p>
          <ul class="feature-list">
            ${plan.features.map((feature) => `<li>${feature}</li>`).join("")}
          </ul>
          <a class="button ${plan.featured ? "button-primary" : "button-secondary"}" href="#/signup">Escolher ${plan.name}</a>
        </article>
      `).join("")}
    </section>
    <section class="faq-block">
      <div class="faq-card">
        <h3>Cobrança</h3>
        <p>Mensalidade por workspace, com faixas de casos, documentos e assentos. Demo data para validação comercial.</p>
      </div>
      <div class="faq-card">
        <h3>FAQ</h3>
        <p>Enterprise inclui governança avançada, auditoria e SSO. Starter mantém a semântica do produto, com menor volume.</p>
      </div>
    </section>
  `;
}

function renderAbout() {
  return `
    <section class="page-hero compact">
      <p class="eyebrow">Sobre a Relluna</p>
      <h1>Documentos não devem virar opinião opaca só porque passaram por IA.</h1>
      <p>O produto existe para transformar material médico em memória probatória auditável, com distinção clara entre fato observado e hipótese.</p>
    </section>
    <section class="manifesto-grid">
      ${[
        ["Problema de mercado", "Casos complexos sofrem com PDFs dispersos, revisão lenta e baixa rastreabilidade entre documento, evento e evidência."],
        ["Princípios do produto", "Custódia explícita, evidência determinística, inferência controlada, revisão humana e timeline pública com uma fonte semântica clara."],
        ["Posicionamento", "A Relluna não quer parecer assistente genérico. Quer parecer software confiável para operação real."],
      ].map(([title, text]) => `
        <article class="manifesto-card">
          <h3>${title}</h3>
          <p>${text}</p>
        </article>
      `).join("")}
    </section>
    <section class="teaser-card">
      <div>
        <p class="eyebrow">Conheça o produto</p>
        <h2>O coração do valor está na biblioteca de casos e na tela de caso.</h2>
      </div>
      <a class="button button-primary" href="#/app">Abrir demo</a>
    </section>
  `;
}

function renderContact() {
  return `
    <section class="page-hero compact">
      <p class="eyebrow">Contato</p>
      <h1>Fale com vendas, suporte ou solicite uma demo guiada.</h1>
      <p>Fluxo mockado, com posicionamento comercial e operacional coerente para um produto vendável.</p>
    </section>
    <section class="contact-grid">
      <form class="panel form-panel">
        <label>Nome<input type="text" value="Marina Teles"></label>
        <label>E-mail<input type="email" value="marina@atlaspericias.com.br"></label>
        <label>Mensagem<textarea>Quero avaliar a Relluna para operação médico-jurídica com foco em timeline e revisão.</textarea></label>
        <button type="button" class="button button-primary">Enviar contato</button>
      </form>
      <div class="panel stack">
        <div>
          <h3>Comercial</h3>
          <p>sales@relluna.demo</p>
        </div>
        <div>
          <h3>Suporte</h3>
          <p>support@relluna.demo</p>
        </div>
        <div>
          <h3>Tempo de resposta</h3>
          <p>Até 1 dia útil para comercial e até 4 horas úteis para suporte enterprise.</p>
        </div>
      </div>
    </section>
  `;
}

function renderAuth(mode) {
  const login = mode === "login";
  return `
    <section class="auth-shell">
      <div class="auth-brand panel">
        <p class="eyebrow">Relluna workspace</p>
        <h1>${login ? "Entrar" : "Criar conta"}</h1>
        <p>
          ${login
            ? "Acesse sua biblioteca de casos, timeline pública e fila de revisão."
            : "Comece um workspace médico-jurídico com semântica auditável desde o primeiro caso."}
        </p>
        <div class="auth-proof">
          <div><strong>${formatScore(benchmark.timelineConsistencyScore)}</strong><span>consistência temporal</span></div>
          <div><strong>observed / inferred / estimated</strong><span>epistemologia visível</span></div>
        </div>
      </div>
      <form class="auth-form panel">
        ${login ? "" : '<label>Nome<input type="text" value="Marina Teles"></label>'}
        <label>E-mail<input type="email" value="marina@atlaspericias.com.br"></label>
        ${login ? "" : '<label>Workspace<input type="text" value="Atlas Perícias"></label>'}
        <label>Senha<input type="password" value="••••••••••"></label>
        <button type="button" class="button button-primary">${login ? "Entrar" : "Começar"}</button>
        <div class="inline-links">
          ${login ? '<a href="#/forgot-password">Esqueci minha senha</a>' : '<a href="#/login">Já tenho conta</a>'}
          <a href="${login ? "#/signup" : "#/login"}">${login ? "Criar conta" : "Entrar"}</a>
        </div>
      </form>
    </section>
  `;
}

function renderForgotPassword() {
  return `
    <section class="auth-shell single">
      <form class="auth-form panel">
        <p class="eyebrow">Recuperar acesso</p>
        <h1>Envie um link seguro para redefinir sua senha.</h1>
        <label>E-mail<input type="email" value="marina@atlaspericias.com.br"></label>
        <button type="button" class="button button-primary">Enviar instruções</button>
        <p class="microcopy">Mensagem de confirmação mockada: “Se existir uma conta para esse e-mail, enviamos o link.”</p>
      </form>
    </section>
  `;
}

function renderInvite(token) {
  return `
    <section class="auth-shell single">
      <div class="auth-form panel">
        <p class="eyebrow">Convite para workspace</p>
        <h1>Aceitar convite</h1>
        <p>Workspace: <strong>Atlas Perícias</strong></p>
        <p>E-mail convidado: <strong>marina@atlaspericias.com.br</strong></p>
        <p>Token de demo: <code>${token}</code></p>
        <button type="button" class="button button-primary">Aceitar convite</button>
      </div>
    </section>
  `;
}

function renderAppDashboard() {
  return `
    <section class="dashboard-shell">
      <div class="dashboard-intro">
        <div>
          <p class="eyebrow">Biblioteca de casos</p>
          <h1>Casos tratados como catálogo premium, não como tabela burocrática.</h1>
        </div>
        <div class="chip-row">
          ${quickActions.map((action) => `<button class="chip">${action.label}</button>`).join("")}
        </div>
      </div>

      <section class="continuation-band panel">
        <div>
          <span class="pill pill-gold">Continue</span>
          <h2>${cases[0].title}</h2>
          <p>${cases[0].summary}</p>
        </div>
        <button class="button button-primary" data-action="open-case" data-case-id="${cases[0].id}">Reabrir caso</button>
      </section>

      ${collections.map((collection) => `
        <section class="collection">
          <div class="collection-head">
            <div>
              <h2>${collection.title}</h2>
              <p>${collection.description}</p>
            </div>
          </div>
          <div class="card-row">
            ${collection.caseIds.map((caseId) => renderCaseCard(findCase(caseId))).join("")}
          </div>
        </section>
      `).join("")}
    </section>
  `;
}

function renderCaseCard(caseItem) {
  return `
    <article class="case-card ${caseItem.artwork}">
      <div class="case-card-cover">
        <span class="pill ${toneClass(caseItem.statusTone)}">${caseItem.coverLabel}</span>
        <span class="microcopy">${caseItem.recentActivity}</span>
      </div>
      <div class="case-card-body">
        <h3>${caseItem.title}</h3>
        <p>${caseItem.subtitle}</p>
        <div class="case-meta">
          <span>${caseItem.documentsCount} docs</span>
          <span>${caseItem.status}</span>
          <span>prontidão ${caseItem.readiness}</span>
        </div>
        <div class="stat-line">
          <div><strong>${caseItem.timelineConsistency}</strong><span>timeline</span></div>
          <div><strong>${caseItem.confidence}</strong><span>confiança</span></div>
          <div><strong>${caseItem.pendingReview}</strong><span>review</span></div>
        </div>
        <button class="button button-secondary" data-action="open-case" data-case-id="${caseItem.id}">Abrir caso</button>
      </div>
    </article>
  `;
}

function renderCasePage() {
  const activeCase = getActiveCase();
  const selectedEvent = activeCase.events.find((event) => event.id === state.selectedEventId) || activeCase.events[0];
  return `
    <section class="case-shell">
      <div class="case-header panel">
        <div>
          <p class="eyebrow">Caso</p>
          <h1>${activeCase.title}</h1>
          <p>${activeCase.client} · ${activeCase.type} · ${activeCase.status}</p>
        </div>
        <div class="stat-line wide">
          <div><strong>${activeCase.readiness}</strong><span>prontidão jurídica</span></div>
          <div><strong>${activeCase.timelineConsistency}</strong><span>consistência da timeline</span></div>
          <div><strong>${activeCase.pendingReview}</strong><span>revisões pendentes</span></div>
          <div><strong>${activeCase.regressions}</strong><span>regressões críticas</span></div>
        </div>
      </div>

      <div class="case-tabs">
        ${["timeline", "clusters", "documents", "events", "review"].map((tab) => `
          <button class="tab ${state.activeCaseTab === tab ? "active" : ""}" data-action="set-tab" data-tab="${tab}">
            ${tab === "timeline" ? "Timeline" : tab === "clusters" ? "Clusters" : tab === "documents" ? "Documentos" : tab === "events" ? "Eventos" : "Revisão"}
          </button>
        `).join("")}
      </div>

      <div class="case-layout">
        <div class="panel canvas">
          ${renderCaseTab(activeCase)}
        </div>
        <aside class="panel evidence-rail">
          <p class="eyebrow">Painel de evidência</p>
          <h3>${selectedEvent.title}</h3>
          <p>${selectedEvent.description}</p>
          <div class="stack">
            <div class="detail-item"><span>Estado</span><strong>${labelState(selectedEvent.state)}</strong></div>
            <div class="detail-item"><span>Confiança</span><strong>${Math.round(selectedEvent.confidence * 100)}%</strong></div>
            <div class="detail-item"><span>Proveniência</span><strong>${selectedEvent.provenanceStatus}</strong></div>
            <div class="detail-item"><span>Review</span><strong>${selectedEvent.reviewState}</strong></div>
            <div class="detail-item"><span>Evidência</span><strong>${selectedEvent.evidenceRef}</strong></div>
          </div>
          <div class="notice-card">
            <strong>Regra obrigatória</strong>
            <p>Evento inferido permanece visualmente distinto e nunca é mostrado como observado.</p>
          </div>
        </aside>
      </div>
    </section>
  `;
}

function renderCaseTab(activeCase) {
  if (state.activeCaseTab === "timeline") {
    return `
      <div class="timeline-list">
        ${activeCase.events.map((event) => `
          <article class="timeline-card ${event.state}" data-action="select-event" data-event-id="${event.id}">
            <div class="timeline-card-head">
              <span>${formatDate(event.date)}</span>
              <span class="pill ${toneClass(eventTone(event.state))}">${labelState(event.state)}</span>
            </div>
            <h3>${event.title}</h3>
            <p>${event.description}</p>
            <div class="micro-row">
              <span>${event.type}</span>
              <span>${event.reviewState}</span>
              <span>${event.evidenceRef}</span>
            </div>
          </article>
        `).join("")}
      </div>
    `;
  }

  if (state.activeCaseTab === "clusters") {
    return `
      <div class="cluster-grid">
        <article class="cluster-card">
          <h3>Cluster documental</h3>
          <p>Atestado, receituário e reavaliação apontam para o mesmo episódio clínico.</p>
          <ul class="feature-list">
            <li>same_patient confirmado</li>
            <li>same_episode provável</li>
            <li>same_provider parcial</li>
          </ul>
        </article>
        <article class="cluster-card">
          <h3>Cluster temporal</h3>
          <p>As datas observadas se concentram no início de março, com extensão estimada claramente rotulada.</p>
          <ul class="feature-list">
            <li>âncora em document_issue_date</li>
            <li>período estimado em revisão</li>
            <li>sem colisão com birth_date</li>
          </ul>
        </article>
      </div>
    `;
  }

  if (state.activeCaseTab === "documents") {
    return `
      <div class="document-grid">
        ${activeCase.documents.map((document) => `
          <article class="document-card">
            <div>
              <h3>${document.title}</h3>
              <p>${document.type} · ${document.pages} páginas</p>
            </div>
            <div class="micro-row">
              <span>${document.processingStatus}</span>
              <span>${document.custodyState}</span>
            </div>
            <button class="button button-secondary" data-action="open-doc" data-case-id="${activeCase.id}" data-doc-id="${document.id}">Abrir documento</button>
          </article>
        `).join("")}
      </div>
    `;
  }

  if (state.activeCaseTab === "events") {
    return `
      <div class="event-table">
        ${activeCase.events.map((event) => `
          <article class="event-row">
            <div>
              <strong>${event.title}</strong>
              <p>${event.description}</p>
            </div>
            <div class="micro-row">
              <span>${formatDate(event.date)}</span>
              <span>${labelState(event.state)}</span>
              <span>${event.provenanceStatus}</span>
            </div>
          </article>
        `).join("")}
      </div>
    `;
  }

  return `
    <div class="review-grid">
      ${activeCase.reviewItems.map((item) => `
        <article class="review-card">
          <div class="timeline-card-head">
            <strong>${item.field}</strong>
            <span class="pill ${toneClass(item.state === "confirmed" ? "success" : "warning")}">${item.state}</span>
          </div>
          <p>${item.value}</p>
          <small>${item.reason}</small>
        </article>
      `).join("")}
    </div>
  `;
}

function renderDocumentPage() {
  const activeCase = getActiveCase();
  const activeDocument = getActiveDocument();
  const page = activeDocument.pagesData.find((item) => item.number === state.selectedPage) || activeDocument.pagesData[0];
  return `
    <section class="document-shell">
      <div class="document-header panel">
        <div>
          <p class="eyebrow">Documento</p>
          <h1>${activeDocument.title}</h1>
          <p>${activeCase.title} · ${activeDocument.type} · ${activeDocument.processingStatus}</p>
        </div>
        <div class="micro-grid">
          <div><span>Fingerprint</span><strong>${activeDocument.fingerprint}</strong></div>
          <div><span>Custódia</span><strong>${activeDocument.custodyState}</strong></div>
          <div><span>Origem</span><strong>${activeDocument.origin}</strong></div>
          <div><span>OCR</span><strong>${activeDocument.ocrMode}</strong></div>
        </div>
      </div>

      <div class="document-layout">
        <div class="panel page-viewer">
          <div class="page-toolbar">
            ${activeDocument.pagesData.map((item) => `
              <button class="chip ${item.number === page.number ? "active" : ""}" data-action="select-page" data-page="${item.number}">
                Página ${item.number}
              </button>
            `).join("")}
          </div>
          <div class="page-canvas">
            <div class="page-paper">
              <div class="bbox-callout">${page.evidenceBox}</div>
              <h3>${page.title}</h3>
              <p>${page.snippet}</p>
            </div>
          </div>
          <div class="ocr-panel">
            <h3>OCR / texto observável</h3>
            <p>${page.snippet}</p>
          </div>
        </div>
        <aside class="panel doc-sidebar">
          <div class="stack">
            <div>
              <p class="eyebrow">Sinais canônicos</p>
              ${activeDocument.canonicalSignals.map((signal) => `
                <div class="detail-item">
                  <span>${signal.field}</span>
                  <strong>${signal.value}</strong>
                  <small>${signal.state}</small>
                </div>
              `).join("")}
            </div>
            <div>
              <p class="eyebrow">Warnings</p>
              ${activeDocument.warnings.length
                ? activeDocument.warnings.map((warning) => `<div class="notice-card">${warning}</div>`).join("")
                : '<div class="notice-card success">Sem warnings críticos neste documento.</div>'}
            </div>
            <div>
              <p class="eyebrow">Eventos relacionados</p>
              ${activeDocument.relatedEvents.map((eventId) => {
                const event = activeCase.events.find((item) => item.id === eventId);
                return `<div class="detail-item"><span>${event.type}</span><strong>${event.title}</strong></div>`;
              }).join("")}
            </div>
          </div>
        </aside>
      </div>
    </section>
  `;
}

function renderBilling() {
  return `
    <section class="page-hero compact app">
      <p class="eyebrow">Billing</p>
      <h1>Faturamento tratado como parte natural do produto.</h1>
      <p>Estado mockado para validação comercial; não indica cobrança real ativa.</p>
    </section>
    <section class="billing-grid">
      <article class="panel">
        <h3>Plano atual</h3>
        <p>${billing.currentPlan} · ${billing.workspace}</p>
        <div class="detail-item"><span>Renovação</span><strong>${billing.renewalDate}</strong></div>
        <div class="detail-item"><span>Pagamento</span><strong>${billing.paymentMethod}</strong></div>
        <button class="button button-primary">Fazer upgrade</button>
      </article>
      <article class="panel">
        <h3>Consumo</h3>
        <div class="detail-item"><span>Assentos</span><strong>${billing.seats.used}/${billing.seats.total}</strong></div>
        <div class="detail-item"><span>Casos</span><strong>${billing.cases.used}/${billing.cases.total}</strong></div>
        <div class="detail-item"><span>Documentos</span><strong>${billing.documents.used}/${billing.documents.total}</strong></div>
      </article>
      <article class="panel invoice-panel">
        <h3>Invoices</h3>
        ${billing.invoices.map((invoice) => `
          <div class="invoice-row">
            <div>
              <strong>${invoice.id}</strong>
              <p>${invoice.period}</p>
            </div>
            <div>
              <strong>${invoice.amount}</strong>
              <p>${invoice.status}</p>
            </div>
          </div>
        `).join("")}
      </article>
    </section>
  `;
}

function renderSettings() {
  return `
    <section class="page-hero compact app">
      <p class="eyebrow">Settings</p>
      <h1>Perfil, workspace, equipe e segurança com linguagem de produto real.</h1>
      <p>Estrutura enxuta nesta primeira entrega, suficiente para validar arquitetura de informação.</p>
    </section>
    <section class="settings-grid">
      ${settingsSections.map((section) => `
        <article class="panel">
          <h3>${section.title}</h3>
          <ul class="feature-list">
            ${section.items.map((item) => `<li>${item}</li>`).join("")}
          </ul>
        </article>
      `).join("")}
    </section>
  `;
}

function renderSystemState(kind) {
  const content = {
    "404": {
      title: "Essa rota não existe no protótipo.",
      body: "O hash routing mantém o demo isolado do backend real. Volte para a home ou para a biblioteca.",
      ctaPrimary: "#/",
      ctaSecondary: "#/app",
      primaryLabel: "Ir para home",
      secondaryLabel: "Ir para biblioteca",
    },
    "500": {
      title: "O demo ficou indisponível nesta visualização.",
      body: "Mensagem tranquilizadora de estado sistêmico. Em produção, isso apontaria para suporte ou retry controlado.",
      ctaPrimary: "#/app",
      ctaSecondary: "#/contact",
      primaryLabel: "Tentar novamente",
      secondaryLabel: "Contatar suporte",
    },
    unauthorized: {
      title: "Você não tem acesso a esta área no plano atual.",
      body: "Estado pensado para diferença de permissão ou gating comercial, sem sugerir controle real já implementado.",
      ctaPrimary: "#/app",
      ctaSecondary: "#/pricing",
      primaryLabel: "Voltar ao app",
      secondaryLabel: "Gerenciar assinatura",
    },
  }[kind];

  return `
    <section class="state-shell panel">
      <p class="eyebrow">System state</p>
      <h1>${content.title}</h1>
      <p>${content.body}</p>
      <div class="hero-actions">
        <a class="button button-primary" href="${content.ctaPrimary}">${content.primaryLabel}</a>
        <a class="button button-secondary" href="${content.ctaSecondary}">${content.secondaryLabel}</a>
      </div>
    </section>
  `;
}

function navLink(route, label) {
  return `<a class="nav-link" data-route="${route}" href="#${route}">${label}</a>`;
}

function highlightActiveNav() {
  document.querySelectorAll("[data-route]").forEach((node) => {
    node.classList.toggle("active", node.dataset.route === state.route);
  });
}

function getActiveCase() {
  return findCase(state.activeCaseId) || cases[0];
}

function getActiveDocument() {
  const activeCase = getActiveCase();
  return activeCase.documents.find((item) => item.id === state.activeDocId) || activeCase.documents[0];
}

function selectDocumentRoute(docId) {
  for (const caseItem of cases) {
    const document = caseItem.documents.find((item) => item.id === docId);
    if (document) {
      state.activeCaseId = caseItem.id;
      state.activeDocId = document.id;
      state.selectedPage = document.pagesData[0]?.number || 1;
      return;
    }
  }
}

function syncRouteSelection() {
  if (state.route.startsWith("/app/cases/")) {
    state.activeCaseId = state.route.split("/")[3] || state.activeCaseId;
    state.selectedEventId = getActiveCase().events[0]?.id || state.selectedEventId;
  }
  if (state.route.startsWith("/app/documents/")) {
    selectDocumentRoute(state.route.split("/")[3]);
  }
}

function normalizeRoute(route) {
  if (!route.startsWith("/")) return `/${route}`;
  return route;
}

function findCase(caseId) {
  return cases.find((item) => item.id === caseId);
}

function eventTone(eventState) {
  if (eventState === "observed") return "success";
  if (eventState === "inferred") return "warning";
  return "danger";
}

function toneClass(tone) {
  if (tone === "success") return "pill-success";
  if (tone === "danger") return "pill-danger";
  if (tone === "warning") return "pill-gold";
  return "";
}

function labelState(stateValue) {
  if (stateValue === "observed") return "Observed";
  if (stateValue === "inferred") return "Inferred";
  if (stateValue === "estimated") return "Estimated";
  return stateValue;
}

function formatDate(value) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatScore(value) {
  return `${value.toFixed(2)}/100`;
}
