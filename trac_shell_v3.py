"""
TRAC — Shell principal v3
Home + Histórico + Configurações + Modo A integrado
"""

import sys
import json
import socket
import struct
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QGridLayout, QSizePolicy,
    QStackedWidget, QScrollArea, QFileDialog, QCheckBox,
    QSpinBox, QComboBox, QLineEdit, QMessageBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette, QCursor, QIntValidator

from trac_modo_a_gui import ModoAGUI, DEFAULT_CONFIG
from trac_modo_b_gui import ModoBGUI, DEFAULT_CONFIG_B
from trac_db import init_db, salvar_sessao, listar_sessoes, exportar_csv
import json
import subprocess
import sys

CONFIG_PATH = Path(__file__).parent / "trac_config.json"


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg: dict) -> bool:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception:
        return False

# ── Paleta ────────────────────────────────────────────────────────────────────
BG_DEEP    = "#09090F"
BG_SURFACE = "#111118"
BG_CARD    = "#16161F"
BORDER     = "#2A2A38"
ACCENT     = "#4F8EF7"
ACCENT_DIM = "#1E3A6E"
TEXT_PRI   = "#E8E8F0"
TEXT_SEC   = "#6B6B80"
TEXT_DIM   = "#3A3A50"
SUCCESS    = "#3DDC84"
WARNING    = "#F5A623"
DANGER     = "#E05252"

MODOS = [
    {"letra": "A", "nome": "Escolha Simbólica",      "desc": "Associação estímulo-resposta",       "status": "ativo"},
    {"letra": "B", "nome": "Inibição Antecipatória", "desc": "Controle de impulsos motores",       "status": "ativo"},
    {"letra": "C", "nome": "Periférico Espacial",    "desc": "Via dorsal e visão periférica",      "status": "em breve"},
    {"letra": "D", "nome": "Carga Cognitiva",        "desc": "Overclock e estado de fluxo",        "status": "em breve"},
    {"letra": "E", "nome": "Oclusão Estroboscópica", "desc": "Antecipação sem feedback visual",    "status": "em breve"},
    {"letra": "F", "nome": "Ghost Mode",             "desc": "Oclusão temporal preditiva",         "status": "em breve"},
    {"letra": "G", "nome": "Resiliência Pós-Erro",   "desc": "Recuperação cognitiva após falhas",  "status": "em breve"},
    {"letra": "H", "nome": "Bio-Feedback de Fadiga", "desc": "Monitoramento neural em tempo real", "status": "em breve"},
]

STYLESHEET = f"""
QMainWindow, QWidget {{ background-color:{BG_DEEP}; color:{TEXT_PRI}; }}
QLabel {{ background:transparent; color:{TEXT_PRI}; }}
QFrame#divider {{ background-color:{BORDER}; max-height:1px; min-height:1px; }}

QFrame#modeCard {{
    background-color:{BG_CARD}; border:1px solid {BORDER}; border-radius:10px;
}}
QFrame#modeCard:hover {{
    border:1px solid {ACCENT}; background-color:{ACCENT_DIM};
}}
QFrame#modeCardDisabled {{
    background-color:{BG_SURFACE}; border:1px solid {TEXT_DIM}; border-radius:10px;
}}
QPushButton#btnPrimary {{
    background-color:{ACCENT}; color:#fff; border:none; border-radius:8px;
    padding:10px 24px; font-size:13px; font-weight:600;
}}
QPushButton#btnPrimary:hover   {{ background-color:#6BA3FF; }}
QPushButton#btnPrimary:pressed {{ background-color:#3A7AE8; }}
QPushButton#btnPrimary:disabled {{ background-color:{TEXT_DIM}; color:{TEXT_SEC}; }}

QPushButton#btnGhost {{
    background-color:transparent; color:{TEXT_SEC};
    border:1px solid {BORDER}; border-radius:8px;
    padding:10px 20px; font-size:13px;
}}
QPushButton#btnGhost:hover {{
    background-color:{BG_CARD}; color:{TEXT_PRI}; border:1px solid {ACCENT};
}}
QPushButton#btnDanger {{
    background-color:transparent; color:{DANGER};
    border:1px solid {DANGER}; border-radius:8px;
    padding:10px 20px; font-size:13px;
}}
QPushButton#btnDanger:hover {{ background-color:#2E0F0F; }}

QLabel#badgeAtivo   {{ color:{SUCCESS}; background-color:#0D2E1C; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:600; }}
QLabel#badgeEmBreve {{ color:{WARNING}; background-color:#2E200A; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:600; }}
QFrame#metricBox    {{ background-color:{BG_SURFACE}; border:1px solid {BORDER}; border-radius:8px; }}
QFrame#configSection {{ background-color:{BG_SURFACE}; border:1px solid {BORDER}; border-radius:10px; }}
QFrame#configSectionDisabled {{ background-color:{BG_DEEP}; border:1px solid {TEXT_DIM}; border-radius:10px; }}

QSpinBox, QComboBox, QLineEdit {{
    background-color:{BG_CARD}; color:{TEXT_PRI};
    border:1px solid {BORDER}; border-radius:6px;
    padding:4px 8px; font-size:13px;
}}
QSpinBox:focus, QComboBox:focus, QLineEdit:focus {{
    border:1px solid {ACCENT};
}}
QComboBox::drop-down {{ border:none; }}
QComboBox QAbstractItemView {{
    background-color:{BG_CARD}; color:{TEXT_PRI};
    border:1px solid {BORDER}; selection-background-color:{ACCENT_DIM};
}}
QCheckBox {{ color:{TEXT_PRI}; spacing:8px; font-size:13px; }}
QCheckBox::indicator {{
    width:18px; height:18px;
    border:1px solid {BORDER}; border-radius:4px;
    background-color:{BG_CARD};
}}
QCheckBox::indicator:checked {{
    background-color:{ACCENT}; border:1px solid {ACCENT};
}}

QTableWidget {{
    background-color:{BG_SURFACE}; color:{TEXT_PRI};
    border:1px solid {BORDER}; border-radius:8px;
    gridline-color:{BORDER}; font-size:12px;
}}
QTableWidget::item {{ padding:6px 10px; }}
QTableWidget::item:selected {{ background-color:{ACCENT_DIM}; color:{TEXT_PRI}; }}
QHeaderView::section {{
    background-color:{BG_CARD}; color:{TEXT_SEC};
    border:none; border-bottom:1px solid {BORDER};
    padding:6px 10px; font-size:11px; font-weight:600;
}}

QScrollBar:vertical {{ width:4px; background:transparent; }}
QScrollBar::handle:vertical {{ background:{BORDER}; border-radius:2px; min-height:40px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ height:4px; background:transparent; }}
QScrollBar::handle:horizontal {{ background:{BORDER}; border-radius:2px; min-width:40px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
"""

