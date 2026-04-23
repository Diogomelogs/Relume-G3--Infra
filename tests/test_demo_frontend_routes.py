import asyncio

from relluna.services.test_ui.router import demo_asset, demo_index


def test_demo_frontend_index_served():
    response = asyncio.run(demo_index())
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Relluna Demo" in body
    assert "./app.js" in body


def test_demo_frontend_asset_served():
    response = asyncio.run(demo_asset("data.js"))
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "timelineConsistencyScore" in body
    assert "birth_date_not_document_date" in body
