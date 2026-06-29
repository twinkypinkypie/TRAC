"""
TRAC — Shell principal v3
Home + Histórico + Configurações + Modos A, B, C integrados
"""

import sys
import json
import socket
import struct
import subprocess
import csv
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QGridLayout, QSizePolicy,
    QStackedWidget, QScrollArea, QFileDialog, QCheckBox,
    QSpinBox, QComboBox, QLineEdit, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette, QCursor, QIntValidator

from trac_modo_a_gui import ModoAGUI, DEFAULT_CONFIG
from trac_modo_b_gui import ModoBGUI, DEFAULT_CONFIG_B
from trac_modo_c_gui import ModoCGUI, DEFAULT_CONFIG_C
from trac_db import init_db, salvar_sessao, listar_sessoes, exportar_csv

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
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

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
    {"letra": "C", "nome": "Periférico Espacial",    "desc": "Via dorsal e visão periférica",      "status": "ativo"},
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
QFrame#modeCard {{ background-color:{BG_CARD}; border:1px solid {BORDER}; border-radius:10px; }}
QFrame#modeCard:hover {{ border:1px solid {ACCENT}; background-color:{ACCENT_DIM}; }}
QFrame#modeCardDisabled {{ background-color:{BG_SURFACE}; border:1px solid {TEXT_DIM}; border-radius:10px; }}
QPushButton#btnPrimary {{ background-color:{ACCENT}; color:#fff; border:none; border-radius:8px; padding:10px 24px; font-size:13px; font-weight:600; }}
QPushButton#btnPrimary:hover {{ background-color:#6BA3FF; }}
QPushButton#btnPrimary:pressed {{ background-color:#3A7AE8; }}
QPushButton#btnPrimary:disabled {{ background-color:{TEXT_DIM}; color:{TEXT_SEC}; }}
QPushButton#btnGhost {{ background-color:transparent; color:{TEXT_SEC}; border:1px solid {BORDER}; border-radius:8px; padding:10px 20px; font-size:13px; }}
QPushButton#btnGhost:hover {{ background-color:{BG_CARD}; color:{TEXT_PRI}; border:1px solid {ACCENT}; }}
QPushButton#btnDanger {{ background-color:transparent; color:{DANGER}; border:1px solid {DANGER}; border-radius:8px; padding:10px 20px; font-size:13px; }}
QPushButton#btnDanger:hover {{ background-color:#2E0F0F; }}
QLabel#badgeAtivo {{ color:{SUCCESS}; background-color:#0D2E1C; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:600; }}
QLabel#badgeEmBreve {{ color:{WARNING}; background-color:#2E200A; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:600; }}
QFrame#metricBox {{ background-color:{BG_SURFACE}; border:1px solid {BORDER}; border-radius:8px; }}
QFrame#configSection {{ background-color:{BG_SURFACE}; border:1px solid {BORDER}; border-radius:10px; }}
QFrame#configSectionDisabled {{ background-color:{BG_DEEP}; border:1px solid {TEXT_DIM}; border-radius:10px; }}
QSpinBox, QComboBox, QLineEdit {{ background-color:{BG_CARD}; color:{TEXT_PRI}; border:1px solid {BORDER}; border-radius:6px; padding:4px 8px; font-size:13px; }}
QSpinBox:focus, QComboBox:focus, QLineEdit:focus {{ border:1px solid {ACCENT}; }}
QComboBox::drop-down {{ border:none; }}
QComboBox QAbstractItemView {{ background-color:{BG_CARD}; color:{TEXT_PRI}; border:1px solid {BORDER}; selection-background-color:{ACCENT_DIM}; }}
QCheckBox {{ color:{TEXT_PRI}; spacing:8px; font-size:13px; }}
QCheckBox::indicator {{ width:18px; height:18px; border:1px solid {BORDER}; border-radius:4px; background-color:{BG_CARD}; }}
QCheckBox::indicator:checked {{ background-color:{ACCENT}; border:1px solid {ACCENT}; }}
QTableWidget {{ background-color:{BG_SURFACE}; color:{TEXT_PRI}; border:1px solid {BORDER}; border-radius:8px; gridline-color:{BORDER}; font-size:12px; }}
QTableWidget::item {{ padding:6px 10px; }}
QTableWidget::item:selected {{ background-color:{ACCENT_DIM}; color:{TEXT_PRI}; }}
QHeaderView::section {{ background-color:{BG_CARD}; color:{TEXT_SEC}; border:none; border-bottom:1px solid {BORDER}; padding:6px 10px; font-size:11px; font-weight:600; }}
QScrollBar:vertical {{ width:4px; background:transparent; }}
QScrollBar::handle:vertical {{ background:{BORDER}; border-radius:2px; min-height:40px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ height:4px; background:transparent; }}
QScrollBar::handle:horizontal {{ background:{BORDER}; border-radius:2px; min-width:40px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
"""


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
        self.setCursor(QCursor(
            Qt.CursorShape.PointingHandCursor if ativo else Qt.CursorShape.ForbiddenCursor
        ))
        self._cb = on_click
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(14)
        lay.addWidget(LetraWidget(modo["letra"], ativo))
        txt = QVBoxLayout(); txt.setSpacing(3)
        nome = QLabel(modo["nome"])
        nome.setStyleSheet(f"font-size:14px; font-weight:600; color:{TEXT_PRI if ativo else TEXT_SEC};")
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
    l.setStyleSheet(f"font-size:11px; font-weight:600; color:{TEXT_SEC}; letter-spacing:1px;")
    return l


class HomeWidget(QWidget):
    def __init__(self, on_modo, parent=None):
        super().__init__(parent)
        self._n_sessoes   = 0
        self._csprng_proc = None
        main = QVBoxLayout(self)
        main.setContentsMargins(32, 28, 32, 24); main.setSpacing(0)

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
        self.m_trc      = MetricBox("Melhor TRC", "—",  ACCENT)
        self.m_precisao = MetricBox("Precisão",   "—",  SUCCESS)
        self.m_sessoes  = MetricBox("Sessões",    "0",  TEXT_PRI)
        for m in (self.m_trc, self.m_precisao, self.m_sessoes):
            mr.addWidget(m)
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
            grid.addWidget(ModeCard(modo, on_click=cb), i // 2, i % 2)
        main.addLayout(grid); main.addStretch(); main.addSpacing(16)
        main.addWidget(divider()); main.addSpacing(14)

        footer = QHBoxLayout()
        self.lbl_csprng = QLabel("● CSPRNG: verificando...")
        self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{TEXT_SEC};")
        footer.addWidget(self.lbl_csprng)
        btn_csprng = QPushButton("Iniciar CSPRNG")
        btn_csprng.setObjectName("btnGhost"); btn_csprng.setFixedHeight(32)
        btn_csprng.clicked.connect(self._try_start_csprng)
        footer.addWidget(btn_csprng)
        footer.addStretch()
        btn_export = QPushButton("Exportar Última")
        btn_export.setObjectName("btnGhost"); btn_export.setFixedHeight(32)
        btn_export.clicked.connect(self._export_last_session)
        footer.addWidget(btn_export)
        self.btn_iniciar = QPushButton("Iniciar Modo A  →")
        self.btn_iniciar.setObjectName("btnPrimary"); self.btn_iniciar.setFixedHeight(38)
        self.btn_iniciar.clicked.connect(lambda: on_modo("A"))
        footer.addWidget(self.btn_iniciar)
        main.addLayout(footer)

        self._load_initial_stats()
        QTimer.singleShot(400, self._checar_csprng)

    def _checar_csprng(self):
        """Verifica conexão real com o servidor CSPRNG via handshake completo."""
        conectado = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.8)
                s.connect(("127.0.0.1", 9999))
                s.sendall(struct.pack("I", 12345))
                data = s.recv(4)
                if len(data) == 4:
                    seed = struct.unpack("I", data)[0]
                    # Seed válida: qualquer valor não-zero é aceito
                    conectado = True
        except Exception:
            pass
        if conectado:
            self.lbl_csprng.setText("● CSPRNG: conectado  |  porta 9999")
            self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{SUCCESS};")
        else:
            self.lbl_csprng.setText("● CSPRNG: offline  —  inicie o csprng_server_v2.py")
            self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{WARNING};")

    def _try_start_csprng(self):
        try:
            with socket.socket() as s:
                s.settimeout(0.5); s.connect(("127.0.0.1", 9999))
                self.lbl_csprng.setText("● CSPRNG: já conectado  |  porta 9999")
                self.lbl_csprng.setStyleSheet(f"font-size:11px; color:{SUCCESS};")
                return
        except Exception:
            pass
        try:
            script = Path(__file__).parent / "csprng_server_v2.py"
            proc = subprocess.Popen(
                [sys.executable, str(script)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self._csprng_proc = proc
            try:
                self.window()._csprng_proc = proc
            except Exception:
                pass
            QTimer.singleShot(800, self._checar_csprng)
        except Exception as e:
            QMessageBox.warning(self, "CSPRNG", f"Falha ao iniciar CSPRNG:\n{e}")

    def _show_placeholder(self, modo):
        QMessageBox.information(
            self, f"Modo {modo['letra']}",
            f"{modo['nome']}\n\n{modo['desc']}\n\nStatus: em breve.",
        )

    def _export_last_session(self):
        sessoes = listar_sessoes(1)
        if not sessoes:
            QMessageBox.information(self, "Exportar", "Nenhuma sessão registrada.")
            return
        path = Path.cwd() / "trac_ultima_sessao.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=sessoes[0].keys())
            writer.writeheader(); writer.writerows(sessoes)
        QMessageBox.information(self, "Exportar", f"Exportado para:\n{path}")

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
        trcs = [s["trc_minimo"] for s in sessoes if s.get("trc_minimo")]
        if trcs:
            self.m_trc.set_valor(f"{min(trcs):.0f}ms")
        precs = [s["precisao"] for s in sessoes if s.get("precisao") is not None]
        if precs:
            avg = sum(precs) / len(precs)
            cor = SUCCESS if avg >= 90 else (WARNING if avg >= 70 else DANGER)
            self.m_precisao.set_valor(f"{avg:.0f}%", cor)
        if sessoes:
            u = sessoes[0]
            self.lbl_ultima.setText(
                f"Última sessão: Modo {u.get('modo','?')} — {u.get('tentativas',0)} tentativas"
            )


class HistoricoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24); lay.setSpacing(0)

        h = QHBoxLayout()
        titulo = QLabel("Histórico de Sessões")
        titulo.setStyleSheet(f"font-size:22px; font-weight:700; color:{TEXT_PRI};")
        h.addWidget(titulo); h.addStretch()
        btn_at = QPushButton("Atualizar")
        btn_at.setObjectName("btnGhost"); btn_at.setFixedHeight(36)
        btn_at.clicked.connect(self.carregar)
        h.addWidget(btn_at); h.addSpacing(8)
        self.btn_exportar = QPushButton("Exportar CSV")
        self.btn_exportar.setObjectName("btnPrimary"); self.btn_exportar.setFixedHeight(36)
        self.btn_exportar.clicked.connect(self._exportar)
        h.addWidget(self.btn_exportar)
        lay.addLayout(h); lay.addSpacing(8)

        self.lbl_resumo = QLabel("—")
        self.lbl_resumo.setStyleSheet(f"font-size:12px; color:{TEXT_SEC};")
        lay.addWidget(self.lbl_resumo); lay.addSpacing(16)
        lay.addWidget(divider()); lay.addSpacing(16)

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
            for j, v in enumerate([
                dt,
                f"Modo {s['modo']}",
                str(s["tentativas"] or 0),
                str(s["acertos"] or 0),
                f"{s['precisao']:.0f}%" if s["precisao"] is not None else "—",
                f"{s['trc_medio']:.0f}ms" if s["trc_medio"] is not None else "—",
                f"{s['trc_minimo']:.0f}ms" if s["trc_minimo"] is not None else "—",
            ]):
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
            self, "Exportar histórico", "trac_historico.csv", "CSV (*.csv)"
        )
        if path:
            n = exportar_csv(path)
            QMessageBox.information(self, "Exportação concluída",
                                    f"{n} sessões exportadas para:\n{path}")


class ConfigWidget(QWidget):
    config_changed = None

    def __init__(self, config_inicial: dict, parent=None):
        super().__init__(parent)
        saved_a      = config_inicial.get("modo_a", {})
        self._cfg_b  = {**DEFAULT_CONFIG_B, **config_inicial.get("modo_b", {})}
        self._cfg_c  = {**DEFAULT_CONFIG_C, **config_inicial.get("modo_c", {})}

        def _a_inputs():
            return saved_a.get("inputs", DEFAULT_CONFIG.get("inputs", []))
        def _a_gp(key, default):
            return saved_a.get("gameplay", {}).get(
                key, DEFAULT_CONFIG.get("gameplay", {}).get(key, default))
        def _a_tm(key, default):
            return saved_a.get("timing", {}).get(
                key, DEFAULT_CONFIG.get("timing", {}).get(key, default))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 28, 32, 32); lay.setSpacing(24)

        titulo = QLabel("Configurações")
        titulo.setStyleSheet(f"font-size:22px; font-weight:700; color:{TEXT_PRI};")
        lay.addWidget(titulo)
        lay.addWidget(divider()); lay.addSpacing(8)

        # ── Modo A ────────────────────────────────────────────────────────────
        lay.addWidget(section_label("MODO A — Escolha Simbólica"))
        sec_a = QFrame(); sec_a.setObjectName("configSection")
        sa = QVBoxLayout(sec_a); sa.setContentsMargins(20, 18, 20, 18); sa.setSpacing(14)

        teclas_atuais = [i["code"] for i in _a_inputs() if i.get("type") == "keyboard"]
        sa.addWidget(self._lbl("Teclas mapeadas (separadas por vírgula):"))
        self.inp_teclas = QLineEdit(", ".join(teclas_atuais))
        self.inp_teclas.setPlaceholderText("Ex: W, A, S, D")
        self.inp_teclas.textChanged.connect(self._on_change)
        sa.addWidget(self.inp_teclas)

        mouse_atuais = [i["code"] for i in _a_inputs() if i.get("type") == "mouse"]
        sa.addWidget(self._lbl("Botões do mouse:"))
        mr = QHBoxLayout(); mr.setSpacing(16)
        self.chk_mouse = {}
        for btn in ["LEFT", "RIGHT", "MIDDLE"]:
            chk = QCheckBox(btn.capitalize())
            chk.setChecked(btn in mouse_atuais)
            chk.stateChanged.connect(self._on_change)
            self.chk_mouse[btn] = chk; mr.addWidget(chk)
        mr.addStretch(); sa.addLayout(mr)

        r1 = QHBoxLayout(); r1.setSpacing(12)
        r1.addWidget(self._lbl("Estímulos simultâneos:"))
        self.spin_est = QSpinBox()
        self.spin_est.setRange(1, 8); self.spin_est.setFixedWidth(70)
        self.spin_est.setValue(_a_gp("estimulos_simultaneos", 1))
        self.spin_est.valueChanged.connect(self._on_change)
        r1.addWidget(self.spin_est); r1.addStretch(); sa.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(12)
        r2.addWidget(self._lbl("Modo de resposta:"))
        self.cmb_resp = QComboBox()
        self.cmb_resp.addItems(["qualquer", "todos", "sequencia"])
        modo_atual = _a_gp("modo_resposta", "qualquer")
        if modo_atual == "simples": modo_atual = "qualquer"
        self.cmb_resp.setCurrentText(modo_atual)
        self.cmb_resp.currentTextChanged.connect(self._on_change)
        r2.addWidget(self.cmb_resp); r2.addStretch(); sa.addLayout(r2)

        r3 = QHBoxLayout(); r3.setSpacing(12)
        r3.addWidget(self._lbl("Meta de TRC (ms):"))
        self.spin_trc = QSpinBox()
        self.spin_trc.setRange(50, 2000); self.spin_trc.setFixedWidth(90)
        self.spin_trc.setValue(_a_gp("limite_trc_ms", 300))
        self.spin_trc.setSuffix(" ms")
        self.spin_trc.valueChanged.connect(self._on_change)
        r3.addWidget(self.spin_trc); r3.addStretch(); sa.addLayout(r3)

        r4 = QHBoxLayout(); r4.setSpacing(12)
        r4.addWidget(self._lbl("Lifespan do estímulo (0 = sem limite):"))
        self.spin_lifespan_a = QSpinBox()
        self.spin_lifespan_a.setRange(0, 5000); self.spin_lifespan_a.setFixedWidth(90)
        self.spin_lifespan_a.setValue(_a_gp("stimulus_lifespan_ms", 0))
        self.spin_lifespan_a.setSuffix(" ms")
        self.spin_lifespan_a.setSpecialValueText("Desabilitado")
        self.spin_lifespan_a.valueChanged.connect(self._on_change)
        r4.addWidget(self.spin_lifespan_a); r4.addStretch(); sa.addLayout(r4)

        rw = QHBoxLayout(); rw.setSpacing(8)
        rw.addWidget(self._lbl("Espera antes do estímulo:"))
        self.spin_wait_min = QSpinBox()
        self.spin_wait_min.setRange(0, 5000); self.spin_wait_min.setFixedWidth(90)
        self.spin_wait_min.setValue(int(_a_tm("wait_min_s", 0.5) * 1000))
        self.spin_wait_min.setSuffix(" ms")
        self.spin_wait_min.setSpecialValueText("0 (imediato)")
        self.spin_wait_min.valueChanged.connect(self._on_change)
        rw.addWidget(self.spin_wait_min)
        rw.addWidget(QLabel("até"))
        self.spin_wait_max = QSpinBox()
        self.spin_wait_max.setRange(0, 10000); self.spin_wait_max.setFixedWidth(90)
        self.spin_wait_max.setValue(int(_a_tm("wait_max_s", 2.0) * 1000))
        self.spin_wait_max.setSuffix(" ms")
        self.spin_wait_max.valueChanged.connect(self._on_change)
        rw.addWidget(self.spin_wait_max); rw.addStretch(); sa.addLayout(rw)

        rp = QHBoxLayout(); rp.setSpacing(12)
        rp.addWidget(self._lbl("Penalidade por erro (ms):"))
        self.spin_pen_a = QSpinBox()
        self.spin_pen_a.setRange(0, 5000); self.spin_pen_a.setFixedWidth(90)
        self.spin_pen_a.setValue(_a_gp("penalidade_ms", 1000))
        self.spin_pen_a.setSuffix(" ms")
        self.spin_pen_a.valueChanged.connect(self._on_change)
        rp.addWidget(self.spin_pen_a); rp.addStretch(); sa.addLayout(rp)

        lay.addWidget(sec_a)

        # ── Modo B ────────────────────────────────────────────────────────────
        lay.addWidget(section_label("MODO B — Inibição Antecipatória"))
        sec_b = QFrame(); sec_b.setObjectName("configSection")
        sb = QVBoxLayout(sec_b); sb.setContentsMargins(20, 18, 20, 18); sb.setSpacing(14)

        sb.addWidget(self._lbl("Teclas mapeadas (separadas por vírgula):"))
        self.inp_teclas_b = QLineEdit(", ".join(self._cfg_b.get("teclas", [])))
        self.inp_teclas_b.setPlaceholderText("Ex: SPACE")
        self.inp_teclas_b.textChanged.connect(self._on_change)
        sb.addWidget(self.inp_teclas_b)

        sb.addWidget(self._lbl("Botões do mouse:"))
        mrb = QHBoxLayout(); mrb.setSpacing(16)
        self.chk_mouse_b = {}
        for btn in ["LEFT", "RIGHT", "MIDDLE"]:
            chk = QCheckBox(btn.capitalize())
            chk.setChecked(btn in self._cfg_b.get("mouse_botoes", []))
            chk.stateChanged.connect(self._on_change)
            self.chk_mouse_b[btn] = chk; mrb.addWidget(chk)
        mrb.addStretch(); sb.addLayout(mrb)

        rb1 = QHBoxLayout(); rb1.setSpacing(12)
        rb1.addWidget(self._lbl("Proporção de NO-GO:"))
        self.spin_nogo = QSpinBox()
        self.spin_nogo.setRange(10, 90); self.spin_nogo.setFixedWidth(70)
        self.spin_nogo.setValue(int(self._cfg_b.get("nogo_ratio", 0.30) * 100))
        self.spin_nogo.setSuffix(" %")
        self.spin_nogo.valueChanged.connect(self._on_change)
        rb1.addWidget(self.spin_nogo); rb1.addStretch(); sb.addLayout(rb1)

        rb2 = QHBoxLayout(); rb2.setSpacing(8)
        rb2.addWidget(self._lbl("Duração do alerta:"))
        self.spin_alert_min_b = QSpinBox()
        self.spin_alert_min_b.setRange(100, 3000); self.spin_alert_min_b.setFixedWidth(90)
        self.spin_alert_min_b.setValue(self._cfg_b.get("alert_min_ms", 500))
        self.spin_alert_min_b.setSuffix(" ms")
        self.spin_alert_min_b.valueChanged.connect(self._on_change)
        rb2.addWidget(self.spin_alert_min_b)
        rb2.addWidget(QLabel("até"))
        self.spin_alert_max_b = QSpinBox()
        self.spin_alert_max_b.setRange(200, 5000); self.spin_alert_max_b.setFixedWidth(90)
        self.spin_alert_max_b.setValue(self._cfg_b.get("alert_max_ms", 1500))
        self.spin_alert_max_b.setSuffix(" ms")
        self.spin_alert_max_b.valueChanged.connect(self._on_change)
        rb2.addWidget(self.spin_alert_max_b); rb2.addStretch(); sb.addLayout(rb2)

        rb3 = QHBoxLayout(); rb3.setSpacing(12)
        rb3.addWidget(self._lbl("Penalidade por false start:"))
        self.cmb_penalty = QComboBox()
        self.cmb_penalty.addItems(["RESET", "MISS", "BLOCK"])
        self.cmb_penalty.setCurrentText(self._cfg_b.get("false_start_penalty", "RESET"))
        self.cmb_penalty.currentTextChanged.connect(self._on_change)
        rb3.addWidget(self.cmb_penalty); rb3.addStretch(); sb.addLayout(rb3)

        lay.addWidget(sec_b)

        # ── Modo C ────────────────────────────────────────────────────────────
        lay.addWidget(section_label("MODO C — Periférico Espacial"))
        sec_c = QFrame(); sec_c.setObjectName("configSection")
        sc = QVBoxLayout(sec_c); sc.setContentsMargins(20, 18, 20, 18); sc.setSpacing(14)

        sc.addWidget(self._lbl("Teclas de resposta (separadas por vírgula):"))
        self.inp_teclas_c = QLineEdit(", ".join(self._cfg_c.get("teclas", [])))
        self.inp_teclas_c.setPlaceholderText("Ex: SPACE")
        self.inp_teclas_c.textChanged.connect(self._on_change)
        sc.addWidget(self.inp_teclas_c)

        sc.addWidget(self._lbl("Botões do mouse:"))
        mrc = QHBoxLayout(); mrc.setSpacing(16)
        self.chk_mouse_c = {}
        for btn in ["LEFT", "RIGHT", "MIDDLE"]:
            chk = QCheckBox(btn.capitalize())
            chk.setChecked(btn in self._cfg_c.get("mouse_botoes", []))
            chk.stateChanged.connect(self._on_change)
            self.chk_mouse_c[btn] = chk; mrc.addWidget(chk)
        mrc.addStretch(); sc.addLayout(mrc)

        rc1 = QHBoxLayout(); rc1.setSpacing(12)
        rc1.addWidget(self._lbl("Área de jogo (%):"))
        self.cmb_grid = QComboBox()
        self.cmb_grid.addItems(["50%", "80%", "100%"])
        self.cmb_grid.setCurrentText(f"{int(self._cfg_c.get('grid_size', 1.0) * 100)}%")
        self.cmb_grid.currentTextChanged.connect(self._on_change)
        rc1.addWidget(self.cmb_grid); rc1.addStretch(); sc.addLayout(rc1)

        self.chk_periph = QCheckBox("Modo periférico (excluir zona foveal central)")
        self.chk_periph.setChecked(self._cfg_c.get("peripheral_only", True))
        self.chk_periph.stateChanged.connect(self._on_change)
        sc.addWidget(self.chk_periph)

        self.chk_fixation = QCheckBox("Exibir cruz de fixação central")
        self.chk_fixation.setChecked(self._cfg_c.get("fixation_cross", True))
        self.chk_fixation.stateChanged.connect(self._on_change)
        sc.addWidget(self.chk_fixation)

        rc2 = QHBoxLayout(); rc2.setSpacing(12)
        rc2.addWidget(self._lbl("Tamanho do estímulo (px):"))
        self.spin_stim_size = QSpinBox()
        self.spin_stim_size.setRange(8, 120); self.spin_stim_size.setFixedWidth(80)
        self.spin_stim_size.setValue(self._cfg_c.get("stimulus_size", 32))
        self.spin_stim_size.setSuffix(" px")
        self.spin_stim_size.valueChanged.connect(self._on_change)
        rc2.addWidget(self.spin_stim_size); rc2.addStretch(); sc.addLayout(rc2)

        rc3 = QHBoxLayout(); rc3.setSpacing(12)
        rc3.addWidget(self._lbl("Tempo máximo para reagir:"))
        self.spin_lifespan_c = QSpinBox()
        self.spin_lifespan_c.setRange(200, 3000); self.spin_lifespan_c.setFixedWidth(90)
        self.spin_lifespan_c.setValue(self._cfg_c.get("stimulus_lifespan_ms", 800))
        self.spin_lifespan_c.setSuffix(" ms")
        self.spin_lifespan_c.valueChanged.connect(self._on_change)
        rc3.addWidget(self.spin_lifespan_c); rc3.addStretch(); sc.addLayout(rc3)

        lay.addWidget(sec_c)

        # ── Placeholders ──────────────────────────────────────────────────────
        for letra, nome in [
            ("D","Carga Cognitiva"), ("E","Oclusão Estroboscópica"),
            ("F","Ghost Mode"), ("G","Resiliência Pós-Erro"), ("H","Bio-Feedback de Fadiga"),
        ]:
            lay.addWidget(section_label(f"MODO {letra} — {nome}"))
            sec = QFrame(); sec.setObjectName("configSectionDisabled")
            sl = QVBoxLayout(sec); sl.setContentsMargins(20, 16, 20, 16)
            lbl = QLabel("Configurações disponíveis após implementação do modo.")
            lbl.setStyleSheet(f"font-size:12px; color:{TEXT_DIM}; font-style:italic;")
            sl.addWidget(lbl); lay.addWidget(sec)

        # ── Geral ─────────────────────────────────────────────────────────────
        lay.addWidget(section_label("GERAL"))
        sec_g = QFrame(); sec_g.setObjectName("configSection")
        sg = QVBoxLayout(sec_g); sg.setContentsMargins(20, 18, 20, 18); sg.setSpacing(14)
        sg.addWidget(self._lbl("Porta do servidor CSPRNG:"))
        rg = QHBoxLayout(); rg.setSpacing(8)
        self.inp_porta = QLineEdit("9999")
        self.inp_porta.setFixedWidth(90)
        self.inp_porta.setValidator(QIntValidator(1024, 65535))
        rg.addWidget(self.inp_porta); rg.addStretch(); sg.addLayout(rg)
        lay.addWidget(sec_g)
        lay.addStretch()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        scroll.setWidget(inner)

    def _lbl(self, texto):
        l = QLabel(texto)
        l.setStyleSheet(f"font-size:13px; color:{TEXT_SEC};")
        return l

    def _on_change(self):
        teclas = [t.strip().upper() for t in self.inp_teclas.text().split(",") if t.strip()]
        mouse  = [b for b, chk in self.chk_mouse.items() if chk.isChecked()]
        inputs = (
            [{"id": f"KEY_{t}", "type": "keyboard", "code": t, "label": t} for t in teclas] +
            [{"id": f"MOUSE_{b}", "type": "mouse", "code": b, "label": f"🖱{b}"} for b in mouse]
        )
        cfg_a = {
            "inputs": inputs,
            "gameplay": {
                "estimulos_simultaneos": self.spin_est.value(),
                "modo_resposta":         self.cmb_resp.currentText(),
                "limite_trc_ms":         self.spin_trc.value(),
                "stimulus_lifespan_ms":  self.spin_lifespan_a.value(),
                "penalidade_ms":         self.spin_pen_a.value(),
            },
            "timing": {
                "wait_min_s":        self.spin_wait_min.value() / 1000,
                "wait_max_s":        self.spin_wait_max.value() / 1000,
                "feedback_delay_ms": 900,
            },
        }
        cfg_b = {
            "teclas":              [t.strip().upper() for t in self.inp_teclas_b.text().split(",") if t.strip()],
            "mouse_botoes":        [b for b, chk in self.chk_mouse_b.items() if chk.isChecked()],
            "nogo_ratio":          self.spin_nogo.value() / 100.0,
            "alert_min_ms":        self.spin_alert_min_b.value(),
            "alert_max_ms":        self.spin_alert_max_b.value(),
            "false_start_penalty": self.cmb_penalty.currentText(),
        }
        cfg_c = {
            "teclas":               [t.strip().upper() for t in self.inp_teclas_c.text().split(",") if t.strip()],
            "mouse_botoes":         [b for b, chk in self.chk_mouse_c.items() if chk.isChecked()],
            "grid_size":            int(self.cmb_grid.currentText().replace("%", "")) / 100,
            "peripheral_only":      self.chk_periph.isChecked(),
            "fixation_cross":       self.chk_fixation.isChecked(),
            "stimulus_size":        self.spin_stim_size.value(),
            "stimulus_lifespan_ms": self.spin_lifespan_c.value(),
        }
        if callable(self.config_changed):
            self.config_changed({"modo_a": cfg_a, "modo_b": cfg_b, "modo_c": cfg_c})


class Sidebar(QWidget):
    def __init__(self, on_nav, on_toggle_fullscreen=None,
                 on_stop_csprng=None, on_quit=None, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet(
            f"background-color:{BG_SURFACE}; border-right:1px solid {BORDER};"
        )
        self._btns: dict[str, QPushButton] = {}
        self._on_nav = on_nav

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

        for key, label in [("home","  Início"),("historico","  Histórico"),("config","  Configurações")]:
            btn = QPushButton(label)
            btn.setFixedHeight(38); btn.setObjectName("btnGhost")
            btn.clicked.connect((lambda k: lambda: self._nav(k))(key))
            self._btns[key] = btn
            lay.addWidget(btn); lay.addSpacing(4)

        lay.addStretch()
        versao = QLabel("v2.0 — Engine Python\nCSPRNG: Hash de Caos")
        versao.setStyleSheet(f"font-size:10px; color:{TEXT_DIM}; line-height:1.6;")
        lay.addWidget(versao); lay.addSpacing(8)

        af = QFrame()
        afl = QVBoxLayout(af)
        afl.setContentsMargins(4, 6, 4, 6); afl.setSpacing(8)
        for label, cb, obj in [
            ("Tela Cheia",    on_toggle_fullscreen, "btnGhost"),
            ("Parar CSPRNG",  on_stop_csprng,       "btnGhost"),
            ("Sair",          on_quit,               "btnDanger"),
        ]:
            if cb:
                btn = QPushButton(label)
                btn.setObjectName(obj); btn.setFixedHeight(40)
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                btn.clicked.connect(cb)
                afl.addWidget(btn)
        lay.addWidget(af)
        self.set_ativo("home")

    def _nav(self, key):
        self.set_ativo(key); self._on_nav(key)

    def set_ativo(self, key):
        for k, btn in self._btns.items():
            if k == key:
                btn.setStyleSheet(
                    f"background-color:{ACCENT_DIM}; color:{ACCENT};"
                    f"border:1px solid {ACCENT}; border-radius:8px;"
                    f"padding:10px 20px; font-size:13px; font-weight:600; text-align:left;"
                )
            else:
                btn.setStyleSheet(
                    f"background-color:transparent; color:{TEXT_SEC};"
                    f"border:1px solid {BORDER}; border-radius:8px;"
                    f"padding:10px 20px; font-size:13px; text-align:left;"
                )


class TRACApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TRAC")
        self.setFixedSize(860, 640)
        self.setStyleSheet(STYLESHEET)
        self._csprng_proc = None

        init_db()
        cfg_saved        = load_config()
        self._cfg_modo_a = cfg_saved.get("modo_a", {})
        self._cfg_modo_b = {**DEFAULT_CONFIG_B, **cfg_saved.get("modo_b", {})}
        self._cfg_modo_c = {**DEFAULT_CONFIG_C, **cfg_saved.get("modo_c", {})}

        root = QWidget()
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0); main.setSpacing(0)

        self.sidebar = Sidebar(
            on_nav=self._nav,
            on_toggle_fullscreen=self._toggle_fullscreen,
            on_stop_csprng=self._stop_csprng,
            on_quit=self._quit_app,
        )
        main.addWidget(self.sidebar)

        self.area = QStackedWidget()
        main.addWidget(self.area)

        self.home      = HomeWidget(on_modo=self._ir_para_modo)
        self.historico = HistoricoWidget()
        self.config_w  = ConfigWidget({
            "modo_a": self._cfg_modo_a,
            "modo_b": self._cfg_modo_b,
            "modo_c": self._cfg_modo_c,
        })
        self.config_w.config_changed = self._on_config_changed

        self.area.addWidget(self.home)
        self.area.addWidget(self.historico)
        self.area.addWidget(self.config_w)

        self._modo_a_widget = None
        self._modo_b_widget = None
        self._modo_c_widget = None
        self.area.setCurrentWidget(self.home)

    def _nav(self, key: str):
        mapping = {"home": self.home, "historico": self.historico, "config": self.config_w}
        if key in mapping:
            if key == "historico":
                self.historico.carregar()
            self.area.setCurrentWidget(mapping[key])

    def _ir_para_modo(self, letra: str):
        if letra == "A":
            if self._modo_a_widget:
                self.area.removeWidget(self._modo_a_widget)
                self._modo_a_widget.deleteLater()
            self._modo_a_widget = ModoAGUI(config=self._cfg_modo_a)
            self._modo_a_widget.finished.connect(self._sessao_encerrada)
            self.area.addWidget(self._modo_a_widget)
            self.area.setCurrentWidget(self._modo_a_widget)
            self._modo_a_widget.setFocus()
            self.sidebar.set_ativo("")

        elif letra == "B":
            if self._modo_b_widget:
                self.area.removeWidget(self._modo_b_widget)
                self._modo_b_widget.deleteLater()
            self._modo_b_widget = ModoBGUI(config=self._cfg_modo_b)
            self._modo_b_widget.finished.connect(self._sessao_encerrada)
            self.area.addWidget(self._modo_b_widget)
            self.area.setCurrentWidget(self._modo_b_widget)
            self._modo_b_widget.setFocus()
            self.sidebar.set_ativo("")

        elif letra == "C":
            if self._modo_c_widget:
                self.area.removeWidget(self._modo_c_widget)
                self._modo_c_widget.deleteLater()
            self._modo_c_widget = ModoCGUI(config=self._cfg_modo_c)
            self._modo_c_widget.finished.connect(self._sessao_encerrada)
            self.area.addWidget(self._modo_c_widget)
            self.area.setCurrentWidget(self._modo_c_widget)
            self._modo_c_widget.setFocus()
            self.sidebar.set_ativo("")

    def _sessao_encerrada(self, resumo: dict):
        salvar_sessao(resumo)
        self.home.atualizar_metricas(resumo)
        self.area.setCurrentWidget(self.home)
        self.sidebar.set_ativo("home")

    def _on_config_changed(self, cfg: dict):
        self._cfg_modo_a = cfg.get("modo_a", self._cfg_modo_a)
        self._cfg_modo_b = cfg.get("modo_b", self._cfg_modo_b)
        self._cfg_modo_c = cfg.get("modo_c", self._cfg_modo_c)
        save_config({"modo_a": self._cfg_modo_a,
                     "modo_b": self._cfg_modo_b,
                     "modo_c": self._cfg_modo_c})
        if self._modo_a_widget:
            try:
                self._modo_a_widget.aplicar_config(self._cfg_modo_a)
            except Exception:
                pass

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _stop_csprng(self):
        for proc_attr in (self, self.home):
            proc = getattr(proc_attr, "_csprng_proc", None)
            if proc:
                try:
                    proc.terminate(); proc.wait(timeout=2)
                except Exception:
                    try: proc.kill()
                    except Exception: pass
                proc_attr._csprng_proc = None
        try:
            self.home.lbl_csprng.setText("● CSPRNG: offline")
            self.home.lbl_csprng.setStyleSheet(f"font-size:11px; color:{WARNING};")
        except Exception:
            pass

    def _quit_app(self):
        try: self._stop_csprng()
        except Exception: pass
        QApplication.quit()


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
