"""Armazenamento local do token OAuth (v5), encriptado com DPAPI.

DPAPI ja ata a decifragem ao usuario+maquina (sem PIN nesta versao de demonstracao).
Guarda {access, refresh, expires_at} em %LOCALAPPDATA%\\Contador de Tokens\\oauth.bin.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import time


class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt(func, data: bytes) -> bytes:
    blob_in = _BLOB(len(data), ctypes.cast(
        ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_char)))
    blob_out = _BLOB()
    if not func(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("DPAPI falhou")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _protect(data: bytes) -> bytes:
    return _crypt(ctypes.windll.crypt32.CryptProtectData, data)


def _unprotect(data: bytes) -> bytes:
    return _crypt(ctypes.windll.crypt32.CryptUnprotectData, data)


def _path() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "Contador de Tokens")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "oauth.bin")


def save(access: str, refresh: str, expires_in) -> None:
    try:
        exp = int(time.time()) + int(expires_in or 0)
    except (TypeError, ValueError):
        exp = 0
    obj = {"access": access, "refresh": refresh, "expires_at": exp}
    with open(_path(), "wb") as f:
        f.write(_protect(json.dumps(obj).encode("utf-8")))


def load() -> dict | None:
    try:
        with open(_path(), "rb") as f:
            return json.loads(_unprotect(f.read()))
    except Exception:
        return None


def clear() -> None:
    try:
        os.remove(_path())
    except OSError:
        pass