# ── Widgets auxiliares ────────────────────────────────────────────────────────
class LetraWidget(QLabel):
    def __init__(self, letra, ativo=True, parent=None):
        super().__init__(letra, parent)
        self.setFixedSize(44, 44)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg = ACCENT_DIM if ativo else BG_SURFACE
        fg = ACCENT     if ativo else TEXT_DIM
        bd = ACCENT     if ativo else TEXT_DIM
        self.setStyleSheet(
            f"background-color:{bg}; color:{fg}; border:1px solid {bd};"
            f"border-radius:10px; font-size:20px; font-weight:700;"
        )

class MetricBox(QFrame):
    def __init__(self, label, valor, cor=ACCENT, parent=None):
        super().__init__(parent)
        self.setObjectName("metricBox")
        self.setFixedHeight(64); self.setMinimumWidth(110)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size:11px; color:{TEXT_SEC}; font-weight:500;")
        lay.addWidget(lbl)
        self._val = QLabel(valor)
        self._val.setStyleSheet(f"font-size:20px; font-weight:700; color:{cor};")
        lay.addWidget(self._val)

    def set_valor(self, texto, cor=None):
        self._val.setText(texto)
        if cor:
            self._val.setStyleSheet(f"font-size:20px; font-weight:700; color:{cor};")

