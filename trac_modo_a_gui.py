"""
TRAC — Modo A: Reação de Escolha Simbólica
v4: lifespan, modo sequência, wait_min = 0, remoção do modo 'simples'.
"""

from __future__ import annotations

import time

from trac_csprng import CSPRNGClient
from trac_modo_base import (
    ModoBase, deep_merge, legacy_inputs_to_modular,
    InputType, ResponseMode, MOUSE_QT_TO_CODE,
    BG_DEEP, BG_CARD, BORDER, ACCENT, TEXT_PRI, TEXT_SEC, TEXT_DIM,
    SUCCESS, WARNING, DANGER, _UI,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QMouseEvent

# ── Modo de resposta — 'simples' removido, 'sequencia' adicionado ─────────────
class ResponseModeA(str):
    QUALQUER  = "qualquer"   # qualquer alvo correto encerra (inclui caso de 1 estímulo)
    TODOS     = "todos"      # todos os alvos devem ser pressionados (ordem livre)
    SEQUENCIA = "sequencia"  # todos os alvos na ordem em que aparecem (esq → dir)

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
        "modo_resposta":         ResponseModeA.QUALQUER,
        "limite_trc_ms":         300,
        "penalidade_ms":         1000,
        # 0 = desabilitado (estímulo fica até o usuário responder)
        "stimulus_lifespan_ms":  0,
    },
    "timing": {
        # wait_min_s = 0.0 é válido — estímulo aparece imediatamente
        "wait_min_s":        0.5,
        "wait_max_s":        2.0,
        "feedback_delay_ms": 900,
    },
}

VALID_RESPONSE_MODES = {
    ResponseModeA.QUALQUER,
    ResponseModeA.TODOS,
    ResponseModeA.SEQUENCIA,
}


