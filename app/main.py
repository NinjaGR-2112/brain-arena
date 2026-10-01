"""Point d'entrée FastAPI : middlewares, montage des routers, page d'accueil."""
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.routes import auth, pages

load_dotenv()

# SECRET_KEY signe le cookie de session. S'il manque, Starlette ne refuse pas
# de démarrer : elle fait str(None) et signe alors toutes les sessions avec la
# chaîne "None", connue de tous. N'importe qui pouvait alors forger un cookie
# {"user_id": 1} et se connecter en n'importe quel compte. On échoue donc au
# démarrage plutôt que de servir une application silencieusement compromise.
SECRET_KEY = os.getenv("SECRET_KEY")
MIN_SECRET_KEY_LENGTH = 32

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Generate one with "
        "`python -c \"import secrets; print(secrets.token_hex(32))\"` and put it "
        "in .env locally (or in the Render environment variables)."
    )

if len(SECRET_KEY) < MIN_SECRET_KEY_LENGTH:
    raise RuntimeError(
        f"SECRET_KEY is too short ({len(SECRET_KEY)} characters); "
        f"at least {MIN_SECRET_KEY_LENGTH} are required. Generate one with "
        "`python -c \"import secrets; print(secrets.token_hex(32))\"`."
    )

# Durée de vie du cookie de session.
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", 14 * 24 * 60 * 60))

# Drapeau Secure du cookie : à activer derrière HTTPS (Render). Faux par
# défaut pour que le développement local en HTTP reste possible.
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

app = FastAPI(title="Brain Arena")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=SESSION_MAX_AGE,
    https_only=SESSION_COOKIE_SECURE,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(pages.router)
