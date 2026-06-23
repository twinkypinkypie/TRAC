import socket
import struct
import time
import sys

def test_protocol():
    print("Iniciando teste de protocolo binário (CSPRNG - Hash de Caos)...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            s.connect(('127.0.0.1', 9999))
            
            # Testa com mouse_jitter = 12345
            jitter = 12345
            print(f"Enviando mouse_jitter: {jitter}")
            s.sendall(struct.pack("I", jitter))
            
            data = s.recv(4)
            if len(data) == 4:
                seed = struct.unpack("I", data)[0]
                print(f"Recebido seed: {seed} (0x{seed:08X})")
                print("Teste de protocolo CSPRNG: SUCESSO")
            else:
                print(f"Erro: Recebeu {len(data)} bytes em vez de 4")
    except Exception as e:
        print(f"Erro na conexão: {e}")

if __name__ == "__main__":
    test_protocol()
