from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from server.config.logging import logging
from server.config.mongodb import get_db
from server.services.auth import get_current_active_user
from server.types.common import ListDataResponse, User

from .schema import Notification

router = APIRouter()


@router.get("/", response_model=ListDataResponse[Notification])
async def get_notifications(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    db = get_db()
    notification_collection = db.get_collection("notifications")
    total_notifications = await notification_collection.count_documents(
        {"receiver": current_user.id},
    )
    existing_notifications = await notification_collection.find(
        {"receiver": current_user.id},
    ).to_list(length=None)

    return ListDataResponse(
        total=total_notifications,
        data=[Notification(**notification) for notification in existing_notifications],
    )


@router.delete("/{notification_id}", response_model=dict)
async def delete_notification(
    current_user: Annotated[User, Depends(get_current_active_user)],
    notification_id,
):
    db = get_db()
    notification_collection = db.get_collection("notifications")
    notification_result = await notification_collection.delete_one(
        {"_id": ObjectId(notification_id), "receiver": current_user.id},
    )

    if notification_result.deleted_count > 0:
        return {
            "detail": "Delete notification successfully",
        }

    else:
        logging.error(f"Error: Could not delete the notification")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete the notification",
        )


@router.post("/{notification_id}/read", response_model=dict)
async def read_notification(
    current_user: Annotated[User, Depends(get_current_active_user)],
    notification_id,
):
    db = get_db()
    notification_collection = db.get_collection("notifications")
    notification_result = await notification_collection.update_one(
        {"_id": ObjectId(notification_id), "receiver": current_user.id},
        {"$set": {"read": True}},
    )

    if notification_result.matched_count > 0:
        return {
            "detail": "Read notification successfully",
        }

    else:
        logging.error(f"Error: Could not read the notification")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read the notification",
        )
