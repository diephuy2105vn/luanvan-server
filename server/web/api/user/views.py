import os
from datetime import timedelta, datetime
from typing import Annotated, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from server.config.logging import logging
from server.config.mongodb import get_db
from server.constants.common import Pagination
from server.services.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_password_hash,
    get_user,
)
from server.types.common import ListDataResponse, Token, User
from .schema import UserRegister, UserResponse, UserUpdate, UserPackageInfo

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    try:
        user = await authenticate_user(form_data.username, form_data.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"username": user.username, "role": user.role},
            expires_delta=access_token_expires,
        )

        return Token(access_token=access_token, token_type="bearer")
    except HTTPException as httpE:
        raise httpE
    except Exception as e:
        logging.error(f"Error: {e}")


@router.post("/register", response_model=UserResponse)
async def register(
    user_register: UserRegister = Body(...),
):
    try:
        user = await get_user(user_register.username)

        if user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User is not authorized",
                headers={"WWW-Authenticate": "Bearer"},
            )
        hashed_password = get_password_hash(user_register.password)
        users_collection = get_db().get_collection("users")
        # Tạo dictionary từ user_register và cập nhật trường password
        user_data = user_register.model_dump()
        user_data["password"] = hashed_password
        new_user = User(**user_data)
        user_result = await users_collection.insert_one(
            new_user.model_dump(by_alias=True, exclude=["id"]),
        )
        user_inserted = await users_collection.find_one(
            {"_id": user_result.inserted_id},
        )

        return UserResponse(**user_inserted)

    except HTTPException as httpE:
        raise httpE
    except Exception as e:
        logging.error(f"Error: {e}")


@router.get("/refresh", response_model=UserResponse)
async def refresh(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    user_data = current_user.model_dump()
    user_data["_id"] = user_data.get("id")
    return UserResponse(**user_data)


class UserQueryParams(BaseModel):
    username: Optional[str] = None


@router.get("/", response_model=ListDataResponse[UserResponse])
async def get_users(
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(Pagination.PAGE_DEFAULT, ge=1, description="Page number"),
    size_page: int = Query(
        Pagination.SIZE_PAGE_DEFAULT,
        ge=1,
        le=20,
        description="Page size",
    ),
    params: UserQueryParams = Depends(),
):

    db = get_db()
    users_collection = db.get_collection("users")

    search_filter = {}
    if params.username:
        search_filter["username"] = params.username

    total_users = await users_collection.count_documents(search_filter)

    users_data = (
        await users_collection.find(search_filter)
        .skip((page - 1) * size_page)
        .limit(size_page)
        .to_list(length=None)
    )

    return ListDataResponse(
        total=total_users,
        data=[UserResponse(**user) for user in users_data],
    )


@router.put("/", response_model=UserResponse)
async def update_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
    user_update: UserUpdate,
):

    db = get_db()
    users_collection = db.get_collection("users")

    updated_data = {k: v for k, v in user_update.model_dump().items() if v is not None}

    await users_collection.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": updated_data},
    )

    updated_user = await users_collection.find_one({"_id": ObjectId(current_user.id)})
    return UserResponse(**updated_user)


@router.put("/upload_avatar", response_model=UserResponse)
async def upload_avatar(
    current_user: Annotated[User, Depends(get_current_active_user)],
    avatar: UploadFile = File(...),
):
    logging.info("Uploading avatar")

    save_dir = os.path.join("server/stores/user/")
    os.makedirs(save_dir, exist_ok=True)

    # Xóa avatar cũ nếu tồn tại
    if current_user.avatar_source:
        old_avatar_path = current_user.avatar_source
        if os.path.exists(old_avatar_path):
            os.remove(old_avatar_path)

    # Tạo tên file ngẫu nhiên dựa trên UUID
    filename = f"{uuid4()}.jpg"
    file_path = os.path.join(save_dir, filename)

    # Lưu file ảnh mới
    with open(file_path, "wb") as f:
        f.write(await avatar.read())

    current_user.avatar_source = file_path

    users_collection = get_db().get_collection("users")
    await users_collection.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"avatar_source": file_path}},
    )

    user_data = current_user.model_dump()
    user_data["_id"] = user_data.get("id")
    return UserResponse(**user_data)


@router.get("/{user_id}/avatar", response_class=FileResponse)
async def get_avatar(user_id: str):
    users_collection = get_db().get_collection("users")
    user = await users_collection.find_one({"_id": ObjectId(user_id)})

    if not user or not user.get("avatar_source"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        )

    avatar_source = user["avatar_source"]

    # Kiểm tra nếu file avatar tồn tại
    if not os.path.exists(avatar_source):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar file not found",
        )

    return FileResponse(avatar_source)


@router.get("/package_info", response_model=UserPackageInfo)
async def get_package_info(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    db = get_db()
    order_collection = db.get_collection("orders")
    package_collection = db.get_collection("packages")

    today = datetime.now()

    latest_order = await order_collection.find_one(
        {
            "user_id": current_user.id,
            "expiration_date": {"$gte": today},
        },
        sort=[("order_date", -1)],
    )

    if not latest_order:
        free_package = await package_collection.find_one({"type": "PACKAGE_FREE"})
        if not free_package:
            raise HTTPException(status_code=404, detail="Free package not found")

        return UserPackageInfo(
            pack=free_package,
            registration_date=None,
            expiration_date=None,
            price=free_package.get("price", 0),  # Nếu package có giá trị price
        )

    existing_package = await package_collection.find_one(
        {"_id": ObjectId(latest_order["package_id"])}
    )
    if not existing_package:
        raise HTTPException(status_code=404, detail="Package not found")

    pack_info = UserPackageInfo(
        pack=existing_package,
        registration_date=latest_order["order_date"],
        expiration_date=latest_order["expiration_date"],
        price=latest_order.get("price"),
    )

    return pack_info


@router.post("/buy_package/{package_id}", response_model=dict)
async def buy_package(
    current_user: Annotated[User, Depends(get_current_active_user)], package_id: str
):
    db = get_db()
    package_collection = db.get_collection("packages")
    order_collection = db.get_collection("orders")

    existing_pack = await package_collection.find_one({"_id": ObjectId(package_id)})
    if not existing_pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )

    today = datetime.now()
    expiration_date = today + timedelta(days=30)

    order_info = {
        "user_id": current_user.id,
        "package_id": package_id,
        "order_date": today,
        "expiration_date": expiration_date,
        "price": existing_pack.get("price", 0),
    }

    await order_collection.insert_one(order_info)

    return {"detail": "Buy package successfully"}
