from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from server.config.logging import logging
from server.config.mongodb import get_db
from server.services.auth import get_current_active_admin, get_current_active_user
from server.types.common import ListDataResponse, User

from .schema import Package, PackageCreate, PackageUpdate

router = APIRouter()


@router.get("/", response_model=ListDataResponse[Package])
async def get_package():
    db = get_db()
    package_collection = db.get_collection("packages")
    total_pacekages = await package_collection.count_documents({})
    existing_pacekages = (
        await package_collection.find().sort("price", 1).to_list(length=None)
    )

    return ListDataResponse(
        total=total_pacekages,
        data=[Package(**package) for package in existing_pacekages],
    )


@router.post("/", response_model=Package)
async def read_notification(
    current_admin: Annotated[User, Depends(get_current_active_admin)],
    new_package: PackageCreate,
):
    db = get_db()
    package_collection = db.get_collection("packages")

    package_result = await package_collection.insert_one(
        new_package.model_dump(by_alias=True, exclude=["id"]),
    )

    package_inserted = await package_collection.find_one(
        {"_id": package_result.inserted_id},
    )

    return Package(**package_inserted)


@router.put("/{package_id}", response_model=Package)
async def update_package(
    package_id: str,
    package_update: PackageUpdate,
    current_admin: Annotated[User, Depends(get_current_active_admin)],
):
    db = get_db()
    package_collection = db.get_collection("packages")

    package = await package_collection.find_one({"_id": ObjectId(package_id)})
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    update_data = {
        k: v
        for k, v in package_update.model_dump(exclude_unset=True).items()
        if v is not None
    }

    if update_data:
        await package_collection.update_one(
            {"_id": ObjectId(package_id)},
            {"$set": update_data},
        )

    updated_package = await package_collection.find_one({"_id": ObjectId(package_id)})

    return Package(**updated_package)


@router.delete("/{package_id}", response_model=dict)
async def delete_package(
    current_admin: Annotated[User, Depends(get_current_active_admin)],
    package_id,
):
    db = get_db()
    package_collection = db.get_collection("packages")
    package_result = await package_collection.delete_one(
        {"_id": ObjectId(package_id)},
    )

    if package_result.deleted_count > 0:
        return {
            "detail": "Delete package successfully",
        }

    else:
        logging.error(f"Error: Could not delete the package")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not delete the package",
        )