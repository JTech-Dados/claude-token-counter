"""Posicionamento de janela consistente com a escala de DPI do Windows.

O pywebview trabalha em coordenadas LOGICAS (ja divididas pela escala), enquanto
as APIs Win32 (GetSystemMetrics, EnumDisplayMonitors) devolvem pixels FISICOS.
Misturar os dois faz a janela nascer fora da tela em qualquer monitor com escala
diferente de 100% — que e o padrao na maioria dos notebooks (125%, 150%).

Tudo aqui e exposto em coordenadas logicas, que sao as que o pywebview espera.
"""
from __future__ import annotations

MIN_VISIBLE_W = 120
MIN_VISIBLE_H = 40


def monitors() -> list[tuple[int, int, int, int]]:
    """Monitores conectados como (x, y, w, h) em pixels FISICOS.

    Mesma unidade de GetWindowRect/SetWindowPos, entao a comparacao com o
    retangulo da janela e direta — sem conversao de escala, que e justamente
    onde o bug original morava.
    """
    import ctypes

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    found: list[tuple[int, int, int, int]] = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                              ctypes.POINTER(RECT), ctypes.c_double)

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

    def cb(hmon, _hdc, lprect, _data):
        r = lprect.contents
        primary = False
        try:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                primary = bool(mi.dwFlags & 1)  # MONITORINFOF_PRIMARY
        except Exception:
            pass
        item = (r.left, r.top, r.right - r.left, r.bottom - r.top)
        # o monitor principal vem sempre primeiro: e nele que centralizamos
        found.insert(0, item) if primary else found.append(item)
        return 1

    try:
        ctypes.windll.user32.EnumDisplayMonitors(None, None, proc(cb), 0)
    except Exception:
        pass
    if not found:
        u = ctypes.windll.user32
        found.append((0, 0, u.GetSystemMetrics(0), u.GetSystemMetrics(1)))
    return found


def window_rect(hwnd) -> tuple[int, int, int, int]:
    """Retangulo da janela (x, y, w, h) em pixels FISICOS."""
    import ctypes

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    r = RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def ensure_on_screen(hwnd) -> bool:
    """Se a janela nao estiver utilizavel em nenhum monitor, recentraliza.

    Faz tudo em pixels fisicos, entao funciona em qualquer escala de DPI.
    Devolve True se precisou mover.
    """
    import ctypes
    if not hwnd:
        return False
    x, y, w, h = window_rect(hwnd)
    if w <= 0 or h <= 0:
        return False
    mons = monitors()
    if is_visible(x, y, w, h, mons):
        return False
    nx, ny = centered_pos(w, h, mons)
    SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x0001, 0x0004, 0x0010
    ctypes.windll.user32.SetWindowPos(
        hwnd, 0, nx, ny, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
    return True


def _overlap(a, b) -> tuple[int, int]:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (max(0, min(ax + aw, bx + bw) - max(ax, bx)),
            max(0, min(ay + ah, by + bh) - max(ay, by)))


def is_visible(x: int, y: int, w: int, h: int, mons) -> bool:
    """True se uma parte util da janela cai dentro de algum monitor."""
    for mon in mons:
        ow, oh = _overlap((x, y, w, h), mon)
        if ow >= min(MIN_VISIBLE_W, w) and oh >= min(MIN_VISIBLE_H, h):
            return True
    return False


def centered_pos(w: int, h: int, mons) -> tuple[int, int]:
    """Posicao padrao: centralizada no monitor principal (o primeiro da lista)."""
    mx, my, mw, mh = mons[0] if mons else (0, 0, 1024, 768)
    return (mx + max(0, (mw - w) // 2), my + max(0, (mh - h) // 2))


def start_pos(saved, w: int, h: int, mons) -> tuple[int, int]:
    """Onde abrir a janela: a posicao salva, se ainda couber na tela atual;
    caso contrario, centralizada."""
    fallback = centered_pos(w, h, mons)
    if not saved:
        return fallback
    x, y = int(saved[0]), int(saved[1])
    return (x, y) if is_visible(x, y, w, h, mons) else fallback
