from typing import List
from urllib.parse import parse_qs

import socketio
from bson import ObjectId
from pydantic import BaseModel

from server.config.logging import logging
from server.config.mongodb import get_db
from server.services.auth import get_current_user
from server.services.openai_service import fetch_answer_by_file_ids_and_chat_id
from server.web.api.chat_history.schema import ChatMessage
from server.web.api.file.schema import FileStatus
from server.web.api.notification.schema import Notification


class ConnectedUser(BaseModel):
    sid: str
    user_id: str


class SocketIOApp:
    def __init__(self):
        self.sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
        self.sio_app = socketio.ASGIApp(self.sio, socketio_path="/ws")
        self.connected_users: List[ConnectedUser] = []

        self.register_events()

    def register_events(self):
        @self.sio.on("connect")
        async def connect(
            sid,
            environ,
        ):
            query_string = environ.get("QUERY_STRING")

            # Parse the query string
            params = parse_qs(query_string)

            # Extract the token parameter
            token = params.get("token", [None])[0]
            if token is None:
                await self.sio.disconnect(sid)
                return

            current_user = await get_current_user(token=token)
            if current_user is None:
                await self.sio.disconnect(sid)
                return

            connected_user = ConnectedUser(sid=sid, user_id=current_user.id)
            self.connected_users.append(connected_user)
            session = await self.sio.get_session(
                sid,
            )
            if session is None:
                session = {
                    "chat_history_id": None,
                    "bot_id": None,
                }
            await self.sio.save_session(sid, session)
            await self.sio.enter_room(sid, room=sid)

        @self.sio.on("disconnect")
        async def disconnect(sid):
            logging.info(f"Room {sid} Disconnected")
            session = await self.sio.get_session(sid)
            if not session:
                await self.sio.leave_room(sid, room=sid)

            chat_history_id = session.get("chat_history_id")

            if chat_history_id:
                chat_histories_collection = get_db().get_collection("chat_histories")
                await chat_histories_collection.update_one(
                    {"_id": ObjectId(chat_history_id)},
                    {"$set": {"disabled": False}},
                )

                await self.sio.leave_room(sid, room=sid)

        @self.sio.event
        async def join_chat(sid, data):
            logging.info(f"Room {sid} join chat data: {data}")
            db = get_db()
            chat_histories_collection = db.get_collection("chat_histories")
            chat_history_id = data.get("chat_history_id")
            bot_id = data.get("bot_id")
            updated_result = await chat_histories_collection.update_one(
                {
                    "_id": ObjectId(
                        chat_history_id,
                    ),
                    "bot_id": bot_id,
                },
                {"$set": {"disabled": True}},
            )
            if updated_result.matched_count > 0:
                await self.sio.save_session(
                    sid,
                    {"chat_history_id": chat_history_id, "bot_id": bot_id},
                )
            else:
                await self.sio.emit(
                    "error",
                    {"error": "Không tìm thấy trợ lý AI"},
                    room=sid,
                )

        @self.sio.event
        async def leave_chat(sid):
            logging.info(f"Room {sid} leave chat")
            try:
                session = await self.sio.get_session(sid)
                if not session:
                    raise Exception("Session is None")

                chat_history_id = session.get("chat_history_id")
                logging.info(f"Chat history {chat_history_id}")
                db = get_db()
                chat_histories_collection = db.get_collection("chat_histories")
                updated_result = await chat_histories_collection.update_one(
                    {"_id": ObjectId(chat_history_id)},
                    {"$set": {"disabled": False}},
                )
                if updated_result.matched_count > 0:
                    await self.sio.save_session(
                        sid,
                        {
                            "chat_history_id": None,
                            "bot_id": None,
                        },
                    )
                else:
                    await self.sio.emit(
                        "error",
                        {"error": "Không tìm thấy trợ lý AI"},
                        room=sid,
                    )

            except Exception as e:
                logging.error(f"Error: {e}")
                await self.sio.emit("error", {"error": "Đã có lỗi xảy ra"}, room=sid)

        @self.sio.event
        async def send_message(sid, data: dict):
            try:
                db = get_db()
                chat_histories_collection = db.get_collection("chat_histories")
                chat_messages_collection = db.get_collection("chat_messages")
                bots_collection = db.get_collection("bots")

                session = await self.sio.get_session(sid)
                chat_history_id = session.get("chat_history_id")
                bot_id = session.get("bot_id")
                existing_chat = await chat_histories_collection.find_one(
                    {"_id": ObjectId(chat_history_id)},
                )
                existing_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
                if existing_bot is None:
                    await self.sio.emit(
                        "error",
                        {"error": "Không tìm thấy trợ lý AI"},
                        room=sid,
                    )
                    return
                file_ids = existing_bot.get("list_files", [])
                if len(file_ids) <= 0:
                    await self.sio.emit(
                        "message",
                        {
                            "message": {
                                "answer": "Hiện tại trợ lý AI chưa có dữ liệu để xử lý các yêu cầu. Vui lòng cung cấp thêm dữ liệu",
                            },
                        },
                        room=sid,
                    )
                    return

                answer = await fetch_answer_by_file_ids_and_chat_id(
                    data.get("message"),
                    file_ids,
                    chat_history_id,
                )

                message = {"answer": answer.get("answer")}
                suggest_question = answer.get("suggest_question")

                # Nếu có suggest_question thì thêm vào message
                if suggest_question:
                    message["suggest_question"] = suggest_question

                await self.sio.emit("message", {"message": message}, room=sid)
                new_chat_message = ChatMessage(
                    question=data.get("message"),
                    answer=answer.get("answer", ""),
                    source=None if not answer.get("source") else answer.get("source"),
                    chat_history_id=chat_history_id,
                )
                chat_message_result = await chat_messages_collection.insert_one(
                    new_chat_message.model_dump(by_alias=True, exclude=["id"]),
                )

                if existing_chat:
                    await chat_histories_collection.update_one(
                        {"_id": ObjectId(chat_history_id)},
                        {
                            "$push": {
                                "list_messages": str(chat_message_result.inserted_id),
                            },
                        },
                    )
            except Exception as e:
                logging.error(e)
                await self.sio.emit("error", {"error": "Đã có lỗi xảy ra"}, room=sid)

    def get_connected_users(self, user_id):
        connected_users = [
            user for user in self.connected_users if user.user_id == user_id
        ]
        return connected_users

    async def send_notification(self, receiver_id, notification: Notification):
        try:
            connected_users = self.get_connected_users(receiver_id)
            if len(connected_users) > 0:

                notification_data = {
                    "_id": notification.id,
                    "sender": notification.sender,
                    "receiver": notification.receiver,
                    "type": notification.type,
                    "content": notification.content,
                    "metadata": notification.metadata,
                    "created_at": notification.created_at.isoformat(),
                    "read": notification.read,
                }

                for connected_user in connected_users:
                    await self.sio.emit(
                        "notification",
                        {"notification": notification_data},
                        room=connected_user.sid,
                    )
        except Exception as e:
            logging.error(f"Error: {e}")

    async def send_file_status(self, receiver_id, file_id: str, status: FileStatus):
        try:
            connected_users = self.get_connected_users(receiver_id)
            for connected_user in connected_users:
                await self.sio.emit(
                    "file_status",
                    {"file_id": file_id, "status": status},
                    room=connected_user.sid,
                )
        except Exception as e:
            logging.error(f"Error: {e}")


socketio_app = SocketIOApp()
