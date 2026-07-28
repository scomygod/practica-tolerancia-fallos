from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReservationCreate(BaseModel):
    event_id: int
    email: str
    amount: float = Field(gt=0)


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: int
    email: str
    amount: float
    status: str
    notification_status: str
    message: str | None = None
