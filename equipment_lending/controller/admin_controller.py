from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from equipment_lending.controller.authentication_controller import AdminUser
from equipment_lending.controller.booking_controller import BookingDependency
from equipment_lending.schema.booking import AdminBookingResponse, ApprovalRequest, BookingActionRequest, RejectionRequest
from equipment_lending.service.booking_service import (
    BookingCannotBeReviewed, BookingDateConflict, BookingNotFound, BookingOperationBusy,
    BookingCannotBePickedUp, BookingCannotBeReturned,
    EquipmentNotFound, EquipmentUnavailable,
)
from equipment_lending.templating import templates


router = APIRouter(tags=["Administration"])


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user: AdminUser, service: BookingDependency):
    return templates.TemplateResponse(request=request, name="admin.html",
                                      context={"user": user, "bookings": [
                                          AdminBookingResponse.model_validate(booking) for booking in service.find_all()
                                      ]},
                                      headers={"Cache-Control": "no-store"})


@router.get("/admin/review", response_class=HTMLResponse)
def review_page(request: Request):
    # Public shell only. Reservation data and decisions require an admin token.
    return templates.TemplateResponse(request=request, name="admin.html",
                                      context={"user": None, "bookings": [], "next_path": "/admin/review"},
                                      headers={"Cache-Control": "no-store"})


def review_booking(service: BookingDependency, booking_id: int, admin_notes: str, *, approve: bool):
    try:
        if approve:
            return service.approve_booking(booking_id, admin_notes)
        return service.reject_booking(booking_id, admin_notes)
    except BookingNotFound:
        raise HTTPException(404, "Booking was not found.") from None
    except BookingCannotBeReviewed:
        raise HTTPException(409, "Only pending bookings can be approved or rejected.") from None
    except BookingDateConflict:
        raise HTTPException(409, "The equipment is already booked for part of this period.") from None
    except EquipmentNotFound:
        raise HTTPException(404, "Equipment was not found.") from None
    except EquipmentUnavailable:
        raise HTTPException(409, "This equipment is not currently available for booking.") from None
    except BookingOperationBusy:
        raise HTTPException(503, "The database is busy. Please retry the review.",
                            headers={"Retry-After": "1"}) from None


@router.post("/admin/bookings/{booking_id}/approve", response_model=AdminBookingResponse)
def approve_booking(booking_id: int, data: ApprovalRequest, user: AdminUser, service: BookingDependency):
    return review_booking(service, booking_id, data.admin_notes, approve=True)


@router.post("/admin/bookings/{booking_id}/reject", response_model=AdminBookingResponse)
def reject_booking(booking_id: int, data: RejectionRequest, user: AdminUser, service: BookingDependency):
    return review_booking(service, booking_id, data.admin_notes, approve=False)


def handover_booking(service: BookingDependency, booking_id: int, *, pickup: bool):
    try:
        return service.pickup_booking(booking_id) if pickup else service.return_booking(booking_id)
    except BookingNotFound:
        raise HTTPException(404, "Booking was not found.") from None
    except BookingCannotBePickedUp:
        raise HTTPException(409, "Only approved bookings can be picked up.") from None
    except BookingCannotBeReturned:
        raise HTTPException(409, "Only borrowed bookings can be returned.") from None
    except BookingOperationBusy:
        raise HTTPException(503, "The database is busy. Please retry the operation.",
                            headers={"Retry-After": "1"}) from None


@router.post("/admin/bookings/{booking_id}/pickup", response_model=AdminBookingResponse)
def pickup_booking(booking_id: int, data: BookingActionRequest, user: AdminUser, service: BookingDependency):
    return handover_booking(service, booking_id, pickup=True)


@router.post("/admin/bookings/{booking_id}/return", response_model=AdminBookingResponse)
def return_booking(booking_id: int, data: BookingActionRequest, user: AdminUser, service: BookingDependency):
    return handover_booking(service, booking_id, pickup=False)
