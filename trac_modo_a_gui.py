"""
TRAC — Modo A: Reação de Escolha Simbólica
Herda de ModoBase. Responsável apenas pela lógica específica do Modo A.
"""

from __future__ import annotations

import time

from trac_csprng import CSPRNGClient
from trac_modo_base import (
    ModoBase, deep_merge, legacy_inputs_to_modular, normalise_inputs,
    InputType, ResponseMode, MOUSE_QT_TO_CODE,
    BG_DEEP, BG_CARD, BORDER, ACCENT, TEXT_PRI, TEXT_SEC, TEXT_DIM,
    SUCCESS, WARNING, DANGER, _UI,
)
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QMouseEvent

# ── Config padrão do Modo A ───────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "inputs": [
        {"id": "KEY_W", "type": InputType.KEYBOARD.value, "code": "W", "label": "W"},
        {"id": "KEY_A", "type": InputType.KEYBOARD.value, "code": "A", "label": "A"},
        {"id": "KEY_S", "type": InputType.KEYBOARD.value, "code": "S", "label": "S"},
        {"id": "KEY_D", "type": InputType.KEYBOARD.value, "code": "D", "label": "D"},
    ],
    "gameplay": {
        "estimulos_simultaneos": 1,
        "modo_resposta":         ResponseMode.SIMPLES.value,
        "limite_trc_ms":         300,
        "penalidade_ms":         1000,
    },
    "timing": {
        "wait_min_s":        0.5,
        "wait_max_s":        2.0,
        "feedback_delay_ms": 900,
    },
}


