from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends

from server.services.auth import create_access_token, get_current_active_user
from server.types.common import Token, User

router = APIRouter()


@router.post("/", response_model=Token)
async def create_token(
    current_user: Annotated[User, Depends(get_current_active_user)],
    expires_delta: int,
):
    access_token_expires = timedelta(seconds=expires_delta)
    access_token = create_access_token(
        data={"username": current_user.username, "role": current_user.role},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")