class ModeCard(QFrame):
    def __init__(self, modo, on_click=None, parent=None):
        super().__init__(parent)
        ativo = modo["status"] == "ativo"
        self.setObjectName("modeCard" if ativo else "modeCardDisabled")
        self.setFixedHeight(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cursor = Qt.CursorShape.PointingHandCursor if ativo else Qt.CursorShape.ForbiddenCursor
        self.setCursor(QCursor(cursor))
        self._cb = on_click if ativo else None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(14)
        lay.addWidget(LetraWidget(modo["letra"], ativo))

        txt = QVBoxLayout(); txt.setSpacing(3)
        nome = QLabel(modo["nome"])
        nome.setStyleSheet(
            f"font-size:14px; font-weight:600; color:{ TEXT_PRI if ativo else TEXT_SEC };"
        )
        txt.addWidget(nome)
        desc = QLabel(modo["desc"])
        desc.setStyleSheet(f"font-size:12px; color:{TEXT_SEC};")
        txt.addWidget(desc)
        lay.addLayout(txt); lay.addStretch()

        badge = QLabel("ativo" if ativo else "em breve")
        badge.setObjectName("badgeAtivo" if ativo else "badgeEmBreve")
        badge.setFixedHeight(20)
        lay.addWidget(badge, alignment=Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, e):
        if self._cb: self._cb()
        super().mousePressEvent(e)

def divider():
    d = QFrame(); d.setObjectName("divider"); return d

def section_label(texto):
    l = QLabel(texto)
    l.setStyleSheet(
        f"font-size:11px; font-weight:600; color:{TEXT_SEC}; letter-spacing:1px;"
    )
    return l

# ── ABA: HOME ─────────────────────────────────────────────────────────────────
class HomeWidget(QWidget):
    def __init__(self, on_modo, parent=None):
        super().__init__(parent)
        self._n_sessoes = 0
        self._csprng_proc = None
        main = QVBoxLayout(self)
        main.setContentsMargins(32, 28, 32, 24); main.setSpacing(0)

        # Header
        header = QHBoxLayout()
        col = QVBoxLayout(); col.setSpacing(2)
        titulo = QLabel("Selecionar Modo")
        titulo.setStyleSheet(f"font-size:22px; font-weight:700; color:{TEXT_PRI};")
        col.addWidget(titulo)
        self.lbl_ultima = QLabel("Nenhuma sessão ainda")
        self.lbl_ultima.setStyleSheet(f"font-size:12px; color:{TEXT_SEC};")
        col.addWidget(self.lbl_ultima)
        header.addLayout(col); header.addStretch()

        mr = QHBoxLayout(); mr.setSpacing(8)
        self.m_trc      = MetricBox("Melhor TRC",  "—",  ACCENT)
        self.m_precisao = MetricBox("Precisão",    "—",  SUCCESS)
        self.m_sessoes  = MetricBox("Sessões",     "0",  TEXT_PRI)
        mr.addWidget(self.m_trc)
        mr.addWidget(self.m_precisao)
        mr.addWidget(self.m_sessoes)
        header.addLayout(mr)
        main.addLayout(header); main.addSpacing(24)
        main.addWidget(divider()); main.addSpacing(16)
        main.addWidget(section_label("MODOS DISPONÍVEIS")); main.addSpacing(10)

        grid = QGridLayout(); grid.setSpacing(10)
        for i, modo in enumerate(MODOS):
            if modo["status"] == "ativo":
                cb = (lambda m: lambda: on_modo(m["letra"]))(modo)
            else:
                cb = (lambda m: lambda: self._show_placeholder(m))(modo)
            card = ModeCard(modo, on_click=cb)
            grid.addWidget(card, i // 2, i % 2)
        main.addLayout(grid); main.addStretch(); main.addSpacing(16)
        main.addWidget(divider()); main.addSpacing(14)

        footer = QHBoxLayout()
        self.lbl_csprng = QLabel("● CSPRNG: verificando...")
        self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{TEXT_SEC};")
        footer.addWidget(self.lbl_csprng)

        self.btn_csprng = QPushButton("Iniciar CSPRNG")
        self.btn_csprng.setObjectName("btnGhost")
        self.btn_csprng.setFixedHeight(32)
        self.btn_csprng.clicked.connect(self._try_start_csprng)
        footer.addWidget(self.btn_csprng)

        footer.addStretch()
        self.btn_iniciar = QPushButton("Iniciar Modo A  →")
        self.btn_iniciar.setObjectName("btnPrimary")
        self.btn_iniciar.setFixedHeight(38)
        self.btn_iniciar.clicked.connect(lambda: on_modo("A"))
        footer.addWidget(self.btn_iniciar)

        self.btn_export_last = QPushButton("Exportar Última")
        self.btn_export_last.setObjectName("btnGhost")
        self.btn_export_last.setFixedHeight(32)
        self.btn_export_last.clicked.connect(self._export_last_session)
        footer.addWidget(self.btn_export_last)

        main.addLayout(footer)
        self._load_initial_stats()

        QTimer.singleShot(400, self._checar_csprng)

    def _checar_csprng(self):
        try:
            with socket.socket() as s:
                s.settimeout(0.5); s.connect(("127.0.0.1", 9999))
                s.sendall(struct.pack("I", 0))
                if len(s.recv(4)) == 4:
                    self.lbl_csprng.setText("● CSPRNG: conectado  |  porta 9999")
                    self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{SUCCESS};")
                    return
        except Exception:
            pass
        self.lbl_csprng.setText("● CSPRNG: offline  —  inicie o csprng_server_v2.py")
        self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{WARNING};")

    def _show_placeholder(self, modo: dict):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, f"Modo {modo['letra']}",
            f"{modo['nome']}\n\n{modo['desc']}\n\nStatus: {modo['status']}. Implementação futura.")

    def _try_start_csprng(self):
        # tenta se conectar primeiro
        try:
            with socket.socket() as s:
                s.settimeout(0.5); s.connect(("127.0.0.1", 9999))
                self.lbl_csprng.setText("● CSPRNG: conectado  |  porta 9999")
                self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{SUCCESS};")
                return
        except Exception:
            pass

        # tenta iniciar o servidor CSPRNG via subprocess
        try:
            script = Path(__file__).parent / 'csprng_server_v2.py'
            proc = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # track process locally and on app
            self._csprng_proc = proc
            try:
                app_win = self.window()
                if hasattr(app_win, '_csprng_proc'):
                    app_win._csprng_proc = proc
            except Exception:
                pass
            QTimer.singleShot(800, self._checar_csprng)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'CSPRNG', f'Falha ao iniciar CSPRNG: {e}')

    def _export_last_session(self):
        sessoes = listar_sessoes(1)
        if not sessoes:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, 'Exportar', 'Nenhuma sessão registrada.')
            return
        s = sessoes[0]
        # salva em CSV simples
        import csv
        path = Path.cwd() / 'trac_ultima_sessao.csv'
        keys = list(s.keys())
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerow(s)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, 'Exportar', f'Última sessão exportada para:\n{path}')

    def atualizar_metricas(self, resumo: dict):
        self._n_sessoes += 1
        self.m_sessoes.set_valor(str(self._n_sessoes))
        if resumo.get("trc_minimo_ms"):
            self.m_trc.set_valor(f"{resumo['trc_minimo_ms']:.0f}ms")
        if resumo.get("precisao_pct") is not None:
            pct = resumo["precisao_pct"]
            cor = SUCCESS if pct >= 90 else (WARNING if pct >= 70 else DANGER)
            self.m_precisao.set_valor(f"{pct:.0f}%", cor)
        n = resumo.get("tentativas", 0)
        self.lbl_ultima.setText(
            f"Última sessão: Modo {resumo.get('modo','?')}  —  {n} tentativas"
        )
        QTimer.singleShot(300, self._checar_csprng)

    def _load_initial_stats(self):
        sessoes = listar_sessoes(1000)
        self._n_sessoes = len(sessoes)
        self.m_sessoes.set_valor(str(self._n_sessoes))

        trc_minimos = [s["trc_minimo"] for s in sessoes if s["trc_minimo"] is not None]
        if trc_minimos:
            self.m_trc.set_valor(f"{min(trc_minimos):.0f}ms")

        precisao_vals = [s["precisao"] for s in sessoes if s["precisao"] is not None]
        if precisao_vals:
            avg_pct = sum(precisao_vals) / len(precisao_vals)
            cor = SUCCESS if avg_pct >= 90 else (WARNING if avg_pct >= 70 else DANGER)
            self.m_precisao.set_valor(f"{avg_pct:.0f}%", cor)

        if sessoes:
            ultima = sessoes[0]
            self.lbl_ultima.setText(
                f"Última sessão: Modo {ultima.get('modo','?')} — {ultima.get('tentativas',0)} tentativas"
            )


