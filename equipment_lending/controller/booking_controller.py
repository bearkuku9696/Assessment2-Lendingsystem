from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from equipment_lending.controller.authentication_controller import AdminUser, CurrentUser
from equipment_lending.database import DatabaseSession
from equipment_lending.schema.booking import BookingRequest, BookingResponse
from equipment_lending.service.booking_service import (
    AccessDeniedError, BookingCannotBeCancelled, BookingNotFound, BookingService, EquipmentNotFound,
    EquipmentUnavailable,
)
from equipment_lending.views.booking import render_booking_form


router = APIRouter(tags=["Bookings"])


def get_booking_service(session: DatabaseSession):
    return BookingService(session)


BookingDependency = Annotated[BookingService, Depends(get_booking_service)]


@router.get("/equipment/{equipment_id}/book", response_class=HTMLResponse)
def booking_page(equipment_id: int, service: BookingDependency):
    try:
        equipment = service.get_available_equipment(equipment_id)
    except EquipmentNotFound:
        raise HTTPException(404, "Equipment was not found.") from None
    except EquipmentUnavailable:
        raise HTTPException(409, "This equipment is not currently available for booking.") from None
    return HTMLResponse(render_booking_form(equipment), headers={"Cache-Control": "no-store"})


@router.post("/bookings", response_model=BookingResponse, status_code=201)
def create_booking(data: BookingRequest, user: CurrentUser, service: BookingDependency):
    try:
        return service.create_booking(user.id, data)
    except EquipmentNotFound:
        raise HTTPException(404, "Equipment was not found.") from None
    except EquipmentUnavailable:
        raise HTTPException(409, "This equipment is not currently available for booking.") from None


@router.get("/my-bookings", response_model=list[BookingResponse])
def my_bookings(user: CurrentUser, service: BookingDependency):
    return service.find_for_user(user.id)


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


@router.get("/admin/bookings", response_model=list[BookingResponse])
def admin_bookings(user: AdminUser, service: BookingDependency):
    return service.find_all()
