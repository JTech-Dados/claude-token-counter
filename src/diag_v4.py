"""Diagnostico v3 — PROCURA onde o app do Claude guarda config.json + Local State."""
import os
import sys
from datetime import datetime

print("=== Procurando os dados do Claude no seu PC ===")
print("hora:", datetime.now())

appdata = os.environ.get("APPDATA", "")
local = os.environ.get("LOCALAPPDATA", "")


def has_signature(d):
    try:
        return (os.path.exists(os.path.join(d, "config.json"))
                and os.path.exists(os.path.join(d, "Local State")))
    except Exception:
        return False


print("\n-- Pastas de topo em %APPDATA% --")
try:
    print("  ", sorted(os.listdir(appdata)))
except Exception as e:  # noqa: BLE001
    print("   erro:", e)

print("\n-- Pastas de topo em %LOCALAPPDATA% --")
try:
    print("  ", sorted(os.listdir(local)))
except Exception as e:  # noqa: BLE001
    print("   erro:", e)

hits = []

# 1) nomes conhecidos direto em Roaming/Local
for base in (appdata, local):
    for name in ("Claude", "AnthropicClaude", "Anthropic", "claude"):
        d = os.path.join(base, name)
        if os.path.isdir(d):
            print(f"\n[pasta] {d}  (assinatura token? {has_signature(d)})")
            if has_signature(d):
                hits.append(d)

# 2) apps da Microsoft Store: %LOCALAPPDATA%\Packages\*Claude*|*Anthropic*
pkgs = os.path.join(local, "Packages")
if os.path.isdir(pkgs):
    for p in os.listdir(pkgs):
        if "claude" in p.lower() or "anthropic" in p.lower():
            root = os.path.join(pkgs, p)
            print(f"\n[Store] pacote encontrado: {p}")
            for sub in ("LocalCache\\Roaming\\Claude", "LocalCache\\Local\\Claude",
                        "LocalCache\\Roaming\\AnthropicClaude", "RoamingState\\Claude"):
                d = os.path.join(root, sub)
                if os.path.isdir(d):
                    print(f"   -> {d}  (assinatura token? {has_signature(d)})")
                    if has_signature(d):
                        hits.append(d)

# 3) varredura rasa: qualquer 'config.json' + 'Local State' ate 2 niveis em Roaming/Local
print("\n-- Varredura rasa por assinatura (config.json + Local State) --")
for base in (appdata, local):
    try:
        for name in os.listdir(base):
            d = os.path.join(base, name)
            if os.path.isdir(d) and has_signature(d) and d not in hits:
                hits.append(d)
                print("   achou:", d)
    except Exception:
        pass

print("\n=== RESULTADO ===")
if hits:
    for h in hits:
        print("  TOKEN PROVAVEL EM:", h)
else:
    print("  Nao encontrei nenhuma pasta com config.json + Local State.")
    print("  -> O app do Claude Desktop pode estar desinstalado ou deslogado.")
    print("     Abra o app do Claude, faca login, e rode este diagnostico de novo.")
print("\n=== fim ===")
