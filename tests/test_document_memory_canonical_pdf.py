from relluna.core.document_memory import DocumentMemory_v0_2_0


def test_minimal_pdf_like_payload_v020_is_canonical():
    dm = DocumentMemory_v0_2_0.model_validate(
        {
            "version": "v0.2.0",
            "layer0": {
                "documentid": "pdf-v020",
                "contentfingerprint": "4" * 64,
                "ingestionagent": "pytest",
                "mimetype": "application/pdf",
            },
            "layer1": {
                "midia": "documento",
                "origem": "digital_nativo",
                "artefatos": [
                    {
                        "id": "artifact-1",
                        "tipo": "original",
                        "uri": "memory://pdf-v020.pdf",
                        "hash_sha256": "4" * 64,
                    }
                ],
            },
            "layer2": {"num_paginas": {"valor": 1, "fonte": "pytest", "metodo": "fixture"}},
        }
    )

    assert dm.version == "v0.2.0"
    assert dm.layer0.documentid == "pdf-v020"
    assert dm.layer1.midia == "documento"
    assert dm.layer2.num_paginas.valor == 1
