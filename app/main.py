import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.routes import auth

load_dotenv()

app = FastAPI(title="Brain Arena")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

from app.routes import pages

app.include_router(pages.router)