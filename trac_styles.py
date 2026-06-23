"""
TRAC — Estilos compartilhados e componentes reutilizáveis
Centraliza cores, templates de layout e componentes visuais.
"""

# ── Paleta de cores padrão ────────────────────────────────────────────────────
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
ALERT      = "#F5E642"   # amarelo para alertas


def create_top_bar_style(height: int = 52) -> str:
    """Estilo padrão para barra superior (header)."""
    return f"""
    QFrame {{
        background-color:#0D0D14;
        border-bottom:1px solid {BORDER};
        min-height:{height}px;
        max-height:{height}px;
    }}
    """


def create_bottom_bar_style(height: int = 52) -> str:
    """Estilo padrão para barra inferior (footer)."""
    return f"""
    QFrame {{
        background-color:#0D0D14;
        border-top:1px solid {BORDER};
        min-height:{height}px;
        max-height:{height}px;
    }}
    """


def create_button_style(btn_type: str = "primary") -> str:
    """Retorna estilo QSS para botão.
    
    Args:
        btn_type: "primary", "ghost", ou "danger"
    """
    if btn_type == "primary":
        return f"""
        background-color:{ACCENT};
        color:#fff;
        border:none;
        border-radius:8px;
        padding:10px 24px;
        font-size:13px;
        font-weight:600;
        """
    elif btn_type == "danger":
        return f"""
        background-color:transparent;
        color:{DANGER};
        border:1px solid {DANGER};
        border-radius:8px;
        padding:10px 20px;
        font-size:13px;
        """
    else:  # ghost
        return f"""
        background-color:transparent;
        color:{TEXT_SEC};
        border:1px solid {BORDER};
        border-radius:8px;
        padding:10px 20px;
        font-size:13px;
        """


def create_signal_indicator(state: str) -> tuple[str, str]:
    """Retorna (cor, símbolo) para indicador de sinal.
    
    Args:
        state: "idle", "alert", "go", "nogo", "blocked"
    
    Returns:
        Tupla (cor_fundo, símbolo)
    """
    states = {
        "idle":    (BG_CARD,    "○"),
        "alert":   ("#2A2200",   "●"),
        "go":      ("#0A1A30",   "●"),
        "nogo":    ("#2E0F0F",   "✗"),
        "blocked": ("#1A0808",   "⛔"),
    }
    return states.get(state, states["idle"])


def create_metric_label(label_text: str, value_text: str, color: str = ACCENT) -> str:
    """Gera QSS para etiqueta métrica (ex: TRC, Precisão)."""
    return f"""
    QLabel {{
        color:{color};
        font-size:20px;
        font-weight:700;
    }}
    QLabel#metricLabel {{
        font-size:11px;
        color:{TEXT_SEC};
        font-weight:500;
    }}
    """
