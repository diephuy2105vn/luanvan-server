import os
from typing import Annotated, List

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
from pymongo.collection import Collection

from server.config.logging import logging
from server.config.mongodb import get_db
from server.constants.common import Pagination
from server.services.auth import get_current_active_user
from server.services.file_service import (
    delete_file_by_file_id,
    get_docs_by_file_id,
    insert_file,
)
from server.types.common import ListDataResponse, User

from .schema import Doc
from .schema import FileResponse as FileResSchema
from .schema import FileSchema

router = APIRouter()


@router.get("/", response_model=ListDataResponse[FileSchema])
async def get_files(
    current_user: Annotated[User , Depends(get_current_active_user)],
    page: int = Query(Pagination.PAGE_DEFAULT, ge=1, description="Page number"),
    size_page: int = Query( 
        Pagination.SIZE_PAGE_DEFAULT,
        ge=1,
        le=20,
        description="Page size",
    ),
    name: str = Query(None, description="Name of the file to search for") 
):
    try:
        files_collection: Collection = get_db().get_collection("files")

        search_query = {
            "owner": current_user.id,
            "disabled": False,
        }

       
        if name:
            search_query["name"] = {"$regex": name, "$options": "i"}  

        total_files = await files_collection.count_documents(search_query)

        pipeline = [
            {
                "$match": search_query,
            },
            {
                "$group": {
                    "_id": None,
                    "total_size": {"$sum": "$size"},
                },
            },
        ]
        result = await files_collection.aggregate(pipeline).to_list(length=1)
        total_size = result[0]["total_size"] if result else 0

        files = (
            await files_collection.find(search_query)
            .skip((page - 1) * size_page)
            .limit(size_page)
            .to_list(length=None)
        )
        return ListDataResponse(
            total=total_files,
            data=[FileSchema(**file) for file in files],
            capacity=total_size,
        )
    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve files",
        )


@router.get("/deleted", response_model=ListDataResponse[FileSchema])
async def get_files(
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(Pagination.PAGE_DEFAULT, ge=1, description="Page number"),
    size_page: int = Query(
        Pagination.SIZE_PAGE_DEFAULT,
        ge=1,
        le=20,
        description="Page size",
    ),
):
    try:
        files_collection: Collection = get_db().get_collection("files")
        total_files = await files_collection.count_documents(
            {"owner": current_user.id, "disabled": True},
        )

        pipeline = [
            {
                "$match": {
                    "owner": current_user.id,
                    "disabled": True,
                },
            },
            {
                "$group": {
                    "_id": None,
                    "total_size": {"$sum": "$size"},
                },
            },
        ]

        result = await files_collection.aggregate(pipeline).to_list(length=1)
        total_size = result[0]["total_size"] if result else 0

        files = (
            await files_collection.find({"owner": current_user.id, "disabled": True})
            .skip((page - 1) * size_page)
            .limit(size_page)
            .to_list(length=None)
        )
        return ListDataResponse(
            total=total_files,
            data=[FileSchema(**file) for file in files],
            capacity=total_size,
        )
    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve files",
        )


@router.get("/{file_id}")
async def get_file(
    current_user: Annotated[User, Depends(get_current_active_user)],
    file_id,
):
    try:
        files_collection: Collection = get_db().get_collection("files")
        file = await files_collection.find_one(
            {"owner": current_user.id, "_id": ObjectId(file_id)},
        )
        # docs = get_docs_by_file_id(file_id)
        file_res = FileResSchema(**file)
        return file_res
    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve files",
        )


@router.get("/download/{file_id}", response_class=FileResponse)
async def download_file(
    current_user: Annotated[User, Depends(get_current_active_user)],
    file_id,
):
    try:
        files_collection: Collection = get_db().get_collection("files")
        existing_file = await files_collection.find_one(
            {"owner": current_user.id, "_id": ObjectId(file_id)},
        )

        if not existing_file or not os.path.isfile(existing_file.get("path")):
            raise HTTPException(status_code=404, detail="File not found")
        file_data = FileSchema(**existing_file)
        return FileResponse(
            file_data.path,
            filename=f"{file_data.name}.{file_data.extension}",
        )
    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve files",
        )


@router.post("/", response_model=List[FileSchema])
async def upload_files(
    current_user: Annotated[User, Depends(get_current_active_user)],
    files: List[UploadFile] = File(...),
):
    
    inserted_files = []

    for file in files:
        inserted_file = await insert_file(file=file, user_id=current_user.id)
        inserted_files.append(inserted_file)

    return inserted_files


@router.post("/restore/{file_id}", response_model=dict)
async def delete_files(
    current_user: Annotated[User, Depends(get_current_active_user)],
    file_id: str,
):
    try:
        files_collection = get_db().get_collection("files")
        update_result = await files_collection.update_one(
            {
                "_id": ObjectId(file_id),
                "owner": current_user.id,
            },
            {"$set": {"disabled": False}},
        )

        if update_result.modified_count > 0:
            return {
                "detail": f"Restore {update_result.modified_count} files successfully",
            }
        else:
            return {"detail": "No file restore"}

    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad request",
        )


@router.delete("/list_id", response_model=dict)
async def delete_files(
    current_user: Annotated[User, Depends(get_current_active_user)],
    list_id: List[str] = Body(...),
):
    try:
        files_collection = get_db().get_collection("files")
        update_result = await files_collection.update_many(
            {
                "_id": {"$in": [ObjectId(file_id) for file_id in list_id]},
                "owner": current_user.id,
            },
            {"$set": {"disabled": True}},
        )

        if update_result.modified_count > 0:
            return {
                "detail": f"Delete {update_result.modified_count} files successfully",
            }
        else:
            return {"detail": "No file were deleted"}

    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad request",
        )


@router.delete("/hard_delete/list_id", response_model=dict)
async def hard_delete_files(
    current_user: Annotated[User, Depends(get_current_active_user)],
    list_id: List[str] = Body(...),
):
    try:
        bots_collection = get_db().get_collection("bots")
        for file_id in list_id:
            result = await delete_file_by_file_id(file_id, user_id=current_user.id)
            if result:
                await bots_collection.update_many(
                    {
                        "owner": current_user.id,
                    },
                    {"$pull": {"list_files": file_id}},
                )
            else:
                raise Exception(f"Could not delete file with ID: {file_id}")

        return {"detail": "Files deleted successfully"}
    except Exception as e:
        logging.error(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad request",
        )
