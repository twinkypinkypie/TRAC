"""
TRAC — Cliente TRNG compartilhado (Hash de Caos)
Centraliza a geração de seeds aleatórias e conversão para valores float/int/bool.
"""

import socket
import struct
import time


class TRNGClient:
    """Cliente para comunicação com servidor TRNG (porta 9999).
    
    Fornece métodos estáticos para gerar seeds pseudoaleatórias baseadas em
    entropia de hardware (Hash de Caos) e conversão para tipos.
    Fallback: se TRNG offline, usa time.perf_counter_ns().
    """

    @staticmethod
    def get_seed(jitter: int = 0) -> int:
        """Obtém uma seed de 32 bits do servidor TRNG.
        
        Args:
            jitter: valor opcional enviado ao servidor (ex: mouse drift).
        
        Returns:
            seed de 32 bits (int).
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(("127.0.0.1", 9999))
                s.sendall(struct.pack("I", jitter))
                data = s.recv(4)
                if len(data) == 4:
                    return struct.unpack("I", data)[0]
        except (OSError, struct.error):
            pass
        # Fallback: usa timing do sistema
        return int(time.perf_counter_ns() & 0xFFFFFFFF)

    @staticmethod
    def to_float(seed: int, lo: float, hi: float) -> float:
        """Converte seed para float no intervalo [lo, hi].
        
        Args:
            seed: seed de 32 bits.
            lo: limite inferior.
            hi: limite superior.
        
        Returns:
            float no intervalo [lo, hi].
        """
        return lo + (seed / 0xFFFFFFFF) * (hi - lo)

    @staticmethod
    def to_int(seed: int, lo: int, hi: int) -> int:
        """Converte seed para int no intervalo [lo, hi].
        
        Args:
            seed: seed de 32 bits.
            lo: limite inferior (inclusivo).
            hi: limite superior (inclusivo).
        
        Returns:
            int no intervalo [lo, hi].
        """
        return lo + (seed % (hi - lo + 1))

    @staticmethod
    def to_bool(seed: int, prob_true: float) -> bool:
        """Converte seed para booleano com probabilidade configurável.
        
        Args:
            seed: seed de 32 bits.
            prob_true: probabilidade de retornar True (0.0 a 1.0).
        
        Returns:
            bool.
        """
        return (seed / 0xFFFFFFFF) < prob_true
