from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class EquipmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class EquipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
