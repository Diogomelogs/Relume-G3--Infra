# tools/generate_schema_v0_2_0.py

from relluna.core.document_memory import DocumentMemory
import json

schema = DocumentMemory.model_json_schema()

with open("relluna/core/document_memory.schema.v0.2.0.json", "w", encoding="utf-8") as f:
    json.dump(schema, f, indent=2, ensure_ascii=False)

print("Schema v0.2.0 gerado com sucesso.")