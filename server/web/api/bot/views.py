import asyncio
import os
from typing import Annotated, List
from uuid import uuid4

from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pymongo import DESCENDING

from server.config.logging import logging
from server.config.mongodb import get_db
from server.constants.common import Pagination
from server.services.auth import get_current_active_user
from server.services.file_service import insert_file
from server.types.common import ListDataResponse, User
from server.web.api.chat_history.schema import ChatHistory
from server.web.api.chat_history.service import delete_messages_by_list_id
from server.web.api.file.schema import FileSchema
from server.web.api.notification.service import send_notification_bot_invite
from server.web.api.user.schema import UserResponse


from .schema import (
    Bot,
    BotResponse,
    BotUpdate,
    PermissionEnum,
    UserPermission,
    UserPermissionResponse,
)

router = APIRouter()


@router.get("/", response_model=ListDataResponse[BotResponse])
async def get_bots_by_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
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

    # Đếm tổng số bots
    total_bots = await bots_collection.count_documents(
        {"list_user_permission": {"$elemMatch": {"user_id": current_user.id}}},
    )

    # Tìm các bot có user_id trong list_user_permission
    bots_data = (
        await bots_collection.find(
            {"list_user_permission": {"$elemMatch": {"user_id": current_user.id}}},
        )
        .skip((page - 1) * size_page)
        .limit(size_page)
        .to_list(length=None)
    )
    return ListDataResponse(
        total=total_bots,
        data=[BotResponse(**bot) for bot in bots_data],
    )


@router.get("/{bot_id}/avatar")
async def get_avatar(bot_id: str):
    try:

        bots_collection = get_db().get_collection("bots")
        bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})

        if not bot or not bot.get("avatar_source"):
            raise HTTPException(status_code=404, detail="Bot not found")

        avatar_source = bot.get("avatar_source")

        if not os.path.exists(avatar_source):
            raise HTTPException(status_code=404, detail="Avatar not found")

        return FileResponse(avatar_source)
    except Exception as e:
        return HTTPException(status_code=404, detail="Bot not found")


@router.post("/")
async def create_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    name: str = Form(...),
    description: str = Form(...),
    response_model: str = Form(...),
    avatar: UploadFile = File(None),
):

    db = get_db()
    bots_collection = db.get_collection("bots")

    owner_permission = UserPermission(
        user_id=str(current_user.id),
        permissions=[
            PermissionEnum.read_file,
            PermissionEnum.write_file,
            PermissionEnum.read_user,
            PermissionEnum.write_user,
        ],
        confirm=True,
    )
    user_permissions = [owner_permission]

    avatar_source = None
    if avatar:
        save_dir = os.path.join("server/stores/bot/")
        os.makedirs(save_dir, exist_ok=True)
        filename = f"{uuid4()}.jpg"
        avatar_path = os.path.join(save_dir, filename)

        with open(avatar_path, "wb") as f:
            f.write(await avatar.read())

        avatar_source = avatar_path

    # bot_create.list_user_permission.append(owner_permission)
    bot_data = {
        "name": name,
        "description": description,
        "list_user_permission": user_permissions,
        "response_model": response_model,
        "owner": current_user.id,
        "avatar_source": avatar_source,
    }

    new_bot = Bot(**bot_data)

    bot_result = await bots_collection.insert_one(
        new_bot.model_dump(by_alias=True, exclude=["id"]),
    )
    bot_inserted = await bots_collection.find_one({"_id": bot_result.inserted_id})

    return BotResponse(**bot_inserted)


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot_by_id(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
):

    bots_collection = get_db().get_collection("bots")
    bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {
                    "user_id": str(current_user.id),
                },
            },
        },
    )

    if not bot:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found",
        )

    return BotResponse(**bot)


