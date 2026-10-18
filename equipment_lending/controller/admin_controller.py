from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from equipment_lending.controller.authentication_controller import AdminUser
from equipment_lending.controller.booking_controller import BookingDependency
from equipment_lending.templating import templates


router = APIRouter(tags=["Administration"])


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user: AdminUser, service: BookingDependency):
    return templates.TemplateResponse(request=request, name="admin.html",
                                      context={"user": user, "bookings": service.find_all()},
                                      headers={"Cache-Control": "no-store"})
