from fastapi.routing import APIRouter

from server.web.api.admin import router as adminRouter
from server.web.api.user import router as userRouter
from server.web.api.bot import router as botRouter
from server.web.api.chat_history import router as chatHistoryRouter
from server.web.api.file import router as fileRouter
from server.web.api.notification import router as notificationRouter
from server.web.api.package import router as packageRouter
from server.web.api.token import router as tokenRouter

api_router = APIRouter()
# api_router.include_router(adminRouter, prefix="/admin", tags=["Admin"])
api_router.include_router(userRouter, prefix="/user", tags=["User"])
api_router.include_router(botRouter, prefix="/bot", tags=["Bot"])
api_router.include_router(fileRouter, prefix="/file", tags=["File"])
api_router.include_router(
    notificationRouter,
    prefix="/notification",
    tags=["Notification"],
)
api_router.include_router(
    chatHistoryRouter,
    prefix="/chat_history",
    tags=["Chat history"],
)

# api_router.include_router(packageRouter, prefix="/package", tags=["Package"])

api_router.include_router(tokenRouter, prefix="/token", tags=["Token"])
