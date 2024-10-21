import asyncio
from datetime import datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from server.config.mongodb import get_db
from server.constants.common import Pagination
from server.services.auth import get_current_active_user
from server.types.common import ListDataResponse, User
from server.web.api.chat_history.schema import ChatHistory, ChatMessage

from .service import delete_messages_by_list_id

router = APIRouter()


@router.get("/{bot_id}")
async def get_chats_by_bot_id(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
    page: int = Query(Pagination.PAGE_DEFAULT, ge=1, description="Page number"),
    size_page: int = Query(
        Pagination.SIZE_PAGE_DEFAULT,
        ge=1,
        le=20,
        description="Page size",
    ),
):
    db = get_db()
    bots_collection = db.get_collection("bots")
    chat_histories_collection = db.get_collection("chat_histories")
    existing_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    if existing_bot is None:
        return HTTPException(status_code=404, detail="Bot not found")

    total_chats = await chat_histories_collection.count_documents(
        {"bot_id": bot_id, "user_id": current_user.id, "list_messages": {"$ne": []}},
    )

    data_chats = (
        await chat_histories_collection.find(
            {
                "bot_id": bot_id,
                "user_id": current_user.id,
                "list_messages": {"$ne": []},
            },
        )
        .skip((page - 1) * size_page)
        .limit(size_page)
        .sort("created_at", -1)
        .to_list(length=None)
    )
    return ListDataResponse(
        total=total_chats,
        data=[ChatHistory(**chat) for chat in data_chats],
    )


@router.get("/join_chat_bot/{bot_id}")
async def join_chat(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
):

    db = get_db()
    bots_collection = db.get_collection("bots")
    chat_histories_collection = db.get_collection("chat_histories")

    existing_bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "$or": [
                {
                    "list_user_permission": {
                        "$elemMatch": {
                            "user_id": str(current_user.id),
                        },
                    },
                },
                {"isPublic": True},
            ],
        },
    )

    if existing_bot is None:
        return HTTPException(status_code=404, detail="Bot not found")

    # Kiểm tra và gửi lại lịch sử trò chuyện nếu chat_messages là []
    existing_chat_history = await chat_histories_collection.find_one(
        {
            "bot_id": bot_id,
            "user_id": current_user.id,
            "list_messages": [],
            "disabled": False,
        },
    )

    if existing_chat_history:
        chat_history = ChatHistory(**existing_chat_history)
        await chat_histories_collection.update_one(
            {"_id": ObjectId(chat_history.id)},
            {
                "$set": {
                    "createdAt": datetime.now(timezone.utc),
                },
            },
        )

    else:
        new_chat_history = ChatHistory(
            bot_id=bot_id,
            user_id=current_user.id,
            disabled=True,
        )
        chat_history_result = await chat_histories_collection.insert_one(
            new_chat_history.model_dump(by_alias=True, exclude={"id"}),
        )
        inserted_chat_history = await chat_histories_collection.find_one(
            {"_id": chat_history_result.inserted_id},
        )
        chat_history = ChatHistory(**inserted_chat_history)

    return chat_history


@router.delete("/{chat_id}")
async def delete_chat(
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_id: str,
):
    db = get_db()
    chats_collection = db.get_collection("chat_histories")

    existing_chat = await chats_collection.find_one(
        {"_id": ObjectId(chat_id), "user_id": current_user.id},
    )

    if existing_chat is None:
        raise HTTPException(status_code=404, detail="Chat history not found")

    # Xóa các tin nhắn liên quan
    message_ids = existing_chat.get("list_messages", [])
    asyncio.create_task(delete_messages_by_list_id(message_ids))

    # Xóa chat
    await chats_collection.delete_one({"_id": ObjectId(chat_id)})

    return {"detail": "Chat and related messages deleted successfully"}


@router.get("/{chat_id}/messages", response_model=ListDataResponse[ChatMessage])
async def get_messages(
    current_user: Annotated[User, Depends(get_current_active_user)],
    chat_id: str,
):
    db = get_db()
    chats_collection = db.get_collection("chat_histories")
    messages_collection = db.get_collection("chat_messages")

    existing_chat = await chats_collection.find_one(
        {"_id": ObjectId(chat_id), "user_id": current_user.id},
    )

    if existing_chat is None:
        raise HTTPException(status_code=404, detail="Chat history not found")

    message_ids = existing_chat.get("list_messages", [])

    messages = await messages_collection.find(
        {"_id": {"$in": [ObjectId(message_id) for message_id in message_ids]}},
    ).to_list(length=None)

    return ListDataResponse(
        total=1,
        data=[ChatMessage(**message) for message in messages],
    )