# ── ABA: HISTÓRICO ────────────────────────────────────────────────────────────
class HistoricoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24); lay.setSpacing(0)

        # Header
        h = QHBoxLayout()
        titulo = QLabel("Histórico de Sessões")
        titulo.setStyleSheet(f"font-size:22px; font-weight:700; color:{TEXT_PRI};")
        h.addWidget(titulo); h.addStretch()

        btn_atualizar = QPushButton("Atualizar")
        btn_atualizar.setObjectName("btnGhost"); btn_atualizar.setFixedHeight(36)
        btn_atualizar.clicked.connect(self.carregar)
        h.addWidget(btn_atualizar)
        h.addSpacing(8)

        self.btn_exportar = QPushButton("Exportar CSV")
        self.btn_exportar.setObjectName("btnPrimary"); self.btn_exportar.setFixedHeight(36)
        self.btn_exportar.clicked.connect(self._exportar)
        h.addWidget(self.btn_exportar)
        lay.addLayout(h); lay.addSpacing(8)

        self.lbl_resumo = QLabel("—")
        self.lbl_resumo.setStyleSheet(f"font-size:12px; color:{TEXT_SEC};")
        lay.addWidget(self.lbl_resumo); lay.addSpacing(16)
        lay.addWidget(divider()); lay.addSpacing(16)

        # Tabela
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(7)
        self.tabela.setHorizontalHeaderLabels([
            "Data / Hora", "Modo", "Tentativas", "Acertos", "Precisão", "TRC Médio", "TRC Mínimo"
        ])
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.horizontalHeader().setStretchLastSection(True)
        self.tabela.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        lay.addWidget(self.tabela, stretch=1)

        self.carregar()

    def carregar(self):
        sessoes = listar_sessoes()
        self.tabela.setRowCount(len(sessoes))

        for i, s in enumerate(sessoes):
            dt = datetime.fromtimestamp(s["timestamp"]).strftime("%d/%m/%Y  %H:%M")
            valores = [
                dt,
                f"Modo {s['modo']}",
                str(s["tentativas"] or 0),
                str(s["acertos"] or 0),
                f"{s['precisao']:.0f}%" if s["precisao"] is not None else "—",
                f"{s['trc_medio']:.0f}ms" if s["trc_medio"] is not None else "—",
                f"{s['trc_minimo']:.0f}ms" if s["trc_minimo"] is not None else "—",
            ]
            for j, v in enumerate(valores):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabela.setItem(i, j, item)

        n = len(sessoes)
        self.lbl_resumo.setText(
            f"{n} sessão{'ões' if n != 1 else ''} registrada{'s' if n != 1 else ''}"
        )
        self.btn_exportar.setEnabled(n > 0)

    def _exportar(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar histórico", "trac_historico.csv",
            "CSV (*.csv)"
        )
        if not path:
            return
        n = exportar_csv(path)
        QMessageBox.information(
            self, "Exportação concluída",
            f"{n} sessões exportadas para:\n{path}"
        )


