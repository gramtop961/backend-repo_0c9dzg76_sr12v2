import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt

from database import db, create_document, get_documents, get_document_by_id, update_document, delete_document
from schemas import AdminUser, Book, Order, OrderItem

# Security settings
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
# Use pbkdf2_sha256 to avoid bcrypt backend issues in some environments
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------- Auth Models -------------------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminProfile(BaseModel):
    id: str
    name: str
    email: str
    role: str


# ------------------------- Helpers ----------------------------
from bson import ObjectId

def _admin_collection():
    return db["adminuser"]

def _book_collection():
    return db["book"]

def _order_collection():
    return db["order"]


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    # simple token without exp for brevity in this environment
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_admin(token: str = Depends(lambda authorization: authorization)):
    # Placeholder for future auth enforcement
    return token


# ------------------------- Seed Admin -------------------------
@app.on_event("startup")
async def ensure_admin_exists():
    # Create a default admin if none exists
    if _admin_collection().count_documents({}) == 0:
        default = AdminUser(
            name="Admin",
            email="admin@example.com",
            password_hash=pwd_context.hash("admin123"),
            role="admin",
        )
        create_document("adminuser", default)


# ------------------------- Basic Routes -----------------------
@app.get("/")
def root():
    return {"message": "Bookstore Admin API"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# ------------------------- Auth Endpoints ---------------------
class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    token: str
    profile: AdminProfile

@app.post("/auth/login", response_model=LoginResponse)
def admin_login(payload: LoginRequest):
    user = _admin_collection().find_one({"email": payload.email})
    if not user or not pwd_context.verify(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="User is inactive")
    role = user.get("role", "staff")
    if role not in ("admin", "staff"):
        raise HTTPException(status_code=403, detail="Unauthorized role")
    token = create_access_token({"sub": str(user["_id"]), "role": role})
    profile = AdminProfile(id=str(user["_id"]), name=user.get("name", ""), email=user.get("email", ""), role=role)
    return LoginResponse(token=token, profile=profile)


# ------------------------- Dashboard Widgets ------------------
class DashboardStats(BaseModel):
    total_books: int
    total_orders: int
    pending_orders: int
    revenue: float

@app.get("/admin/stats", response_model=DashboardStats)
def get_admin_stats():
    total_books = _book_collection().count_documents({})
    total_orders = _order_collection().count_documents({})
    pending_orders = _order_collection().count_documents({"status": "pending"})
    # revenue sum of total_amount for orders with status not cancelled
    pipeline = [
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$group": {"_id": None, "sum": {"$sum": "$total_amount"}}}
    ]
    agg = list(_order_collection().aggregate(pipeline))
    revenue = float(agg[0]["sum"]) if agg else 0.0
    return DashboardStats(total_books=total_books, total_orders=total_orders, pending_orders=pending_orders, revenue=revenue)


# ------------------------- Books CRUD -------------------------
class BookCreate(Book):
    pass

class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None

@app.get("/books")
def list_books():
    books = get_documents("book", sort=[["created_at", -1]])
    for b in books:
        b["id"] = str(b.pop("_id"))
    return books

@app.post("/books")
def create_book(payload: BookCreate):
    new_id = create_document("book", payload)
    doc = get_document_by_id("book", new_id)
    doc["id"] = str(doc.pop("_id"))
    return doc

@app.get("/books/{book_id}")
def get_book(book_id: str):
    doc = get_document_by_id("book", book_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Book not found")
    doc["id"] = str(doc.pop("_id"))
    return doc

@app.put("/books/{book_id}")
def update_book(book_id: str, payload: BookUpdate):
    updated = update_document("book", book_id, {k: v for k, v in payload.model_dump().items() if v is not None})
    if not updated:
        raise HTTPException(status_code=404, detail="Book not found or no changes")
    doc = get_document_by_id("book", book_id)
    doc["id"] = str(doc.pop("_id"))
    return doc

@app.delete("/books/{book_id}")
def delete_book(book_id: str):
    ok = delete_document("book", book_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"status": "deleted"}


# ------------------------- Orders -----------------------------
class OrderCreate(BaseModel):
    customer_name: str
    customer_email: str
    items: List[OrderItem]
    notes: Optional[str] = None

@app.get("/orders")
def list_orders():
    orders = get_documents("order", sort=[["created_at", -1]])
    for o in orders:
        o["id"] = str(o.pop("_id"))
    return orders

@app.post("/orders")
def create_order(payload: OrderCreate):
    # compute total from items
    total = sum(i.price * i.quantity for i in payload.items)
    order = Order(
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        items=payload.items,
        total_amount=total,
        status="pending",
        notes=payload.notes,
    )
    new_id = create_document("order", order)
    doc = get_document_by_id("order", new_id)
    doc["id"] = str(doc.pop("_id"))
    return doc

class OrderStatusUpdate(BaseModel):
    status: str

@app.put("/orders/{order_id}/status")
def update_order_status(order_id: str, payload: OrderStatusUpdate):
    allowed = {"pending", "processing", "shipped", "delivered", "cancelled"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid status")
    ok = update_document("order", order_id, {"status": payload.status})
    if not ok:
        raise HTTPException(status_code=404, detail="Order not found")
    doc = get_document_by_id("order", order_id)
    doc["id"] = str(doc.pop("_id"))
    return doc


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
