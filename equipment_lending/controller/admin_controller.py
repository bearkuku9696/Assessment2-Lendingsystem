from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from equipment_lending.controller.authentication_controller import AdminUser
from equipment_lending.controller.booking_controller import BookingDependency
from equipment_lending.schema.booking import AdminBookingResponse, ApprovalRequest, RejectionRequest
from equipment_lending.service.booking_service import (
    BookingCannotBeReviewed, BookingDateConflict, BookingNotFound, BookingReviewBusy,
    EquipmentNotFound, EquipmentUnavailable,
)
from equipment_lending.templating import templates


router = APIRouter(tags=["Administration"])


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user: AdminUser, service: BookingDependency):
    return templates.TemplateResponse(request=request, name="admin.html",
                                      context={"user": user, "bookings": service.find_all()},
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
    except BookingReviewBusy:
        raise HTTPException(503, "The database is busy. Please retry the review.",
                            headers={"Retry-After": "1"}) from None


@router.post("/admin/bookings/{booking_id}/approve", response_model=AdminBookingResponse)
def approve_booking(booking_id: int, data: ApprovalRequest, user: AdminUser, service: BookingDependency):
    return review_booking(service, booking_id, data.admin_notes, approve=True)


@router.post("/admin/bookings/{booking_id}/reject", response_model=AdminBookingResponse)
def reject_booking(booking_id: int, data: RejectionRequest, user: AdminUser, service: BookingDependency):
    return review_booking(service, booking_id, data.admin_notes, approve=False)