@router.get("/{bot_id}/favorite", response_model=ListDataResponse[UserResponse])
async def get_favorited(
    bot_id: str,
):
    bots_collection = get_db().get_collection("bots")
    users_collection = get_db().get_collection("users")
    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})

    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found",
        )

    favorited_user_ids = bot.get("favorited_users", [])

    if not favorited_user_ids:
        return ListDataResponse(total=0, data=[])

    favorited_users = await users_collection.find(
        {"_id": {"$in": [ObjectId(user_id) for user_id in favorited_user_ids]}},
    ).to_list(length=None)

    return ListDataResponse(
        total=len(favorited_users),
        data=[UserResponse(**user) for user in favorited_users],
    )


@router.post("/{bot_id}/favorite", response_model=BotResponse)
async def toggle_favorite_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
):
    bots_collection = get_db().get_collection("bots")

    bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})

    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found",
        )

    if str(current_user.id) in bot.get("favorited_users", []):
        await bots_collection.update_one(
            {"_id": ObjectId(bot_id)},
            {"$pull": {"favorited_users": str(current_user.id)}},
        )
    else:
        await bots_collection.update_one(
            {"_id": ObjectId(bot_id)},
            {"$addToSet": {"favorited_users": str(current_user.id)}},
        )

    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})

    return BotResponse(**updated_bot)


@router.put("/{bot_id}", response_model=BotResponse)
async def update_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
    bot_update: BotUpdate = Body(...),
):
    bots_collection = get_db().get_collection("bots")
    existing_bot = await bots_collection.find_one(
        {"_id": ObjectId(bot_id), "owner": current_user.id},
    )
    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found",
        )

    updated_data = {k: v for k, v in bot_update.model_dump().items() if v is not None}
    if (
        "list_user_permission" not in updated_data
        or updated_data["list_user_permission"] is None
    ):
        updated_data["list_users_id"] = existing_bot.get("list_user_permission", [])

    if "list_files" not in updated_data or updated_data["list_files"] is None:
        updated_data["list_files"] = existing_bot.get("list_files", [])

    await bots_collection.update_one({"_id": ObjectId(bot_id)}, {"$set": updated_data})
    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    return BotResponse(**updated_bot)


@router.put("/{bot_id}/upload_avatar", response_model=BotResponse)
async def update_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
    avatar: UploadFile = File(...),
):
    bots_collection = get_db().get_collection("bots")
    existing_bot = await bots_collection.find_one(
        {"_id": ObjectId(bot_id), "owner": current_user.id},
    )
    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found",
        )

    save_dir = os.path.join("server/stores/bot/")
    os.makedirs(save_dir, exist_ok=True)

    old_avatar = existing_bot.get("avatar_source")
    if old_avatar and os.path.exists(old_avatar):
        os.remove(old_avatar)

    filename = f"{uuid4()}.jpg"
    file_path = os.path.join(save_dir, filename)

    with open(file_path, "wb") as f:
        f.write(await avatar.read())

    await bots_collection.update_one(
        {"_id": ObjectId(bot_id)},
        {"$set": {"avatar_source": file_path}},
    )

    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})

    return BotResponse(**updated_bot)


@router.delete("/{bot_id}", response_model=dict)
async def delete_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
):
    db = get_db()
    bots_collection = db.get_collection("bots")
    chats_collection = db.get_collection("chat_histories")
    messages_collection = db.get_collection("chat_messages")
    existing_bot = await bots_collection.find_one(
        {"_id": ObjectId(bot_id), "owner": current_user.id},
    )

    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found",
        )

    avatar_source = existing_bot.get("avatar_source")
    if avatar_source and os.path.exists(avatar_source):
        os.remove(avatar_source)

    existing_chats = await chats_collection.find(
        {"bot_id": existing_bot.get("_id")},
    ).to_list(length=None)
    list_msg_ids = []
    for chat_data in existing_chats:
        chat = ChatHistory(**chat_data)
        # Xóa các tin nhắn liên quan
        list_msg_ids.append(chat.list_messages)

        # Xóa lịch sử chat
        await chats_collection.delete_one({"_id": ObjectId(chat.id)})

    asyncio.create_task(delete_messages_by_list_id(list_msg_ids))

    await bots_collection.delete_one({"_id": ObjectId(bot_id)})

    return {"detail": "Bot deleted successfully"}


