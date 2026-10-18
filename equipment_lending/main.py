from fastapi import FastAPI

from equipment_lending.controller.health_controller import router
from equipment_lending.controller.authentication_controller import router as authentication_router
from equipment_lending.controller.admin_controller import router as admin_router
from equipment_lending.controller.booking_controller import router as booking_router
from equipment_lending.controller.equipment_controller import router as equipment_router


app = FastAPI(title="Community Equipment Lending System", version="0.1.0")
app.include_router(router)
app.include_router(authentication_router)
app.include_router(admin_router)
app.include_router(booking_router)
app.include_router(equipment_router)
