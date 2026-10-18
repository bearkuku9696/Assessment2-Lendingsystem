from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from equipment_lending.templating import templates


router = APIRouter(tags=["Account pages"])
# Only the catalogue and booking pages are valid login destinations.
NextPath = Annotated[str, Query(pattern=r"^(?:/|/equipment/[1-9][0-9]*/book)$")]


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: NextPath = "/", registered: bool = False):
    return templates.TemplateResponse(request=request, name="login.html",
                                      context={"next_path": next, "registered": registered},
                                      headers={"Cache-Control": "no-store"})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, next: NextPath = "/"):
    return templates.TemplateResponse(request=request, name="register.html",
                                      context={"next_path": next}, headers={"Cache-Control": "no-store"})
