from __future__ import annotations
from datetime import date, datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, EmailStr


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class UserOut(BaseModel):
    user_id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field(default="analyst", pattern="^(admin|analyst)$")


# ─── Cities / Localities ──────────────────────────────────────────────────────

class CityOut(BaseModel):
    city_id: int
    city_name: str
    model_config = {"from_attributes": True}

class LocalityOut(BaseModel):
    locality_id: int
    locality_name: str
    city_id: int
    city_name: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    model_config = {"from_attributes": True}


# ─── Listings ─────────────────────────────────────────────────────────────────

class ListingBase(BaseModel):
    property_type: Optional[str] = Field(None, max_length=100)
    transact_type: int = Field(1, ge=1, le=2, description="1=Buy/Sell, 2=Rent")
    bedroom_num:   Optional[int] = Field(None, ge=0, le=20)
    bathroom_num:  Optional[int] = Field(None, ge=0, le=20)
    balcony_num:   Optional[int] = Field(None, ge=0, le=20)
    furnish_id:    Optional[int] = Field(None)
    age:           Optional[int] = Field(None, ge=0, le=200)
    floor_num:     Optional[int] = Field(None, ge=0, le=200)
    total_floor:   Optional[int] = Field(None, ge=0, le=200)
    min_area_sqft: Optional[Decimal] = Field(None, gt=0)
    max_area_sqft: Optional[Decimal] = Field(None, gt=0)
    price_inr:     Decimal = Field(..., gt=0, description="Price in INR")
    price_sqft:    Optional[Decimal] = Field(None, gt=0)
    description:   Optional[str] = Field(None, max_length=2000)
    prop_name:     Optional[str] = Field(None, max_length=400)
    latitude:      Optional[Decimal] = None
    longitude:     Optional[Decimal] = None
    register_date: Optional[date] = None
    expiry_date:   Optional[date] = None
    verified:      bool = False
    city_id:       int
    locality_id:   Optional[int] = None
    building_id:   Optional[int] = None
    agent_id:      Optional[int] = None
    amenities:     Optional[str] = Field(None, max_length=500)

    @field_validator("furnish_id")
    @classmethod
    def validate_furnish(cls, v):
        if v is not None and v not in (0, 1, 2, 4):
            raise ValueError("furnish_id must be 0, 1, 2, or 4")
        return v


class ListingCreate(ListingBase):
    prop_id: str = Field(..., min_length=3, max_length=50)


class ListingUpdate(BaseModel):
    property_type: Optional[str] = None
    transact_type: Optional[int] = Field(None, ge=1, le=2)
    bedroom_num:   Optional[int] = Field(None, ge=0, le=20)
    bathroom_num:  Optional[int] = Field(None, ge=0, le=20)
    balcony_num:   Optional[int] = Field(None, ge=0, le=20)
    furnish_id:    Optional[int] = None
    age:           Optional[int] = Field(None, ge=0)
    floor_num:     Optional[int] = Field(None, ge=0)
    total_floor:   Optional[int] = Field(None, ge=0)
    min_area_sqft: Optional[Decimal] = None
    max_area_sqft: Optional[Decimal] = None
    price_inr:     Optional[Decimal] = Field(None, gt=0)
    price_sqft:    Optional[Decimal] = Field(None, gt=0)
    description:   Optional[str] = Field(None, max_length=2000)
    prop_name:     Optional[str] = Field(None, max_length=400)
    verified:      Optional[bool] = None
    is_active:     Optional[bool] = None
    amenities:     Optional[str] = None
    locality_id:   Optional[int] = None
    agent_id:      Optional[int] = None


class ListingOut(BaseModel):
    listing_id:    int
    prop_id:       str
    property_type: Optional[str]
    transact_type: Optional[int]
    bedroom_num:   Optional[int]
    bathroom_num:  Optional[int]
    balcony_num:   Optional[int]
    furnish_id:    Optional[int]
    age:           Optional[int]
    floor_num:     Optional[int]
    total_floor:   Optional[int]
    min_area_sqft: Optional[Decimal]
    max_area_sqft: Optional[Decimal]
    price_inr:     Optional[Decimal]
    price_sqft:    Optional[Decimal]
    description:   Optional[str]
    prop_name:     Optional[str]
    latitude:      Optional[Decimal]
    longitude:     Optional[Decimal]
    register_date: Optional[date]
    expiry_date:   Optional[date]
    verified:      Optional[bool]
    is_active:     Optional[bool]
    city_id:       int
    city_name:     Optional[str] = None
    locality_id:   Optional[int]
    locality_name: Optional[str] = None
    building_id:   Optional[int]
    agent_id:      Optional[int]
    agent_name:    Optional[str] = None
    amenities:     Optional[str]
    created_at:    Optional[datetime]
    updated_at:    Optional[datetime]
    model_config = {"from_attributes": True}


