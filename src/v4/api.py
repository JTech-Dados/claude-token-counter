"""Backend de dados do widget v4 (exposto ao JS via pywebview js_api).

Le o uso oficial (via claude_usage), enriquece cada limite com status, projecao
de esgotamento e textos de reset, mantem um historico local para o grafico de
"consumo diario" e guarda as preferencias de alerta.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone

_PYDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PYDIR)
sys.path.insert(0, os.path.join(_PYDIR, "v5"))
import claude_usage  # noqa: E402
try:
    import oauth as _oauth  # noqa: E402  (login in-app v5, uso pessoal)
    import token_store as _store  # noqa: E402
except Exception:  # v5 opcional
    _oauth = _store = None

_MINUTE_MS = 60_000
_HOUR_MS = 3_600_000
_DAY_MS = 86_400_000
FIVE_HOUR_WINDOW_MS = 5 * _HOUR_MS
SEVEN_DAY_WINDOW_MS = 7 * _DAY_MS

KIND_LABELS = {
    "session": ("SESSÃO", "5 H", FIVE_HOUR_WINDOW_MS),
    "weekly_all": ("SEMANA", "7 DIAS", SEVEN_DAY_WINDOW_MS),
    "weekly_scoped": ("SEMANA", "7 DIAS", SEVEN_DAY_WINDOW_MS),
}

HISTORY_MAX = 400
DEFAULT_ALERT = {"threshold": 20, "enabled": True}


def _data_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "Contador de Tokens")
    os.makedirs(d, exist_ok=True)
    return d


# --------------------------------------------------------------- projecao/tempo
def _format_duration(ms: float) -> str:
    ms = max(ms, 0)
    minutes = round(ms / _MINUTE_MS)
    if minutes < 60:
        return f"{minutes} min"
    hours, mm = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} h {mm:02d} min" if mm else f"{hours} h"
    days, hh = divmod(hours, 24)
    return f"{days} d {hh} h" if hh else f"{days} d"


def _ms_until(iso: str | None, now: datetime) -> float:
    if not iso:
        return -1
    return (datetime.fromisoformat(iso) - now).total_seconds() * 1000


def _project_ms(util: float, iso: str | None, window_ms: float, now: datetime):
    if not iso:
        return None
    reset_ms = datetime.fromisoformat(iso).timestamp() * 1000
    elapsed = max(now.timestamp() * 1000 - (reset_ms - window_ms), _MINUTE_MS)
    rate = util / elapsed
    if rate <= 0:
        return None
    return (100 - util) / rate


# --------------------------------------------------------------- montagem
def _status(remaining: int, severity: str, exhausted: bool) -> str:
    if exhausted or remaining <= 0:
        return "limite"
    if severity == "critical":
        return "critico"
    if severity == "warning":
        return "atencao"
    return "seguro"


def _title(limit: dict) -> tuple[str, str]:
    name, sub, _ = KIND_LABELS.get(limit.get("kind"), ("LIMITE", "", SEVEN_DAY_WINDOW_MS))
    model = ((limit.get("scope") or {}).get("model") or {}).get("display_name")
    if model and limit.get("kind") == "weekly_scoped":
        return f"{name} · {model.upper()}", sub
    return name, sub


def _build_limit(limit: dict, now: datetime) -> dict:
    percent = int(limit.get("percent") or 0)          # % usado
    remaining = max(0, 100 - percent)
    severity = limit.get("severity", "normal")
    _, _, window_ms = KIND_LABELS.get(limit.get("kind"), ("", "", SEVEN_DAY_WINDOW_MS))
    exhausted = percent >= 100
    name, sub = _title(limit)

    proj = _project_ms(percent, limit.get("resets_at"), window_ms, now)
    if exhausted:
        rhythm = "Cota esgotada"
    elif proj is None:
        rhythm = "Sem consumo recente"
    else:
        rhythm = f"No ritmo atual, esgota em ~{_format_duration(proj)}"

    reset_ms = _ms_until(limit.get("resets_at"), now)
    reset_txt = f"Reseta em {_format_duration(reset_ms)}" if reset_ms >= 0 else ""

    return {
        "kind": limit.get("kind"),
        "name": name,
        "sub": sub,
        "used": percent,
        "remaining": remaining,
        "status": _status(remaining, severity, exhausted),
        "rhythm": rhythm,
        "reset": reset_txt,
    }


def _credits(data: dict) -> dict | None:
    """Creditos de uso (quando a sessao esgota). None se nao houver consumo."""
    spend = data.get("spend") or {}
    used = spend.get("used") or {}
    minor = used.get("amount_minor")
    if not minor:
        return None
    cur = used.get("currency") or ""
    exp = int(used.get("exponent", 2))
    limit_minor = (spend.get("limit") or {}).get("amount_minor")

    def fmt(m):
        return None if m is None else f"{cur} {m / (10 ** exp):.2f}"

    return {"used": fmt(minor), "limit": fmt(limit_minor),
            "percent": spend.get("percent")}


class Api:
    """Exposto ao JS. Um poller em thread atualiza o snapshot e a bandeja."""

    def __init__(self, on_snapshot=None) -> None:
        self._on_snapshot = on_snapshot        # callback(snapshot) p/ atualizar tray
        self._lock = threading.Lock()
        self._history: list[dict] = self._load_history()
        self.alert = self._load_alert()
        self.pos = self._load_pos()
        self.snapshot = {"state": "loading"}
        self._window = None                    # janela pywebview (ligada depois)
        self._verifier = None                  # PKCE em andamento (v5)
        self._pending_login = False            # forca a tela de login
        self._login_msg = ""

    # ---- controle de janela (chamado pelo JS)
    def bind_window(self, window) -> None:
        self._window = window

    def _hwnd(self):
        """Handle Win32 da janela (o pywebview nao expoe de forma estavel)."""
        import ctypes
        try:
            native = getattr(self._window, "native", None)
            if native is not None and hasattr(native, "Handle"):
                return int(native.Handle)
        except Exception:
            pass
        return ctypes.windll.user32.FindWindowW(None, "Contador de Tokens")

    def minimize(self) -> None:
        """Minimiza a janela.

        O window.minimize() do pywebview (WindowState = Minimized) nao tem
        efeito nesta janela frameless, entao vamos direto no Win32.
        """
        if not self._window:
            return
        import ctypes
        SW_MINIMIZE = 6
        try:
            hwnd = self._hwnd()
            if hwnd and ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE):
                return
        except Exception:
            pass
        try:
            self._window.minimize()
        except Exception:
            pass

    def hide_window(self) -> None:
        if self._window:
            try:
                self._window.hide()
            except Exception:
                pass

    def resize_window(self, width: int, height: int) -> None:
        if self._window:
            try:
                self._window.resize(int(width), int(height))
            except Exception:
                pass

    # ---- persistencia
    def _load_alert(self) -> dict:
        try:
            with open(os.path.join(_data_dir(), "settings.json"), encoding="utf-8") as f:
                d = json.load(f)
            return {"threshold": int(d.get("threshold", 20)),
                    "enabled": bool(d.get("enabled", True))}
        except Exception:
            return dict(DEFAULT_ALERT)

    def _load_pos(self):
        try:
            with open(os.path.join(_data_dir(), "settings.json"), encoding="utf-8") as f:
                d = json.load(f)
            return (int(d["x"]), int(d["y"]))
        except Exception:
            return None

    def _save_alert(self) -> None:
        data = dict(self.alert)
        if self.pos:
            data["x"], data["y"] = int(self.pos[0]), int(self.pos[1])
        try:
            with open(os.path.join(_data_dir(), "settings.json"), "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def save_pos(self, x, y) -> None:
        try:
            self.pos = (int(x), int(y))
        except (TypeError, ValueError):
            return
        self._save_alert()

    def _load_history(self) -> list[dict]:
        try:
            with open(os.path.join(_data_dir(), "usage_history.json"), encoding="utf-8") as f:
                h = json.load(f)
            return h if isinstance(h, list) else []
        except Exception:
            return []

    def _save_history(self) -> None:
        try:
            with open(os.path.join(_data_dir(), "usage_history.json"), "w", encoding="utf-8") as f:
                json.dump(self._history[-HISTORY_MAX:], f)
        except Exception:
            pass

    # ---- token OAuth (v5, uso pessoal)
    def _oauth_access(self):
        """Access token do login in-app, renovando se perto de expirar. None se nao ha."""
        if not (_store and _oauth):
            return None
        tok = _store.load()
        if not tok or not tok.get("access"):
            return None
        if tok.get("expires_at", 0) - time.time() < 120:
            try:
                new = _oauth.refresh(tok["refresh"])
                _store.save(new["access_token"],
                            new.get("refresh_token", tok["refresh"]),
                            new.get("expires_in"))
                tok = _store.load()
            except Exception:
                return None
        return tok.get("access")

    def _finish(self, snap: dict) -> dict:
        snap["alert"] = self.alert
        with self._lock:
            self.snapshot = snap
        if self._on_snapshot:
            try:
                self._on_snapshot(snap)
            except Exception:
                pass
        return snap

    # ---- refresh
    def refresh(self) -> dict:
        now = datetime.now(timezone.utc)
        if self._pending_login:
            return self._finish({"state": "login", "message": self._login_msg})

        access = self._oauth_access()
        try:
            data = (claude_usage.get_usage(token=access) if access
                    else claude_usage.get_usage())
            mode = "oauth" if access else "desktop"
        except claude_usage.UsageError as e:
            return self._finish({"state": "error", "message": f"API indisponivel ({e})"})
        except Exception as e:  # noqa: BLE001 - sem token utilizavel -> oferece login
            return self._finish({"state": "login", "message": f"Sem sessao. {e}"})

        limits = data.get("limits") or []
        if not limits:
            return self._finish({"state": "empty",
                                 "message": "Sem dados de uso disponiveis"})

        built = [_build_limit(l, now) for l in limits]
        session = next((b for b in built if b["kind"] == "session"), built[0])
        week = next((b for b in built if b["kind"] == "weekly_all"), None)
        self._history.append({
            "t": int(now.timestamp()),
            "session": session["used"],
            "week": (week or session)["used"],
        })
        self._history = self._history[-HISTORY_MAX:]
        self._save_history()
        # creditos so quando a sessao 5h esgota (e ai que se usa credito de fato)
        credits = _credits(data) if session["status"] == "limite" else None
        return self._finish({
            "state": "ok",
            "limits": built,
            "session_remaining": session["remaining"],
            "session_status": session["status"],
            "credits": credits,
            "auth_mode": mode,
            "history": self._history[-60:],
            "updated": datetime.now().strftime("%d/%m %H:%M"),
        })

    # ---- API para o JS
    def get_data(self) -> dict:
        with self._lock:
            return self.snapshot

    def refresh_now(self) -> dict:
        return self.refresh()

    def set_alert(self, threshold: int, enabled: bool) -> dict:
        try:
            threshold = max(1, min(99, int(threshold)))
        except Exception:
            threshold = 20
        self.alert = {"threshold": threshold, "enabled": bool(enabled)}
        self._save_alert()
        with self._lock:
            self.snapshot["alert"] = self.alert
        return self.alert

    # ---- login OAuth in-app (v5, uso pessoal)
    def start_login(self) -> dict:
        if not _oauth:
            return {"ok": False, "error": "v5 indisponivel"}
        verifier, challenge = _oauth.make_pkce()
        self._verifier = verifier
        self._pending_login = True
        self._login_msg = ""
        url = _oauth.authorize_url(verifier, challenge)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        self.refresh()
        return {"ok": True, "url": url}

    def submit_login(self, code: str) -> dict:
        if not (_oauth and _store and self._verifier):
            return {"ok": False, "error": "login nao iniciado"}
        try:
            tok = _oauth.exchange_code((code or "").strip(), self._verifier)
            _store.save(tok["access_token"], tok.get("refresh_token", ""),
                        tok.get("expires_in"))
        except Exception as e:  # noqa: BLE001
            self._login_msg = f"Codigo invalido ou expirado ({e})"
            self.refresh()
            return {"ok": False, "error": str(e)}
        self._verifier = None
        self._pending_login = False
        self._login_msg = ""
        self.refresh()
        return {"ok": True}

    def cancel_login(self) -> dict:
        self._pending_login = False
        self._verifier = None
        self.refresh()
        return {"ok": True}

    def logout(self) -> dict:
        if _store:
            _store.clear()
        self.refresh()
        return {"ok": True}
