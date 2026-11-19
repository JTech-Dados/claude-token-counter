# Contador de Tokens · Claude — v5.1 (uso pessoal)

Widget de bandeja que mostra o uso do seu plano Claude (sessão 5 h, semanal, créditos).
A **novidade da v5** é o **login pela sua conta Claude dentro do app** — assim funciona
em qualquer máquina, **sem depender do Claude Desktop instalado**.

---

## Instalação (suas outras máquinas)

1. Copie para a máquina o arquivo **`Instalador Contador de Tokens (v5.1).exe`**.
2. Dê **duplo-clique**. Ele instala o app, cria atalho no Menu Iniciar, liga o "iniciar com o
   Windows", instala o **WebView2** se faltar, e abre o app. (Mata versão antiga antes.)
3. Se aparecer o **SmartScreen** (não assinado): *Mais informações → Executar assim mesmo*.

## Como logar (para ver o uso sem Claude Desktop)

1. No widget, clique no **ícone de pessoa** (no cabeçalho) → **Entrar na conta Claude**.
2. Abre o login do Claude no navegador → faça login → **Authorize** → copie o **código**
   (formato `CODE#STATE`).
3. Cole o código no campo do widget → **Entrar**.
4. Aparece **"● Conectado à sua conta Claude"**. O token fica guardado localmente (DPAPI) e
   **renova sozinho**. Para sair, clique de novo no ícone de pessoa (**Sair da conta**).

> Se o **Claude Desktop** estiver instalado e logado na máquina, o app usa o token dele
> automaticamente (não precisa logar). O login pela conta é o **plano B** para máquinas sem o
> Desktop.

## Recursos

- Sessão 5 h e semanal, com "esgota em ~X" e reset.
- **Créditos de uso**: quando a sessão zera, mostra o valor (R$) em vez de % negativo.
- Alerta configurável (bip + aviso no widget) quando restar X %.
- Gráfico de consumo diário, tema claro/escuro, instância única, lembra a posição.
- Janela com **altura automática** (sem scroll).

## Novidades da v5.1 (correção)

- **Corrigido: o app abria fora da tela.** Em telas com escala do Windows diferente de 100 %
  (125 % e 150 % são o padrão na maioria dos notebooks), a janela era posicionada em pixels
  físicos enquanto a interface usa pixels lógicos — ela nascia além da borda direita do
  monitor. O app estava rodando normalmente, só que num ponto invisível: parecia que o ícone
  da bandeja não respondia e que, depois de fechado, não abria mais.
- A posição padrão agora é **centralizada** na tela (antes era o canto inferior direito).
- A posição salva é **validada** ao abrir: se não couber mais na tela atual (por exemplo, um
  monitor que foi desconectado), a janela volta ao centro em vez de sumir.
- Clicar em **Mostrar** na bandeja **recentraliza** a janela caso ela esteja fora da tela.
- **Corrigido: barra de rolagem na janela.** A altura automática era calculada uma única vez
  logo após carregar os dados, então qualquer coisa que crescesse depois (fonte terminando de
  carregar, seção nova aparecendo) passava a sobrar e virava barra de rolagem. Agora a janela
  acompanha o conteúdo continuamente, e o cálculo não mistura mais as unidades do `zoom` da
  interface.

## Desinstalar

`%LOCALAPPDATA%\Contador de Tokens\desinstalar.bat` (ou o `desinstalar.bat` desta pasta).

## Conteúdo

```
count_tokens_v5/
├─ Contador de Tokens.exe                 ← app v5 (autônomo)
├─ Instalador Contador de Tokens (v5).exe ← instalador único (WebView2 embutido)
├─ instalado_final.bat                    ← instalador alternativo (2 arquivos)
├─ desinstalar.bat
├─ LEIA-ME.md
└─ fonte/  (código: v4/{app,api,ui.html}, claude_usage.py, v5/{oauth,token_store}, claude.ico)
```

## Requisitos

- Windows 10/11 com **WebView2** (o instalador instala se faltar).
- Uma **conta Claude** (login no app) OU o **Claude Desktop** logado na máquina.
