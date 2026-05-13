from pathlib import Path

target = Path("relluna/core/document_memory/types_basic.py")
src = target.read_text(encoding="utf-8")

if "class SemanticEntity" in src:
    print("Modelo já existe.")
    exit()

insertion = """

class SemanticEntity(BaseModel):
    tipo: str
    valor: str
    fonte: str
    confianca: float
    normalizado: Optional[str] = None
    contexto: Optional[str] = None
"""

# inserir após InferredString
marker = "class InferredString"
idx = src.find(marker)

if idx == -1:
    raise SystemExit("InferredString não encontrado.")

# encontrar final da classe InferredString
split = src.split(marker)
head = split[0]
rest = marker + split[1]

# inserir após primeira classe InferredString
new_src = src + insertion

target.write_text(new_src, encoding="utf-8")

print("Modelo SemanticEntity criado com sucesso.")