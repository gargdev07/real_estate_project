from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, SmallInteger, String, Numeric, Boolean,
    Date, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from database import Base


class City(Base):
    __tablename__ = "cities"
    city_id    = Column(Integer, primary_key=True, index=True)
    city_name  = Column(String(100), unique=True, nullable=False)
    city_code  = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    localities = relationship("Locality", back_populates="city")
    listings   = relationship("Listing",  back_populates="city")


class Locality(Base):
    __tablename__ = "localities"
    locality_id   = Column(Integer, primary_key=True, index=True)
    locality_name = Column(String(200), nullable=False)
    city_id       = Column(Integer, ForeignKey("cities.city_id", ondelete="CASCADE"), nullable=False)
    latitude      = Column(Numeric(10, 7))
    longitude     = Column(Numeric(10, 7))
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    city      = relationship("City",     back_populates="localities")
    buildings = relationship("Building", back_populates="locality")
    listings  = relationship("Listing",  back_populates="locality")


class Building(Base):
    __tablename__ = "buildings"
    building_id   = Column(Integer, primary_key=True)
    building_name = Column(String(300))
    society_name  = Column(String(300))
    locality_id   = Column(Integer, ForeignKey("localities.locality_id", ondelete="SET NULL"))
    total_floors  = Column(SmallInteger)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    locality = relationship("Locality", back_populates="buildings")
    listings = relationship("Listing",  back_populates="building")


class Agent(Base):
    __tablename__ = "agents"
    agent_id     = Column(Integer, primary_key=True, index=True)
    contact_name = Column(String(200))
    company_name = Column(String(300))
    phone        = Column(String(30))
    email        = Column(String(200))
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    listings = relationship("Listing", back_populates="agent")


class Listing(Base):
    __tablename__ = "listings"
    listing_id    = Column(Integer, primary_key=True, index=True)
    prop_id       = Column(String(50), unique=True, nullable=False)
    property_type = Column(String(100))
    transact_type = Column(SmallInteger)           # 1=Buy/Sell, 2=Rent
    bedroom_num   = Column(SmallInteger)
    bathroom_num  = Column(SmallInteger)
    balcony_num   = Column(SmallInteger)
    furnish_id    = Column(SmallInteger, ForeignKey("furnish_types.furnish_id"))
    age           = Column(SmallInteger)
    floor_num     = Column(SmallInteger)
    total_floor   = Column(SmallInteger)
    min_area_sqft = Column(Numeric(12, 4))
    max_area_sqft = Column(Numeric(12, 4))
    price_inr     = Column(Numeric(18, 2))
    price_sqft    = Column(Numeric(12, 2))
    description   = Column(Text)
    prop_name     = Column(String(400))
    latitude      = Column(Numeric(10, 7))
    longitude     = Column(Numeric(10, 7))
    register_date = Column(Date)
    expiry_date   = Column(Date)
    verified      = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    building_id   = Column(Integer, ForeignKey("buildings.building_id", ondelete="SET NULL"))
    agent_id      = Column(Integer, ForeignKey("agents.agent_id",   ondelete="SET NULL"))
    city_id       = Column(Integer, ForeignKey("cities.city_id"),    nullable=False)
    locality_id   = Column(Integer, ForeignKey("localities.locality_id", ondelete="SET NULL"))
    amenities     = Column(Text)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    city         = relationship("City",     back_populates="listings")
    locality     = relationship("Locality", back_populates="listings")
    building     = relationship("Building", back_populates="listings")
    agent        = relationship("Agent",    back_populates="listings")
    transactions = relationship("Transaction", back_populates="listing")


class Transaction(Base):
    __tablename__ = "transactions"
    txn_id           = Column(Integer, primary_key=True, index=True)
    listing_id       = Column(Integer, ForeignKey("listings.listing_id", ondelete="CASCADE"), nullable=False)
    sale_price       = Column(Numeric(18, 2), nullable=False)
    transaction_date = Column(Date, nullable=False)
    buyer_name       = Column(String(200))
    ownership_type   = Column(String(100))
    status           = Column(String(30), default="Completed")
    notes            = Column(Text)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    listing = relationship("Listing", back_populates="transactions")


class User(Base):
    __tablename__ = "users"
    user_id    = Column(Integer, primary_key=True, index=True)
    username   = Column(String(100), unique=True, nullable=False)
    email      = Column(String(200), unique=True, nullable=False)
    hashed_pw  = Column(String(300), nullable=False)
    role       = Column(String(20), default="analyst")
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FurnishType(Base):
    __tablename__ = "furnish_types"
    furnish_id = Column(SmallInteger, primary_key=True)
    label      = Column(String(50), nullable=False)
