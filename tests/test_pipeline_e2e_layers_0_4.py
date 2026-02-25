import io

from fastapi.testclient import TestClient

from relluna.services.ingestion.api import app
from relluna.core.document_memory import DocumentMemory, ConfidenceState


def test_pipeline_layers_0_4_via_api_for_image():
    fake_image = io.BytesIO(b"\xFF\xD8\xFF\xE0" + b"0" * 4096)
    fake_image.name = "teste_exif.jpg"

    with TestClient(app) as client:
        resp_ingest = client.post(
            "/ingest",
            files={"file": ("teste_exif.jpg", fake_image, "image/jpeg")},
        )
        assert resp_ingest.status_code == 200
        documentid = resp_ingest.json()["documentid"]

        resp_extract = client.post(f"/extract/{documentid}")
        assert resp_extract.status_code == 200

        # inferência é o que pode criar layer3 no Modelo A
        resp_infer = client.post(f"/infer_context/{documentid}")
        assert resp_infer.status_code == 200

        resp_dm = client.get(f"/documents/{documentid}")
        assert resp_dm.status_code == 200
        dm = DocumentMemory.model_validate(resp_dm.json())

    # Layer2 pelo menos parcialmente preenchida
    assert dm.layer2 is not None
    assert dm.layer2.largura_px is not None
    assert dm.layer2.largura_px.estado in {
        ConfidenceState.confirmado,
        ConfidenceState.insuficiente,
    }

    # Modelo A: layer3 só existe se houver evidência (dimensões já contam como evidência real)
    # Portanto, após /infer_context, para imagem com largura/altura, layer3 deve existir.
    assert dm.layer3 is not None
    assert dm.layer3.tipo_evento is not None
    assert dm.layer3.tipo_evento.valor == "imagem"