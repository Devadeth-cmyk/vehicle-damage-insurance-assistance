from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: int
    claim_id: int
    file_name: str
    file_path: str
    file_type: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)
