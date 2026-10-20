from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from equipment_lending.controller.authentication_controller import AdminUser, CurrentUser
from equipment_lending.database import DatabaseSession
from equipment_lending.schema.booking import AdminBookingResponse, BookingRequest, BookingResponse
from equipment_lending.service.booking_service import (
    AccessDeniedError, BookingCannotBeCancelled, BookingNotFound, BookingService, EquipmentNotFound,
    EquipmentUnavailable, BookingDateConflict, BookingOperationBusy,
)
from equipment_lending.templating import templates


router = APIRouter(tags=["Bookings"])


def get_booking_service(session: DatabaseSession):
    return BookingService(session)


BookingDependency = Annotated[BookingService, Depends(get_booking_service)]


@router.get("/equipment/{equipment_id}/book", response_class=HTMLResponse)
def booking_page(request: Request, equipment_id: int, service: BookingDependency):
    try:
        equipment = service.get_available_equipment(equipment_id)
    except EquipmentNotFound:
        raise HTTPException(404, "Equipment was not found.") from None
    except EquipmentUnavailable:
        raise HTTPException(409, "This equipment is not currently available for booking.") from None
    today = date.today()
    return templates.TemplateResponse(request=request, name="booking.html", context={
        "equipment": equipment, "today": today.isoformat(), "tomorrow": (today + timedelta(days=1)).isoformat(),
        "next_path": f"/equipment/{equipment_id}/book",
    }, headers={"Cache-Control": "no-store"})


@router.post("/bookings", response_model=BookingResponse, status_code=201)
def create_booking(data: BookingRequest, user: CurrentUser, service: BookingDependency):
    try:
        return service.create_booking(user.id, data)
    except EquipmentNotFound:
        raise HTTPException(404, "Equipment was not found.") from None
    except EquipmentUnavailable:
        raise HTTPException(409, "This equipment is not currently available for booking.") from None
    except BookingDateConflict:
        raise HTTPException(409, "The equipment is already booked for part of this period.") from None


@router.get("/my-bookings", response_model=list[BookingResponse])
def my_bookings(user: CurrentUser, service: BookingDependency, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.find_for_user(user.id)


@router.get("/account/bookings", response_class=HTMLResponse)
def my_bookings_page(request: Request):
    # Public shell; the existing owner-filtered API provides private data.
    return templates.TemplateResponse(request=request, name="my_bookings.html",
                                      context={"next_path": "/account/bookings"},
                                      headers={"Cache-Control": "no-store"})


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
def booking_detail(booking_id: int, user: CurrentUser, service: BookingDependency):
    try:
        return service.find_for_owner(booking_id, user.id)
    except BookingNotFound:
        raise HTTPException(404, "Booking was not found.") from None
    except AccessDeniedError:
        raise HTTPException(403, "You can only view your own bookings.") from None


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(booking_id: int, user: CurrentUser, service: BookingDependency):
    try:
        return service.cancel_booking(booking_id, user.id)
    except BookingNotFound:
        raise HTTPException(404, "Booking was not found.") from None
    except AccessDeniedError:
        raise HTTPException(403, "You can only cancel your own bookings.") from None
    except BookingCannotBeCancelled:
        raise HTTPException(409, "Only pending or approved bookings can be cancelled.") from None
    except BookingOperationBusy:
        raise HTTPException(503, "The database is busy. Please retry the cancellation.",
                            headers={"Retry-After": "1"}) from None


@router.get("/admin/bookings", response_model=list[AdminBookingResponse])
def admin_bookings(user: AdminUser, service: BookingDependency, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return service.find_all()
