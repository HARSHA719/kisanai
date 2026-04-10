from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from utils.database import get_db
from utils.security import get_password_hash, verify_password, create_access_token, decode_token
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId

router = APIRouter()

class UserCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = "Farmer"

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/register")
def register(user: UserCreate):
    db = get_db()
    if db.users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = {
        "email": user.email,
        "password": hashed_password,
        "name": user.name,
        "created_at": datetime.now(timezone.utc)
    }
    result = db.users.insert_one(new_user)
    
    token = create_access_token({"sub": str(result.inserted_id), "email": user.email})
    return {"message": "User created effectively", "token": token, "name": user.name}

@router.post("/login")
def login(user: UserLogin):
    db = get_db()
    db_user = db.users.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token({"sub": str(db_user["_id"]), "email": user.email})
    return {"message": "Login successful", "token": token, "name": db_user.get("name", "Farmer")}

@router.get("/me")
def get_me(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authorized")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    db = get_db()
    user = db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"email": user["email"], "name": user.get("name", "Farmer"), "id": str(user["_id"])}

@router.get("/history")
def get_user_history(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authorized")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    db = get_db()
    history = list(db.history.find({"user_id": payload["sub"]}).sort("timestamp", -1))
    
    for item in history:
        item["_id"] = str(item["_id"])
        
    return {"history": history}
