from pathlib import Path
import re

target = Path("relluna/services/context_inference/basic.py")

src = target.read_text(encoding="utf-8")

if "REGEX_ENTITIES_V020" in src:
    print("Regex já implementado.")
    exit()

insertion_block = '''
    # ===============================
    # REGEX_ENTITIES_V020
    # ===============================
    entidades = []

    def _add_entity(tipo, valor):
        entidades.append({
            "tipo": tipo,
            "valor": valor,
            "fonte": "regex",
            "confianca": 0.9,
        })

    # CPF
    for m in re.findall(r"\\b\\d{3}\\.\\d{3}\\.\\d{3}-\\d{2}\\b", text):
        _add_entity("cpf", m)

    # CNPJ
    for m in re.findall(r"\\b\\d{2}\\.\\d{3}\\.\\d{3}/\\d{4}-\\d{2}\\b", text):
        _add_entity("cnpj", m)

    # Valores monetários (R$ 1.234,56)
    for m in re.findall(r"R\\$\\s?\\d{1,3}(?:\\.\\d{3})*,\\d{2}", text):
        _add_entity("valor_monetario", m)

    # Datas explícitas dd/mm/yyyy
    for m in re.findall(r"\\b\\d{2}/\\d{2}/\\d{4}\\b", text):
        _add_entity("data_textual", m)

    if entidades:
        l3.entidades_semanticas = entidades
'''

# inserir antes de dm.layer3 = l3
pattern = re.compile(r"dm\.layer3\s*=\s*l3")

match = pattern.search(src)
if not match:
    raise SystemExit("Não encontrei ponto de inserção.")

new_src = src[:match.start()] + insertion_block + "\n    " + src[match.start():]

target.write_text(new_src, encoding="utf-8")

print("Regex transversal implementado com sucesso.")