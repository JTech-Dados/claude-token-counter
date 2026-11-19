"""Recupera o token OAuth que o app do Claude Desktop ja guardou neste PC e
consulta o uso oficial (sessao 5h + semanal) via https://api.anthropic.com/api/oauth/usage.

Nada e criado nem colado: o token e decifrado localmente com a sua conta do Windows
(DPAPI protege a chave do os_crypt; o token fica em AES-256-GCM no config.json do app).
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import json
import os
import urllib.request
import urllib.error

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


# ---------------------------------------------------------------- DPAPI (ctypes)
class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi_unprotect(data: bytes) -> bytes:
    blob_in = _BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)),
                                           ctypes.POINTER(ctypes.c_char)))
    blob_out = _BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptUnprotectData falhou (DPAPI).")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


# ---------------------------------------------------------------- localizacao
def _candidate_roots() -> list[str]:
    """Bases onde o app pode ter guardado os dados.

    Inclui %APPDATA%/%LOCALAPPDATA% E os caminhos derivados de %USERPROFILE%,
    porque o Python da Microsoft Store redireciona %APPDATA% para uma sandbox
    e, nesse caso, so o USERPROFILE aponta para a pasta real do Claude.
    """
    roots: list[str] = []
    for env in ("APPDATA", "LOCALAPPDATA"):
        val = os.environ.get(env)
        if val:
            roots.append(val)
    profile = os.environ.get("USERPROFILE")
    if profile:
        roots.append(os.path.join(profile, "AppData", "Roaming"))
        roots.append(os.path.join(profile, "AppData", "Local"))
    # Versao da Microsoft Store: os dados ficam em
    #   %LOCALAPPDATA%\Packages\<Claude_xxx>\LocalCache\{Roaming,Local}\Claude
    local = os.environ.get("LOCALAPPDATA") or (
        os.path.join(profile, "AppData", "Local") if profile else "")
    pkgs = os.path.join(local, "Packages") if local else ""
    if pkgs and os.path.isdir(pkgs):
        try:
            for name in os.listdir(pkgs):
                low = name.lower()
                if low.startswith("claude") or "anthropic" in low:
                    cache = os.path.join(pkgs, name, "LocalCache")
                    roots.append(os.path.join(cache, "Roaming"))
                    roots.append(os.path.join(cache, "Local"))
        except OSError:
            pass
    # remove duplicatas preservando ordem
    return list(dict.fromkeys(roots))


def _app_dir() -> str:
    for root in _candidate_roots():
        for name in ("Claude", "AnthropicClaude"):
            d = os.path.join(root, name)
            if os.path.exists(os.path.join(d, "config.json")) and os.path.exists(
                os.path.join(d, "Local State")
            ):
                return d
    raise FileNotFoundError(
        "Nao encontrei a pasta do app do Claude (config.json + Local State). "
        "Abra o app do Claude uma vez."
    )


def _aes_key(app_dir: str) -> bytes:
    with open(os.path.join(app_dir, "Local State"), "r", encoding="utf-8") as f:
        ls = json.load(f)
    enc = base64.b64decode(ls["os_crypt"]["encrypted_key"])
    if enc[:5] == b"DPAPI":
        enc = enc[5:]
    return _dpapi_unprotect(enc)


class _AppBoundError(Exception):
    """Blob cifrado com 'app-bound encryption' (prefixo != v10): so o proprio app
    consegue decifrar. Nao tentamos contornar essa protecao de seguranca."""

    def __init__(self, prefix: str):
        super().__init__(prefix)
        self.prefix = prefix


def _decrypt_blob(b64: str, key: bytes) -> dict:
    raw = base64.b64decode(b64)          # Chromium: 'v10' + nonce(12) + ct + tag(16)
    if raw[:3] != b"v10":
        raise _AppBoundError(raw[:3].decode("latin-1", "replace"))
    nonce, ct = raw[3:15], raw[15:]
    plain = AESGCM(key).decrypt(nonce, ct, None)
    return json.loads(plain)


def _find_token(obj) -> tuple[str, float] | None:
    """Busca recursiva por um token 'sk-ant-...' no JSON decifrado, tolerando
    mudancas de estrutura entre versoes do Claude. Retorna (token, expiresAt)."""
    best: tuple[str, float] | None = None
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            tok = cur.get("token") or cur.get("accessToken")
            if isinstance(tok, str) and tok.startswith("sk-ant"):
                raw_exp = cur.get("expiresAt", cur.get("expires_at", 0))
                try:
                    exp = float(raw_exp)
                except (TypeError, ValueError):
                    exp = 0.0
                if best is None or exp > best[1]:
                    best = (tok, exp)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
        elif isinstance(cur, str) and cur.startswith("sk-ant") and len(cur) > 20:
            if best is None:
                best = (cur, 0.0)
    return best


def get_token() -> str:
    app_dir = _app_dir()
    key = _aes_key(app_dir)
    with open(os.path.join(app_dir, "config.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)

    present = [n for n in ("oauth:tokenCacheV2", "oauth:tokenCache") if n in cfg]
    if not present:
        raise RuntimeError(
            "O Claude Desktop nao tem uma sessao salva aqui. Abra o app do Claude "
            "e faca login uma vez."
        )

    best: tuple[str, float] | None = None
    app_bound = False
    for name in present:
        try:
            obj = _decrypt_blob(cfg[name], key)
        except _AppBoundError:
            app_bound = True
            continue
        except Exception:
            continue
        found = _find_token(obj)
        if found and (best is None or found[1] > best[1]):
            best = found

    if best:
        return best[0]
    if app_bound:
        raise RuntimeError(
            "Esta versao do Claude Desktop cifra o token com 'app-bound encryption', "
            "que impede outros apps de le-lo. Nao da para obter o uso nesta maquina."
        )
    raise RuntimeError(
        "Nao consegui decifrar o token do Claude (formato inesperado, talvez uma "
        "versao nova do app). Reabra o Claude e tente novamente."
    )


class UsageError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def get_usage(token: str | None = None) -> dict:
    if token is None:
        token = get_token()
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "claude-code/1.0.0",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise UsageError(f"HTTP {e.code}", status=e.code) from e
    except urllib.error.URLError as e:
        raise UsageError(str(e.reason)) from e


if __name__ == "__main__":
    u = get_usage()
    fh, sd = u.get("five_hour") or {}, u.get("seven_day") or {}
    print(f"Sessao 5h : {100 - (fh.get('utilization') or 0):.0f}% restante  (reset {fh.get('resets_at')})")
    print(f"Semana 7d : {100 - (sd.get('utilization') or 0):.0f}% restante  (reset {sd.get('resets_at')})")