# ── ABA: CONFIGURAÇÕES ────────────────────────────────────────────────────────
class ConfigWidget(QWidget):
    config_changed = None   # definido em TRACApp

    def __init__(self, config_inicial: dict, parent=None):
        super().__init__(parent)
        self._cfg = {**DEFAULT_CONFIG, **config_inicial}
        self._cfg_b = {**DEFAULT_CONFIG_B, **config_inicial.get("modo_b", {})}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 28, 32, 32); lay.setSpacing(24)

        titulo = QLabel("Configurações")
        titulo.setStyleSheet(f"font-size:22px; font-weight:700; color:{TEXT_PRI};")
        lay.addWidget(titulo)
        lay.addWidget(divider())
        lay.addSpacing(8)

        # ── Seção: Modo A ─────────────────────────────────────────────────────
        lay.addWidget(self._section_label("MODO A — Escolha Simbólica"))

        sec_a = QFrame(); sec_a.setObjectName("configSection")
        sa = QVBoxLayout(sec_a); sa.setContentsMargins(20, 18, 20, 18); sa.setSpacing(14)

        # Teclas
        sa.addWidget(self._label("Teclas mapeadas (separadas por vírgula):"))
        self.inp_teclas = QLineEdit(", ".join(self._cfg.get("teclas", [])))
        self.inp_teclas.setPlaceholderText("Ex: W, A, S, D")
        self.inp_teclas.textChanged.connect(self._on_change)
        sa.addWidget(self.inp_teclas)

        # Mouse
        sa.addWidget(self._label("Botões do mouse:"))
        mouse_row = QHBoxLayout(); mouse_row.setSpacing(16)
        self.chk_mouse = {}
        for btn in ["LEFT", "RIGHT", "MIDDLE"]:
            chk = QCheckBox(btn.capitalize())
            chk.setChecked(btn in self._cfg.get("mouse_botoes", []))
            chk.stateChanged.connect(self._on_change)
            self.chk_mouse[btn] = chk
            mouse_row.addWidget(chk)
        mouse_row.addStretch()
        sa.addLayout(mouse_row)

        # Estímulos simultâneos
        est_row = QHBoxLayout(); est_row.setSpacing(12)
        est_row.addWidget(self._label("Estímulos simultâneos:"))
        self.spin_est = QSpinBox()
        self.spin_est.setRange(1, 8); self.spin_est.setFixedWidth(70)
        self.spin_est.setValue(self._cfg.get("estimulos_simultaneos", 1))
        self.spin_est.valueChanged.connect(self._on_change)
        est_row.addWidget(self.spin_est); est_row.addStretch()
        sa.addLayout(est_row)

        # Modo de resposta
        resp_row = QHBoxLayout(); resp_row.setSpacing(12)
        resp_row.addWidget(self._label("Modo de resposta (múltiplos estímulos):"))
        self.cmb_resp = QComboBox()
        self.cmb_resp.addItems(["simples", "qualquer", "todos"])
        self.cmb_resp.setCurrentText(self._cfg.get("modo_resposta", "simples"))
        self.cmb_resp.currentTextChanged.connect(self._on_change)
        resp_row.addWidget(self.cmb_resp); resp_row.addStretch()
        sa.addLayout(resp_row)

        # TRC alvo
        trc_row = QHBoxLayout(); trc_row.setSpacing(12)
        trc_row.addWidget(self._label("Meta de TRC (ms):"))
        self.spin_trc = QSpinBox()
        self.spin_trc.setRange(50, 2000); self.spin_trc.setFixedWidth(90)
        self.spin_trc.setValue(self._cfg.get("limite_trc_ms", 300))
        self.spin_trc.setSuffix(" ms")
        self.spin_trc.valueChanged.connect(self._on_change)
        trc_row.addWidget(self.spin_trc); trc_row.addStretch()
        sa.addLayout(trc_row)

        # Espera
        wait_row = QHBoxLayout(); wait_row.setSpacing(8)
        wait_row.addWidget(self._label("Espera antes do estímulo:"))
        self.spin_wait_min = QSpinBox()
        self.spin_wait_min.setRange(100, 5000); self.spin_wait_min.setFixedWidth(90)
        self.spin_wait_min.setValue(int(self._cfg.get("wait_min_s", 0.5) * 1000))
        self.spin_wait_min.setSuffix(" ms")
        self.spin_wait_min.valueChanged.connect(self._on_change)
        wait_row.addWidget(self.spin_wait_min)
        wait_row.addWidget(QLabel("até"))
        self.spin_wait_max = QSpinBox()
        self.spin_wait_max.setRange(200, 10000); self.spin_wait_max.setFixedWidth(90)
        self.spin_wait_max.setValue(int(self._cfg.get("wait_max_s", 2.0) * 1000))
        self.spin_wait_max.setSuffix(" ms")
        self.spin_wait_max.valueChanged.connect(self._on_change)
        wait_row.addWidget(self.spin_wait_max); wait_row.addStretch()
        sa.addLayout(wait_row)

        lay.addWidget(sec_a)

        # ── Seção: Modo B ─────────────────────────────────────────────────────
        lay.addWidget(self._section_label("MODO B — Inibição Antecipatória"))

        sec_b = QFrame(); sec_b.setObjectName("configSection")
        sb = QVBoxLayout(sec_b); sb.setContentsMargins(20, 18, 20, 18); sb.setSpacing(14)

        # Teclas
        sb.addWidget(self._label("Teclas mapeadas (separadas por vírgula):"))
        self.inp_teclas_b = QLineEdit(", ".join(self._cfg_b.get("teclas", [])))
        self.inp_teclas_b.setPlaceholderText("Ex: SPACE")
        self.inp_teclas_b.textChanged.connect(self._on_change)
        sb.addWidget(self.inp_teclas_b)

        # Mouse
        sb.addWidget(self._label("Botões do mouse:"))
        mouse_row_b = QHBoxLayout(); mouse_row_b.setSpacing(16)
        self.chk_mouse_b = {}
        for btn in ["LEFT", "RIGHT", "MIDDLE"]:
            chk = QCheckBox(btn.capitalize())
            chk.setChecked(btn in self._cfg_b.get("mouse_botoes", []))
            chk.stateChanged.connect(self._on_change)
            self.chk_mouse_b[btn] = chk
            mouse_row_b.addWidget(chk)
        mouse_row_b.addStretch()
        sb.addLayout(mouse_row_b)

        # NO-GO ratio
        nogo_row = QHBoxLayout(); nogo_row.setSpacing(12)
        nogo_row.addWidget(self._label("Proporção de NO-GO:"))
        self.spin_nogo = QSpinBox()
        self.spin_nogo.setRange(10, 90); self.spin_nogo.setFixedWidth(70)
        self.spin_nogo.setValue(int((self._cfg_b.get("nogo_ratio", 0.30) * 100)))
        self.spin_nogo.setSuffix(" %")
        self.spin_nogo.valueChanged.connect(self._on_change)
        nogo_row.addWidget(self.spin_nogo); nogo_row.addStretch()
        sb.addLayout(nogo_row)

        # Alert duration
        alert_row = QHBoxLayout(); alert_row.setSpacing(8)
        alert_row.addWidget(self._label("Duração do alerta:"))
        self.spin_alert_min_b = QSpinBox()
        self.spin_alert_min_b.setRange(100, 3000); self.spin_alert_min_b.setFixedWidth(90)
        self.spin_alert_min_b.setValue(int(self._cfg_b.get("alert_min_ms", 500)))
        self.spin_alert_min_b.setSuffix(" ms")
        self.spin_alert_min_b.valueChanged.connect(self._on_change)
        alert_row.addWidget(self.spin_alert_min_b)
        alert_row.addWidget(QLabel("até"))
        self.spin_alert_max_b = QSpinBox()
        self.spin_alert_max_b.setRange(200, 5000); self.spin_alert_max_b.setFixedWidth(90)
        self.spin_alert_max_b.setValue(int(self._cfg_b.get("alert_max_ms", 1500)))
        self.spin_alert_max_b.setSuffix(" ms")
        self.spin_alert_max_b.valueChanged.connect(self._on_change)
        alert_row.addWidget(self.spin_alert_max_b); alert_row.addStretch()
        sb.addLayout(alert_row)

        # False start penalty
        penalty_row = QHBoxLayout(); penalty_row.setSpacing(12)
        penalty_row.addWidget(self._label("Penalidade por false start:"))
        self.cmb_penalty = QComboBox()
        self.cmb_penalty.addItems(["RESET", "MISS", "BLOCK"])
        self.cmb_penalty.setCurrentText(self._cfg_b.get("false_start_penalty", "RESET"))
        self.cmb_penalty.currentTextChanged.connect(self._on_change)
        penalty_row.addWidget(self.cmb_penalty); penalty_row.addStretch()
        sb.addLayout(penalty_row)

        lay.addWidget(sec_b)

        # ── Seções placeholder para modos futuros ─────────────────────────────
        for letra, nome in [("C","Periférico Espacial"),
                             ("D","Carga Cognitiva"), ("E","Oclusão Estroboscópica"),
                             ("F","Ghost Mode"), ("G","Resiliência Pós-Erro"),
                             ("H","Bio-Feedback de Fadiga")]:
            lay.addWidget(self._section_label(f"MODO {letra} — {nome}"))
            sec = QFrame(); sec.setObjectName("configSectionDisabled")
            sl = QVBoxLayout(sec); sl.setContentsMargins(20, 16, 20, 16)
            lbl = QLabel("Configurações disponíveis após implementação do modo.")
            lbl.setStyleSheet(f"font-size:12px; color:{TEXT_DIM}; font-style:italic;")
            sl.addWidget(lbl)
            lay.addWidget(sec)

        # ── Seção: Geral ──────────────────────────────────────────────────────
        lay.addWidget(self._section_label("GERAL"))
        sec_g = QFrame(); sec_g.setObjectName("configSection")
        sg = QVBoxLayout(sec_g); sg.setContentsMargins(20, 18, 20, 18); sg.setSpacing(14)
        sg.addWidget(self._label("Duração máxima de sessão (0 = ilimitado):"))
        dur_row = QHBoxLayout(); dur_row.setSpacing(8)
        self.spin_dur = QSpinBox()
        self.spin_dur.setRange(0, 120); self.spin_dur.setFixedWidth(80)
        self.spin_dur.setValue(0); self.spin_dur.setSuffix(" min")
        dur_row.addWidget(self.spin_dur); dur_row.addStretch()
        sg.addLayout(dur_row)
        sg.addWidget(self._label("Porta do servidor TRNG:"))
        porta_row = QHBoxLayout(); porta_row.setSpacing(8)
        self.inp_porta = QLineEdit("9999")
        self.inp_porta.setFixedWidth(90)
        self.inp_porta.setValidator(QIntValidator(1024, 65535))
        porta_row.addWidget(self.inp_porta); porta_row.addStretch()
        sg.addLayout(porta_row)
        lay.addWidget(sec_g)

        # ── Seção: Aparência ──────────────────────────────────────────────────
        lay.addWidget(self._section_label("APARÊNCIA"))
        sec_ap = QFrame(); sec_ap.setObjectName("configSection")
        sap = QVBoxLayout(sec_ap); sap.setContentsMargins(20, 16, 20, 16)
        lbl_ap = QLabel("Opções de tema e fonte disponíveis em versão futura.")
        lbl_ap.setStyleSheet(f"font-size:12px; color:{TEXT_DIM}; font-style:italic;")
        sap.addWidget(lbl_ap)
        lay.addWidget(sec_ap)

        lay.addStretch()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        scroll.setWidget(inner)

    def _label(self, texto):
        l = QLabel(texto)
        l.setStyleSheet(f"font-size:13px; color:{TEXT_SEC};")
        return l

    def _section_label(self, texto):
        l = QLabel(texto)
        l.setStyleSheet(
            f"font-size:11px; font-weight:600; color:{TEXT_SEC}; letter-spacing:1px;"
        )
        return l

    def _on_change(self):
        """Lê os widgets e emite a config atualizada para o app."""
        teclas_raw = [t.strip().upper() for t in self.inp_teclas.text().split(",") if t.strip()]
        mouse_raw  = [b for b, chk in self.chk_mouse.items() if chk.isChecked()]

        cfg_a = {
            "teclas":                teclas_raw,
            "mouse_botoes":          mouse_raw,
            "estimulos_simultaneos": self.spin_est.value(),
            "modo_resposta":         self.cmb_resp.currentText(),
            "limite_trc_ms":         self.spin_trc.value(),
            "wait_min_s":            self.spin_wait_min.value() / 1000,
            "wait_max_s":            self.spin_wait_max.value() / 1000,
            "penalidade_ms":         1000,
        }
        self._cfg = cfg_a

        # Modo B config
        teclas_b_raw = [t.strip().upper() for t in self.inp_teclas_b.text().split(",") if t.strip()]
        mouse_b_raw  = [b for b, chk in self.chk_mouse_b.items() if chk.isChecked()]

        cfg_b = {
            "teclas":                teclas_b_raw,
            "mouse_botoes":          mouse_b_raw,
            "nogo_ratio":            self.spin_nogo.value() / 100.0,
            "alert_min_ms":          self.spin_alert_min_b.value(),
            "alert_max_ms":          self.spin_alert_max_b.value(),
            "false_start_penalty":   self.cmb_penalty.currentText(),
        }

        if callable(self.config_changed):
            self.config_changed({"modo_a": cfg_a, "modo_b": cfg_b})

    def get_config(self) -> dict:
        return self._cfg


