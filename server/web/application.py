import logging
from importlib import metadata

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import UJSONResponse
from fastapi.routing import APIRouter

from server.config.socketio import socketio_app
from server.web.api.router import api_router
from server.web.lifetime import register_shutdown_event, register_startup_event

logger = logging.getLogger(__name__)


def get_app() -> FastAPI:
    """
    Get FastAPI application.

    This is the main constructor of an application.

    :return: application.
    """
    app = FastAPI(
        title="Code Chat",
        version=metadata.version("server"),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        default_response_class=UJSONResponse,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers="*",
    )

    # Adds startup and shutdown events.
    register_startup_event(app)
    register_shutdown_event(app)

    welcome_route = APIRouter()

    @welcome_route.get("/")
    def welcome():
        return {"detail": "Welcome to chat bot server"}

    # Main router for the API.
    app.include_router(router=welcome_route, tags=["Welcome"])
    app.include_router(router=api_router, prefix="/api")
    app.mount("/", socketio_app.sio_app)
    return app
