from fastapi import FastAPI

from equipment_lending.controller.health_controller import router


app = FastAPI(title="Community Equipment Lending System", version="0.1.0")
app.include_router(router)