@router.get("/{bot_id}/list_user", response_model=List[UserPermissionResponse])
async def get_list_user_by_bot_id(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
):
    bots_collection = get_db().get_collection("bots")
    users_collection = get_db().get_collection("users")
    existing_bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {
                    "user_id": str(current_user.id),
                    "permissions": {"$in": [PermissionEnum.read_user]},
                },
            },
        },
    )

    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found or You does not have permission to get users",
        )

    bot = Bot(**existing_bot)

    list_user_permission_res: List[UserPermissionResponse] = []

    for user_permission in bot.list_user_permission:
        user = await users_collection.find_one(
            {"_id": ObjectId(user_permission.user_id)},
        )
        user_permission_res = UserPermissionResponse(
            user=UserResponse(**user),
            permissions=user_permission.permissions,
            confirm=user_permission.confirm,
        )
        list_user_permission_res.append(user_permission_res)

    return list_user_permission_res


@router.post("/{bot_id}/invite_user", response_model=BotResponse)
async def invite_user_with_permission_to_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
    user_permission_request: UserPermission = Body(...),
):
    db = get_db()
    bots_collection = db.get_collection("bots")
    users_collection = db.get_collection("users")

    existing_bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {
                    "user_id": current_user.id,
                    "permissions": {"$in": [PermissionEnum.write_user]},
                },
            },
        },
    )

    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found or You does not have permission to edit users",
        )

    existing_user = await users_collection.find_one(
        {"_id": ObjectId(user_permission_request.user_id)},
    )
    if existing_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with id {user_permission_request.user_id} not found",
        )

    # Kiểm tra xem user đã có trong danh sách permissions chưa
    for user_permission in existing_bot["list_user_permission"]:
        if user_permission["user_id"] == user_permission_request.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with id {user_permission_request.user_id} already has permissions in this bot",
            )

    # Thêm user_permission vào list_user_permission
    update_result = await bots_collection.update_one(
        {"_id": ObjectId(bot_id)},
        {"$push": {"list_user_permission": user_permission_request.model_dump()}},
    )

    if update_result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to add user permission to bot with id {bot_id}",
        )

    # Lấy lại thông tin bot sau khi cập nhật
    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})

    users_collection.find_one({"_id": ObjectId(user_permission_request.user_id)})

    await send_notification_bot_invite(
        sender=current_user,
        receiver=User(**existing_user),
        bot_invite=Bot(**existing_bot),
    )

    return BotResponse(**updated_bot)


@router.post("/{bot_id}/confirm_invite_user", response_model=dict)
async def confirm_invite_user_permission_to_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
):
    db = get_db()
    bots_collection = db.get_collection("bots")

    updated_result = await bots_collection.update_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {"user_id": current_user.id, "confirm": False},
            },
        },
        {"$set": {"list_user_permission.$.confirm": True}},
    )

    if updated_result.modified_count > 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Confirm invitation failure",
        )

    return {"detail": "Confirmed invitation successfully"}


@router.post("/{bot_id}/decline_invite_user", response_model=dict)
async def decline_invite_user_permission_to_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
):

    db = get_db()
    bots_collection = db.get_collection("bots")

    updated_result = await bots_collection.update_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {"user_id": current_user.id, "confirm": False},
            },
        },
        {
            "$pull": {
                "list_user_permission": {
                    "user_id": current_user.id,
                },
            },
        },
    )

    if updated_result.modified_count > 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decline invitation failure",
        )

    return {"detail": "Declined invitation successfully"}


@router.put("/{bot_id}/edit_user", response_model=BotResponse)
async def edit_user_permission_in_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
    user_permission_request: UserPermission,
):
    bots_collection = get_db().get_collection("bots")

    existing_bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {
                    "user_id": str(current_user.id),
                    "permissions": {"$in": [PermissionEnum.write_user]},
                },
            },
        },
    )

    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found or You does not have permission to edit users",
        )

    # Kiểm tra sửa thông tin người sở hữu bot
    if existing_bot.get("owner") == user_permission_request.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't edit the bot owner",
        )

    # Tìm và cập nhật quyền của user trong list_user_permission của bot
    update_result = await bots_collection.update_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission.user_id": user_permission_request.user_id,
        },
        {
            "$set": {
                "list_user_permission.$.permissions": user_permission_request.permissions,
            },
        },
    )

    if update_result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_permission_request.user_id} not found in bot's user permissions",
        )

    # Lấy lại thông tin bot sau khi cập nhật
    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})

    return BotResponse(**updated_bot)


