def test_ingest_creates_dm_and_blob(client, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello relluna")

    with open(test_file, "rb") as f:
        res = client.post(
            "/ingest",
            files={"file": ("test.txt", f, "text/plain")},
            data={
                "media_type": "documento",
                "origin": "digital_nativo",
            },
        )

    assert res.status_code == 200
    data = res.json()

    assert "documentid" in data
    assert data["blob_uri"] == data["artifact_uri"]
    assert data["blob_uri"] == data["local_file_uri"]
    assert data["storage_kind"] == "local_file"
    assert data["storage_state"] == "local_file_persisted"
    assert data["is_remote_blob"] is False
    assert "/.uploads/" in data["local_file_uri"]
