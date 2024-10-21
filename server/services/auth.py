from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from server.config.logging import logging
from server.config.mongodb import get_db
from server.types.common import TokenData, User

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def get_user(username: str):

    user_collection = get_db().get_collection("users")
    user = await user_collection.find_one({"username": username})
    if user is None:
        return None
    else:
        return User(**user)


async def authenticate_user(username: str, password: str):
    user = await get_user(username)

    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    try:
        to_encode = data.copy()
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        return encoded_jwt
    except Exception as e:
        logging.error(f"Error: {e}")
        return None


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception

        token_data = TokenData(username=username, role=role)
    except Exception as e:
        logging.error(f"Error: {e}")
        raise e
    user = await get_user(username=token_data.username)

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):

    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")

    return current_user


async def get_current_active_admin(
    current_user: Annotated[User, Depends(get_current_user)],
):
    if current_user.role != "admin" or current_user.disabled:
        raise HTTPException(status_code=400, detail="Permission denied")
    return current_user
