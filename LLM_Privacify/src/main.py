from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from src.routers import analysis, auth, user

from .infrastructure.startup import on_startup
from .infrastructure.middleware import configure_middleware
from .infrastructure.database import engine, SQLModel
from .routers import document

SQLModel.metadata.create_all(engine)

app = configure_middleware(FastAPI())

app.add_event_handler("startup", on_startup)
app.include_router(document.router)
app.include_router(analysis.router)
app.include_router(user.router)
app.include_router(auth.router)
app.mount("/", StaticFiles(directory="path of../kp_ppaf_client"), name="static")

