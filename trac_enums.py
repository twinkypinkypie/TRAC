"""
TRAC — Enums compartilhados
Define estados dos modos de treinamento.
"""

from enum import Enum


class EstadoModoA(Enum):
    """Estados do Modo A (Escolha Simbólica)."""
    IDLE = "idle"
    WAITING = "waiting"
    STIMULUS_SHOWN = "stimulus_shown"
    FEEDBACK = "feedback"


class EstadoModoB(Enum):
    """Estados do Modo B (Inibição Antecipatória)."""
    IDLE = "idle"
    WAITING = "waiting"
    ALERTING = "alerting"
    GO = "go"
    NOGO = "nogo"
    BLOCKED = "blocked"
