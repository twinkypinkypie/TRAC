"""
TRAC — Modo B: Inibição Antecipatória
Treina controle inibitório e supressão de impulsos motores prematuros.
"""

import time
import socket
import struct
from enum import Enum

from trac_csprng import CSPRNGClient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QMouseEvent

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
ALERT    = "#F5E642"   # amarelo do sinal de alerta

DEFAULT_CONFIG_B = {
    "teclas":               ["SPACE"],
    "mouse_botoes":         [],
    "nogo_ratio":           0.30,       # 30% das tentativas são NO-GO
    "alert_min_ms":         500,        # duração mínima do sinal de alerta
    "alert_max_ms":         1500,       # duração máxima do sinal de alerta
    "action_signal_variation": True,    # varia cor/forma do GO
    "false_start_penalty":  "RESET",    # RESET | MISS | BLOCK
    "block_duration_ms":    1500,       # duração do bloqueio se BLOCK
    "wait_min_s":           0.5,
    "wait_max_s":           2.0,
    "limite_trc_ms":        300,
    "penalidade_ms":        1000,
}


class Estado(Enum):
    """Estados do Modo B."""
    IDLE     = "idle"
    WAITING  = "waiting"
    ALERTING = "alerting"
    GO       = "go"
    NOGO     = "nogo"
    BLOCKED  = "blocked"


