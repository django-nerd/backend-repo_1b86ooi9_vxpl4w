import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Customer, Order, OrderItem

app = FastAPI(title="Order Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers

def to_str_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def compute_totals(items: List[OrderItem], order_discount_percent: float) -> dict:
    subtotal = 0.0
    item_discount_total = 0.0
    for it in items:
        line_sub = it.quantity * it.unit_price
        line_discount = line_sub * (it.discount_percent / 100.0)
        subtotal += line_sub
        item_discount_total += line_discount
    after_item_discounts = subtotal - item_discount_total
    order_discount = after_item_discounts * (order_discount_percent / 100.0)
    total_discount = item_discount_total + order_discount
    total = after_item_discounts - order_discount
    return {
        "subtotal": round(subtotal, 2),
        "discount_total": round(total_discount, 2),
        "total": round(total, 2),
    }


# Public endpoints

@app.get("/")
def read_root():
    return {"name": "Order Management", "status": "ok"}


# Customers CRUD

@app.post("/customers")
def create_customer(customer: Customer):
    # ensure unique email
    existing = db["customer"].find_one({"email": customer.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    new_id = create_document("customer", customer)
    saved = db["customer"].find_one({"_id": ObjectId(new_id)})
    return to_str_id(saved)


@app.get("/customers")
def list_customers():
    docs = get_documents("customer")
    return [to_str_id(d) for d in docs]


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    doc = db["customer"].find_one({"_id": ObjectId(customer_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
    return to_str_id(doc)


@app.put("/customers/{customer_id}")
def update_customer(customer_id: str, customer: Customer):
    res = db["customer"].update_one({"_id": ObjectId(customer_id)}, {"$set": customer.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    doc = db["customer"].find_one({"_id": ObjectId(customer_id)})
    return to_str_id(doc)


@app.delete("/customers/{customer_id}")
def delete_customer(customer_id: str):
    res = db["customer"].delete_one({"_id": ObjectId(customer_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"deleted": True}


# Orders CRUD

class OrderCreate(BaseModel):
    customer_id: str
    status: Optional[str] = "Pending"
    order_discount_percent: float = 0
    items: List[OrderItem] = []


@app.post("/orders")
def create_order(payload: OrderCreate):
    # verify customer exists
    cust = db["customer"].find_one({"_id": ObjectId(payload.customer_id)})
    if not cust:
        raise HTTPException(status_code=400, detail="Invalid customer_id")
    totals = compute_totals(payload.items, payload.order_discount_percent)
    order_doc = {
        "customer_id": payload.customer_id,
        "status": payload.status or "Pending",
        "order_discount_percent": payload.order_discount_percent,
        "items": [i.model_dump() for i in payload.items],
        **totals,
    }
    new_id = create_document("order", order_doc)
    saved = db["order"].find_one({"_id": ObjectId(new_id)})
    return to_str_id(saved)


@app.get("/orders")
def list_orders(status: Optional[str] = None, customer_id: Optional[str] = None):
    q = {}
    if status:
        q["status"] = status
    if customer_id:
        q["customer_id"] = customer_id
    docs = list(db["order"].find(q).sort("created_at", -1))
    # attach customer name for convenience
    out = []
    for d in docs:
        cust = db["customer"].find_one({"_id": ObjectId(d["customer_id"])}) if d.get("customer_id") else None
        d["customer_name"] = cust.get("name") if cust else None
        out.append(to_str_id(d))
    return out


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    d = db["order"].find_one({"_id": ObjectId(order_id)})
    if not d:
        raise HTTPException(status_code=404, detail="Order not found")
    cust = db["customer"].find_one({"_id": ObjectId(d["customer_id"])}) if d.get("customer_id") else None
    d["customer_name"] = cust.get("name") if cust else None
    return to_str_id(d)


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    order_discount_percent: Optional[float] = None
    items: Optional[List[OrderItem]] = None


@app.put("/orders/{order_id}")
def update_order(order_id: str, payload: OrderUpdate):
    d = db["order"].find_one({"_id": ObjectId(order_id)})
    if not d:
        raise HTTPException(status_code=404, detail="Order not found")
    update_fields = {}
    if payload.status is not None:
        update_fields["status"] = payload.status
    if payload.items is not None:
        update_fields["items"] = [i.model_dump() for i in payload.items]
    if payload.order_discount_percent is not None:
        update_fields["order_discount_percent"] = payload.order_discount_percent
    # recompute totals if items or discount changed
    if (payload.items is not None) or (payload.order_discount_percent is not None):
        totals = compute_totals(
            payload.items if payload.items is not None else [OrderItem(**it) for it in d.get("items", [])],
            payload.order_discount_percent if payload.order_discount_percent is not None else d.get("order_discount_percent", 0),
        )
        update_fields.update(totals)
    if not update_fields:
        return to_str_id(d)
    db["order"].update_one({"_id": ObjectId(order_id)}, {"$set": update_fields})
    saved = db["order"].find_one({"_id": ObjectId(order_id)})
    return to_str_id(saved)


@app.delete("/orders/{order_id}")
def delete_order(order_id: str):
    res = db["order"].delete_one({"_id": ObjectId(order_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"deleted": True}


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
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:10]
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
