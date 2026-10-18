from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints


class EquipmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    category: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    location: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    status: Literal["available", "maintenance", "inactive"] = "available"


class EquipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    category: str
    location: str
    status: Literal["available", "maintenance", "inactive"]
