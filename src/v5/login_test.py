"""Teste do login OAuth in-app (v5) — PROVA que o fluxo gera um token que le o uso.

Abre o login do Claude no navegador, voce cola o codigo, e ele testa /api/oauth/usage.
Se der SUCESSO, o conceito da v5 esta validado e podemos ligar na UI.
"""
import json
import os
import sys
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oauth  # noqa: E402

print("=== Teste de login OAuth (v5) ===\n")
verifier, challenge = oauth.make_pkce()
url = oauth.authorize_url(verifier, challenge)
print("1) Vou abrir o login do Claude no navegador.")
print("   Se nao abrir, copie e cole esta URL:\n")
print(url, "\n")
try:
    webbrowser.open(url)
except Exception:
    pass

print("2) Faca login e clique em Authorize.")
print("   A pagina vai mostrar um CODIGO (formato CODE#STATE).")
code = input("3) Cole o codigo aqui e tecle Enter: ").strip()

print("\nTrocando o codigo por token...")
try:
    tok = oauth.exchange_code(code, verifier)
except Exception as e:  # noqa: BLE001
    print("ERRO na troca do codigo:", repr(e))
    input("\nEnter para fechar...")
    sys.exit(1)

at = tok.get("access_token", "")
print("  access_token:", at[:14], "...",
      "| expires_in:", tok.get("expires_in"),
      "| refresh:", "sim" if tok.get("refresh_token") else "nao")

print("\nTestando /api/oauth/usage com esse token...")
try:
    req = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/usage",
        headers={
            "Authorization": "Bearer " + at,
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "claude-code/1.0.0",
        },
    )
    u = json.loads(urllib.request.urlopen(req, timeout=20).read())
    lims = u.get("limits") or []
    print("  USAGE OK! limites:", len(lims))
    for l in lims:
        print("   -", l.get("kind"), l.get("percent"), "%")
    print("\n>>> SUCESSO: o login in-app funciona e le o uso. <<<")
except Exception as e:  # noqa: BLE001
    print("  ERRO no usage:", repr(e))
    print("  (se for 401/403, talvez o scope/endpoint precise de ajuste)")

input("\nEnter para fechar...")