@router.delete("/{bot_id}/delete_user/{user_id}", response_model=BotResponse)
async def delete_user_permission_by_bot_id(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
    user_id: str,
):
    bots_collection = get_db().get_collection("bots")

    existing_bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {
                    "user_id": str(current_user.id),
                    "permissions": {"$in": [PermissionEnum.write_user]},
                },
            },
        },
    )

    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found or you do not have permission to edit users",
        )

    if existing_bot.get("owner") == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't delete the bot owner",
        )

    # Loại bỏ user_permission khỏi list_user_permission
    update_result = await bots_collection.update_one(
        {"_id": ObjectId(bot_id)},
        {"$pull": {"list_user_permission": {"user_id": user_id}}},
    )

    if update_result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found in bot's user permissions",
        )

    # Lấy lại thông tin bot sau khi cập nhật
    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})

    return BotResponse(**updated_bot)


@router.get("/{bot_id}/list_file", response_model=ListDataResponse[FileSchema])
async def get_list_file(
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
    bots_collection = get_db().get_collection("bots")
    files_collection = get_db().get_collection("files")

    # Kiểm tra xem bot có tồn tại và người dùng hiện tại có quyền xem file hay không
    existing_bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {
                    "user_id": str(current_user.id),
                    "permissions": {"$in": [PermissionEnum.read_file]},
                },
            },
        },
    )

    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found or you does not have permission to edit files",
        )

    total_files = await files_collection.count_documents(
        {
            "_id": {
                "$in": [
                    ObjectId(file_id) for file_id in existing_bot.get("list_files")
                ],
            },
        },
    )

    pipeline = [
        {
            "$match": {
                "_id": {
                    "$in": [
                        ObjectId(file_id)
                        for file_id in existing_bot.get("list_files", [])
                    ],
                }
            }
        },
        {
            "$group": {
                "_id": None,
                "total_size": {"$sum": "$size"},  # Tổng kích thước
            }
        },
    ]

    result = await files_collection.aggregate(pipeline).to_list(length=1)
    total_size = result[0]["total_size"] if result else 0

    pipeline = [
        {
            "$match": {
                "_id": {
                    "$in": [
                        ObjectId(file_id) for file_id in existing_bot.get("list_files")
                    ],
                },
            },
        },
        {"$addFields": {"owner": {"$toObjectId": "$owner"}}},
        {
            "$lookup": {
                "from": "users",
                "localField": "owner",
                "foreignField": "_id",
                "as": "owner_info",
            },
        },
        {
            "$unwind": {
                "path": "$owner_info",
                "preserveNullAndEmptyArrays": True,
            },
        },
        {"$skip": (page - 1) * size_page},
        {"$limit": size_page},
    ]

    files_data = await files_collection.aggregate(pipeline).to_list(length=None)

    return ListDataResponse(
        total=total_files,
        data=[FileSchema(**file) for file in files_data],
        capacity=total_size,
    )


@router.post("/{bot_id}/upload_files", response_model=BotResponse)
async def upload_files_to_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
    files: List[UploadFile] = File(...),
):
    bots_collection = get_db().get_collection("bots")
    packages_collection = get_db().get_collection("packages")
    files_collection = get_db().get_collection("files")
    orders_collection = get_db().get_collection("orders")
    # Kiểm tra xem bot có tồn tại và người dùng hiện tại có quyền xóa file hay không
    existing_bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {
                    "user_id": str(current_user.id),
                    "permissions": {"$in": [PermissionEnum.write_file]},
                },
            },
        },
    )
    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found or you does not have permission to edit files",
        )

    inserted_file_ids = []

    for file in files:
        inserted_file = await insert_file(file=file, user_id=current_user.id)
        inserted_file_ids.append(inserted_file.id)

    # Thêm file vào bot
    update_result = await bots_collection.update_one(
        {"_id": ObjectId(bot_id)},
        {"$push": {"list_files": {"$each": inserted_file_ids}}},
    )

    if update_result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update the bot",
        )

    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})

    return BotResponse(**updated_bot)


