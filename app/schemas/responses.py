from pydantic import BaseModel


class UsageIngestResponse(BaseModel):
    ok: bool
    deduped: bool
    requestId: str
    eventId: str
