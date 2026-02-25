from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ReadModelDocument(BaseModel):
    document_id: str
    media_type: str

    data_canonica: Optional[datetime] = None
    periodo: Optional[str] = None
    tipo_evento: Optional[str] = None

    tags: List[str] = []
    search_text: str

    updated_at: datetime
