"""
TRAC — Modo A: Reação de Escolha Simbólica
Versão 3: suporte a múltiplos estímulos, teclas configuráveis,
          mouse configurável, modo de resposta configurável.
"""

import time
import socket
import struct

from trac_csprng import CSPRNGClient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QMouseEvent

# ── Paleta ────────────────────────────────────────────────────────────────────
BG_DEEP  = "#09090F"
BG_CARD  = "#16161F"
BORDER   = "#2A2A38"
ACCENT   = "#4F8EF7"
TEXT_PRI = "#E8E8F0"
TEXT_SEC = "#6B6B80"
TEXT_DIM = "#3A3A50"
SUCCESS  = "#3DDC84"
WARNING  = "#F5A623"
DANGER   = "#E05252"

# ── Config padrão do Modo A ───────────────────────────────────────────────────
DEFAULT_CONFIG = {
    # Teclas do teclado mapeadas (lista de strings maiúsculas)
    "teclas": ["W", "A", "S", "D"],
    # Botões do mouse: "LEFT", "RIGHT", "MIDDLE"
    "mouse_botoes": [],
    # Quantos estímulos aparecem ao mesmo tempo (1 = clássico)
    "estimulos_simultaneos": 1,
    # Como responder a múltiplos estímulos
    # "simples"   → apenas 1 estímulo aparece por vez
    # "qualquer"  → pressionar qualquer uma das teclas acende
    # "todos"     → pressionar todas (em qualquer ordem) para completar
    "modo_resposta": "simples",
    # TRC alvo em ms
    "limite_trc_ms": 300,
    # Faixa de espera antes do estímulo
    "wait_min_s": 0.5,
    "wait_max_s": 2.0,
    # Penalidade por erro em ms
    "penalidade_ms": 1000,
}


