"""Testes de posicionamento de janela (coordenadas logicas)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from winpos import centered_pos, is_visible, start_pos  # noqa: E402

ONE = [(0, 0, 1536, 864)]
TWO = [(0, 0, 1536, 864), (1536, 0, 1920, 1080)]
W, H = 360, 600


def test_posicao_salva_fora_da_tela_cai_para_o_centro():
    # 1953 foi salvo quando a janela estava perdida fora da area visivel
    assert start_pos((1953, 60), W, H, ONE) == centered_pos(W, H, ONE)


def test_a_mesma_posicao_e_mantida_quando_o_monitor_existe():
    assert start_pos((1953, 60), W, H, TWO) == (1953, 60)


def test_posicao_valida_e_preservada():
    assert start_pos((300, 100), W, H, ONE) == (300, 100)


def test_sem_posicao_salva_abre_centralizada():
    assert start_pos(None, W, H, ONE) == (588, 132)


def test_centralizada_fica_inteiramente_dentro_da_tela():
    x, y = centered_pos(W, H, ONE)
    mx, my, mw, mh = ONE[0]
    assert x >= mx and y >= my
    assert x + W <= mx + mw and y + H <= my + mh


def test_janela_quase_toda_fora_pela_direita_e_rejeitada():
    assert not is_visible(1506, 100, W, H, ONE)


def test_janela_parcialmente_fora_mas_utilizavel_e_aceita():
    assert is_visible(1300, 100, W, H, ONE)


def test_janela_acima_do_topo_da_tela_e_rejeitada():
    assert not is_visible(300, -590, W, H, ONE)


def test_monitor_a_esquerda_com_coordenadas_negativas_e_aceito():
    screens = [(-1920, 0, 1920, 1080), (0, 0, 1536, 864)]
    assert start_pos((-1500, 200), W, H, screens) == (-1500, 200)


def test_regressao_canto_inferior_direito_em_escala_125_ficava_fora():
    """O bug original: o canto era calculado em px fisicos (1920) e entregue
    ao pywebview, que usa logicos (1536) — a janela nascia fora da tela."""
    bug_pos = (1920 - W - 24, 1080 - H - 64)   # como o codigo antigo calculava
    assert not is_visible(bug_pos[0], bug_pos[1], W, H, ONE)
    assert start_pos(bug_pos, W, H, ONE) == centered_pos(W, H, ONE)
