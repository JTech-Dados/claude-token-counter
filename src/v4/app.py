"""Contador de Tokens v4 — janela web (pywebview) + icone na bandeja.

UI fiel ao mockup (HTML/CSS em ui.html), tema claro/escuro com botao, e um
poller que atualiza os dados e a bandeja a cada 5 min. Fechar recolhe para a
bandeja; nao aparece como "python" na barra de tarefas (janela frameless).
"""
from __future__ import annotations

import glob
import math
import os
import subprocess
import sys
import threading
import time


def _notify(title: str, message: str) -> None:
    """Balao de notificacao do Windows via PowerShell NotifyIcon — mais confiavel
    que o notify do pystray, que as vezes nao aparece sem AppUserModelID."""
    def esc(s: str) -> str:
        return s.replace("'", "''")

    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "Add-Type -AssemblyName System.Drawing;"
        "$n=New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon=[System.Drawing.SystemIcons]::Warning;"
        "$n.Visible=$true;"
        f"$n.ShowBalloonTip(10000,'{esc(title)}','{esc(message)}',"
        "[System.Windows.Forms.ToolTipIcon]::Warning);"
        "Start-Sleep -Seconds 6;$n.Dispose()"
    )
    subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _reexec_if_store_python() -> None:
    """O Python da Microsoft Store virtualiza o %APPDATA% e nao acha a pasta do
    Claude. Se for ele, reexecuta no Python real de Programs\\Python."""
    exe = sys.executable or ""
    if "WindowsApps" not in exe:
        return
    if os.environ.get("_CLAUDE_TK_REEXEC"):
        return
    local = os.environ.get("LOCALAPPDATA", "")
    for real in sorted(glob.glob(os.path.join(
            local, "Programs", "Python", "Python*", "pythonw.exe")), reverse=True):
        if os.path.exists(real):
            os.execve(real, [real, os.path.abspath(__file__)],
                      dict(os.environ, _CLAUDE_TK_REEXEC="1"))


_reexec_if_store_python()

import webview  # noqa: E402
import pystray  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api import Api  # noqa: E402
import winpos  # noqa: E402

APP_VERSION = "5.2"
POLL_SECONDS = 300
BACKOFF = (120, 240, 300)
CORAL_RGB, CRIT_RGB, ERR_RGB, BURST_DARK = (217, 119, 87), (224, 85, 78), (120, 118, 110), (34, 33, 31, 255)