# ── Sidebar de navegação ──────────────────────────────────────────────────────
class Sidebar(QWidget):
    def __init__(self, on_nav, on_toggle_fullscreen=None, on_stop_trng=None, on_quit=None, parent=None):
        super().__init__(parent)
        # Slightly wider sidebar to better fit quick-action buttons
        self.setFixedWidth(260)
        self.setStyleSheet(
            f"background-color:{BG_SURFACE}; border-right:1px solid {BORDER};"
        )
        self._btns: dict[str, QPushButton] = {}
        self._on_nav = on_nav
        self._on_toggle_fullscreen = on_toggle_fullscreen
        self._on_stop_trng = on_stop_trng
        self._on_quit = on_quit

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 28, 20, 24); lay.setSpacing(0)

        logo = QLabel("TRAC")
        logo.setStyleSheet(
            f"font-size:26px; font-weight:800; color:{ACCENT}; letter-spacing:4px;"
        )
        lay.addWidget(logo)
        sub = QLabel("Treinador de Reação\nAdaptativo e Contextual")
        sub.setStyleSheet(f"font-size:11px; color:{TEXT_SEC}; margin-top:4px;")
        sub.setWordWrap(True)
        lay.addWidget(sub); lay.addSpacing(32)
        lay.addWidget(divider()); lay.addSpacing(20)

        for key, label in [("home", "  Início"), ("historico", "  Histórico"), ("config", "  Configurações")]:
            btn = QPushButton(label)
            btn.setFixedHeight(38)
            btn.setObjectName("btnGhost")
            btn.clicked.connect((lambda k: lambda: self._nav(k))(key))
            self._btns[key] = btn
            lay.addWidget(btn); lay.addSpacing(4)

        lay.addStretch()
        self._versao = QLabel("v2.0 — Engine Python\nCSPRNG: Hash de Caos")
        self._versao.setStyleSheet(f"font-size:10px; color:{TEXT_DIM}; line-height:1.6;")
        lay.addWidget(self._versao)

        # Quick actions grouped in a separate panel with spacing
        lay.addSpacing(8)
        action_frame = QFrame()
        action_frame.setStyleSheet("background:transparent;")
        afl = QVBoxLayout(action_frame)
        afl.setContentsMargins(4, 6, 4, 6)
        afl.setSpacing(8)

        if self._on_toggle_fullscreen:
            btn_fs = QPushButton("Tela Cheia")
            btn_fs.setObjectName("btnGhost")
            btn_fs.setFixedHeight(40)
            btn_fs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn_fs.clicked.connect(lambda: self._on_toggle_fullscreen())
            afl.addWidget(btn_fs)
        if self._on_stop_trng:
            btn_stop = QPushButton("Parar TRNG")
            btn_stop.setObjectName("btnGhost")
            btn_stop.setFixedHeight(40)
            btn_stop.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn_stop.clicked.connect(lambda: self._on_stop_trng())
            afl.addWidget(btn_stop)
        if self._on_quit:
            btn_quit = QPushButton("Sair")
            btn_quit.setObjectName("btnDanger")
            btn_quit.setFixedHeight(40)
            btn_quit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn_quit.clicked.connect(lambda: self._on_quit())
            afl.addWidget(btn_quit)

        lay.addWidget(action_frame)

        self.set_ativo("home")

    def _nav(self, key: str):
        self.set_ativo(key)
        self._on_nav(key)

    def set_ativo(self, key: str):
        for k, btn in self._btns.items():
            if k == key:
                btn.setStyleSheet(
                    f"background-color:{ACCENT_DIM}; color:{ACCENT};"
                    f"border:1px solid {ACCENT}; border-radius:8px;"
                    f"padding:10px 20px; font-size:13px; font-weight:600; text-align:left;"
                )
            else:
                btn.setObjectName("btnGhost")
                btn.setStyleSheet(
                    f"background-color:transparent; color:{TEXT_SEC};"
                    f"border:1px solid {BORDER}; border-radius:8px;"
                    f"padding:10px 20px; font-size:13px; text-align:left;"
                )


