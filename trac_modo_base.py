"""
TRAC — Classe base para todos os modos de treino.

Fornece:
  - Infraestrutura de config (deep_merge, validação, legacy support)
  - CSPRNG check padronizado
  - Barra superior e rodapé reutilizáveis
  - Interface de encerramento via sinal finished
  - Helpers de timing (repaint-safe start_time)
  - Constantes de layout (_UI) separadas da config persistida
"""

from __future__ import annotations

import time
from abc import abstractmethod
from copy import deepcopy
from enum import Enum

from trac_csprng import CSPRNGClient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QMouseEvent

# ── Paleta global ─────────────────────────────────────────────────────────────
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

# ── Constantes de layout (NÃO persistidas em JSON/DB) ────────────────────────
_UI = {
    "barra_altura":            52,
    "rodape_altura":           52,
    "stimulus_altura":        160,
    "indicador_largura":       56,
    "indicador_altura":        56,
    "spacing_centro":          16,
    "spacing_indicadores":     10,
    "spacing_apos_indicadores":28,
}

# ── Tipos compartilhados ──────────────────────────────────────────────────────
class InputType(str, Enum):
    KEYBOARD = "keyboard"
    MOUSE    = "mouse"

class ResponseMode(str, Enum):
    SIMPLES  = "simples"
    QUALQUER = "qualquer"
    TODOS    = "todos"

MOUSE_QT_TO_CODE = {
    Qt.MouseButton.LeftButton:   "LEFT",
    Qt.MouseButton.RightButton:  "RIGHT",
    Qt.MouseButton.MiddleButton: "MIDDLE",
}

# ── Utilitários de config ─────────────────────────────────────────────────────
def deep_merge(base: dict, override: dict | None) -> dict:
    """Merge profundo: override sobrescreve folhas, preserva subchaves não mencionadas."""
    if override is None:
        return deepcopy(base)
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def legacy_inputs_to_modular(cfg: dict) -> list[dict] | None:
    """
    Converte teclas/mouse_botoes do formato antigo para lista de inputs modular.
    Retorna None se cfg já estiver no formato novo ou não tiver inputs antigos.
    """
    if "inputs" in cfg:
        return None
    teclas      = cfg.get("teclas", [])
    mouse_botoes = cfg.get("mouse_botoes", [])
    if not teclas and not mouse_botoes:
        return None

    inputs = []
    for t in teclas:
        t = str(t).upper()
        inputs.append({"id": f"KEY_{t}", "type": InputType.KEYBOARD.value,
                        "code": t, "label": t})
    for b in mouse_botoes:
        b = str(b).upper()
        inputs.append({"id": f"MOUSE_{b}", "type": InputType.MOUSE.value,
                        "code": b, "label": f"🖱{b}"})
    return inputs


def normalise_inputs(inputs: list[dict]) -> list[dict]:
    """Valida e normaliza a lista de inputs, adicionando label se ausente."""
    for inp in inputs:
        for key in ("id", "type", "code"):
            if key not in inp:
                raise ValueError(f"Input sem chave obrigatória '{key}': {inp}")
        inp["type"] = str(inp["type"]).lower()
        inp["code"] = str(inp["code"]).upper()
        if inp["type"] not in {InputType.KEYBOARD.value, InputType.MOUSE.value}:
            raise ValueError(f"Tipo de input inválido: {inp['type']!r}")
        if "label" not in inp:
            inp["label"] = inp["code"]
    return inputs


