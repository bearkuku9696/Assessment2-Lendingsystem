from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field, field_validator, model_validator


class BookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equipment_id: int = Field(gt=0)
    start_date: date
    end_date: date
    purpose: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date < date.today():
            raise ValueError("The start date cannot be in the past.")
        if self.end_date <= self.start_date:
            raise ValueError("The end date must be after the start date.")
        return self


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    equipment_id: int
    start_date: date
    end_date: date
    purpose: str
    status: Literal["pending", "approved", "borrowed", "returned", "rejected", "cancelled"]
    created_at: datetime
    picked_up_at: datetime | None
    returned_at: datetime | None

    @field_validator("picked_up_at", "returned_at")
    @classmethod
    def utc_actual_times(cls, value):
        # SQLite stores naive datetimes; these server-recorded values are UTC.
        return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value

    @computed_field
    @property
    def is_overdue(self) -> bool:
        return self.status == "borrowed" and self.end_date < date.today()


class BookingActionRequest(BaseModel):
    """No client-supplied status or timestamps are accepted for handovers."""
    model_config = ConfigDict(extra="forbid")


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    admin_notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""


class RejectionRequest(ApprovalRequest):
    admin_notes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class AdminBookingResponse(BookingResponse):
    applicant_name: str
    applicant_email: str
    equipment_name: str
    admin_notes: str
