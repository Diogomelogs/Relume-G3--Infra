import pytest

from relluna.services.read_model.store import ReadModelStore
from relluna.services.read_model.models import DocumentReadModel
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_search_returns_results_when_text_matches(mocker):
    store = ReadModelStore()

    # mock collection (não bater no mongo real no teste)
    fake_docs = [
        {"document_id": "doc-1", "search_text": "mãe viagem 2008", "updated_at": datetime.now(timezone.utc)},
    ]

    async def _aiter():
        for d in fake_docs:
            yield d

    mock_col = mocker.Mock()
    mock_cursor = mocker.Mock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = _aiter()
    mock_col.find.return_value = mock_cursor
    store.col = mock_col

    res = await store.search(q="viagem", limit=10)
    assert len(res) == 1
    assert res[0]["document_id"] == "doc-1"
