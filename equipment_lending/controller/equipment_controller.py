from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BeforeValidator

from equipment_lending.controller.authentication_controller import AdminUser
from equipment_lending.templating import templates
from equipment_lending.database import DatabaseSession
from equipment_lending.schema.equipment import EquipmentRequest, EquipmentResponse
from equipment_lending.service.equipment_service import EquipmentService


router = APIRouter(tags=["Equipment"])


def get_equipment_service(session: DatabaseSession):
    return EquipmentService(session)


EquipmentDependency = Annotated[EquipmentService, Depends(get_equipment_service)]
StatusFilter = Literal["", "available", "unavailable", "maintenance", "inactive"]
DateFilter = Annotated[date | None, BeforeValidator(lambda value: None if value == "" else value)]


@router.get("/equipment", response_model=list[EquipmentResponse])
def list_equipment(
    request: Request,
    response: Response,
    service: EquipmentDependency,
    search: str = "",
    category: str = "",
    status: StatusFilter = "",
    start_date: DateFilter = None,
    end_date: DateFilter = None,
):
    _validate_period(start_date, end_date)
    response.headers["Cache-Control"] = "no-store"
    equipment = service.find_all(search, category, status, start_date, end_date)
    if "text/html" in request.headers.get("accept", ""):
        return _catalogue_response(
            request, service, equipment, search, category, status, start_date, end_date,
        )
    return equipment


@router.get("/", response_class=HTMLResponse)
def catalogue_page(
    request: Request,
    service: EquipmentDependency,
    search: str = "",
    category: str = "",
    status: StatusFilter = "",
    start_date: DateFilter = None,
    end_date: DateFilter = None,
):
    _validate_period(start_date, end_date)
    equipment = service.find_all(search, category, status, start_date, end_date)
    return _catalogue_response(request, service, equipment, search, category, status, start_date, end_date)


def _catalogue_response(request, service, equipment, search, category, status, start_date, end_date):
    return templates.TemplateResponse(request=request, name="catalogue.html", context={
        "equipment": equipment,
        "categories": service.find_categories(), "search": search, "category": category, "status": status,
        "start_date": start_date.isoformat() if start_date else "",
        "end_date": end_date.isoformat() if end_date else "",
    }, headers={"Cache-Control": "no-store"})


@router.post("/admin/equipment", response_model=EquipmentResponse, status_code=201)
def create_equipment(data: EquipmentRequest, user: AdminUser, service: EquipmentDependency):
    return service.create(data.name, data.category, data.location, data.status, data.description)


def _validate_period(start_date: date | None, end_date: date | None):
    if (start_date is None) != (end_date is None):
        raise HTTPException(422, "Both start_date and end_date are required for a period filter.")
    if start_date is not None and end_date <= start_date:
        raise HTTPException(422, "The end date must be after the start date.")
