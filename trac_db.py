"""
TRAC — Banco de dados local (SQLite)
Gerencia histórico de sessões e tentativas.
"""

import sqlite3
import csv
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "trac_historico.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   INTEGER NOT NULL,
                modo        TEXT    NOT NULL,
                config_json TEXT,
                duracao_ms  INTEGER,
                tentativas  INTEGER,
                acertos     INTEGER,
                precisao    REAL,
                trc_medio   REAL,
                trc_minimo  REAL
            );
            CREATE TABLE IF NOT EXISTS attempts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      INTEGER REFERENCES sessions(id),
                numero          INTEGER,
                tecla_alvo      TEXT,
                tecla_input     TEXT,
                trc_ms          REAL,
                acerto          INTEGER,
                modo_resposta   TEXT
            );
        """)


def salvar_sessao(resumo: dict) -> int:
    """Salva sessão e tentativas. Retorna o id da sessão."""
    import json
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO sessions
               (timestamp, modo, config_json, duracao_ms, tentativas,
                acertos, precisao, trc_medio, trc_minimo)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                int(datetime.now().timestamp()),
                resumo.get("modo", "?"),
                json.dumps(resumo.get("config", {})),
                resumo.get("duracao_ms"),
                resumo.get("tentativas", 0),
                resumo.get("acertos", 0),
                resumo.get("precisao_pct"),
                resumo.get("trc_medio_ms"),
                resumo.get("trc_minimo_ms"),
            ),
        )
        session_id = cur.lastrowid
        for i, t in enumerate(resumo.get("detalhes", []), 1):
            con.execute(
                """INSERT INTO attempts
                   (session_id, numero, tecla_alvo, tecla_input,
                    trc_ms, acerto, modo_resposta)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    session_id, i,
                    t.get("tecla_alvo", ""),
                    t.get("tecla_pressionada", ""),
                    t.get("trc_ms"),
                    1 if t.get("acerto") else 0,
                    t.get("modo_resposta", "simples"),
                ),
            )
    return session_id


def listar_sessoes(limite: int = 100) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT * FROM sessions ORDER BY timestamp DESC LIMIT ?""",
            (limite,)
        ).fetchall()
    return [dict(r) for r in rows]


def exportar_csv(path: str) -> int:
    """Exporta todas as sessões para CSV. Retorna número de linhas."""
    sessoes = listar_sessoes(limite=10000)
    if not sessoes:
        return 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sessoes[0].keys())
        writer.writeheader()
        writer.writerows(sessoes)
    return len(sessoes)