import os
import certifi
from pymongo import MongoClient

# Default to creating a local kisanai DB if MongoDB URI is missing
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/kisanai")

client = None

def get_db():
    global client
    if client is None:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsCAFile=certifi.where())
    # Return the target database 'kisanai' regardless of URI format
    return client["kisanai"]
    
def log_user_history(user_id: str, action: str, details: dict):
    if not user_id:
        return
    db = get_db()
    from datetime import datetime, timezone
    
    db.history.insert_one({
        "user_id": user_id,
        "action": action,
        "details": details,
        "timestamp": datetime.now(timezone.utc)
    })
