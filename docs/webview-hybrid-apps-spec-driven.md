# Apps Webview / Híbridos — Guia Spec-Driven (arquitetura, pastas, contrato, segurança, empacotamento)

> Documento de referência **genérico** para projetar, especificar e construir aplicativos
> desktop cuja interface é **HTML/CSS/JS renderizado em um WebView embutido**, com um
> **núcleo nativo** (janela, bandeja, acesso ao SO, dados/segredos).
> Aplica-se a pywebview, Tauri, Electron, Wails, Neutralino, CEF, etc.

---

## Índice

1. [O modelo mental](#1-o-modelo-mental)
2. [Quando escolher (e quando não)](#2-quando-escolher-e-quando-não)
3. [Arquitetura: host, renderer e a ponte](#3-arquitetura-host-renderer-e-a-ponte)
4. [Spec-Driven: o que é e por quê](#4-spec-driven-o-que-é-e-por-quê)
5. [Anatomia de uma spec completa](#5-anatomia-de-uma-spec-completa)
6. [O contrato da ponte (IPC/bridge) — projete primeiro](#6-o-contrato-da-ponte-ipcbridge--projete-primeiro)
7. [Organização de pastas](#7-organização-de-pastas)
8. [Padrões de UI e estado](#8-padrões-de-ui-e-estado)
9. [Segurança — a fronteira de confiança](#9-segurança--a-fronteira-de-confiança)
10. [Empacotamento e distribuição](#10-empacotamento-e-distribuição)
11. [Estratégia de testes](#11-estratégia-de-testes)
12. [Fluxo de trabalho spec-driven (passo a passo)](#12-fluxo-de-trabalho-spec-driven-passo-a-passo)
13. [Templates prontos](#13-templates-prontos)
14. [Anti-padrões e armadilhas](#14-anti-padrões-e-armadilhas)
15. [Ecossistema e leituras](#15-ecossistema-e-leituras)

---

## 1. O modelo mental

Um app híbrido tem **duas metades** conversando por uma **ponte**:

```
┌─────────────────────────────────────────────────────────────┐
│                      PROCESSO HOST (nativo)                   │
│  Janela · Bandeja · Menus · Notificações · FS · Rede · Cripto │
│  Regras de negócio · Segredos · Acesso ao SO                  │
│                          ▲     │                              │
│                   eventos│     │chamadas (comandos)           │
│                          │     ▼                              │
│                    ┌───────────────┐                          │
│                    │     PONTE      │  (IPC / js_api / bridge) │
│                    │  serialização  │  JSON, validação        │
│                    └───────────────┘                          │
│                          ▲     │                              │
│                          │     ▼                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                RENDERER (WebView)                      │    │
│  │  HTML/CSS/JS · apresentação · estado de UI            │    │
│  │  SEM segredos · SEM confiança implícita              │    │
│  └──────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

Princípio central: **o renderer é "burro e desconfiado"**. Ele só apresenta e
coleta interação. Toda lógica sensível, segredo e acesso ao SO vive no **host**.
A ponte é uma **fronteira de confiança** — tudo que cruza é dado não-confiável.

---

## 2. Quando escolher (e quando não)

**Escolha webview/híbrido quando:**
- A UI é rica/visual e você já domina web (CSS, animação, dataviz).
- Precisa de **um código de UI** para desktop, e talvez reaproveitar na web.
- Quer iterar rápido no visual (hot-reload, DevTools).

**Prefira UI nativa (Qt, WinUI, Tkinter, SwiftUI) quando:**
- Latência/consumo de memória são críticos.
- Você precisa de integração visual "pixel-nativa" com o SO.
- O app é essencialmente formulários simples.

**Comparativo de motores/frameworks:**

| Framework   | Linguagem host | Motor web            | Peso do binário | Observação                          |
|-------------|----------------|----------------------|-----------------|-------------------------------------|
| Electron    | JS/Node        | Chromium **embutido**| ~120–200 MB     | Consistente, pesado                 |
| Tauri       | Rust           | WebView **do SO**    | ~3–10 MB        | Leve, seguro, curva de Rust         |
| pywebview   | Python         | WebView **do SO**    | ~5–30 MB        | Simples, ótimo pra Python           |
| Wails       | Go             | WebView **do SO**    | ~5–15 MB        | Leve, bindings Go↔JS                 |
| Neutralino  | qualquer       | WebView **do SO**    | ~2 MB           | Minimalista                         |

> **"WebView do SO"** = usa o navegador já instalado (WebView2 no Windows, WKWebView
> no macOS, WebKitGTK no Linux). Binário menor, mas depende do runtime existir/atualizar.
> **Chromium embutido** = mesma renderização em toda máquina, ao custo de tamanho.

---

## 3. Arquitetura: host, renderer e a ponte

### 3.1 Responsabilidades

| Camada       | Faz                                                            | NÃO faz                          |
|--------------|---------------------------------------------------------------|----------------------------------|
| **Host**     | janela, bandeja, SO, FS, rede, cripto, segredos, regra de negócio | renderizar UI, confiar no renderer |
| **Ponte**    | expor comandos, emitir eventos, serializar, **validar entrada** | lógica de negócio                |
| **Renderer** | apresentação, estado de UI, chamadas de comando, tratar eventos | guardar segredo, acessar SO direto |

### 3.2 Dois sentidos de comunicação

- **Comando (renderer → host):** "faça X", geralmente `async` e retorna resultado.
  Ex.: `getUsage()`, `saveSettings(x)`, `minimizeWindow()`.
- **Evento (host → renderer):** "algo mudou", push assíncrono.
  Ex.: `onData(snapshot)`, `onError(e)`, `onThemeChanged(t)`.

### 3.3 Modelo de concorrência

- O **renderer** é single-thread (event loop do JS). Nunca bloqueie a UI.
- O **host** faz trabalho pesado (rede, disco) **fora** da thread de UI: worker/thread/
  task async. Ao terminar, **empurra um evento** ou responde ao comando.
- Padrão robusto: um **poller** no host mantém um *snapshot* atual; o renderer lê o
  snapshot (rápido) e/ou recebe eventos quando ele muda.

---

## 4. Spec-Driven: o que é e por quê

**Spec-driven development** = escrever a **especificação executável/verificável antes**
do código: o que o sistema faz, quais estados existem, qual o contrato entre as partes
e como saber que está pronto. O código passa a ser a *implementação de uma spec*, não o
lugar onde as decisões são tomadas ad-hoc.

**Por que casa perfeitamente com apps híbridos:**
- A **ponte é um contrato** entre dois mundos (host/renderer) — contrato pede spec.
- A UI tem **muitos estados** (carregando/vazio/erro/sucesso/limite) fáceis de esquecer.
- Segurança e empacotamento têm requisitos que precisam ser **explícitos e checados**.

**Benefícios:** menos retrabalho, testes derivados da spec, onboarding rápido, e um
"contrato" estável mesmo trocando o framework (Electron→Tauri) sem reescrever a UI.

---

## 5. Anatomia de uma spec completa

Uma spec "top" para esse tipo de app tem **7 blocos**. Mantenha cada um curto e verificável.

### 5.1 Produto (o "porquê")
- **Problema / job-to-be-done**, público, valor.
- **Escopo** (in/out), não-objetivos (YAGNI explícito).
- **Métricas de sucesso**.

### 5.2 Funcional (o "o quê")
- Lista de **features** com IDs (`F-01`, `F-02`…).
- **Fluxos** principais (passo a passo) e **casos de borda**.
- **Regras de negócio** (limiares, formatação, cálculos) — puras e testáveis.

### 5.3 UI (as telas e **todos** os estados)
- Inventário de **telas/janelas** e **componentes**.
- Para cada tela, os **estados obrigatórios**:
  `loading` · `empty` · `error` · `success` · estados especiais do domínio.
- Regras de **tema** (claro/escuro/auto), **responsividade** e **acessibilidade**.

### 5.4 Contrato da ponte (o coração — ver §6)
- Lista de **comandos** e **eventos** com assinatura, tipos e **envelope de erro**.
- Formato de serialização (JSON), versão do contrato.

### 5.5 Não-funcional
- **Segurança** (CSP, isolamento, validação, segredos).
- **Performance** (tempo de boot, uso de memória, tamanho do binário).
- **Persistência** (onde salva config/estado; formato; migração).
- **Atualização** (auto-update? manual?).

### 5.6 Empacotamento / distribuição
- Alvos de SO, **dependências de runtime** (ex.: WebView do SO), assinatura, instalador.

### 5.7 Critérios de aceite / Definition of Done
- Checklist objetivo por feature + qualidade (testes, cobertura, review, build verde).

---

## 6. O contrato da ponte (IPC/bridge) — projete primeiro

**Regra de ouro:** desenhe o **contrato antes** da UI e do host. Ele é a interface que
segura tudo. Trate como uma **API** — versione, valide, padronize erros.

### 6.1 Envelope de resposta padronizado

Toda resposta de comando usa o **mesmo formato** (sucesso/erro previsíveis):

```jsonc
// sucesso
{ "ok": true,  "data": { /* payload */ } }
// erro
{ "ok": false, "error": { "code": "TOKEN_MISSING", "message": "texto amigável" } }
```

### 6.2 Snapshot orientado a estado

O renderer nunca "calcula" — ele **renderiza um snapshot** que o host entrega pronto:

```jsonc
{
  "state": "ok",              // "loading" | "empty" | "error" | "ok"
  "message": null,            // preenchido em empty/error
  "items": [ /* ... */ ],
  "updatedAt": "2025-01-01T10:22:00Z",
  "meta": { "version": 1 }
}
```

Vantagem: adicionar um estado novo = mudar o host + um branch no `render(snapshot)`.
A UI vira uma **função pura do estado**: `UI = render(snapshot)`.

### 6.3 Catálogo de comandos e eventos (exemplo genérico)

```
COMANDOS (renderer → host)          EVENTOS (host → renderer)
  getSnapshot() -> Snapshot           onSnapshot(Snapshot)
  refresh()     -> Snapshot           onError(Error)
  saveSettings(Settings) -> Settings  onSettingsChanged(Settings)
  window.minimize() -> void
  window.hide()     -> void
  window.resize(w,h)-> void
```

### 6.4 Boas práticas de contrato
- **Nomes estáveis e versionados** (`meta.version`); mudanças quebram → suba a versão.
- **Valide toda entrada** no host (nunca confie em tipos vindos do JS).
- **Idempotência** onde fizer sentido (chamar duas vezes = mesmo efeito).
- **Erros como dados** (envelope), não exceções que atravessam a ponte.
- **Sem segredo no snapshot** — só o necessário para exibir.

---

## 7. Organização de pastas

### 7.1 Layout genérico (independente de framework)

```
meu-app/
├─ src/
│  ├─ host/                  # núcleo nativo (backend)
│  │  ├─ main.*              # entrypoint: cria janela, bandeja, inicia loops
│  │  ├─ bridge/             # a PONTE: registra comandos/eventos, valida
│  │  │  ├─ commands.*       # handlers de comando
│  │  │  └─ contract.*       # tipos/schema do contrato (fonte da verdade)
│  │  ├─ services/           # regra de negócio, integrações (rede, FS, cripto)
│  │  ├─ domain/             # lógica pura, testável (cálculos, formatação)
│  │  └─ platform/           # tray, notificações, autostart, específicos de SO
│  │
│  └─ web/                   # renderer (frontend)
│     ├─ index.html
│     ├─ styles/             # tokens.css, themes.css, components.css
│     ├─ components/         # por feature (não por tipo)
│     ├─ lib/                # bridge-client, render, helpers
│     └─ state/              # store/estado da UI
│
├─ assets/                   # ícones, imagens, fontes
├─ tests/
│  ├─ unit/                  # domínio puro (host) + helpers (web)
│  ├─ contract/              # valida snapshot/comandos contra o schema
│  └─ e2e/                   # dirige a UI real
├─ packaging/                # specs de build, instalador, assinatura
├─ docs/
│  ├─ SPEC.md                # a especificação (§5)
│  ├─ CONTRACT.md            # o contrato da ponte (§6)
│  └─ ARCHITECTURE.md
├─ .gitignore                # ignora build/, dist/, artefatos, segredos/estado local
├─ LICENSE
└─ README.md
```

Princípios: **muitos arquivos pequenos**, organizados **por feature/domínio** (não por
tipo), com a **lógica pura isolada** em `domain/` para testar sem UI nem rede.

### 7.2 Variações por framework

**pywebview (Python):**
```
src/host/main.py            # webview.create_window(js_api=Api()); webview.start()
src/host/bridge/api.py      # classe Api: métodos = comandos expostos ao JS
src/host/domain/*.py        # funções puras (pytest)
src/web/index.html
packaging/*.spec            # PyInstaller
```

**Tauri (Rust + web):**
```
src-tauri/                  # host em Rust
  src/main.rs               # #[tauri::command] = comandos
  tauri.conf.json           # allowlist, CSP, bundler, updater
src/                        # frontend (Vite/React/Svelte/…)
```

**Electron (JS):**
```
main/                       # processo principal (Node): janela, IPC main
  main.js
  preload.js                # contextBridge: expõe API segura ao renderer
renderer/                   # UI (sem Node integration)
```

> Note o padrão comum: **um lugar para o host**, **um para a web**, **um para a ponte**,
> **um para lógica pura**, **um para empacotamento**. Só mudam os nomes.

---

## 8. Padrões de UI e estado

- **UI como função do estado:** `render(snapshot)` decide tudo; sem estado escondido no DOM.
- **Máquina de estados de tela:** `loading → (ok | empty | error)`; cada um tem layout próprio.
  Nunca deixe a tela "em branco" num estado não previsto.
- **Design tokens em CSS** (`--color-*`, `--space-*`, `--radius-*`) — troca de tema é só
  trocar variáveis (`[data-theme="dark"]`).
- **Tema:** decida claro/escuro/auto; persista a escolha (localStorage); ofereça toggle.
- **Responsividade:** unidades relativas, flex/grid, conteúdo com **rolagem** própria em
  overflow; nada de tamanho fixo que corte conteúdo.
- **Acessibilidade:** HTML semântico, foco visível, contraste, `prefers-reduced-motion`.
- **Feedback:** todo comando que demora mostra estado (spinner/desabilita botão) e trata erro.

---

## 9. Segurança — a fronteira de confiança

O renderer roda **conteúdo web**: trate-o como potencialmente hostil (XSS, dependência
comprometida). Checklist:

- [ ] **CSP restritiva** (sem `unsafe-inline` para script; nada de origem externa não
      necessária). Idealmente **tudo local/embutido**.
- [ ] **Isolamento de contexto** ligado; **sem** acesso direto a Node/SO no renderer
      (Electron: `contextIsolation:true`, `nodeIntegration:false`, use `preload` +
      `contextBridge`). Tauri: **allowlist** mínima. pywebview: exponha **só** os
      métodos necessários no `js_api`.
- [ ] **Valide toda entrada** vinda do renderer no host (tipos, faixas, tamanho).
- [ ] **Segredos só no host** — nunca no HTML/JS nem no snapshot. Guarde com o cofre do
      SO (DPAPI/Keychain/libsecret) quando aplicável.
- [ ] **Sem `eval`/`innerHTML`** com dado dinâmico não sanitizado.
- [ ] **Superfície mínima:** exponha o menor conjunto de comandos possível.
- [ ] **Empacotamento:** assine o binário; fixe versões de dependências; audite terceiros.
- [ ] **Rede:** valide respostas externas; trate timeouts; sem confiar em payload remoto.

> Mnemônico: **"o renderer nunca é dono de nada perigoso"** — janela, arquivo, segredo e
> rede são do host, acessados por comandos explícitos e validados.

---

## 10. Empacotamento e distribuição

- **Bundler por framework:** PyInstaller/Briefcase (Python), `tauri build` (Tauri),
  electron-builder/Forge (Electron).
- **Dependência de runtime:** se usa WebView do SO, **documente/instale** o runtime
  (ex.: WebView2 no Windows) — ou embuta, se o framework permitir.
- **Assinatura de código:** essencial para evitar avisos do SO e **falsos-positivos de
  antivírus** (comuns em binários "onefile" não assinados). Sem verba de assinatura,
  prefira **onedir** (pasta) a **onefile**, que costuma disparar menos heurística.
- **Instalador:** MSI/NSIS/`.pkg`/AppImage; atalhos; opção de **iniciar com o sistema**.
- **Auto-update:** Tauri/Electron têm updaters; senão, cheque versão e baixe manual.
- **Tamanho:** WebView do SO ≪ Chromium embutido. Faça *tree-shaking* do frontend.
- **Distribuição:** binários grandes vão em **Releases**, não no repositório git.

---

## 11. Estratégia de testes

Pirâmide adaptada ao híbrido:

| Nível        | Alvo                                              | Ferramenta (ex.)                  |
|--------------|---------------------------------------------------|-----------------------------------|
| **Unit**     | `domain/` puro do host + helpers de UI            | pytest / vitest / cargo test      |
| **Contract** | snapshot e comandos batem com o **schema**        | validação de JSON Schema          |
| **Integração** | serviços do host (rede/FS) com mocks            | pytest / jest                     |
| **E2E**      | dirige a **UI real** e verifica comportamento      | Playwright / WebdriverIO / Tauri  |
| **Visual**   | regressão de screenshot (temas, breakpoints)      | Playwright screenshots            |

Dicas:
- **Isole a lógica pura** (`domain/`) → 80% dos testes rápidos vivem aqui, sem UI.
- **Testes de contrato** pegam o erro mais caro: host e UI divergirem no formato.
- **E2E** cobre os **estados** (loading/empty/error/ok) e fluxos críticos.

---

## 12. Fluxo de trabalho spec-driven (passo a passo)

```
1. SPEC        Escreva docs/SPEC.md (§5). Defina escopo, features, estados.
2. CONTRATO    Escreva docs/CONTRACT.md (§6): comandos, eventos, envelope, snapshot.
3. ESQUELETO   Crie a estrutura de pastas (§7). Stubs de comando retornando mock.
4. UI-MOCK     Construa render(snapshot) para TODOS os estados usando snapshots falsos.
               (Dá pra validar visualmente sem backend pronto.)
5. DOMÍNIO TDD Implemente a lógica pura com testes primeiro (RED→GREEN→REFACTOR).
6. SERVIÇOS    Ligue rede/FS/cripto no host; preencha o snapshot de verdade.
7. PONTE       Conecte comandos/eventos reais; valide entradas; testes de contrato.
8. NÃO-FUNC.   Segurança (§9), persistência, tema, responsividade, acessibilidade.
9. EMPACOTE    Build + instalador + runtime + (assinatura). Teste em máquina limpa.
10. REVIEW     Code review + checklist de Definition of Done. E2E dos fluxos-chave.
```

Repare que **UI-mock (4)** vem **antes** do backend real: como a UI é função do
snapshot, você desenha e aprova o visual com dados falsos e só depois "liga o cano".

---

## 13. Templates prontos

### 13.1 `SPEC.md` (esqueleto)

```markdown
# <Nome do App> — Especificação

## 1. Produto
- Problema / usuário / valor:
- Escopo (in):        | Fora do escopo (out):
- Métricas de sucesso:

## 2. Funcional
- F-01 <feature>: <descrição> | fluxo | bordas | regras
- F-02 ...

## 3. UI
- Telas: <lista>
- Estados por tela: loading | empty | error | ok | <especiais>
- Tema: claro/escuro/auto | Responsividade | Acessibilidade

## 4. Contrato (resumo — detalhe em CONTRACT.md)
- Comandos: ...
- Eventos: ...

## 5. Não-funcional
- Segurança | Performance | Persistência | Atualização

## 6. Empacotamento
- SOs | Runtime | Instalador | Assinatura

## 7. Definition of Done
- [ ] Testes (unit/contract/e2e)  [ ] Cobertura ≥ X%
- [ ] Estados de UI cobertos       [ ] Review + build verde
```

### 13.2 `CONTRACT.md` (esqueleto)

```markdown
# Contrato da Ponte — v1

## Envelope
- sucesso: { ok:true, data:<T> }
- erro:    { ok:false, error:{ code, message } }

## Snapshot
{ state: "loading|empty|error|ok", message, items[], updatedAt, meta:{version} }

## Comandos (renderer → host)
| nome            | args            | retorno    | erros possíveis        |
|-----------------|-----------------|------------|------------------------|
| getSnapshot     | —               | Snapshot   | —                      |
| refresh         | —               | Snapshot   | NETWORK, AUTH          |
| saveSettings    | Settings        | Settings   | VALIDATION             |
| window.resize   | w:int, h:int    | void       | —                      |

## Eventos (host → renderer)
| nome              | payload   | quando                     |
|-------------------|-----------|----------------------------|
| onSnapshot        | Snapshot  | poller atualizou           |
| onError           | Error     | falha assíncrona           |
```

### 13.3 Definition of Done (checklist reutilizável)

```
[ ] Spec e contrato atualizados
[ ] Todos os estados de UI implementados e testados
[ ] Entradas validadas no host; erros no envelope padrão
[ ] Sem segredo no renderer; CSP/isolamento aplicados
[ ] Testes unit + contract + e2e verdes; cobertura ≥ meta
[ ] Build empacotado testado em máquina limpa
[ ] README + screenshots + licença
```

---

## 14. Anti-padrões e armadilhas

- ❌ **Lógica de negócio no renderer.** Migração de framework quebra tudo; segredo vaza.
- ❌ **Confiar em dados do renderer** sem validar no host.
- ❌ **Snapshot que a UI precisa "recalcular".** Entregue pronto para exibir.
- ❌ **Esquecer estados** (só implementar o "sucesso"): tela em branco em erro/vazio.
- ❌ **Tamanho fixo sem rolagem** → conteúdo cortado ao redimensionar.
- ❌ **CSP permissiva / `innerHTML` com dado externo** → XSS.
- ❌ **Chamar comando a cada frame** (ex.: em `resize`) sem *throttle*/`requestAnimationFrame`.
- ❌ **Binário não assinado "onefile"** e surpresa com antivírus/SmartScreen.
- ❌ **Bloquear a thread de UI** com rede/disco no renderer.
- ❌ **Commitar build/segredos/estado local** no git.

---

## 15. Ecossistema e leituras

- **Frameworks:** Electron, Tauri, pywebview, Wails, Neutralino, NW.js, CEF.
- **Motores web do SO:** WebView2 (Win), WKWebView (macOS), WebKitGTK (Linux).
- **Bridges/segurança:** Electron `contextBridge`/`preload`; Tauri *commands*+*allowlist*;
  pywebview `js_api`.
- **Empacotadores:** electron-builder/Forge, `tauri build`, PyInstaller/Briefcase.
- **Testes E2E:** Playwright, WebdriverIO, `tauri-driver`.
- **Conceitos p/ aprofundar:** IPC e fronteira de confiança, JSON Schema/contract testing,
  máquinas de estado de UI, design tokens, code signing, auto-update.

---

> **Resumo em uma frase:** projete o **contrato** e os **estados** primeiro, mantenha o
> **renderer burro e desconfiado**, isole a **lógica pura** para testar, e trate a **ponte**
> como a API que segura o app inteiro — o framework (Electron/Tauri/pywebview) vira detalhe.
```