class ModoAGUI(ModoBase):
    MODO_LETRA   = "A"
    MODO_NOME    = "Escolha Simbólica"
    DEFAULT_CONFIG = DEFAULT_CONFIG

    def __init__(self, config: dict | None = None, parent=None):
        # Estado específico do Modo A (antes de super().__init__ que chama _build_centro)
        self._is_running       = False
        self._waiting          = False
        self._alvos_ativos:  list[str] = []
        self._respondidos:   set[str]  = set()
        self._start_time     = 0.0
        self._variation_idx  = 0

        # Timers (criados antes de super() para estarem prontos no _build_centro)
        self._timer_stimulus = QTimer()
        self._timer_stimulus.setSingleShot(True)
        self._timer_stimulus.timeout.connect(self._show_stimulus)

        self._timer_next = QTimer()
        self._timer_next.setSingleShot(True)
        self._timer_next.timeout.connect(self._next_trial)

        super().__init__(config=config, parent=parent)

    # ── Hook: normalização de config legada ───────────────────────────────────
    def _normalise_cfg(self, config: dict | None) -> dict | None:
        if not config:
            return config
        # Converte formato antigo (teclas/mouse_botoes) para inputs modular
        converted_inputs = legacy_inputs_to_modular(config)
        if converted_inputs is not None:
            new_cfg = {k: v for k, v in config.items()
                       if k not in ("teclas", "mouse_botoes")}
            new_cfg["inputs"] = converted_inputs
            # Mapeia chaves de gameplay antigas
            gameplay = {}
            for old, new in (("estimulos_simultaneos", "estimulos_simultaneos"),
                             ("modo_resposta",         "modo_resposta"),
                             ("limite_trc_ms",         "limite_trc_ms"),
                             ("penalidade_ms",         "penalidade_ms")):
                if old in config:
                    gameplay[new] = config[old]
            if gameplay:
                new_cfg["gameplay"] = gameplay
            timing = {}
            for old, new in (("wait_min_s", "wait_min_s"),
                             ("wait_max_s", "wait_max_s")):
                if old in config:
                    timing[new] = config[old]
            if timing:
                new_cfg["timing"] = timing
            return new_cfg
        return config

    # ── Hooks obrigatórios da base ────────────────────────────────────────────
    def _build_centro(self) -> QWidget:
        centro = QWidget()
        centro.setStyleSheet(f"background-color:{BG_DEEP};")
        cl = QVBoxLayout(centro)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.setSpacing(_UI["spacing_centro"])

        # Indicadores
        self.indicadores: dict[str, QLabel] = {}
        ind_row = QHBoxLayout()
        ind_row.setSpacing(_UI["spacing_indicadores"])
        ind_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ind_layout = ind_row
        cl.addLayout(ind_row)
        cl.addSpacing(_UI["spacing_apos_indicadores"])

        # Status
        self.lbl_status = QLabel("Pressione qualquer input configurado para começar")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:500; color:{TEXT_SEC};"
        )
        cl.addWidget(self.lbl_status)

        # Estímulo
        self.lbl_stimulus = QLabel("")
        self.lbl_stimulus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_stimulus.setFixedHeight(_UI["stimulus_altura"])
        self.lbl_stimulus.setStyleSheet(
            f"font-size:130px; font-weight:800; color:{ACCENT};"
        )
        cl.addWidget(self.lbl_stimulus)

        # Resultado
        self.lbl_result = QLabel("")
        self.lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_result.setStyleSheet(f"font-size:16px; font-weight:600;")
        cl.addWidget(self.lbl_result)

        self._rebuild_indicators()
        return centro

    def _build_rodape_dica(self) -> str:
        modo = self.cfg["gameplay"]["modo_resposta"]
        n    = self.cfg["gameplay"]["estimulos_simultaneos"]
        return f"{n} estímulo(s)  |  resposta: {modo}  |  ESC para encerrar"

    # ── Mapeamentos de input ──────────────────────────────────────────────────
    def _rebuild_maps(self):
        inputs = self.cfg["inputs"]
        self._by_id         = {i["id"]: i for i in inputs}
        self._kb_to_id      = {i["code"]: i["id"] for i in inputs
                                if i["type"] == InputType.KEYBOARD.value}
        self._mouse_to_id   = {i["code"]: i["id"] for i in inputs
                                if i["type"] == InputType.MOUSE.value}

    def _label(self, input_id: str) -> str:
        return self._by_id.get(input_id, {}).get("label", input_id)

    def _all_ids(self) -> list[str]:
        return [i["id"] for i in self.cfg["inputs"]]

    # ── Indicadores ──────────────────────────────────────────────────────────
    def _rebuild_indicators(self):
        self._rebuild_maps()
        for box in list(getattr(self, "indicadores", {}).values()):
            self._ind_layout.removeWidget(box)
            box.deleteLater()
        self.indicadores = {}
        for inp in self.cfg["inputs"]:
            box = QLabel(inp["label"])
            box.setFixedSize(_UI["indicador_largura"], _UI["indicador_altura"])
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._style_ind(box, False)
            self.indicadores[inp["id"]] = box
            self._ind_layout.addWidget(box)

    def _style_ind(self, box: QLabel, ativo: bool):
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

    def _reset_inds(self):
        for box in self.indicadores.values():
            self._style_ind(box, False)

    def _highlight_inds(self, alvos: list[str]):
        for a in alvos:
            if a in self.indicadores:
                self._style_ind(self.indicadores[a], True)

    def _dim_ind(self, alvo: str):
        if alvo in self.indicadores:
            self.indicadores[alvo].setStyleSheet(
                f"background-color:#0D2E1C; color:{SUCCESS};"
                f"border:2px solid {SUCCESS}; border-radius:10px;"
                f"font-size:18px; font-weight:800;"
            )

    # ── Eventos ───────────────────────────────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)   # ESC → _encerrar_base
        if event.isAccepted():
            return
        inp_id = self._kb_to_id.get(event.text().upper())
        if not inp_id:
            return
        if not self._is_running:
            self._start_session(); return
        if self._waiting:
            self._process_input(inp_id)

    def mousePressEvent(self, event: QMouseEvent):
        code   = MOUSE_QT_TO_CODE.get(event.button())
        inp_id = self._mouse_to_id.get(code) if code else None
        if not inp_id:
            return
        if not self._is_running:
            self._start_session(); return
        if self._waiting:
            self._process_input(inp_id)

    # ── Fluxo de sessão ───────────────────────────────────────────────────────
    def _start_session(self):
        self._is_running   = True
        self.resultados    = []
        self._session_start = time.perf_counter()
        self.lbl_result.setText("")
        self._next_trial()

    def _next_trial(self):
        self._reset_inds()
        self._alvos_ativos = []
        self._respondidos  = set()
        self.lbl_stimulus.setText("")
        self.lbl_status.setText("Preparar...")
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:500; color:{TEXT_SEC};"
        )
        seed    = CSPRNGClient.get_seed(0)
        wait_ms = int(CSPRNGClient.to_float(
            seed,
            self.cfg["timing"]["wait_min_s"],
            self.cfg["timing"]["wait_max_s"],
        ) * 1000)
        self._timer_stimulus.start(wait_ms)

    def _pick_alvos(self) -> list[str]:
        pool = self._all_ids()
        n    = min(self.cfg["gameplay"]["estimulos_simultaneos"], len(pool))
        sel, rest = [], pool[:]
        for _ in range(n):
            seed = CSPRNGClient.get_seed(0)
            idx  = CSPRNGClient.to_int(seed, 0, len(rest) - 1)
            sel.append(rest.pop(idx))
        return sel

    def _show_stimulus(self):
        self._alvos_ativos = self._pick_alvos()
        self.lbl_status.setText("REAGE!")
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:700; color:{TEXT_PRI};"
        )
        self.lbl_stimulus.setText(
            "  ".join(self._label(a) for a in self._alvos_ativos)
        )
        self._highlight_inds(self._alvos_ativos)
        self.lbl_stimulus.repaint()   # síncrono — garante render antes do start_time
        self._start_time = time.perf_counter()
        self._waiting    = True

    def _process_input(self, inp_id: str):
        modo = self.cfg["gameplay"]["modo_resposta"]
        trc  = (time.perf_counter() - self._start_time) * 1000

        if inp_id not in self._alvos_ativos:
            self._waiting = False
            self._reg(inp_id, trc, acerto=False)
            self.lbl_result.setText(f"✗  [{self._label(inp_id)}] não era o alvo")
            self.lbl_result.setStyleSheet(
                f"font-size:16px; font-weight:700; color:{DANGER};"
            )
            self._timer_next.start(self.cfg["gameplay"]["penalidade_ms"])
            return

        if modo in (ResponseMode.SIMPLES.value, ResponseMode.QUALQUER.value):
            self._waiting = False
            self._reg(inp_id, trc, acerto=True)
            self._dim_ind(inp_id)
            self._feedback_sucesso(trc)
            self._timer_next.start(self.cfg["timing"]["feedback_delay_ms"])

        elif modo == ResponseMode.TODOS.value:
            self._respondidos.add(inp_id)
            self._dim_ind(inp_id)
            if self._respondidos >= set(self._alvos_ativos):
                self._waiting = False
                self._reg(inp_id, trc, acerto=True, todos=True)
                self._feedback_sucesso(trc)
                self._timer_next.start(self.cfg["timing"]["feedback_delay_ms"])

    def _feedback_sucesso(self, trc: float):
        limite = self.cfg["gameplay"]["limite_trc_ms"]
        if trc <= limite:
            self.lbl_result.setText(f"✓  {trc:.0f}ms")
            self.lbl_result.setStyleSheet(
                f"font-size:20px; font-weight:700; color:{SUCCESS};"
            )
        else:
            self.lbl_result.setText(f"LENTO  {trc:.0f}ms")
            self.lbl_result.setStyleSheet(
                f"font-size:20px; font-weight:700; color:{WARNING};"
            )

    def _reg(self, inp_id: str, trc: float, acerto: bool, todos: bool = False):
        self.resultados.append({
            "alvos_ids":       self._alvos_ativos[:],
            "alvos_labels":    [self._label(a) for a in self._alvos_ativos],
            "input_id":        inp_id,
            "input_label":     self._label(inp_id),
            "trc_ms":          round(trc, 2),
            "acerto":          acerto,
            "modo_resposta":   self.cfg["gameplay"]["modo_resposta"],
            "todos_concluidos":todos,
        })
        self._atualizar_barra(self.cfg["gameplay"]["limite_trc_ms"])

    # ── Encerramento ──────────────────────────────────────────────────────────
    def _encerrar_base(self):
        self._timer_stimulus.stop()
        self._timer_next.stop()
        self._is_running = False
        self._waiting    = False
        super()._encerrar_base()

    # ── Config em tempo real ──────────────────────────────────────────────────
    def aplicar_config(self, cfg: dict):
        """Atualiza config. Para sessão em andamento antes de reconstruir."""
        self._timer_stimulus.stop()
        self._timer_next.stop()
        self._is_running = False
        self._waiting    = False

        normalised = self._normalise_cfg(cfg)
        self.cfg   = deep_merge(DEFAULT_CONFIG, normalised)
        self._rebuild_indicators()
        self.lbl_result.setText("")
        self.lbl_status.setText("Configuração atualizada — pressione qualquer tecla para começar")
        self.lbl_status.setStyleSheet(
            f"font-size:16px; font-weight:500; color:{TEXT_SEC};"
        )
