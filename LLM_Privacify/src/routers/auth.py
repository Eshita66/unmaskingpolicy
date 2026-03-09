from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from src.infrastructure.auth import ACCESS_TOKEN_EXPIRE_MINUTES, authenticate_user, create_access_token
from src.infrastructure.dependencies import get_db
from src.models.auth import Token
from src.models.user import User

router = APIRouter(
    prefix="/auth"
)

@router.post("/token")
async def login_for_access_token(*, form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db : Session = Depends(get_db)) -> Token:
    user = db.exec(select(User).where(User.email==form_data.username)).one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = authenticate_user(db=db, uid=user.id, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")
