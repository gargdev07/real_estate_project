from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from database import get_db
import models
import schemas
import auth

router = APIRouter(prefix="/listings", tags=["Listings"])


def _enrich(listing: models.Listing) -> dict:
    d = {c.name: getattr(listing, c.name) for c in listing.__table__.columns}
    d["city_name"]     = listing.city.city_name     if listing.city     else None
    d["locality_name"] = listing.locality.locality_name if listing.locality else None
    d["agent_name"]    = listing.agent.contact_name  if listing.agent   else None
    return d


@router.get("", response_model=schemas.PaginatedListings, summary="List listings with filters")
def list_listings(
    page:          int  = Query(1,    ge=1),
    size:          int  = Query(20,   ge=1, le=100),
    city_id:       Optional[int]   = Query(None),
    locality_id:   Optional[int]   = Query(None),
    property_type: Optional[str]   = Query(None),
    transact_type: Optional[int]   = Query(None, ge=1, le=2),
    bedroom_num:   Optional[int]   = Query(None, ge=0),
    min_price:     Optional[float] = Query(None, ge=0),
    max_price:     Optional[float] = Query(None, ge=0),
    min_area:      Optional[float] = Query(None, ge=0),
    max_area:      Optional[float] = Query(None, ge=0),
    verified:      Optional[bool]  = Query(None),
    is_active:     Optional[bool]  = Query(True),
    search:        Optional[str]   = Query(None, description="Search in prop_name, description"),
    db:            Session = Depends(get_db),
    _:             models.User = Depends(auth.get_current_user),
):
    """
    Retrieve paginated listings with optional filters.
    Supports filtering by city, locality, property type, price range, bedrooms, etc.
    """
    q = db.query(models.Listing)

    if is_active is not None:
        q = q.filter(models.Listing.is_active == is_active)
    if city_id:
        q = q.filter(models.Listing.city_id == city_id)
    if locality_id:
        q = q.filter(models.Listing.locality_id == locality_id)
    if property_type:
        q = q.filter(models.Listing.property_type.ilike(f"%{property_type}%"))
    if transact_type:
        q = q.filter(models.Listing.transact_type == transact_type)
    if bedroom_num is not None:
        q = q.filter(models.Listing.bedroom_num == bedroom_num)
    if min_price is not None:
        q = q.filter(models.Listing.price_inr >= min_price)
    if max_price is not None:
        q = q.filter(models.Listing.price_inr <= max_price)
    if min_area is not None:
        q = q.filter(models.Listing.min_area_sqft >= min_area)
    if max_area is not None:
        q = q.filter(models.Listing.max_area_sqft <= max_area)
    if verified is not None:
        q = q.filter(models.Listing.verified == verified)
    if search:
        term = f"%{search}%"
        q = q.filter(or_(
            models.Listing.prop_name.ilike(term),
            models.Listing.description.ilike(term),
        ))

    total = q.count()
    items = (
        q.order_by(models.Listing.register_date.desc().nullslast(), models.Listing.listing_id.desc())
         .offset((page - 1) * size)
         .limit(size)
         .all()
    )
    return schemas.PaginatedListings(
        total=total,
        page=page,
        size=size,
        pages=-(-total // size),
        items=[_enrich(i) for i in items],
    )


@router.get("/by-prop/{prop_id}", response_model=schemas.ListingOut,
            summary="Get listing by original property ID")
def get_by_prop_id(
    prop_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    listing = db.query(models.Listing).filter(models.Listing.prop_id == prop_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    return _enrich(listing)


@router.get("/{listing_id}", response_model=schemas.ListingOut, summary="Get listing by ID")
def get_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    listing = db.query(models.Listing).filter(models.Listing.listing_id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _enrich(listing)


@router.post("", response_model=schemas.ListingOut, status_code=status.HTTP_201_CREATED,
             summary="Create a new listing")
def create_listing(
    payload: schemas.ListingCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    """Create a new property listing. `prop_id` must be unique."""
    if db.query(models.Listing).filter(models.Listing.prop_id == payload.prop_id).first():
        raise HTTPException(400, f"Listing with prop_id '{payload.prop_id}' already exists")

    # Validate foreign keys
    if not db.query(models.City).filter(models.City.city_id == payload.city_id).first():
        raise HTTPException(400, f"city_id {payload.city_id} does not exist")
    if payload.locality_id and not db.query(models.Locality).filter(
            models.Locality.locality_id == payload.locality_id).first():
        raise HTTPException(400, f"locality_id {payload.locality_id} does not exist")

    listing = models.Listing(**payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return _enrich(listing)


@router.put("/{listing_id}", response_model=schemas.ListingOut, summary="Update a listing")
def update_listing(
    listing_id: int,
    payload: schemas.ListingUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    """Partial update — only provided fields are updated."""
    listing = db.query(models.Listing).filter(models.Listing.listing_id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(listing, field, value)
    db.commit()
    db.refresh(listing)
    return _enrich(listing)


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Soft-delete a listing")
def delete_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Soft-deletes the listing by setting is_active = False. Admin can hard-delete."""
    listing = db.query(models.Listing).filter(models.Listing.listing_id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    if current_user.role == "admin":
        db.delete(listing)
    else:
        listing.is_active = False
    db.commit()

