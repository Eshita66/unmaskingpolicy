from datetime import timedelta, timezone, datetime
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlmodel import Session, select
from jose import JWTError, jwt

from src.infrastructure.dependencies import get_db
from src.models.auth import TokenData
from src.models.user import User

#Place in ENVs
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password, salt):
    return pwd_context.hash(password + salt)


def get_user(*, db : Session = Depends(get_db), uid: str):
    user = db.exec(select(User).where(User.id==uid)).one_or_none()
    return user


def authenticate_user(*, db : Session = Depends(get_db), uid: str, password: str,):
    user = get_user(db=db, uid=uid)
    if user is None:
        return False
    if not verify_password(password+user.salt, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(*, db : Session = Depends(get_db), token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    print(token)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid: str = payload.get("sub")
        if uid is None:
            print("uid is none")
            raise credentials_exception
        token_data = TokenData(uid=uid)
    except JWTError as e:
        print("jwterror", e)
        raise credentials_exception
    user = get_user(db=db, uid=token_data.uid)
    if user is None:
        print("get user error")
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
