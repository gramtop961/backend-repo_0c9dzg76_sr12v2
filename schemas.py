"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- AdminUser -> "adminuser" collection
- Book -> "book" collection
- Order -> "order" collection
"""

from pydantic import BaseModel, Field, EmailStr, conlist
from typing import Optional, List, Literal

class AdminUser(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: str = Field(..., description="BCrypt hash of the password")
    role: Literal["admin", "staff"] = Field("admin", description="Role for access control")
    is_active: bool = Field(True, description="Whether user is active")

class Book(BaseModel):
    title: str = Field(..., description="Book title")
    author: str = Field(..., description="Author name")
    price: float = Field(..., ge=0, description="Price")
    stock: int = Field(0, ge=0, description="Stock count")
    description: Optional[str] = Field(None, description="Description")
    cover_url: Optional[str] = Field(None, description="Cover image URL")

class OrderItem(BaseModel):
    book_id: str = Field(..., description="Referenced Book _id as string")
    title: str = Field(..., description="Snapshot of book title")
    price: float = Field(..., ge=0, description="Unit price at time of order")
    quantity: int = Field(..., ge=1, description="Quantity ordered")

class Order(BaseModel):
    customer_name: str = Field(..., description="Customer name")
    customer_email: EmailStr = Field(..., description="Customer email")
    items: conlist(OrderItem, min_length=1) = Field(..., description="Ordered items")
    total_amount: float = Field(..., ge=0, description="Computed total amount")
    status: Literal["pending", "processing", "shipped", "delivered", "cancelled"] = Field("pending", description="Order status")
    notes: Optional[str] = Field(None, description="Optional notes")
