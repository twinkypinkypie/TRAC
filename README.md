# TRAC (Prototype)

Treinador de Reação Adaptativo e Contextual — protótipo em Python/PyQt6.

Requisitos:
- Python 3.8+
- PyQt6

Instalar dependências:

```bash
python -m pip install -r requirements.txt
```

Executar TRNG (recomendado em terminal separado):

```bash
python trng_server_v2.py
```

Executar interface:

```bash
python trac_shell_v3.py
```

Testar protocolo TRNG:

```bash
python validate_v2.py
```

Arquivos principais:
- `trac_shell_v3.py` — interface principal (Home / Histórico / Config)
- `trac_modo_a_gui.py` — implementação do Modo A
- `trng_server_v2.py` — servidor TRNG (porta 9999)
- `trac_db.py` — banco SQLite local

Notas:
- As configurações do Modo A são salvas em `trac_config.json` na mesma pasta.
- Modos B–E estão marcados como "em breve"; ao clicar mostram um placeholder.
