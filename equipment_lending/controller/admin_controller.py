from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from equipment_lending.controller.authentication_controller import AdminUser
from equipment_lending.controller.booking_controller import BookingDependency


router = APIRouter(tags=["Administration"])


@router.get("/admin", response_class=HTMLResponse)
def admin_page(user: AdminUser, service: BookingDependency):
    rows = "".join(
        f"<tr><td>{booking.id}</td><td>{booking.user_id}</td><td>{booking.equipment_id}</td>"
        f"<td>{booking.start_date}</td><td>{booking.end_date}</td>"
        f"<td>{escape(booking.purpose)}</td><td>{escape(booking.status)}</td></tr>"
        for booking in service.find_all()
    )
    return HTMLResponse(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Booking administration</title></head><body>'
        f"<h1>Booking administration</h1><p>Signed in as {escape(user.name)}</p>"
        "<table><thead><tr><th>Booking</th><th>Member</th><th>Equipment</th>"
        "<th>Start</th><th>End</th><th>Purpose</th><th>Status</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></body></html>",
        headers={"Cache-Control": "no-store"},
    )