class ModoBGUI(QWidget):
    """Modo B — Inibição Antecipatória.
    
    Treina controle inibitório e supressão de impulsos motores. Usa paradigma GO/NO-GO:
    - GO: estímulo azul, usuário deve reagir rapidamente
    - NO-GO: estímulo vermelho, usuário deve inibir reação
    
    Estados da máquina:
        IDLE → WAITING → ALERTING → (GO ou NOGO) → feedback → IDLE
    
    Se reação prematura (false-start) durante alerting/nogo:
        aplicar penalidade (RESET/MISS/BLOCK) e reiniciar.
    
    Signals:
        finished: emite dict com resumo da sessão ao encerrar (ESC).
    """
    finished = pyqtSignal(dict)

    def __init__(self, config: dict | None = None, parent=None):
        super().__init__(parent)
        self.cfg = {**DEFAULT_CONFIG_B, **(config or {})}
        self.setStyleSheet(f"background-color:{BG_DEEP};")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # ── Estado ────────────────────────────────────────────────────────────
        self.estado          = Estado.IDLE
        self.start_time      = 0.0
        self._session_start  = 0.0
        self.resultados: list[dict] = []
        self._is_go_trial    = False
        self._variation_idx  = 0      # alterna visual do sinal GO

        # ── Timers ────────────────────────────────────────────────────────────
        self._t_wait  = QTimer(self); self._t_wait.setSingleShot(True)
        self._t_wait.timeout.connect(self._show_alert)

        self._t_alert = QTimer(self); self._t_alert.setSingleShot(True)
        self._t_alert.timeout.connect(self._show_go_or_nogo)

        self._t_nogo  = QTimer(self); self._t_nogo.setSingleShot(True)
        self._t_nogo.timeout.connect(self._nogo_success)

        self._t_miss  = QTimer(self); self._t_miss.setSingleShot(True)
        self._t_miss.timeout.connect(self._go_miss)

        self._t_next  = QTimer(self); self._t_next.setSingleShot(True)
        self._t_next.timeout.connect(self._next_trial)

        self._t_block = QTimer(self); self._t_block.setSingleShot(True)
        self._t_block.timeout.connect(self._unblock)

        self._t_start_reaction = QTimer(self); self._t_start_reaction.setSingleShot(True)
        self._t_start_reaction.timeout.connect(self._start_reaction_timer_b)

        # ── Layout ────────────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # Barra superior
        barra = QFrame()
        barra.setFixedHeight(52)
        barra.setStyleSheet(
            f"background-color:#0D0D14; border-bottom:1px solid {BORDER};"
        )
        bl = QHBoxLayout(barra); bl.setContentsMargins(24, 0, 24, 0)
        titulo = QLabel("MODO B  —  Inibição Antecipatória")
        titulo.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{ACCENT}; letter-spacing:2px;"
        )
        bl.addWidget(titulo); bl.addStretch()
        self.lbl_tentativas = QLabel("0 tentativas")
        self.lbl_tentativas.setStyleSheet(f"font-size:12px; color:{TEXT_SEC};")
        bl.addWidget(self.lbl_tentativas); bl.addSpacing(24)
        self.lbl_inibicoes = QLabel("—  inibições")
        self.lbl_inibicoes.setStyleSheet(f"font-size:12px; color:{SUCCESS};")
        bl.addWidget(self.lbl_inibicoes); bl.addSpacing(24)
        self.lbl_media = QLabel("TRC: —")
        self.lbl_media.setStyleSheet(f"font-size:12px; color:{TEXT_PRI};")
        bl.addWidget(self.lbl_media)
        root.addWidget(barra)

        # Centro
        centro = QWidget()
        centro.setStyleSheet(f"background-color:{BG_DEEP};")
        cl = QVBoxLayout(centro)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter); cl.setSpacing(0)

        # Círculo de sinal (alerta / GO / NO-GO)
        self.sinal = QLabel("")
        self.sinal.setFixedSize(180, 180)
        self.sinal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_sinal("idle")
        cl.addWidget(self.sinal, alignment=Qt.AlignmentFlag.AlignCenter)
        cl.addSpacing(28)

        # Indicadores de teclas/mouse disponíveis
        self.indicadores = {}
        ind_layout = QHBoxLayout()
        ind_layout.setSpacing(12); ind_layout.setContentsMargins(0, 0, 0, 0)
        ind_layout.addStretch()
        for tecla in self.cfg.get("teclas", []):
            lbl = QLabel(tecla)
            lbl.setFixedSize(48, 48)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"background-color:{BG_CARD}; color:{TEXT_PRI}; border:1px solid {BORDER};"
                f"border-radius:4px; font-size:12px; font-weight:600;"
            )
            self.indicadores[tecla] = lbl
            ind_layout.addWidget(lbl)
        for btn in self.cfg.get("mouse_botoes", []):
            lbl = QLabel(f"Mouse {btn}")
            lbl.setFixedSize(64, 48)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"background-color:{BG_CARD}; color:{TEXT_PRI}; border:1px solid {BORDER};"
                f"border-radius:4px; font-size:11px; font-weight:600;"
            )
            self.indicadores[btn] = lbl
            ind_layout.addWidget(lbl)
        ind_layout.addStretch()
        if self.indicadores:
            cl.addLayout(ind_layout)
            cl.addSpacing(20)

        # Status
        self.lbl_status = QLabel("Pressione qualquer tecla para começar")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:500; color:{TEXT_SEC};"
        )
        cl.addWidget(self.lbl_status)
        cl.addSpacing(12)

        # Resultado
        self.lbl_result = QLabel("")
        self.lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_result.setStyleSheet(f"font-size:16px; font-weight:700;")
        cl.addWidget(self.lbl_result)

        root.addWidget(centro, stretch=1)

        # Rodapé
        rodape = QFrame()
        rodape.setFixedHeight(52)
        rodape.setStyleSheet(
            f"background-color:#0D0D14; border-top:1px solid {BORDER};"
        )
        rl = QHBoxLayout(rodape); rl.setContentsMargins(24, 0, 24, 0)
        self.lbl_trng = QLabel("● CSPRNG: verificando...")
        self.lbl_trng.setStyleSheet(f"font-size:11px; color:{TEXT_SEC};")
        rl.addWidget(self.lbl_trng); rl.addStretch()
        ratio = int(self.cfg["nogo_ratio"] * 100)
        dica = QLabel(
            f"GO/NO-GO: {100-ratio}% / {ratio}%  |  "
            f"penalidade: {self.cfg['false_start_penalty']}  |  ESC para encerrar"
        )
        dica.setStyleSheet(f"font-size:11px; color:{TEXT_DIM};")
        rl.addWidget(dica)
        root.addWidget(rodape)

        QTimer.singleShot(200, self._checar_csprng)

    # ── Visual do sinal central ───────────────────────────────────────────────
    _VARIACOES_GO = [
        (ACCENT,   "●"),   # azul  — padrão
        ("#FFFFFF", "●"),  # branco
        (ACCENT,   "▶"),  # azul triângulo
        ("#FFFFFF", "▶"),  # branco triângulo
    ]

    def _set_sinal(self, modo: str):
        """Atualiza o visual do círculo central de sinal.
        
        Args:
            modo: "idle" (vazio), "alert" (amarelo), "go" (azul), 
                  "nogo" (vermelho), "blocked" (vermelho escuro)
        """
        estilos = {
            "idle": (TEXT_DIM,  BG_CARD,  BORDER,  "○",  80),
            "alert":(ALERT,     "#2A2200", ALERT,   "●", 100),
            "nogo": (DANGER,    "#2E0F0F", DANGER,  "✗",  90),
            "blocked": (DANGER, "#1A0808", DANGER,  "⛔", 70),
        }
        if modo == "go":
            if self.cfg.get("action_signal_variation"):
                fg, sym = self._VARIACOES_GO[
                    self._variation_idx % len(self._VARIACOES_GO)
                ]
                self._variation_idx += 1
            else:
                fg, sym = ACCENT, "●"
            bg, bd, sz = "#0A1A30", ACCENT, 100
        else:
            fg, bg, bd, sym, sz = estilos.get(modo, estilos["idle"])

        self.sinal.setText(sym)
        self.sinal.setStyleSheet(
            f"background-color:{bg}; color:{fg}; border:2px solid {bd};"
            f"border-radius:90px; font-size:{sz}px; font-weight:900;"
        )

    def _checar_csprng(self):
        """Verifica conectividade do servidor TRNG e atualiza status."""
        seed = CSPRNGClient.get_seed(0)
        ts   = int(time.perf_counter_ns() & 0xFFFFFFFF)
        if seed != ts:
            self.lbl_trng.setText("● CSPRNG: conectado")
            self.lbl_trng.setStyleSheet(f"font-size:11px; color:{SUCCESS};")
        else:
            self.lbl_trng.setText("● CSPRNG: offline (fallback ativo)")
            self.lbl_trng.setStyleSheet(f"font-size:11px; color:{WARNING};")

    # ── Input ─────────────────────────────────────────────────────────────────
    def keyPressEvent(self, e: QKeyEvent):
        """Processa entrada de teclado. ESC para encerrar, outras teclas para interação."""
        if e.key() == Qt.Key.Key_Escape:
            self._encerrar(); return
        if self.estado == Estado.IDLE:
            self._start_session(); return
        key = e.text().upper()
        if key:
            self._process_input(key)

    def mousePressEvent(self, e: QMouseEvent):
        if not self.cfg["mouse_botoes"]: return
        btn_map = {
            Qt.MouseButton.LeftButton:   "LEFT",
            Qt.MouseButton.RightButton:  "RIGHT",
            Qt.MouseButton.MiddleButton: "MIDDLE",
        }
        btn = btn_map.get(e.button())
        if not btn or btn not in self.cfg["mouse_botoes"]: return
        if self.estado == Estado.IDLE:
            self._start_session(); return
        self._process_input(btn)

    def _process_input(self, inp: str):
        inputs_validos = self.cfg["teclas"] + self.cfg["mouse_botoes"]
        if inp not in inputs_validos:
            return

        if self.estado == Estado.GO:
            # Resposta correta ao GO
            trc = (time.perf_counter() - self.start_time) * 1000
            self._t_miss.stop()
            self.estado = Estado.WAITING
            self._registrar("GO", inp, trc, acerto=True)
            self._feedback_sucesso(trc)
            self._t_next.start(900)

        elif self.estado == Estado.ALERTING:
            # False start durante o alerta
            self._false_start(inp, fase="ALERT")

        elif self.estado == Estado.NOGO:
            # False start durante NO-GO
            self._t_nogo.stop()
            self._false_start(inp, fase="NOGO")

        elif self.estado == Estado.WAITING:
            # Clique ansioso antes do alerta
            self._false_start(inp, fase="WAIT")

        elif self.estado == Estado.BLOCKED:
            pass  # ignora durante bloqueio

    # ── Fluxo de sessão ───────────────────────────────────────────────────────
    def _start_session(self):
        """Inicializa uma nova sessão de treinamento."""
        self._session_start = time.perf_counter()
        self.resultados = []
        self.lbl_result.setText("")
        self._next_trial()

    def _next_trial(self):
        """Inicia um novo trial, aguardando intervalo aleatório antes do alerta."""
        self._set_sinal("idle")
        self.lbl_status.setText("Aguarde...")
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:500; color:{TEXT_SEC};"
        )
        seed_w = CSPRNGClient.get_seed(0)
        wait_ms = int(CSPRNGClient.to_float(
            seed_w, self.cfg["wait_min_s"], self.cfg["wait_max_s"]
        ) * 1000)
        self._t_wait.start(wait_ms)

    def _show_alert(self):
        """Exibe o sinal de alerta e decide se será GO ou NO-GO via TRNG."""
        self._set_sinal("alert")
        self.lbl_status.setText("Prepare-se...")
        self.lbl_status.setStyleSheet(
            f"font-size:18px; font-weight:600; color:{ALERT};"
        )
        seed_a = CSPRNGClient.get_seed(0)
        alert_ms = int(CSPRNGClient.to_float(
            seed_a,
            self.cfg["alert_min_ms"] / 1000,
            self.cfg["alert_max_ms"] / 1000,
        ) * 1000)
        # CSPRNG decide GO ou NO-GO
        seed_tipo = CSPRNGClient.get_seed(0)
        self._is_go_trial = not CSPRNGClient.to_bool(seed_tipo, self.cfg["nogo_ratio"])
        self._t_alert.start(alert_ms)

    def _show_go_or_nogo(self):
        """Exibe GO (azul, reage!) ou NO-GO (vermelho, não reaja!) conforme trial."""
        if self._is_go_trial:
            self.estado = Estado.GO
            self._set_sinal("go")
            self.lbl_status.setText("REAGE!")
            self.lbl_status.setStyleSheet(
                f"font-size:22px; font-weight:800; color:{TEXT_PRI};"
            )
            # Agenda o registro de start_time para DEPOIS da renderização
            self._t_start_reaction.start(0)
            # Miss se não reagir em 1s
            self._t_miss.start(1000)
        else:
            self.estado = Estado.NOGO
            self._set_sinal("nogo")
            self.lbl_status.setText("NÃO REAJA!")
            self.lbl_status.setStyleSheet(
                f"font-size:22px; font-weight:800; color:{DANGER};"
            )
            # Período NO-GO dura 800ms
            self._t_nogo.start(800)

    def _start_reaction_timer_b(self):
        """Registra o tempo de reação APÓS a renderização estar completa."""
        self.start_time = time.perf_counter()

    def _nogo_success(self):
        """Usuário sobreviveu ao NO-GO sem reagir."""
        self.estado = Estado.WAITING
        self._registrar("NOGO", None, None, acerto=True, inibicao=True)
        self.lbl_result.setText("✓  Inibição correta")
        self.lbl_result.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{SUCCESS};"
        )
        self._t_next.start(700)

    def _go_miss(self):
        """GO apareceu mas o usuário não reagiu a tempo."""
        self.estado = Estado.WAITING
        self._registrar("GO", None, None, acerto=False, miss=True)
        self.lbl_result.setText("✗  Lento demais (miss)")
        self.lbl_result.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{WARNING};"
        )
        self._t_next.start(self.cfg["penalidade_ms"])

    def _false_start(self, inp: str, fase: str):
        """Processa reação prematura (antes do GO ou durante NO-GO).
        
        Args:
            inp: tecla/botão que foi pressionado
            fase: "ALERT", "NOGO" ou "WAIT"
        """
        penalidade = self.cfg["false_start_penalty"]
        self._registrar("NOGO" if fase == "NOGO" else "GO", inp, None,
                        acerto=False, false_start=True, fase=fase)

        if penalidade == "RESET":
            self._t_alert.stop(); self._t_nogo.stop(); self._t_miss.stop(); self._t_start_reaction.stop()
            self.lbl_result.setText(f"✗  False start [{inp}]  —  reiniciando")
            self.lbl_result.setStyleSheet(
                f"font-size:16px; font-weight:700; color:{DANGER};"
            )
            self._t_next.start(self.cfg["penalidade_ms"])

        elif penalidade == "MISS":
            self._t_alert.stop(); self._t_nogo.stop(); self._t_miss.stop(); self._t_start_reaction.stop()
            self.lbl_result.setText(f"✗  False start [{inp}]  —  erro contado")
            self.lbl_result.setStyleSheet(
                f"font-size:16px; font-weight:700; color:{DANGER};"
            )
            self._t_next.start(self.cfg["penalidade_ms"])

        elif penalidade == "BLOCK":
            self._t_alert.stop(); self._t_nogo.stop(); self._t_miss.stop(); self._t_start_reaction.stop()
            self.estado = Estado.BLOCKED
            self._set_sinal("blocked")
            self.lbl_status.setText("Bloqueado...")
            self.lbl_status.setStyleSheet(
                f"font-size:18px; font-weight:600; color:{DANGER};"
            )
            self.lbl_result.setText(f"✗  False start [{inp}]  —  bloqueado")
            self.lbl_result.setStyleSheet(
                f"font-size:16px; font-weight:700; color:{DANGER};"
            )
            self._t_block.start(self.cfg["block_duration_ms"])

    def _unblock(self):
        self._t_next.start(300)

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

    def _registrar(self, tipo, inp, trc, acerto,
                   inibicao=False, miss=False, false_start=False, fase=""):
        """Registra resultado de um trial.
        
        Args:
            tipo: "GO" ou "NOGO"
            inp: tecla/botão pressionado
            trc: tempo de reação em ms
            acerto: sucesso/fracasso
            inibicao: indica inibição bem-sucedida (NO-GO correto)
            miss: GO não respondido a tempo
            false_start: reação prematura
            fase: fase em que ocorreu o false start
        """
        self.resultados.append({
            "tipo":           tipo,
            "tecla_alvo":     tipo,
            "tecla_pressionada": inp,
            "trc_ms":         round(trc, 2) if trc is not None else None,
            "acerto":         acerto,
            "inibicao":       inibicao,
            "miss":           miss,
            "false_start":    false_start,
            "fase":           fase,
        })
        self._atualizar_barra()

    def _atualizar_barra(self):
        n         = len(self.resultados)
        gos       = [r for r in self.resultados if r["tipo"] == "GO"]
        nogos     = [r for r in self.resultados if r["tipo"] == "NOGO"]
        go_ok     = [r for r in gos   if r["acerto"] and not r["inibicao"]]
        nogo_ok   = [r for r in nogos if r["inibicao"]]
        trcs      = [r["trc_ms"] for r in go_ok if r["trc_ms"]]

        self.lbl_tentativas.setText(f"{n} tentativa{'s' if n!=1 else ''}")
        self.lbl_inibicoes.setText(
            f"{len(nogo_ok)}/{len(nogos)} inibições"
        )
        if trcs:
            media = sum(trcs) / len(trcs)
            cor   = SUCCESS if media <= self.cfg["limite_trc_ms"] else WARNING
            self.lbl_media.setText(f"TRC GO: {media:.0f}ms")
            self.lbl_media.setStyleSheet(f"font-size:12px; color:{cor};")

    # ── Encerramento ──────────────────────────────────────────────────────────
    def _encerrar(self):
        for t in (self._t_wait, self._t_alert, self._t_nogo,
                  self._t_miss, self._t_next, self._t_block):
            t.stop()
        self.estado = Estado.IDLE

        n       = len(self.resultados)
        gos     = [r for r in self.resultados if r["tipo"] == "GO" and r["acerto"]]
        nogos   = [r for r in self.resultados if r["inibicao"]]
        trcs    = [r["trc_ms"] for r in gos if r["trc_ms"]]
        dur_ms  = int((time.perf_counter() - self._session_start) * 1000)

        self.finished.emit({
            "modo":            "B",
            "config":          self.cfg,
            "duracao_ms":      dur_ms,
            "tentativas":      n,
            "acertos":         len(gos),
            "inibicoes_ok":    len(nogos),
            "precisao_pct":    round(len(gos) / max(n, 1) * 100, 1),
            "trc_medio_ms":    round(sum(trcs) / len(trcs), 1) if trcs else None,
            "trc_minimo_ms":   round(min(trcs), 1) if trcs else None,
            "detalhes":        self.resultados,
        })