# ------------------------------------------------------------------ icones tray
def _font(size: int):
    for name in ("segoeuib.ttf", "arialbd.ttf", "seguisb.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _burst(size: int, color) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size / 2
    w = max(2, round(size * 0.10))
    for i in range(12):
        a = math.pi * 2 * i / 12
        r = size * (0.44 if i % 2 == 0 else 0.30)
        d.line((c, c, c + r * math.cos(a), c + r * math.sin(a)), fill=color, width=w)
    return img


def tray_image(pct: int, err: bool) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = ERR_RGB if err else (CRIT_RGB if pct <= 10 else CORAL_RGB)
    d.rounded_rectangle((2, 2, 61, 61), radius=15, fill=color)
    text = "!" if err else str(pct)
    fs = 34 if len(text) >= 3 else (42 if len(text) == 2 else 46)
    f = _font(fs)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    d.text(((64 - (r - l)) / 2 - l, (64 - (b - t)) / 2 - t), text, font=f, fill="white")
    return img


def _html_path() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ui.html")


def _single_instance():
    """Instancia unica via mutex nomeado. Se ja existe uma instancia, sinaliza
    para ela aparecer e retorna (False, evento); senao retorna (True, evento)."""
    import ctypes
    k = ctypes.windll.kernel32
    ev = k.CreateEventW(None, False, False, "Local\\ContadorTokensShow")
    k.CreateMutexW(None, False, "Local\\ContadorTokensMutex")
    if k.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        k.SetEvent(ev)
        return False, ev
    return True, ev


def _default_pos(w: int, h: int) -> tuple[int, int]:
    """Posicao padrao da janela: centralizada no monitor principal."""
    return winpos.centered_pos(w, h, winpos.monitors())


class App:
    def __init__(self, show_event=None) -> None:
        self._show_event = show_event
        self.api = Api(on_snapshot=self._on_snapshot)
        self._running = True
        self._alerted = False
        pos = self.api.pos or (None, None)
        self.window = webview.create_window(
            "Contador de Tokens",
            url=_html_path(),
            js_api=self.api,
            width=360, height=600,
            x=pos[0], y=pos[1],
            frameless=True, easy_drag=False,
            background_color="#1b1b19",
            resizable=False,
        )
        self.api.bind_window(self.window)
        self.icon = pystray.Icon("claude_tokens", tray_image(0, True), "Claude — carregando...")
        self.icon.menu = pystray.Menu(
            pystray.MenuItem("Mostrar", self._show, default=True),
            pystray.MenuItem("Atualizar agora", lambda _i, _it: self._refresh_async()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self._quit),
        )

    # ---- tray callbacks
    def _show(self, _i=None, _it=None) -> None:
        try:
            self.window.show()
            self.window.restore()
        except Exception:
            pass
        self._ensure_on_screen()

    def _hwnd(self):
        """Handle Win32 da janela (o pywebview nao expoe de forma estavel)."""
        import ctypes
        try:
            native = getattr(self.window, "native", None)
            if native is not None and hasattr(native, "Handle"):
                return int(native.Handle)
        except Exception:
            pass
        return ctypes.windll.user32.FindWindowW(None, "Contador de Tokens")

    def _ensure_on_screen(self) -> None:
        """Rede de seguranca: se a janela estiver fora de qualquer monitor,
        recentraliza. Tudo em pixels fisicos, entao vale para qualquer escala."""
        try:
            if winpos.ensure_on_screen(self._hwnd()):
                x, y, _w, _h = winpos.window_rect(self._hwnd())
                self.api.save_pos(x, y)
        except Exception:
            pass

    def _quit(self, _i=None, _it=None) -> None:
        self._running = False
        try:
            self.icon.stop()
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass

    def _refresh_async(self) -> None:
        threading.Thread(target=self.api.refresh, daemon=True).start()

    def _on_snapshot(self, snap: dict) -> None:
        """Atualiza a bandeja e dispara alerta quando a sessao fica baixa."""
        if snap.get("state") == "ok":
            rem = snap.get("session_remaining", 0)
            self.icon.icon = tray_image(rem, False)
            self.icon.title = f"Claude · sessao {rem}% restante · v{APP_VERSION}"
            alert = snap.get("alert") or {}
            low = alert.get("enabled") and rem <= alert.get("threshold", 20)
            if low and not self._alerted:
                self._alerted = True
                # 1) bip audivel (sempre funciona; o aviso visual vai na UI)
                try:
                    import winsound
                    winsound.MessageBeep(0x30)  # MB_ICONWARNING
                except Exception:
                    pass
                # 3) traz a janela para frente (garante que o usuario ve)
                try:
                    self._show()
                except Exception:
                    pass
            if not low:
                self._alerted = False
        else:
            self.icon.icon = tray_image(0, True)
            self.icon.title = f"Claude · {snap.get('message', 'sem dados')} · v{APP_VERSION}"

    # ---- loops
    def _poller(self) -> None:
        fails = 0
        while self._running:
            snap = self.api.refresh()
            ok = snap.get("state") == "ok"
            wait = POLL_SECONDS if ok else BACKOFF[min(fails, len(BACKOFF) - 1)]
            fails = 0 if ok else fails + 1
            for _ in range(wait):
                if not self._running:
                    return
                time.sleep(1)

    def _watch_show(self) -> None:
        import ctypes
        k = ctypes.windll.kernel32
        while self._running and self._show_event:
            if k.WaitForSingleObject(self._show_event, 500) == 0:  # sinalizado
                self._show()

    def _fix_pos_when_ready(self) -> None:
        """Espera a janela existir e garante que ela nasca dentro da tela."""
        for _ in range(60):
            if not self._running:
                return
            if self._hwnd():
                self._ensure_on_screen()
                return
            time.sleep(0.25)

    def run(self) -> None:
        threading.Thread(target=self._fix_pos_when_ready, daemon=True).start()
        self.icon.run_detached()
        threading.Thread(target=self._poller, daemon=True).start()
        if self._show_event:
            threading.Thread(target=self._watch_show, daemon=True).start()
        webview.start(gui="edgechromium", debug=False)
        self._running = False
        try:
            self.icon.stop()
        except Exception:
            pass


def main() -> None:
    first, show_event = _single_instance()
    if not first:
        return  # ja ha uma instancia rodando; ela foi sinalizada para aparecer
    App(show_event).run()


if __name__ == "__main__":
    main()
