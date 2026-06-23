"""
TRAC — Servidor CSPRNG v2
Fornece seeds pseudoaleatórias via Hash de Caos (não é TRNG real).

Protocolo: 
  - Cliente envia: 4 bytes (mouse_jitter)
  - Servidor responde: 4 bytes (seed de 32 bits)
"""

import os
import sys
import time
import struct
import secrets
import socket

def _entropia_os(num_bytes: int) -> bytes:
    """Usa /dev/urandom (nunca bloqueia) ou fallback para secrets."""
    try:
        # Tenta /dev/urandom primeiro (padrão Unix)
        if os.path.exists("/dev/urandom"):
            with open("/dev/urandom", "rb") as f:
                return f.read(num_bytes)
        else:
            return os.urandom(num_bytes)
    except Exception:
        return secrets.token_bytes(num_bytes)

def hash_de_caos(mouse_jitter: int = 0) -> int:
    """
    Combina múltiplas fontes de entropia em uma seed de 32 bits.
    
    Nota: Este é um CSPRNG (Cryptographically Secure Pseudo-Random),
    não um TRNG real. Usa algoritmo determinístico com entropia do OS.
    
    Args:
        mouse_jitter: valor enviado pelo engine Python (ex: movimento do cursor).
    
    Returns:
        Seed de 32 bits (int).
    """
    ts_ns     = time.time_ns()
    perf_ns   = time.perf_counter_ns()
    mono_ns   = time.monotonic_ns()
    mem_state = id(object())
    os_bytes  = _entropia_os(4)
    os_int    = int.from_bytes(os_bytes, "big")

    seed = ts_ns ^ perf_ns ^ mono_ns ^ mem_state ^ os_int ^ mouse_jitter
    return seed & 0xFFFFFFFF  # seed de 32 bits

# ── Servidor socket ───────────────────────────────────────────────────────
def iniciar_servidor(host="127.0.0.1", port=9999):
    """Inicia servidor CSPRNG na porta especificada."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        print(f"[TRAC CSPRNG] Aguardando conexões em {host}:{port}", file=sys.stderr)

        while True:
            conn, _ = s.accept()
            try:
                with conn:
                    # Protocolo: recebe 4 bytes de jitter, responde com 4 bytes de seed
                    data = conn.recv(4)
                    mouse_jitter = struct.unpack("I", data)[0] if len(data) == 4 else 0
                    seed = hash_de_caos(mouse_jitter)
                    conn.send(struct.pack("I", seed))
            except Exception as e:
                print(f"[ERRO] Falha na conexão: {e}", file=sys.stderr)

if __name__ == "__main__":
    iniciar_servidor()
