from typing import Annotated

from fastapi import APIRouter, Depends

from equipment_lending.controller.authentication_controller import AdminUser, CurrentUser
from equipment_lending.database import DatabaseSession
from equipment_lending.schema.equipment import EquipmentRequest, EquipmentResponse
from equipment_lending.service.equipment_service import EquipmentService


router = APIRouter(tags=["Equipment"])


def get_equipment_service(session: DatabaseSession):
    return EquipmentService(session)


EquipmentDependency = Annotated[EquipmentService, Depends(get_equipment_service)]


@router.get("/equipment", response_model=list[EquipmentResponse])
def list_equipment(user: CurrentUser, service: EquipmentDependency):
    return service.find_all()


@router.post("/admin/equipment", response_model=EquipmentResponse, status_code=201)
def create_equipment(data: EquipmentRequest, user: AdminUser, service: EquipmentDependency):
    return service.create(data.name)
