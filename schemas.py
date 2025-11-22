"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# Customers, Orders, and Order Items for transactional CRUD

class Customer(BaseModel):
    """
    Customers collection schema
    Collection name: "customer"
    """
    name: str = Field(..., description="Customer full name")
    email: str = Field(..., description="Unique email")
    phone: Optional[str] = Field(None, description="Phone number")
    address: Optional[str] = Field(None, description="Mailing address")
    note: Optional[str] = Field(None, description="Internal note")

class OrderItem(BaseModel):
    """Embedded schema for items inside an order"""
    name: str = Field(..., description="Item name/description")
    quantity: int = Field(..., ge=1, description="Quantity of the item")
    unit_price: float = Field(..., ge=0, description="Unit price")
    discount_percent: float = Field(0, ge=0, le=100, description="Discount percent applied to this item (0-100)")

class Order(BaseModel):
    """
    Orders collection schema
    Collection name: "order"
    """
    customer_id: str = Field(..., description="Reference to customer _id as string")
    status: str = Field("Pending", description="Order status: Pending, Paid, Shipped, Cancelled")
    order_discount_percent: float = Field(0, ge=0, le=100, description="Discount percent applied to whole order")
    items: List[OrderItem] = Field(default_factory=list, description="List of order items")
    subtotal: float = Field(0, ge=0, description="Calculated subtotal before order-level discount")
    discount_total: float = Field(0, ge=0, description="Total discount amount (items + order)")
    total: float = Field(0, ge=0, description="Final order total after discounts")

# Example schemas retained (not used by app but kept for reference)
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True

# The Flames database viewer can read these schemas via /schema endpoint