# ── Classe base ───────────────────────────────────────────────────────────────
class ModoBase(QWidget):
    """
    Classe base para todos os modos do TRAC.

    Subclasses devem:
      - Definir MODO_LETRA (str) e MODO_NOME (str) como atributos de classe
      - Definir DEFAULT_CONFIG (dict) com as chaves do modo
      - Implementar _build_centro() → QWidget com a área de jogo
      - Implementar _build_rodape_dica() → str com o texto de dica do rodapé
      - Implementar keyPressEvent / mousePressEvent (chamar super() para ESC)
      - Emitir self.finished(resumo) ao encerrar

    Fornece automaticamente:
      - Barra superior com título, tentativas, precisão e TRC médio
      - Rodapé com status CSPRNG e dica configurável
      - deep_merge e legacy support para config
      - Acesso a self.cfg, self.resultados, self._session_start
      - _checar_csprng(), _atualizar_barra(), _encerrar_base()
    """

    MODO_LETRA: str = "?"
    MODO_NOME:  str = "Modo Base"
    DEFAULT_CONFIG: dict = {}

    finished = pyqtSignal(dict)

    def __init__(self, config: dict | None = None, parent=None):
        super().__init__(parent)

        # Config: merge profundo com DEFAULT_CONFIG do modo filho
        self.cfg = deep_merge(self.DEFAULT_CONFIG, self._normalise_cfg(config))
        self.setStyleSheet(f"background-color:{BG_DEEP};")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)

        # ── Estado compartilhado ──────────────────────────────────────────────
        self.resultados: list[dict] = []
        self._session_start = 0.0

        # ── Layout raiz ───────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_barra())
        root.addWidget(self._build_centro(), stretch=1)
        root.addWidget(self._build_rodape())

        QTimer.singleShot(200, self._checar_csprng)

    # ── Hooks para subclasses ─────────────────────────────────────────────────
    @abstractmethod
    def _build_centro(self) -> QWidget:
        """Retorna o widget da área de jogo do modo."""
        ...

    @abstractmethod
    def _build_rodape_dica(self) -> str:
        """Retorna o texto de dica exibido no rodapé."""
        ...

    def _normalise_cfg(self, config: dict | None) -> dict | None:
        """
        Hook opcional: subclasses podem transformar config antes do merge.
        Ex: Modo A usa para converter formato legado de inputs.
        """
        return config

    # ── Barra superior ────────────────────────────────────────────────────────
    def _build_barra(self) -> QFrame:
        barra = QFrame()
        barra.setFixedHeight(_UI["barra_altura"])
        barra.setStyleSheet(
            f"background-color:#0D0D14; border-bottom:1px solid {BORDER};"
        )
        bl = QHBoxLayout(barra)
        bl.setContentsMargins(24, 0, 24, 0)

        titulo = QLabel(f"MODO {self.MODO_LETRA}  —  {self.MODO_NOME}")
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

        return barra

    # ── Rodapé ────────────────────────────────────────────────────────────────
    def _build_rodape(self) -> QFrame:
        rodape = QFrame()
        rodape.setFixedHeight(_UI["rodape_altura"])
        rodape.setStyleSheet(
            f"background-color:#0D0D14; border-top:1px solid {BORDER};"
        )
        rl = QHBoxLayout(rodape)
        rl.setContentsMargins(24, 0, 24, 0)

        self.lbl_csprng = QLabel("● CSPRNG: verificando...")
        self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{TEXT_SEC};")
        rl.addWidget(self.lbl_csprng)
        rl.addStretch()

        dica = QLabel(self._build_rodape_dica())
        dica.setStyleSheet(f"font-size:11px; color:{TEXT_DIM};")
        rl.addWidget(dica)

        return rodape

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

    # ── Barra: atualização em tempo real ──────────────────────────────────────
    def _atualizar_barra(self, limite_trc_ms: int):
        """Atualiza os três indicadores da barra com os dados de self.resultados."""
        n       = len(self.resultados)
        acertos = [r for r in self.resultados if r.get("acerto")]
        trcs    = [r["trc_ms"] for r in acertos if r.get("trc_ms") is not None]

        self.lbl_tentativas.setText(f"{n} tentativa{'s' if n != 1 else ''}")

        pct = (len(acertos) / n * 100) if n > 0 else 0
        cor = SUCCESS if pct >= 90 else (WARNING if pct >= 70 else DANGER)
        self.lbl_precisao.setText(f"{pct:.0f}% precisão")
        self.lbl_precisao.setStyleSheet(f"font-size:12px; color:{cor};")

        if trcs:
            media = sum(trcs) / len(trcs)
            cor_t = SUCCESS if media <= limite_trc_ms else WARNING
            self.lbl_media.setText(f"TRC: {media:.0f}ms")
            self.lbl_media.setStyleSheet(f"font-size:12px; color:{cor_t};")
        else:
            self.lbl_media.setText("TRC: —")
            self.lbl_media.setStyleSheet(f"font-size:12px; color:{TEXT_PRI};")

    # ── ESC padrão ────────────────────────────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        """Intercepta ESC e marca como aceito. Outras teclas NÃO são marcadas,
        permitindo que subclasses as processem normalmente."""
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            self._encerrar_base()
        else:
            event.ignore()   # essencial: não bloquear teclas das subclasses

    def _encerrar_base(self):
        """
        Calcula o resumo base e emite finished.
        Subclasses com timers devem pará-los ANTES de chamar super()._encerrar_base(),
        ou sobrescrever completamente e emitir finished elas mesmas.
        """
        n       = len(self.resultados)
        acertos = [r for r in self.resultados if r.get("acerto")]
        trcs    = [r["trc_ms"] for r in acertos if r.get("trc_ms") is not None]
        dur_ms  = int((time.perf_counter() - self._session_start) * 1000)

        self.finished.emit({
            "modo":          self.MODO_LETRA,
            "config":        self.cfg,
            "duracao_ms":    dur_ms,
            "tentativas":    n,
            "acertos":       len(acertos),
            "precisao_pct":  round(len(acertos) / n * 100, 1) if n > 0 else 0,
            "trc_medio_ms":  round(sum(trcs) / len(trcs), 1) if trcs else None,
            "trc_minimo_ms": round(min(trcs), 1) if trcs else None,
            "detalhes":      self.resultados,
        })
