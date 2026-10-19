from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from equipment_lending.controller.authentication_controller import AdminUser
from equipment_lending.templating import templates
from equipment_lending.database import DatabaseSession
from equipment_lending.schema.equipment import EquipmentRequest, EquipmentResponse
from equipment_lending.service.equipment_service import EquipmentService


router = APIRouter(tags=["Equipment"])


def get_equipment_service(session: DatabaseSession):
    return EquipmentService(session)


EquipmentDependency = Annotated[EquipmentService, Depends(get_equipment_service)]
StatusFilter = Literal["", "available", "maintenance", "inactive"]


@router.get("/equipment", response_model=list[EquipmentResponse])
def list_equipment(
    service: EquipmentDependency,
    search: str = "",
    category: str = "",
    status: StatusFilter = "",
    start_date: date | None = None,
    end_date: date | None = None,
):
    _validate_period(start_date, end_date)
    return service.find_all(search, category, status, start_date, end_date)


@router.get("/", response_class=HTMLResponse)
def catalogue_page(
    request: Request,
    service: EquipmentDependency,
    search: str = "",
    category: str = "",
    status: StatusFilter = "",
    start_date: date | None = None,
    end_date: date | None = None,
):
    _validate_period(start_date, end_date)
    return templates.TemplateResponse(request=request, name="catalogue.html", context={
        "equipment": service.find_all(search, category, status, start_date, end_date),
        "categories": service.find_categories(), "search": search, "category": category, "status": status,
        "start_date": start_date.isoformat() if start_date else "",
        "end_date": end_date.isoformat() if end_date else "",
    })


@router.post("/admin/equipment", response_model=EquipmentResponse, status_code=201)
def create_equipment(data: EquipmentRequest, user: AdminUser, service: EquipmentDependency):
    return service.create(data.name, data.category, data.location, data.status, data.description)


def _validate_period(start_date: date | None, end_date: date | None):
    if (start_date is None) != (end_date is None):
        raise HTTPException(422, "Both start_date and end_date are required for a period filter.")
    if start_date is not None and end_date <= start_date:
        raise HTTPException(422, "The end date must be after the start date.")
