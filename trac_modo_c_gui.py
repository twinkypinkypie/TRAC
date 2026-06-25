"""
TRAC — Modo C: Periférico Espacial
Treina detecção de movimento e posição via visão periférica e via dorsal.
"""

import time
import math

from trac_csprng import CSPRNGClient
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import (
    QKeyEvent, QMouseEvent, QPainter, QColor, QPen, QBrush, QRadialGradient
)

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

DEFAULT_CONFIG_C = {
    "teclas":           ["SPACE"],
    "mouse_botoes":     ["LEFT"],
    "grid_size":        1.0,        # fração da área da tela usada (0.5, 0.8, 1.0)
    "peripheral_only":  True,       # exclui zona foveal central (15% da área)
    "stimulus_size":    32,         # diâmetro do estímulo em px
    "stimulus_lifespan_ms": 800,    # tempo máximo antes de sumir
    "fixation_cross":   True,       # exibe cruz de fixação central
    "wait_min_s":       0.5,
    "wait_max_s":       2.0,
    "limite_trc_ms":    350,
    "penalidade_ms":    800,
}


class Estado:
    IDLE     = "idle"
    WAITING  = "waiting"
    STIMULUS = "stimulus"   # estímulo visível, aguardando resposta
    FEEDBACK = "feedback"


