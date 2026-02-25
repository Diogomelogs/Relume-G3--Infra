from datetime import datetime


def artefact_blob_path(artefact_id: str) -> str:
    """
    Caminho lógico canônico do artefato.
    Exemplo:
      artefacts/2026/01/artefact_id.bin
    """
    now = datetime.utcnow()
    return f"artefacts/{now.year}/{now.month:02d}/{artefact_id}"
