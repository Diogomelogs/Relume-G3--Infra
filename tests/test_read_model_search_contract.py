import pytest

from relluna.services.read_model.store import ReadModelStore
from relluna.services.read_model.models import DocumentReadModel
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_search_returns_results_when_text_matches(mocker):
    store = ReadModelStore.__new__(ReadModelStore)

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


@pytest.mark.asyncio
async def test_search_filters_by_patient_cid_event_type_and_doc_type(mocker):
    store = ReadModelStore.__new__(ReadModelStore)

    fake_docs = [
        {
            "document_id": "doc-1",
            "search_text": "maria silva m54.5 parecer_emitido",
            "patient": "MARIA SILVA",
            "provider": "DRA ANA LIMA",
            "cids": ["M54.5"],
            "event_types": ["parecer_emitido"],
            "doc_type": "parecer_medico",
            "date_canonical": "2024-03-05",
            "tags": ["cid:M54.5", "event:parecer_emitido"],
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "document_id": "doc-2",
            "search_text": "joao z00.0 recibo",
            "patient": "JOAO",
            "provider": "CLINICA X",
            "cids": ["Z00.0"],
            "event_types": ["pagamento_registrado"],
            "doc_type": "recibo",
            "date_canonical": "2024-01-10",
            "tags": ["cid:Z00.0"],
            "updated_at": datetime.now(timezone.utc),
        },
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

    res = await store.search(
        q="maria",
        patient="maria",
        cid="M54.5",
        tipo_evento="parecer_emitido",
        doc_type="parecer_medico",
        start_date="2024-03-01",
        end_date="2024-03-31",
        limit=10,
    )

    assert len(res) == 1
    assert res[0]["document_id"] == "doc-1"
