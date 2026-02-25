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
    assert data["blob_uri"].startswith("https://")