class ModoCGUI(QWidget):
    finished = pyqtSignal(dict)

    def __init__(self, config: dict | None = None, parent=None):
        super().__init__(parent)
        self.cfg = {**DEFAULT_CONFIG_C, **(config or {})}
        self.setStyleSheet(f"background-color:{BG_DEEP};")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        # ── Estado ────────────────────────────────────────────────────────────
        self.estado         = Estado.IDLE
        self.start_time     = 0.0
        self._session_start = 0.0
        self.resultados: list[dict] = []

        # Posição atual do estímulo (coordenadas da área de jogo, px absolutos)
        self._stim_pos: QPoint | None = None
        self._stim_visible = False

        # Feedback visual temporário (cor do círculo após resposta)
        self._feedback_color: QColor | None = None
        self._feedback_pos:   QPoint | None = None

        # ── Timers ────────────────────────────────────────────────────────────
        self._t_wait     = QTimer(self); self._t_wait.setSingleShot(True)
        self._t_wait.timeout.connect(self._show_stimulus)

        self._t_lifespan = QTimer(self); self._t_lifespan.setSingleShot(True)
        self._t_lifespan.timeout.connect(self._stimulus_miss)

        self._t_feedback = QTimer(self); self._t_feedback.setSingleShot(True)
        self._t_feedback.timeout.connect(self._clear_feedback)

        self._t_next     = QTimer(self); self._t_next.setSingleShot(True)
        self._t_next.timeout.connect(self._next_trial)

        # ── Layout ────────────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # Barra superior
        barra = QFrame()
        barra.setFixedHeight(52)
        barra.setStyleSheet(
            f"background-color:#0D0D14; border-bottom:1px solid {BORDER};"
        )
        barra.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        bl = QHBoxLayout(barra); bl.setContentsMargins(24, 0, 24, 0)
        titulo = QLabel("MODO C  —  Periférico Espacial")
        titulo.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{ACCENT}; letter-spacing:2px;"
        )
        bl.addWidget(titulo); bl.addStretch()
        self.lbl_tentativas = QLabel("0 tentativas")
        self.lbl_tentativas.setStyleSheet(f"font-size:12px; color:{TEXT_SEC};")
        bl.addWidget(self.lbl_tentativas); bl.addSpacing(24)
        self.lbl_precisao = QLabel("—")
        self.lbl_precisao.setStyleSheet(f"font-size:12px; color:{SUCCESS};")
        bl.addWidget(self.lbl_precisao); bl.addSpacing(24)
        self.lbl_media = QLabel("TRC: —")
        self.lbl_media.setStyleSheet(f"font-size:12px; color:{TEXT_PRI};")
        bl.addWidget(self.lbl_media)
        root.addWidget(barra)

        # Área de jogo (canvas — ocupa o resto da tela)
        self.canvas = _CanvasC(self)
        root.addWidget(self.canvas, stretch=1)

        # Rodapé
        rodape = QFrame()
        rodape.setFixedHeight(52)
        rodape.setStyleSheet(
            f"background-color:#0D0D14; border-top:1px solid {BORDER};"
        )
        rl = QHBoxLayout(rodape); rl.setContentsMargins(24, 0, 24, 0)
        self.lbl_csprng = QLabel("● CSPRNG: verificando...")
        self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{TEXT_SEC};")
        rl.addWidget(self.lbl_csprng); rl.addStretch()
        periph = "periférico" if self.cfg["peripheral_only"] else "tela cheia"
        dica = QLabel(
            f"Área: {int(self.cfg['grid_size']*100)}%  |  modo: {periph}  |  ESC para encerrar"
        )
        dica.setStyleSheet(f"font-size:11px; color:{TEXT_DIM};")
        rl.addWidget(dica)
        root.addWidget(rodape)

        QTimer.singleShot(200, self._checar_csprng)

    # ── CSPRNG ────────────────────────────────────────────────────────────────
    def _checar_csprng(self):
        seed = CSPRNGClient.get_seed(0)
        ts   = int(time.perf_counter_ns() & 0xFFFFFFFF)
        if seed != ts:
            self.lbl_csprng.setText("● CSPRNG: conectado")
            self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{SUCCESS};")
        else:
            self.lbl_csprng.setText("● CSPRNG: offline (fallback ativo)")
            self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{WARNING};")

    # ── Input ─────────────────────────────────────────────────────────────────
    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Escape:
            self._encerrar(); return
        if self.estado == Estado.IDLE:
            self._start_session(); return
        if e.text().upper() in self.cfg["teclas"] and self.estado == Estado.STIMULUS:
            self._process_hit()

    def mousePressEvent(self, e: QMouseEvent):
        btn_map = {
            Qt.MouseButton.LeftButton:   "LEFT",
            Qt.MouseButton.RightButton:  "RIGHT",
            Qt.MouseButton.MiddleButton: "MIDDLE",
        }
        btn = btn_map.get(e.button())
        if not btn or btn not in self.cfg["mouse_botoes"]: return
        if self.estado == Estado.IDLE:
            self._start_session(); return
        if self.estado == Estado.STIMULUS:
            self._process_hit()

    # ── Fluxo ─────────────────────────────────────────────────────────────────
    def _start_session(self):
        self._session_start = time.perf_counter()
        self.resultados = []
        self.canvas.set_status("Fixe o olhar na cruz central")
        self._next_trial()

    def _next_trial(self):
        self.estado        = Estado.WAITING
        self._stim_visible = False
        self._stim_pos     = None
        self.canvas.update_state(None, False, None, None)

        seed    = CSPRNGClient.get_seed(0)
        wait_ms = int(CSPRNGClient.to_float(
            seed, self.cfg["wait_min_s"], self.cfg["wait_max_s"]
        ) * 1000)
        self._t_wait.start(wait_ms)

    def _pick_position(self) -> QPoint:
        """Escolhe posição aleatória dentro da área configurada, respeitando PERIPHERAL_ONLY."""
        cw = self.canvas.width()
        ch = self.canvas.height()
        cx = cw // 2
        cy = ch // 2

        # Raio mínimo (zona foveal excluída) e raio máximo (grid_size)
        foveal_r = int(min(cw, ch) * 0.075)   # 15% do menor lado = 7.5% de raio
        max_rx   = int(cw * self.cfg["grid_size"] / 2) - self.cfg["stimulus_size"]
        max_ry   = int(ch * self.cfg["grid_size"] / 2) - self.cfg["stimulus_size"]

        for _ in range(50):   # máximo de 50 tentativas
            seed_x = CSPRNGClient.get_seed(0)
            seed_y = CSPRNGClient.get_seed(0)
            x = int(CSPRNGClient.to_float(seed_x, cx - max_rx, cx + max_rx))
            y = int(CSPRNGClient.to_float(seed_y, cy - max_ry, cy + max_ry))

            if self.cfg["peripheral_only"]:
                dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                if dist < foveal_r:
                    continue   # muito perto do centro — tenta de novo
            return QPoint(x, y)

        # Fallback: canto aleatório se todas as tentativas falharem
        return QPoint(cx + max_rx // 2, cy + max_ry // 2)

    def _show_stimulus(self):
        self.estado        = Estado.STIMULUS
        self._stim_pos     = self._pick_position()
        self._stim_visible = True
        self.canvas.update_state(
            self._stim_pos, True, None, self.cfg["stimulus_size"]
        )
        # repaint() síncrono — garante que o paintEvent do canvas completou
        # antes de registrar start_time. Mais preciso que QTimer(0) para
        # widgets com QPainter customizado.
        self.canvas.repaint()
        self.start_time = time.perf_counter()
        self._t_lifespan.start(self.cfg["stimulus_lifespan_ms"])

    def _process_hit(self):
        trc = (time.perf_counter() - self.start_time) * 1000
        self._t_lifespan.stop()
        self.estado        = Estado.FEEDBACK
        self._stim_visible = False

        acerto = trc <= self.cfg["limite_trc_ms"]
        cor    = QColor(SUCCESS) if acerto else QColor(WARNING)

        self.canvas.update_state(
            self._stim_pos, False, cor, self.cfg["stimulus_size"]
        )
        self._registrar(trc, acerto=True)

        status = f"✓  {trc:.0f}ms" if acerto else f"LENTO  {trc:.0f}ms"
        self.canvas.set_status(status, cor.name())

        self._t_feedback.start(500)
        self._t_next.start(900)

    def _stimulus_miss(self):
        """Estímulo sumiu sem resposta."""
        self.estado        = Estado.FEEDBACK
        self._stim_visible = False
        self.canvas.update_state(
            self._stim_pos, False, QColor(DANGER), self.cfg["stimulus_size"]
        )
        self._registrar(None, acerto=False, miss=True)
        self.canvas.set_status("✗  Miss — muito lento", DANGER)
        self._t_feedback.start(500)
        self._t_next.start(self.cfg["penalidade_ms"])

    def _clear_feedback(self):
        self.canvas.update_state(None, False, None, None)

    def _registrar(self, trc, acerto, miss=False):
        self.resultados.append({
            "tecla_alvo":        "PERIPH",
            "tecla_pressionada": "HIT" if acerto else ("MISS" if miss else "EARLY"),
            "trc_ms":            round(trc, 2) if trc is not None else None,
            "acerto":            acerto,
            "miss":              miss,
            "pos_x":             self._stim_pos.x() if self._stim_pos else None,
            "pos_y":             self._stim_pos.y() if self._stim_pos else None,
            "modo_resposta":     "periférico",
        })
        self._atualizar_barra()

    def _atualizar_barra(self):
        n       = len(self.resultados)
        acertos = [r for r in self.resultados if r["acerto"]]
        trcs    = [r["trc_ms"] for r in acertos if r["trc_ms"]]

        self.lbl_tentativas.setText(f"{n} tentativa{'s' if n!=1 else ''}")
        pct = (len(acertos) / n * 100) if n > 0 else 0
        cor = SUCCESS if pct >= 85 else (WARNING if pct >= 65 else DANGER)
        self.lbl_precisao.setText(f"{pct:.0f}% precisão")
        self.lbl_precisao.setStyleSheet(f"font-size:12px; color:{cor};")

        if trcs:
            media = sum(trcs) / len(trcs)
            cor_t = SUCCESS if media <= self.cfg["limite_trc_ms"] else WARNING
            self.lbl_media.setText(f"TRC: {media:.0f}ms")
            self.lbl_media.setStyleSheet(f"font-size:12px; color:{cor_t};")

    def _encerrar(self):
        for t in (self._t_wait, self._t_lifespan, self._t_feedback, self._t_next):
            t.stop()
        self.estado = Estado.IDLE

        n       = len(self.resultados)
        acertos = [r for r in self.resultados if r["acerto"]]
        trcs    = [r["trc_ms"] for r in acertos if r["trc_ms"]]
        dur_ms  = int((time.perf_counter() - self._session_start) * 1000)

        self.finished.emit({
            "modo":          "C",
            "config":        self.cfg,
            "duracao_ms":    dur_ms,
            "tentativas":    n,
            "acertos":       len(acertos),
            "precisao_pct":  round(len(acertos) / max(n, 1) * 100, 1),
            "trc_medio_ms":  round(sum(trcs) / len(trcs), 1) if trcs else None,
            "trc_minimo_ms": round(min(trcs), 1) if trcs else None,
            "detalhes":      self.resultados,
        })


class _CanvasC(QWidget):
    """
    Canvas de jogo do Modo C.
    Responsável por desenhar:
      - cruz de fixação central
      - zona periférica (anel sutil)
      - estímulo (círculo com gradiente radial)
      - feedback visual pós-resposta
      - texto de status centralizado
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color:{BG_DEEP};")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        self._stim_pos:    QPoint | None = None
        self._stim_visible = False
        self._feedback_color: QColor | None = None
        self._stim_size    = 32
        self._status_text  = "Pressione qualquer tecla para começar"
        self._status_color = TEXT_SEC
        self._show_fixation = True

    def update_state(self, pos, visible, feedback_color, size):
        self._stim_pos      = pos
        self._stim_visible  = visible
        self._feedback_color = feedback_color
        if size is not None:
            self._stim_size = size
        self.update()

    def set_status(self, text, color=TEXT_SEC):
        self._status_text  = text
        self._status_color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w  = self.width()
        h  = self.height()
        cx = w // 2
        cy = h // 2

        # Fundo
        p.fillRect(0, 0, w, h, QColor(BG_DEEP))

        # Zona periférica: anel sutil mostrando a área de jogo (opcional)
        # desenhado como um retângulo arredondado levemente visível
        p.setPen(QPen(QColor(BORDER), 1, Qt.PenStyle.DotLine))
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Cruz de fixação central
        if self._show_fixation:
            arm = 12
            thickness = 2
            p.setPen(QPen(QColor(TEXT_DIM), thickness))
            p.drawLine(cx - arm, cy, cx + arm, cy)
            p.drawLine(cx, cy - arm, cx, cy + arm)

            # Círculo da zona foveal (muito sutil)
            foveal_r = int(min(w, h) * 0.075)
            p.setPen(QPen(QColor(TEXT_DIM), 1, Qt.PenStyle.DotLine))
            p.drawEllipse(QPoint(cx, cy), foveal_r, foveal_r)

        # Estímulo ou feedback
        r = self._stim_size // 2

        if self._stim_visible and self._stim_pos:
            # Gradiente radial para o estímulo — parece uma "luz"
            grad = QRadialGradient(
                float(self._stim_pos.x()), float(self._stim_pos.y()), float(r),
                float(self._stim_pos.x()), float(self._stim_pos.y()), 0.0
            )
            grad.setColorAt(0.0, QColor("#FFFFFF"))
            grad.setColorAt(0.4, QColor(ACCENT))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(self._stim_pos, r, r)

        elif self._feedback_color and self._stim_pos:
            # Feedback: círculo sólido na posição do estímulo
            p.setPen(Qt.PenStyle.NoPen)
            fade = QColor(self._feedback_color)
            fade.setAlpha(160)
            p.setBrush(QBrush(fade))
            p.drawEllipse(self._stim_pos, r + 4, r + 4)

        # Status text (centro inferior)
        p.setPen(QPen(QColor(self._status_color)))
        font = p.font()
        font.setPointSize(14)
        font.setBold(True)
        p.setFont(font)
        p.drawText(
            QRect(0, h - 80, w, 40),
            Qt.AlignmentFlag.AlignCenter,
            self._status_text
        )

        p.end()
