from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
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
def list_equipment(service: EquipmentDependency, search: str = "", category: str = "", status: StatusFilter = ""):
    return service.find_all(search, category, status)


@router.get("/", response_class=HTMLResponse)
def catalogue_page(request: Request, service: EquipmentDependency, search: str = "", category: str = "", status: StatusFilter = ""):
    return templates.TemplateResponse(request=request, name="catalogue.html", context={
        "equipment": service.find_all(search, category, status),
        "categories": service.find_categories(), "search": search, "category": category, "status": status,
    })


@router.post("/admin/equipment", response_model=EquipmentResponse, status_code=201)
def create_equipment(data: EquipmentRequest, user: AdminUser, service: EquipmentDependency):
    return service.create(data.name, data.category, data.location, data.status, data.description)
