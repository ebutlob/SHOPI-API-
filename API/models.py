from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CardData(BaseModel):
    number: str
    month: str
    year: str
    cvv: str
    bin: Optional[str] = None
    last4: Optional[str] = None
    hash: Optional[str] = None

class Address(BaseModel):
    first_name: str
    last_name: str
    address1: str
    city: str
    state: str
    zip: str
    country: str = "US"

class Site(BaseModel):
    id: Optional[int] = None
    store: str
    product: str
    price: str = "2.95 USD"
    gateway: str = "Shopify Payments"
    weight: int = 1
    enabled: bool = True

class Proxy(BaseModel):
    id: Optional[int] = None
    host: str
    port: int
    username: str
    password: str
    
    @property
    def string(self) -> str:
        return f"{self.host}:{self.port}:{self.username}:{self.password}"

class CheckRequest(BaseModel):
    card: str
    proxy: Optional[str] = None
    email: Optional[str] = None
    site: Optional[str] = None

class CheckResponse(BaseModel):
    response: str
    cc: str
    price: str
    gateway: str
    charged: str
    approved: str
    time: str
    email: str
    store: str
    proxy: str
    address: Address
    timestamp: datetime = datetime.now()
