"""
Database Helper Functions

MongoDB helper functions ready to use in your backend code.
Import and use these functions in your API endpoints for database operations.
"""

from pymongo import MongoClient
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from typing import Union, Optional, Dict, Any
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

_client = None
db = None

database_url = os.getenv("DATABASE_URL")
database_name = os.getenv("DATABASE_NAME")

if database_url and database_name:
    _client = MongoClient(database_url)
    db = _client[database_name]

# Helper functions for common database operations
def _ensure_db():
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")


def create_document(collection_name: str, data: Union[BaseModel, dict]):
    """Insert a single document with timestamp"""
    _ensure_db()

    # Convert Pydantic model to dict if needed
    if isinstance(data, BaseModel):
        data_dict = data.model_dump()
    else:
        data_dict = data.copy()

    now = datetime.now(timezone.utc)
    data_dict['created_at'] = now
    data_dict['updated_at'] = now

    result = db[collection_name].insert_one(data_dict)
    return str(result.inserted_id)


def get_documents(collection_name: str, filter_dict: Optional[dict] = None, limit: Optional[int] = None, sort: Optional[list] = None):
    """Get documents from collection"""
    _ensure_db()
    cursor = db[collection_name].find(filter_dict or {})
    if sort:
        cursor = cursor.sort(sort)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def get_document_by_id(collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """Get a single document by _id string"""
    _ensure_db()
    from bson import ObjectId
    try:
        return db[collection_name].find_one({"_id": ObjectId(doc_id)})
    except Exception:
        return None


def update_document(collection_name: str, doc_id: str, data: dict) -> bool:
    """Update a document by id with $set and updated_at"""
    _ensure_db()
    from bson import ObjectId
    data = data.copy()
    data['updated_at'] = datetime.now(timezone.utc)
    res = db[collection_name].update_one({"_id": ObjectId(doc_id)}, {"$set": data})
    return res.modified_count > 0


def delete_document(collection_name: str, doc_id: str) -> bool:
    """Delete a document by id"""
    _ensure_db()
    from bson import ObjectId
    res = db[collection_name].delete_one({"_id": ObjectId(doc_id)})
    return res.deleted_count > 0