@router.post("/{bot_id}/add_files", response_model=BotResponse)
async def add_files_to_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
    file_ids: List[str] = Body(...),  # Nhận danh sách file_ids
):
    bots_collection = get_db().get_collection("bots")
    packages_collection = get_db().get_collection("packages")
    files_collection = get_db().get_collection("files")
    orders_collection = get_db().get_collection("orders")

    existing_bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {
                    "user_id": str(current_user.id),
                    "permissions": {"$in": [PermissionEnum.write_file]},
                },
            },
        },
    )
    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found or you do not have permission to edit files",
        )

    update_result = await bots_collection.update_one(
        {"_id": ObjectId(bot_id)},
        {"$push": {"list_files": {"$each": file_ids}}},
    )

    if update_result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update the bot",
        )

    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})
    return BotResponse(**updated_bot)


@router.put("/{bot_id}/delete_files", response_model=BotResponse)
async def remove_list_files_from_bot(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
    list_files: List[str],
):
    bots_collection = get_db().get_collection("bots")

    # Kiểm tra xem bot có tồn tại và người dùng hiện tại có quyền xóa file hay không
    existing_bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {
                    "user_id": str(current_user.id),
                    "permissions": {"$in": [PermissionEnum.write_file]},
                },
            },
        },
    )

    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found or you does not have permission to edit files",
        )

    # Xóa các file từ bot
    update_result = await bots_collection.update_one(
        {"_id": ObjectId(bot_id)},
        {"$pull": {"list_files": {"$in": list_files}}},
    )

    if update_result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể cập nhật bot",
        )

    updated_bot = await bots_collection.find_one({"_id": ObjectId(bot_id)})

    return BotResponse(**updated_bot)


@router.get("/{bot_id}/list_chat", response_model=ListDataResponse[ChatHistory])
async def get_list_chat_histories(
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
    chats_collection = db.get_collection("chat_histories")

    # Kiểm tra xem bot có tồn tại và người dùng hiện tại có quyền xem file hay không
    existing_bot = await bots_collection.find_one(
        {
            "_id": ObjectId(bot_id),
            "list_user_permission": {
                "$elemMatch": {
                    "user_id": str(current_user.id),
                },
            },
        },
    )

    if not existing_bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found or you does not have permission to edit files",
        )

    bot = Bot(**existing_bot)

    total_chats = await chats_collection.count_documents(
        {
            "bot_id": bot.id,
            "user_id": current_user.id,
        },
    )

    chats_data = (
        await chats_collection.find(
            {
                "bot_id": bot.id,
                "user_id": current_user.id,
            },
        )
        .skip((page - 1) * size_page)
        .limit(size_page)
        .to_list(length=None)
    )
    logging.info(f"Data: {chats_data}")
    return ListDataResponse(
        total=total_chats,
        data=[ChatHistory(**chat) for chat in chats_data],
    )


@router.delete("/{bot_id}/delete_chat/{chat_id}")
async def get_list_chat_histories(
    current_user: Annotated[User, Depends(get_current_active_user)],
    bot_id: str,
    chat_id: str,
    page: int = Query(Pagination.PAGE_DEFAULT, ge=1, description="Page number"),
    size_page: int = Query(
        Pagination.SIZE_PAGE_DEFAULT,
        ge=1,
        le=20,
        description="Page size",
    ),
):
    db = get_db()
    chats_collection = db.get_collection("chat_histories")

    deleted_resulte = await chats_collection.delete_one(
        {
            "_id": ObjectId(chat_id),
            "bot_id": bot_id,
            "user_id": current_user.id,
        },
    )
    if deleted_resulte.deleted_count > 0:
        return {"detail": "Deleted chat history successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete chat history",
        )
