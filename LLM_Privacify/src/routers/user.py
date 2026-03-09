from typing import Annotated, List
from bcrypt import gensalt

from fastapi import APIRouter, Depends

from langchain_community.document_loaders import WebBaseLoader
from requests import Session

from src.infrastructure.auth import get_current_active_user, get_password_hash
from src.infrastructure.dependencies import get_db


from ..models.user import *

router = APIRouter(
    prefix="/user"
)

@router.get("/me", response_model=UserRead)
async def get_user(user: Annotated[User, Depends(get_current_active_user)]):
    return user

@router.post("/", response_model=UserReadShort)
async def create_user(*, create_user : UserCreate, db : Session = Depends(get_db)):
    salt = str(gensalt())

    hashed_password = get_password_hash(create_user.password, salt)
    db_user = User(
        id=None,
        name=create_user.name,
        email=create_user.email,
        disabled=False,
        email_verified=False,
        hashed_password=hashed_password,
        salt=salt
    )

    db_user = User.model_validate(db_user)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user