class ModoAGUI(QWidget):
    """Modo A — Reação de Escolha Simbólica.
    
    Treina velocidade de processamento cognitivo e precisão na associação
    estímulo-resposta. Apresenta estímulos aleatórios (teclas ou botões de mouse)
    e mede tempo de reação (TRC) da resposta do usuário.
    
    Signals:
        finished: emite dict com resumo da sessão ao encerrar (ESC).
    """
    finished = pyqtSignal(dict)

    def __init__(self, config: dict | None = None, parent=None):
        super().__init__(parent)
        self.cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.setStyleSheet(f"background-color: {BG_DEEP};")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Captura cliques do mouse
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)

        # ── Estado ────────────────────────────────────────────────────────────
        self.is_running        = False
        self.waiting_for_input = False
        self.alvos_ativos: list[str] = []   # estímulos visíveis agora
        self.respondidos: set[str]   = set()
        self.start_time        = 0.0
        self.resultados: list[dict]  = []
        self._session_start    = 0.0

        # ── Timers ────────────────────────────────────────────────────────────
        self.timer_stimulus = QTimer(self); self.timer_stimulus.setSingleShot(True)
        self.timer_stimulus.timeout.connect(self._show_stimulus)
        self.timer_next     = QTimer(self); self.timer_next.setSingleShot(True)
        self.timer_next.timeout.connect(self._next_trial)

        # ── Layout ────────────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Barra superior
        barra = QFrame()
        barra.setFixedHeight(52)
        barra.setStyleSheet(
            f"background-color:#0D0D14; border-bottom:1px solid {BORDER};"
        )
        bl = QHBoxLayout(barra)
        bl.setContentsMargins(24, 0, 24, 0)

        titulo = QLabel("MODO A  —  Escolha Simbólica")
        titulo.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{ACCENT}; letter-spacing:2px;"
        )
        bl.addWidget(titulo)
        bl.addStretch()

        self.lbl_tentativas = QLabel("0 tentativas")
        self.lbl_tentativas.setStyleSheet(f"font-size:12px; color:{TEXT_SEC};")
        bl.addWidget(self.lbl_tentativas)
        bl.addSpacing(24)

        self.lbl_precisao = QLabel("—")
        self.lbl_precisao.setStyleSheet(f"font-size:12px; color:{SUCCESS};")
        bl.addWidget(self.lbl_precisao)
        bl.addSpacing(24)

        self.lbl_media = QLabel("TRC: —")
        self.lbl_media.setStyleSheet(f"font-size:12px; color:{TEXT_PRI};")
        bl.addWidget(self.lbl_media)

        root.addWidget(barra)

        # Centro
        centro = QWidget()
        centro.setStyleSheet(f"background-color:{BG_DEEP};")
        cl = QVBoxLayout(centro)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.setSpacing(16)

        # Indicadores de inputs disponíveis
        self.indicadores: dict[str, QLabel] = {}
        ind_row = QHBoxLayout()
        ind_row.setSpacing(10)
        ind_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._indicadores_layout = ind_row

        todos_inputs = self.cfg["teclas"] + [
            f"Mouse {b}" for b in self.cfg["mouse_botoes"]
        ]
        for inp in todos_inputs:
            box = self._make_indicator(inp, ativo=False)
            self.indicadores[inp] = box
            ind_row.addWidget(box)
        cl.addLayout(ind_row)
        cl.addSpacing(28)

        # Status
        self.lbl_status = QLabel("Pressione qualquer tecla para começar")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:500; color:{TEXT_SEC};"
        )
        cl.addWidget(self.lbl_status)

        # Estímulo(s) — área de exibição
        self.lbl_stimulus = QLabel("")
        self.lbl_stimulus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_stimulus.setFixedHeight(160)
        self.lbl_stimulus.setStyleSheet(
            f"font-size:130px; font-weight:800; color:{ACCENT};"
        )
        cl.addWidget(self.lbl_stimulus)

        # Resultado
        self.lbl_result = QLabel("")
        self.lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_result.setStyleSheet(f"font-size:16px; font-weight:600;")
        cl.addWidget(self.lbl_result)

        root.addWidget(centro, stretch=1)

        # Rodapé
        rodape = QFrame()
        rodape.setFixedHeight(52)
        rodape.setStyleSheet(
            f"background-color:#0D0D14; border-top:1px solid {BORDER};"
        )
        rl = QHBoxLayout(rodape)
        rl.setContentsMargins(24, 0, 24, 0)

        self.lbl_csprng = QLabel("● CSPRNG: verificando...")
        self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{TEXT_SEC};")
        rl.addWidget(self.lbl_csprng)
        rl.addStretch()

        modo_resp = self.cfg["modo_resposta"]
        n_est     = self.cfg["estimulos_simultaneos"]
        dica_modo = f"{n_est} estímulo(s)  |  resposta: {modo_resp}  |  ESC para encerrar"
        dica = QLabel(dica_modo)
        dica.setStyleSheet(f"font-size:11px; color:{TEXT_DIM};")
        rl.addWidget(dica)

        root.addWidget(rodape)

        QTimer.singleShot(200, self._checar_trng)


    # ── Helpers de UI ─────────────────────────────────────────────────────────
    def _make_indicator(self, label: str, ativo: bool) -> QLabel:
        box = QLabel(label)
        box.setFixedSize(56, 56)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._style_indicator(box, ativo)
        return box

    def _rebuild_indicators(self):
        # helper to rebuild indicators layout (used when config changes)
        try:
            for box in list(self.indicadores.values()):
                # remove from layout
                self._indicadores_layout.removeWidget(box)
                box.deleteLater()
        except Exception:
            pass
        self.indicadores.clear()
        todos_inputs = self.cfg["teclas"] + [f"Mouse {b}" for b in self.cfg["mouse_botoes"]]
        for inp in todos_inputs:
            box = self._make_indicator(inp, ativo=False)
            self.indicadores[inp] = box
            self._indicadores_layout.addWidget(box)

    def _style_indicator(self, box: QLabel, ativo: bool):
        if ativo:
            box.setStyleSheet(
                f"background-color:{ACCENT}; color:white;"
                f"border:2px solid {ACCENT}; border-radius:10px;"
                f"font-size:18px; font-weight:800;"
            )
        else:
            box.setStyleSheet(
                f"background-color:{BG_CARD}; color:{TEXT_SEC};"
                f"border:1px solid {BORDER}; border-radius:10px;"
                f"font-size:18px; font-weight:700;"
            )

    def _reset_indicators(self):
        for box in self.indicadores.values():
            self._style_indicator(box, False)

    def _highlight_indicators(self, alvos: list[str]):
        for alvo in alvos:
            key = alvo if alvo in self.indicadores else f"Mouse {alvo}"
            if key in self.indicadores:
                self._style_indicator(self.indicadores[key], True)

    def _dim_indicator(self, alvo: str):
        """Marca indicador como respondido (verde)."""
        key = alvo if alvo in self.indicadores else f"Mouse {alvo}"
        if key in self.indicadores:
            self.indicadores[key].setStyleSheet(
                f"background-color:#0D2E1C; color:{SUCCESS};"
                f"border:2px solid {SUCCESS}; border-radius:10px;"
                f"font-size:18px; font-weight:800;"
            )

    # ── TRNG ─────────────────────────────────────────────────────────────────
    def _checar_trng(self):
        seed = CSPRNGClient.get_seed(0)
        ts   = int(time.perf_counter_ns() & 0xFFFFFFFF)
        if seed != ts:
            self.lbl_csprng.setText("● CSPRNG: conectado")
            self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{SUCCESS};")
        else:
            self.lbl_csprng.setText("● CSPRNG: offline (fallback ativo")
            self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{WARNING};")

    # ── Eventos de input ──────────────────────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self._encerrar(); return
        key = event.text().upper()
        if not key:
            return
        if not self.is_running:
            self._start_session(); return
        if self.waiting_for_input:
            self._process_input(key)

    def mousePressEvent(self, event: QMouseEvent):
        if not self.cfg["mouse_botoes"]:
            return
        btn_map = {
            Qt.MouseButton.LeftButton:   "LEFT",
            Qt.MouseButton.RightButton:  "RIGHT",
            Qt.MouseButton.MiddleButton: "MIDDLE",
        }
        btn = btn_map.get(event.button())
        if not btn or btn not in self.cfg["mouse_botoes"]:
            return
        if not self.is_running:
            self._start_session(); return
        if self.waiting_for_input:
            self._process_input(btn)

    # ── Fluxo de sessão ───────────────────────────────────────────────────────
    def _start_session(self):
        self.is_running    = True
        self.resultados    = []
        self._session_start = time.perf_counter()
        self.lbl_result.setText("")
        self._next_trial()

    def _next_trial(self):
        self._reset_indicators()
        self.alvos_ativos  = []
        self.respondidos   = set()
        self.lbl_stimulus.setText("")
        self.lbl_status.setText("Preparar...")
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:500; color:{TEXT_SEC};"
        )

        seed     = CSPRNGClient.get_seed(0)
        wait_ms  = int(CSPRNGClient.to_float(
            seed,
            self.cfg["wait_min_s"],
            self.cfg["wait_max_s"],
        ) * 1000)
        self.timer_stimulus.start(wait_ms)

    def _pick_alvos(self) -> list[str]:
        """Seleciona N alvos aleatórios sem repetição."""
        pool = self.cfg["teclas"] + self.cfg["mouse_botoes"]
        n    = min(self.cfg["estimulos_simultaneos"], len(pool))
        selecionados = []
        restantes    = pool[:]
        for _ in range(n):
            seed = CSPRNGClient.get_seed(0)
            idx  = CSPRNGClient.to_int(seed, 0, len(restantes) - 1)
            selecionados.append(restantes.pop(idx))
        return selecionados

    def _show_stimulus(self):
        self.alvos_ativos = self._pick_alvos()
        self.lbl_status.setText("REAGE!")
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:700; color:{TEXT_PRI};"
        )
        self.lbl_stimulus.setText("  ".join(self.alvos_ativos))
        self._highlight_indicators(self.alvos_ativos)
        # repaint() é síncrono — só retorna após o paintEvent completar.
        # Registrar start_time APÓS garante que o visual já está na tela.
        self.lbl_stimulus.repaint()
        self.start_time        = time.perf_counter()
        self.waiting_for_input = True

    def _process_input(self, inp: str):
        modo = self.cfg["modo_resposta"]
        trc  = (time.perf_counter() - self.start_time) * 1000

        # Verifica se o input é um alvo válido agora
        if inp not in self.alvos_ativos:
            # Tecla errada
            self.waiting_for_input = False
            self._registrar(inp, trc, acerto=False)
            self.lbl_result.setText(f"✗  [{inp}] não era o alvo")
            self.lbl_result.setStyleSheet(
                f"font-size:16px; font-weight:700; color:{DANGER};"
            )
            self.timer_next.start(self.cfg["penalidade_ms"])
            return

        if modo == "simples" or modo == "qualquer":
            # Qualquer alvo correto encerra a tentativa
            self.waiting_for_input = False
            self._registrar(inp, trc, acerto=True)
            self._dim_indicator(inp)
            self._feedback_sucesso(trc)
            self.timer_next.start(900)

        elif modo == "todos":
            # Precisa responder a todos os alvos
            self.respondidos.add(inp)
            self._dim_indicator(inp)
            if self.respondidos >= set(self.alvos_ativos):
                # Todos respondidos
                self.waiting_for_input = False
                self._registrar(inp, trc, acerto=True, todos=True)
                self._feedback_sucesso(trc)
                self.timer_next.start(900)
            # Caso contrário, continua aguardando

    def _feedback_sucesso(self, trc: float):
        if trc <= self.cfg["limite_trc_ms"]:
            self.lbl_result.setText(f"✓  {trc:.0f}ms")
            self.lbl_result.setStyleSheet(
                f"font-size:20px; font-weight:700; color:{SUCCESS};"
            )
        else:
            self.lbl_result.setText(f"LENTO  {trc:.0f}ms")
            self.lbl_result.setStyleSheet(
                f"font-size:20px; font-weight:700; color:{WARNING};"
            )

    def _registrar(self, inp: str, trc: float, acerto: bool, todos: bool = False):
        self.resultados.append({
            "tecla_alvo":       "/".join(self.alvos_ativos),
            "tecla_pressionada": inp,
            "trc_ms":           round(trc, 2),
            "acerto":           acerto,
            "modo_resposta":    self.cfg["modo_resposta"],
        })
        self._atualizar_barra()

    def _atualizar_barra(self):
        n       = len(self.resultados)
        acertos = [r for r in self.resultados if r["acerto"]]
        trcs    = [r["trc_ms"] for r in acertos]

        self.lbl_tentativas.setText(f"{n} tentativa{'s' if n != 1 else ''}")
        pct = (len(acertos) / n * 100) if n > 0 else 0
        self.lbl_precisao.setText(f"{pct:.0f}% precisão")

        if trcs:
            media = sum(trcs) / len(trcs)
            cor   = SUCCESS if media <= self.cfg["limite_trc_ms"] else WARNING
            self.lbl_media.setText(f"TRC médio: {media:.0f}ms")
            self.lbl_media.setStyleSheet(f"font-size:12px; color:{cor};")

    # ── Encerramento ──────────────────────────────────────────────────────────
    def _encerrar(self):
        self.timer_stimulus.stop()
        self.timer_next.stop()
        self.is_running        = False
        self.waiting_for_input = False

        n       = len(self.resultados)
        acertos = [r for r in self.resultados if r["acerto"]]
        trcs    = [r["trc_ms"] for r in acertos]
        dur_ms  = int((time.perf_counter() - self._session_start) * 1000)

        resumo = {
            "modo":         "A",
            "config":       self.cfg,
            "duracao_ms":   dur_ms,
            "tentativas":   n,
            "acertos":      len(acertos),
            "precisao_pct": round(len(acertos) / n * 100, 1) if n > 0 else 0,
            "trc_medio_ms": round(sum(trcs) / len(trcs), 1) if trcs else None,
            "trc_minimo_ms":round(min(trcs), 1) if trcs else None,
            "detalhes":     self.resultados,
        }
        self.finished.emit(resumo)

    def _rebuild_indicators(self):
        for box in list(self.indicadores.values()):
            self._indicadores_layout.removeWidget(box)
            box.deleteLater()
        self.indicadores.clear()

        todos_inputs = self.cfg["teclas"] + [
            f"🖱{b}" for b in self.cfg["mouse_botoes"]
        ]
        for inp in todos_inputs:
            box = self._make_indicator(inp, ativo=False)
            self.indicadores[inp] = box
            self._indicadores_layout.addWidget(box)

    def aplicar_config(self, cfg: dict):
        """Atualiza config em tempo real (chamado pelas Configurações)."""
        self.cfg = {**DEFAULT_CONFIG, **cfg}
        self._rebuild_indicators()
        self.lbl_status.setText("Configuração atualizada")
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:500; color:{TEXT_SEC};"
        )