# ── Janela principal ──────────────────────────────────────────────────────────
class TRACApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TRAC")
        self.setFixedSize(860, 640)
        self.setStyleSheet(STYLESHEET)

        init_db()
        cfg_saved = load_config()
        self._cfg_modo_a = {**DEFAULT_CONFIG, **cfg_saved.get("modo_a", {})}
        self._cfg_modo_b = {**DEFAULT_CONFIG_B, **cfg_saved.get("modo_b", {})}

        root = QWidget()
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0); main.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar(
            on_nav=self._nav,
            on_toggle_fullscreen=self._toggle_fullscreen,
            on_stop_trng=self._stop_trng,
            on_quit=self._quit_app,
        )
        main.addWidget(self.sidebar)

        # Stack de abas (Home / Histórico / Config) + Modos sobrepostos
        self.area = QStackedWidget()
        main.addWidget(self.area)

        # Abas
        self.home      = HomeWidget(on_modo=self._ir_para_modo)
        self.historico = HistoricoWidget()
        self.config_w  = ConfigWidget({"modo_a": self._cfg_modo_a, "modo_b": self._cfg_modo_b})
        self.config_w.config_changed = self._on_config_changed

        self.area.addWidget(self.home)
        self.area.addWidget(self.historico)
        self.area.addWidget(self.config_w)

        # Widgets dos modos (sem sidebar — tela cheia dentro do area)
        self._modo_a_widget = None
        self._modo_b_widget = None
        self.area.setCurrentWidget(self.home)

        # track CSPRNG process if started by the app
        self._csprng_proc = None

    def _nav(self, key: str):
        mapping = {"home": self.home, "historico": self.historico, "config": self.config_w}
        if key in mapping:
            if key == "historico":
                self.historico.carregar()
            self.area.setCurrentWidget(mapping[key])

    def _ir_para_modo(self, letra: str):
        if letra == "A":
            # Recria o widget com a config atual para refletir mudanças
            if self._modo_a_widget:
                self.area.removeWidget(self._modo_a_widget)
                self._modo_a_widget.deleteLater()

            self._modo_a_widget = ModoAGUI(config=self._cfg_modo_a)
            self._modo_a_widget.finished.connect(self._sessao_encerrada)
            self.area.addWidget(self._modo_a_widget)
            self.area.setCurrentWidget(self._modo_a_widget)
            self._modo_a_widget.setFocus()
            self.sidebar.set_ativo("")   # nenhuma aba ativa durante treino

        elif letra == "B":
            # Recria o widget com a config atual para refletir mudanças
            if self._modo_b_widget:
                self.area.removeWidget(self._modo_b_widget)
                self._modo_b_widget.deleteLater()

            self._modo_b_widget = ModoBGUI(config=self._cfg_modo_b)
            self._modo_b_widget.finished.connect(self._sessao_encerrada)
            self.area.addWidget(self._modo_b_widget)
            self.area.setCurrentWidget(self._modo_b_widget)
            self._modo_b_widget.setFocus()
            self.sidebar.set_ativo("")   # nenhuma aba ativa durante treino

    def _sessao_encerrada(self, resumo: dict):
        salvar_sessao(resumo)
        self.home.atualizar_metricas(resumo)
        self.area.setCurrentWidget(self.home)
        self.sidebar.set_ativo("home")

    def _on_config_changed(self, cfg: dict):
        # Suporta dois formatos: direto (para Modo A) ou nested (para ambos)
        if "modo_a" in cfg and "modo_b" in cfg:
            # Novo formato com ambos os modos
            self._cfg_modo_a = cfg["modo_a"]
            self._cfg_modo_b = cfg["modo_b"]
            cfg_store = cfg
        else:
            # Apenas Modo A (compatibilidade)
            self._cfg_modo_a = cfg
            cfg_store = load_config()
            cfg_store["modo_a"] = cfg

        # Persist config to disk
        save_config(cfg_store)

        # If Modo A is currently active, apply the new config live
        if self._modo_a_widget:
            try:
                self._modo_a_widget.aplicar_config(self._cfg_modo_a)
            except Exception:
                pass

        # If Modo B is currently active, apply the new config live
        if self._modo_b_widget:
            try:
                self._modo_b_widget.cfg = self._cfg_modo_b
            except Exception:
                pass

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _stop_trng(self):
        # Try to stop CSPRNG started by HomeWidget or by app
        stopped = False
        # prefer process tracked on app
        if getattr(self, '_csprng_proc', None):
            proc = self._csprng_proc
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self._csprng_proc = None
            stopped = True

        # ask home widget to stop if it has a process
        try:
            if hasattr(self.home, '_csprng_proc') and self.home._csprng_proc:
                try:
                    self.home._csprng_proc.terminate()
                    self.home._csprng_proc.wait(timeout=2)
                except Exception:
                    try:
                        self.home._csprng_proc.kill()
                    except Exception:
                        pass
                self.home._csprng_proc = None
                stopped = True
        except Exception:
            pass

        if stopped:
            try:
                self.home.lbl_csprng.setText('● CSPRNG: offline')
                self.home.lbl_csprng.setStyleSheet(f"font-size:11px; color:{WARNING};")
            except Exception:
                pass

    def _quit_app(self):
        # Attempt to stop CSPRNG first
        try:
            self._stop_csprng()
        except Exception:
            pass
        QApplication.quit()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window,          BG_DEEP),
        (QPalette.ColorRole.WindowText,      TEXT_PRI),
        (QPalette.ColorRole.Base,            BG_SURFACE),
        (QPalette.ColorRole.AlternateBase,   BG_CARD),
        (QPalette.ColorRole.Text,            TEXT_PRI),
        (QPalette.ColorRole.Button,          BG_SURFACE),
        (QPalette.ColorRole.ButtonText,      TEXT_PRI),
        (QPalette.ColorRole.Highlight,       ACCENT),
        (QPalette.ColorRole.HighlightedText, "#ffffff"),
    ]:
        palette.setColor(role, QColor(color))
    app.setPalette(palette)

    w = TRACApp()
    w.show()
    sys.exit(app.exec())