class PaginatedListings(BaseModel):
    total: int
    page:  int
    size:  int
    pages: int
    items: List[ListingOut]


# ─── Agents ───────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    contact_name: str = Field(..., min_length=2, max_length=200)
    company_name: Optional[str] = Field(None, max_length=300)
    phone:        Optional[str] = Field(None, max_length=30)
    email:        Optional[EmailStr] = None

class AgentUpdate(BaseModel):
    contact_name: Optional[str] = Field(None, max_length=200)
    company_name: Optional[str] = Field(None, max_length=300)
    phone:        Optional[str] = Field(None, max_length=30)
    email:        Optional[EmailStr] = None
    is_active:    Optional[bool] = None

class AgentOut(BaseModel):
    agent_id:     int
    contact_name: Optional[str]
    company_name: Optional[str]
    phone:        Optional[str]
    email:        Optional[str]
    is_active:    bool
    created_at:   datetime
    model_config = {"from_attributes": True}


# ─── Transactions ─────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    listing_id:       int
    sale_price:       Decimal = Field(..., gt=0)
    transaction_date: date
    buyer_name:       Optional[str] = Field(None, max_length=200)
    ownership_type:   Optional[str] = Field(None, max_length=100)
    status:           str = Field("Completed", pattern="^(Completed|Pending|Cancelled)$")
    notes:            Optional[str] = None

class TransactionUpdate(BaseModel):
    sale_price:       Optional[Decimal] = Field(None, gt=0)
    transaction_date: Optional[date] = None
    buyer_name:       Optional[str] = None
    ownership_type:   Optional[str] = None
    status:           Optional[str] = Field(None, pattern="^(Completed|Pending|Cancelled)$")
    notes:            Optional[str] = None

class TransactionOut(BaseModel):
    txn_id:           int
    listing_id:       int
    sale_price:       Decimal
    transaction_date: date
    buyer_name:       Optional[str]
    ownership_type:   Optional[str]
    status:           str
    notes:            Optional[str]
    created_at:       datetime
    # Enriched
    property_type:    Optional[str] = None
    city_name:        Optional[str] = None
    locality_name:    Optional[str] = None
    model_config = {"from_attributes": True}


# ─── Analytics ────────────────────────────────────────────────────────────────

class PriceTrendPoint(BaseModel):
    month:          str
    city_name:      str
    listing_count:  int
    avg_price_sqft: Optional[Decimal]
    avg_price_inr:  Optional[Decimal]

class LocalityDemandPoint(BaseModel):
    city_name:      str
    locality_name:  str
    locality_id:    int
    property_type:  Optional[str]
    listing_count:  int
    avg_price_sqft: Optional[Decimal]
    avg_price_inr:  Optional[Decimal]
    avg_area_sqft:  Optional[Decimal]
    latitude:       Optional[Decimal]
    longitude:      Optional[Decimal]

class PropertyDistPoint(BaseModel):
    city_name:      str
    property_type:  str
    listing_count:  int
    avg_price_sqft: Optional[Decimal]
    avg_price_inr:  Optional[Decimal]

class AgentPerfPoint(BaseModel):
    agent_id:          int
    contact_name:      Optional[str]
    company_name:      Optional[str]
    city_name:         Optional[str]
    total_listings:    int
    total_transactions:int
    total_sales_value: Optional[Decimal]
    avg_sale_price:    Optional[Decimal]

class DashboardSummary(BaseModel):
    total_listings:       int
    active_listings:      int
    total_transactions:   int
    total_sales_value:    Optional[Decimal]
    avg_price_inr:        Optional[Decimal]
    avg_price_sqft:       Optional[Decimal]
    cities_covered:       int
    localities_covered:   int
