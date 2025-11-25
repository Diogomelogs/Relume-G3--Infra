from datetime import datetime, timedelta
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

# ======= MONGO SETUP =======
MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI not configured")

mongo_client = MongoClient(MONGO_URI)

# ATENÇÃO:
# Troque "relume" pelo nome EXATO do seu banco NO MESMO FORMATO DO main.py
db = mongo_client["relume"]  
users_coll = db["users"]

# Índice de email único
users_coll.create_index("email", unique=True)

# ======= JWT CONFIG =======
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "relluna-secret")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.environ.get("JWT_EXPIRES_MINUTES", "1440"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter()

# ======= MODELOS =======

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ======= FUNÇÕES AUXILIARES =======

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRES_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def get_user_by_email(email: str) -> Optional[dict]:
    return users_coll.find_one({"email": email})

def get_user_by_id(user_id: str) -> Optional[dict]:
    from bson import ObjectId
    try:
        oid = ObjectId(user_id)
    except:
        return None
    return users_coll.find_one({"_id": oid})

# ======= AUTENTICAÇÃO DEPENDENCY =======

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_id(user_id)
    if not user:
        raise credentials_exception

    user["id"] = str(user["_id"])
    return user

# ======= ENDPOINT: REGISTER =======

@router.post("/register", response_model=UserOut, status_code=201)
def register(user_in: UserCreate):
    existing = get_user_by_email(user_in.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    hashed_pw = get_password_hash(user_in.password)

    doc = {
        "email": user_in.email,
        "password_hash": hashed_pw,
        "name": user_in.name,
        "created_at": datetime.utcnow()
    }

    try:
        result = users_coll.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    return UserOut(
        id=str(result.inserted_id),
        email=doc["email"],
        name=doc["name"]
    )

# ======= ENDPOINT: LOGIN =======

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Email ou senha inválidos")

    if not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Email ou senha inválidos")

    user_id = str(user["_id"])
    token = create_access_token({"sub": user_id})

    return Token(access_token=token)
