from server.config.logging import logging
from server.config.mongodb import get_db
from server.config.socketio import socketio_app
from server.types.common import User
from server.web.api.bot.schema import Bot

from .schema import Notification, NotificationType


async def send_notification_bot_invite(
    sender: User,
    receiver: User,
    bot_invite: Bot,
) -> Notification:
    try:
        notification = Notification(
            sender=sender.id,
            receiver=receiver.id,
            type=NotificationType.bot_invite,
            content=f"{sender.username} đã chia sẽ trợ lý AI {bot_invite.name} với bạn",
            metadata={"bot_invite": bot_invite.id},
            read=False,
        )
        db = get_db()
        notifications_collection = db.get_collection("notifications")
        result_notification = await notifications_collection.insert_one(
            notification.model_dump(by_alias=True, exclude=["id"]),
        )
        existing_notification = await notifications_collection.find_one(
            {"_id": result_notification.inserted_id},
        )
        inserted_notification = Notification(**existing_notification)
        await socketio_app.send_notification(
            receiver_id=receiver.id,
            notification=inserted_notification,
        )
    except Exception as e:
        logging.error(f"Error {e}")