class ModoAGUI(ModoBase):
    MODO_LETRA     = "A"
    MODO_NOME      = "Escolha Simbólica"
    DEFAULT_CONFIG = DEFAULT_CONFIG

    def __init__(self, config: dict | None = None, parent=None):
        # Estado específico — inicializado antes de super() que chama _build_centro
        self._is_running    = False
        self._waiting       = False
        self._alvos_ativos: list[str] = []   # IDs na ordem de exibição (esq → dir)
        self._respondidos:  list[str] = []   # IDs já respondidos (para sequência)
        self._start_time    = 0.0

        self._timer_stimulus = QTimer(); self._timer_stimulus.setSingleShot(True)
        self._timer_stimulus.timeout.connect(self._show_stimulus)

        self._timer_lifespan = QTimer(); self._timer_lifespan.setSingleShot(True)
        self._timer_lifespan.timeout.connect(self._stimulus_miss)

        self._timer_next = QTimer(); self._timer_next.setSingleShot(True)
        self._timer_next.timeout.connect(self._next_trial)

        super().__init__(config=config, parent=parent)

    # ── Hook: normalização de config legada ───────────────────────────────────
    def _normalise_cfg(self, config: dict | None) -> dict | None:
        if not config:
            return config
        converted_inputs = legacy_inputs_to_modular(config)
        if converted_inputs is None:
            return config
        new_cfg = {k: v for k, v in config.items()
                   if k not in ("teclas", "mouse_botoes")}
        new_cfg["inputs"] = converted_inputs
        gameplay = {}
        for old, new in (("estimulos_simultaneos", "estimulos_simultaneos"),
                         ("modo_resposta",          "modo_resposta"),
                         ("limite_trc_ms",          "limite_trc_ms"),
                         ("penalidade_ms",          "penalidade_ms")):
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
        # Migra 'simples' → 'qualquer'
        gp = new_cfg.get("gameplay", {})
        if gp.get("modo_resposta") == "simples":
            gp["modo_resposta"] = ResponseModeA.QUALQUER
        return new_cfg

    # ── Hooks obrigatórios ────────────────────────────────────────────────────
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

        # Barra de sequência (visível só no modo sequência)
        self._seq_frame = QFrame()
        self._seq_frame.setStyleSheet(
            f"background-color:{BG_CARD}; border:1px solid {BORDER}; border-radius:8px;"
        )
        self._seq_frame.setFixedHeight(40)
        seq_layout = QHBoxLayout(self._seq_frame)
        seq_layout.setContentsMargins(16, 0, 16, 0)
        self._lbl_seq = QLabel("")
        self._lbl_seq.setStyleSheet(
            f"font-size:14px; font-weight:600; color:{TEXT_SEC}; letter-spacing:4px;"
        )
        self._lbl_seq.setAlignment(Qt.AlignmentFlag.AlignCenter)
        seq_layout.addWidget(self._lbl_seq)
        self._seq_frame.setVisible(False)
        cl.addWidget(self._seq_frame)
        cl.addSpacing(8)

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
        modo     = self.cfg["gameplay"]["modo_resposta"]
        n        = self.cfg["gameplay"]["estimulos_simultaneos"]
        lifespan = self.cfg["gameplay"]["stimulus_lifespan_ms"]
        ls_str   = f"  |  lifespan: {lifespan}ms" if lifespan > 0 else ""
        return f"{n} estímulo(s)  |  resposta: {modo}{ls_str}  |  ESC para encerrar"

    # ── Mapeamentos ───────────────────────────────────────────────────────────
    def _rebuild_maps(self):
        inputs           = self.cfg["inputs"]
        self._by_id      = {i["id"]: i for i in inputs}
        self._kb_to_id   = {i["code"]: i["id"] for i in inputs
                            if i["type"] == InputType.KEYBOARD.value}
        self._mouse_to_id = {i["code"]: i["id"] for i in inputs
                             if i["type"] == InputType.MOUSE.value}

    def _label(self, inp_id: str) -> str:
        return self._by_id.get(inp_id, {}).get("label", inp_id)

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

    def _style_ind(self, box: QLabel, ativo: bool, ordem: int | None = None):
        """
        ativo=False → cinza padrão
        ativo=True  → azul (sem ordem) ou azul com número (sequência)
        ordem=N     → exibe o número da posição na sequência sobre o indicador
        """
        if ativo:
            label_text = box.text().split("\n")[0]   # preserva label original
            if ordem is not None:
                box.setText(f"{label_text}\n{ordem}")
                box.setStyleSheet(
                    f"background-color:{ACCENT}; color:white;"
                    f"border:2px solid {ACCENT}; border-radius:10px;"
                    f"font-size:14px; font-weight:800; line-height:1.2;"
                )
            else:
                box.setText(label_text)
                box.setStyleSheet(
                    f"background-color:{ACCENT}; color:white;"
                    f"border:2px solid {ACCENT}; border-radius:10px;"
                    f"font-size:18px; font-weight:800;"
                )
        else:
            # Restaura label original (sem número de ordem)
            inp = self._by_id.get(
                next((k for k, v in self.indicadores.items() if v is box), ""), {}
            )
            box.setText(inp.get("label", box.text().split("\n")[0]))
            box.setStyleSheet(
                f"background-color:{BG_CARD}; color:{TEXT_SEC};"
                f"border:1px solid {BORDER}; border-radius:10px;"
                f"font-size:18px; font-weight:700;"
            )

    def _reset_inds(self):
        for box in self.indicadores.values():
            self._style_ind(box, False)

    def _highlight_inds(self, alvos: list[str]):
        """Destaca alvos; no modo sequência mostra a ordem (1, 2, 3...)."""
        modo = self.cfg["gameplay"]["modo_resposta"]
        for i, alvo in enumerate(alvos):
            if alvo in self.indicadores:
                ordem = (i + 1) if modo == ResponseModeA.SEQUENCIA else None
                self._style_ind(self.indicadores[alvo], True, ordem=ordem)

    def _dim_ind(self, alvo: str):
        if alvo in self.indicadores:
            self.indicadores[alvo].setStyleSheet(
                f"background-color:#0D2E1C; color:{SUCCESS};"
                f"border:2px solid {SUCCESS}; border-radius:10px;"
                f"font-size:18px; font-weight:800;"
            )
            # Restaura label sem número de ordem
            inp = self._by_id.get(alvo, {})
            self.indicadores[alvo].setText(inp.get("label", ""))

    def _update_seq_bar(self):
        """Atualiza a barra de sequência mostrando próximo alvo esperado."""
        modo = self.cfg["gameplay"]["modo_resposta"]
        if modo != ResponseModeA.SEQUENCIA:
            self._seq_frame.setVisible(False)
            return

        respondidos = len(self._respondidos)
        total       = len(self._alvos_ativos)
        restantes   = self._alvos_ativos[respondidos:]

        if restantes:
            proximo = self._label(restantes[0])
            self._lbl_seq.setText(
                f"Sequência: " +
                "  ·  ".join(
                    f"[{self._label(a)}]" if j == 0 else self._label(a)
                    for j, a in enumerate(restantes)
                )
            )
            self._lbl_seq.setStyleSheet(
                f"font-size:14px; font-weight:600; color:{ACCENT}; letter-spacing:2px;"
            )
        self._seq_frame.setVisible(True)

    # ── Eventos ───────────────────────────────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)
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
        self._is_running    = True
        self.resultados     = []
        self._session_start = time.perf_counter()
        self.lbl_result.setText("")
        self._next_trial()

    def _next_trial(self):
        self._reset_inds()
        self._alvos_ativos = []
        self._respondidos  = []
        self.lbl_stimulus.setText("")
        self._seq_frame.setVisible(False)
        self.lbl_status.setText("Preparar...")
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:500; color:{TEXT_SEC};"
        )

        wait_min = self.cfg["timing"]["wait_min_s"]
        wait_max = self.cfg["timing"]["wait_max_s"]

        if wait_min == 0.0 and wait_max == 0.0:
            # Sem espera — dispara imediatamente
            self._show_stimulus()
        else:
            seed    = CSPRNGClient.get_seed(0)
            # Garante que wait_min >= 0 e wait_max >= wait_min
            lo      = max(0.0, wait_min)
            hi      = max(lo, wait_max)
            wait_ms = int(CSPRNGClient.to_float(seed, lo, hi) * 1000)
            if wait_ms == 0:
                self._show_stimulus()
            else:
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
        self._respondidos  = []

        self.lbl_status.setText("REAGE!")
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:700; color:{TEXT_PRI};"
        )
        self.lbl_stimulus.setText(
            "  ".join(self._label(a) for a in self._alvos_ativos)
        )
        self._highlight_inds(self._alvos_ativos)
        self._update_seq_bar()

        # repaint() síncrono — start_time registrado após render completo
        self.lbl_stimulus.repaint()
        self._start_time = time.perf_counter()
        self._waiting    = True

        # Lifespan: se > 0, agenda miss automático
        lifespan = self.cfg["gameplay"]["stimulus_lifespan_ms"]
        if lifespan > 0:
            self._timer_lifespan.start(lifespan)

    def _stimulus_miss(self):
        """Chamado quando o lifespan expira sem resposta."""
        self._waiting = False
        self._timer_lifespan.stop()
        trc = (time.perf_counter() - self._start_time) * 1000
        self._reg(None, trc, acerto=False, miss=True)
        self._seq_frame.setVisible(False)
        self.lbl_result.setText(f"✗  Miss — {trc:.0f}ms")
        self.lbl_result.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{DANGER};"
        )
        self._timer_next.start(self.cfg["gameplay"]["penalidade_ms"])

    def _process_input(self, inp_id: str):
        modo = self.cfg["gameplay"]["modo_resposta"]
        trc  = (time.perf_counter() - self._start_time) * 1000

        # ── Modo QUALQUER ─────────────────────────────────────────────────────
        if modo == ResponseModeA.QUALQUER:
            if inp_id not in self._alvos_ativos:
                self._waiting = False
                self._timer_lifespan.stop()
                self._reg(inp_id, trc, acerto=False)
                self._show_erro(inp_id)
                self._timer_next.start(self.cfg["gameplay"]["penalidade_ms"])
            else:
                self._waiting = False
                self._timer_lifespan.stop()
                self._reg(inp_id, trc, acerto=True)
                self._dim_ind(inp_id)
                self._feedback_sucesso(trc)
                self._timer_next.start(self.cfg["timing"]["feedback_delay_ms"])

        # ── Modo TODOS ────────────────────────────────────────────────────────
        elif modo == ResponseModeA.TODOS:
            if inp_id not in self._alvos_ativos or inp_id in self._respondidos:
                self._waiting = False
                self._timer_lifespan.stop()
                self._reg(inp_id, trc, acerto=False)
                self._show_erro(inp_id)
                self._timer_next.start(self.cfg["gameplay"]["penalidade_ms"])
            else:
                self._respondidos.append(inp_id)
                self._dim_ind(inp_id)
                if set(self._respondidos) >= set(self._alvos_ativos):
                    self._waiting = False
                    self._timer_lifespan.stop()
                    self._reg(inp_id, trc, acerto=True, todos=True)
                    self._feedback_sucesso(trc)
                    self._timer_next.start(self.cfg["timing"]["feedback_delay_ms"])
                # Caso contrário, continua aguardando os restantes

        # ── Modo SEQUÊNCIA ────────────────────────────────────────────────────
        elif modo == ResponseModeA.SEQUENCIA:
            esperado = self._alvos_ativos[len(self._respondidos)] \
                       if len(self._respondidos) < len(self._alvos_ativos) else None

            if inp_id != esperado:
                # Ordem errada ou tecla errada — encerra a tentativa
                self._waiting = False
                self._timer_lifespan.stop()
                self._seq_frame.setVisible(False)
                self._reg(inp_id, trc, acerto=False, sequencia_errada=True)
                esperado_label = self._label(esperado) if esperado else "?"
                self.lbl_result.setText(
                    f"✗  Ordem errada — esperava [{esperado_label}], pressionou [{self._label(inp_id)}]"
                )
                self.lbl_result.setStyleSheet(
                    f"font-size:15px; font-weight:700; color:{DANGER};"
                )
                self._timer_next.start(self.cfg["gameplay"]["penalidade_ms"])
            else:
                self._respondidos.append(inp_id)
                self._dim_ind(inp_id)
                self._update_seq_bar()

                if len(self._respondidos) >= len(self._alvos_ativos):
                    # Sequência completa
                    self._waiting = False
                    self._timer_lifespan.stop()
                    self._seq_frame.setVisible(False)
                    self._reg(inp_id, trc, acerto=True, sequencia_ok=True)
                    self._feedback_sucesso(trc)
                    self._timer_next.start(self.cfg["timing"]["feedback_delay_ms"])
                # Caso contrário, continua aguardando o próximo da sequência

    def _show_erro(self, inp_id: str):
        self.lbl_result.setText(f"✗  [{self._label(inp_id)}] não era o alvo")
        self.lbl_result.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{DANGER};"
        )

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

    def _reg(self, inp_id: str | None, trc: float, acerto: bool,
             miss: bool = False, todos: bool = False,
             sequencia_ok: bool = False, sequencia_errada: bool = False):
        self.resultados.append({
            "alvos_ids":        self._alvos_ativos[:],
            "alvos_labels":     [self._label(a) for a in self._alvos_ativos],
            "input_id":         inp_id,
            "input_label":      self._label(inp_id) if inp_id else None,
            "trc_ms":           round(trc, 2),
            "acerto":           acerto,
            "miss":             miss,
            "modo_resposta":    self.cfg["gameplay"]["modo_resposta"],
            "todos_concluidos": todos,
            "sequencia_ok":     sequencia_ok,
            "sequencia_errada": sequencia_errada,
        })
        self._atualizar_barra(self.cfg["gameplay"]["limite_trc_ms"])

    # ── Encerramento ──────────────────────────────────────────────────────────
    def _encerrar_base(self):
        self._timer_stimulus.stop()
        self._timer_lifespan.stop()
        self._timer_next.stop()
        self._is_running = False
        self._waiting    = False
        super()._encerrar_base()

    # ── Config em tempo real ──────────────────────────────────────────────────
    def aplicar_config(self, cfg: dict):
        self._timer_stimulus.stop()
        self._timer_lifespan.stop()
        self._timer_next.stop()
        self._is_running = False
        self._waiting    = False
        normalised = self._normalise_cfg(cfg)
        self.cfg   = deep_merge(DEFAULT_CONFIG, normalised)
        self._rebuild_indicators()
        self.lbl_result.setText("")
        self._seq_frame.setVisible(False)
        self.lbl_status.setText(
            "Configuração atualizada — pressione qualquer tecla para começar"
        )
        self.lbl_status.setStyleSheet(
            f"font-size:16px; font-weight:500; color:{TEXT_SEC};"
        )
