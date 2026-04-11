from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
import auth

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def _enrich(t: models.Transaction) -> dict:
    d = {c.name: getattr(t, c.name) for c in t.__table__.columns}
    if t.listing:
        d["property_type"] = t.listing.property_type
        d["city_name"]     = t.listing.city.city_name     if t.listing.city     else None
        d["locality_name"] = t.listing.locality.locality_name if t.listing.locality else None
    else:
        d["property_type"] = d["city_name"] = d["locality_name"] = None
    return d


@router.get("", response_model=list[schemas.TransactionOut], summary="List transactions")
def list_transactions(
    listing_id:  Optional[int]  = Query(None),
    city_id:     Optional[int]  = Query(None),
    txn_status:  Optional[str]  = Query(None, alias="status"),
    date_from:   Optional[str]  = Query(None, description="YYYY-MM-DD"),
    date_to:     Optional[str]  = Query(None, description="YYYY-MM-DD"),
    limit:       int = Query(50, ge=1, le=200),
    offset:      int = Query(0,  ge=0),
    db:          Session = Depends(get_db),
    _:           models.User = Depends(auth.get_current_user),
):
    q = db.query(models.Transaction)
    if listing_id:
        q = q.filter(models.Transaction.listing_id == listing_id)
    if txn_status:
        q = q.filter(models.Transaction.status == txn_status)
    if date_from:
        q = q.filter(models.Transaction.transaction_date >= date_from)
    if date_to:
        q = q.filter(models.Transaction.transaction_date <= date_to)
    if city_id:
        q = q.join(models.Listing).filter(models.Listing.city_id == city_id)

    txns = q.order_by(models.Transaction.transaction_date.desc()).offset(offset).limit(limit).all()
    return [_enrich(t) for t in txns]


@router.get("/{txn_id}", response_model=schemas.TransactionOut, summary="Get transaction by ID")
def get_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    txn = db.query(models.Transaction).filter(models.Transaction.txn_id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    return _enrich(txn)


@router.post("", response_model=schemas.TransactionOut, status_code=status.HTTP_201_CREATED,
             summary="Record a new transaction")
def create_transaction(
    payload: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    listing = db.query(models.Listing).filter(models.Listing.listing_id == payload.listing_id).first()
    if not listing:
        raise HTTPException(400, f"Listing {payload.listing_id} does not exist")
    txn = models.Transaction(**payload.model_dump())
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return _enrich(txn)


@router.put("/{txn_id}", response_model=schemas.TransactionOut, summary="Update a transaction")
def update_transaction(
    txn_id: int,
    payload: schemas.TransactionUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    txn = db.query(models.Transaction).filter(models.Transaction.txn_id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)
    db.commit()
    db.refresh(txn)
    return _enrich(txn)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a transaction (admin only)")
def delete_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    txn = db.query(models.Transaction).filter(models.Transaction.txn_id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    db.delete(txn)
    db.commit()
