"""Fluxo OAuth (PKCE) reusando o client publico do Claude Code — login in-app.

Modo copy/paste (sem servidor local): abre a URL de authorize; o usuario faz login,
autoriza e cola o codigo (CODE#STATE) de volta.

NAO-OFICIAL: reusa o client_id do Claude Code. Serve para ler o uso da PROPRIA conta
do usuario. Nao ha registro de client de terceiros na Anthropic.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.parse
import urllib.request

CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
AUTHORIZE_URL = "https://claude.ai/oauth/authorize"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"
SCOPE = "org:create_api_key user:profile user:inference"
_TIMEOUT = 120


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def make_pkce() -> tuple[str, str]:
    """Retorna (verifier, challenge) para o fluxo PKCE S256."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def authorize_url(verifier: str, challenge: str) -> str:
    """URL para abrir no navegador. O Claude Code usa o verifier como 'state'."""
    params = {
        "code": "true",
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": verifier,
    }
    return AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)


def _post_token(body: dict) -> dict:
    # O endpoint exige x-www-form-urlencoded (JSON retorna erro).
    data = urllib.parse.urlencode(body).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "claude-code/1.0.0"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


def exchange_code(code_input: str, verifier: str) -> dict:
    """Troca o codigo por tokens. `code_input` pode vir como 'CODE#STATE'.

    Retorna o dict cru da Anthropic: access_token, refresh_token, expires_in, ...
    """
    code, _, state = code_input.partition("#")
    body = {
        "grant_type": "authorization_code",
        "code": code.strip(),
        "state": (state or verifier).strip(),
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }
    return _post_token(body)


def refresh(refresh_token: str) -> dict:
    """Renova o access_token usando o refresh_token."""
    return _post_token({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
    })
