from datetime import datetime
from typing import Annotated, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from server.config.mongodb import get_db
from server.constants.common import Pagination
from server.services.auth import get_current_active_admin
from server.types.common import ListDataResponse, User
from server.web.api.chat_history.schema import ChatMessage
from server.web.api.file.schema import FileSchema
from server.web.api.user.schema import UserResponse

from .schema import OrderResponse

router = APIRouter()


@router.get("/message", response_model=ListDataResponse[ChatMessage])
async def get_messages(
    current_admin: Annotated[User, Depends(get_current_active_admin)],
    start_date: Optional[datetime] = Query(
        None,
        description="Start date to filter messages",
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="End date to filter messages",
    ),
):
    db = get_db()
    messages_collection = db.get_collection("chat_messages")

    query = {}

    if start_date and end_date:
        query["created_at"] = {"$gte": start_date, "$lt": end_date}
    elif start_date:
        query["created_at"] = {"$gte": start_date}
    elif end_date:
        query["created_at"] = {"$lt": end_date}

    messages = await messages_collection.find(query).to_list(length=None)

    return ListDataResponse(
        total=len(messages),
        data=[ChatMessage(**message) for message in messages],
    )


@router.get("/user", response_model=ListDataResponse[UserResponse])
async def get_users(
    current_admin: Annotated[User, Depends(get_current_active_admin)],
    page: int = Query(Pagination.PAGE_DEFAULT, ge=1, description="Page number"),
    size_page: int = Query(
        Pagination.SIZE_PAGE_DEFAULT,
        ge=1,
        le=20,
        description="Page size",
    ),
):
    db = get_db()
    users_collection = db.get_collection("users")
    orders_collection = db.get_collection("orders")
    packages_collection = db.get_collection("packages")

    search_filter = {}

    total_users = await users_collection.count_documents(search_filter)

    users_data = (
        await users_collection.find(search_filter)
        .skip((page - 1) * size_page)
        .limit(size_page)
        .to_list(length=None)
    )

    user_responses = []

    for user in users_data:
        latest_order = await orders_collection.find_one(
            {"user_id": user["_id"]},
            sort=[("order_date", -1)],
        )

        if latest_order:
            pack = await packages_collection.find_one(
                {"_id": ObjectId(latest_order["package_id"])},
            )
            
        else:
            pack = await packages_collection.find_one({"type": "PACKAGE_FREE"})
        pack["_id"] = str(pack["_id"])
        user_responses.append(UserResponse(**user, pack=pack))

    return ListDataResponse(
        total=total_users,
        data=user_responses,
    )


@router.delete("/user/{user_id}", response_model=dict)
async def delete_order(
    current_admin: Annotated[User, Depends(get_current_active_admin)],
    user_id: str,
):
    db = get_db()
    users_collection = db.get_collection("users")

    existing_user = await users_collection.find_one({"_id": ObjectId(user_id)})

    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await users_collection.delete_one({"_id": ObjectId(user_id)})

    return {"detail": "Order deleted successfully"}


@router.get("/file", response_model=ListDataResponse[FileSchema])
async def get_all_files(
    current_admin: Annotated[User, Depends(get_current_active_admin)],
    start_date: Optional[datetime] = Query(
        None,
        description="Start date to filter files",
    ),
    end_date: Optional[datetime] = Query(None, description="End date to filter files"),
    page: int = Query(Pagination.PAGE_DEFAULT, ge=1, description="Page number"),
    size_page: int = Query(
        Pagination.SIZE_PAGE_DEFAULT,
        ge=1,
        le=20,
        description="Page size",
    ),
):
    try:
        files_collection = get_db().get_collection("files")

        filter_query = {}

        if start_date and end_date:
            filter_query["created_at"] = {"$gte": start_date, "$lt": end_date}
        elif start_date:
            filter_query["created_at"] = {"$gte": start_date}
        elif end_date:
            filter_query["created_at"] = {"$lt": end_date}

        total_files = await files_collection.count_documents(filter_query)

        files = (
            await files_collection.find(filter_query)
            .skip((page - 1) * size_page)
            .limit(size_page)
            .to_list(length=None)
        )

        total_size = sum(file['size'] for file in files) 

        return ListDataResponse(
            total=total_files,
            data=[FileSchema(**file) for file in files],
            capacity=total_size
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve files",
        )


@router.get("/order", response_model=ListDataResponse[OrderResponse])
async def get_orders_by_date(
    current_admin: Annotated[User, Depends(get_current_active_admin)],
    start_date: Optional[datetime] = Query(
        None,
        description="Start date to filter orders",
    ),
    end_date: Optional[datetime] = Query(None, description="End date to filter orders"),
    page: int = Query(Pagination.PAGE_DEFAULT, ge=1, description="Page number"),
    size_page: int = Query(
        Pagination.SIZE_PAGE_DEFAULT,
        ge=1,
        le=20,
        description="Page size",
    ),
):
    db = get_db()
    orders_collection = db.get_collection("orders")
    packages_collection = db.get_collection("packages")
    users_collection = db.get_collection("users")
    search_filter = {}

    if start_date and end_date:
        search_filter["order_date"] = {"$gte": start_date, "$lt": end_date}
    elif start_date:
        search_filter["order_date"] = {"$gte": start_date}
    elif end_date:
        search_filter["order_date"] = {"$lt": end_date}

    total_orders = await orders_collection.count_documents(search_filter)

    orders_data = (
        await orders_collection.find(search_filter)
        .skip((page - 1) * size_page)
        .limit(size_page)
        .to_list(length=None)
    )

    order_responses = []

    for order in orders_data:
        package = await packages_collection.find_one(
            {"_id": ObjectId(order["package_id"])},
        )
        user = await users_collection.find_one({"_id": ObjectId(order["user_id"])},)
        if user :
            order_responses.append(OrderResponse(**order, pack=package, user_info=UserResponse(**user)))
        else:
            order_responses.append(OrderResponse(**order, pack=package, user_info=None))

        

    return ListDataResponse(
        total=total_orders,
        data=order_responses,
    )


@router.delete("/order/{order_id}", response_model=dict)
async def delete_order(
    current_admin: Annotated[User, Depends(get_current_active_admin)],
    order_id: str,
):
    db = get_db()
    orders_collection = db.get_collection("orders")

    existing_order = await orders_collection.find_one({"_id": ObjectId(order_id)})

    if not existing_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    await orders_collection.delete_one({"_id": ObjectId(order_id)})

    return {"detail": "Order deleted successfully"}
