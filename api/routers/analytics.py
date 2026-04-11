from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import logging

from database import get_db
import models
import schemas
import auth

router = APIRouter(prefix="/analytics", tags=["Analytics"])
log = logging.getLogger(__name__)


def _safe_query(db: Session, sql: str, params: dict | None = None):
    """Execute SQL, return rows or [] on any error (never 500)."""
    if params is None:
        params = {}
    try:
        result = db.execute(text(sql), params)
        return result.fetchall()
    except Exception as e:
        log.warning(f"Query failed, rolling back: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return []


@router.get("/summary", response_model=schemas.DashboardSummary,
            summary="Top-level KPI summary for dashboard header")
def get_summary(
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user)):
    
    l_cond = "price_inr > 0"
    params = {}
    if date_from: l_cond += " AND register_date >= :date_from::date"; params["date_from"] = date_from
    if date_to:   l_cond += " AND register_date <= :date_to::date";   params["date_to"] = date_to

    t_cond = "status='Completed'"
    if date_from: t_cond += " AND transaction_date >= :date_from::date"
    if date_to:   t_cond += " AND transaction_date <= :date_to::date"

    row     = _safe_query(db, f"SELECT COUNT(*), COUNT(*) FILTER (WHERE is_active=TRUE), ROUND(AVG(price_inr)::NUMERIC,2), ROUND(AVG(price_sqft)::NUMERIC,2) FROM listings WHERE {l_cond}", params)
    txn_row = _safe_query(db, f"SELECT COUNT(*), ROUND(SUM(sale_price)::NUMERIC,2) FROM transactions WHERE {t_cond}", params)
    geo_row = _safe_query(db, f"SELECT COUNT(DISTINCT city_id), COUNT(DISTINCT locality_id) FROM listings WHERE is_active=TRUE AND {l_cond}", params)

    r = row[0]     if row     else (0,0,None,None)
    t = txn_row[0] if txn_row else (0, None)
    g = geo_row[0] if geo_row else (0, 0)

    return schemas.DashboardSummary(
        total_listings=int(r[0] or 0), active_listings=int(r[1] or 0),
        total_transactions=int(t[0] or 0), total_sales_value=t[1],
        avg_price_inr=r[2], avg_price_sqft=r[3],
        cities_covered=int(g[0] or 0), localities_covered=int(g[1] or 0),
    )


@router.get("/price-trends", response_model=list[schemas.PriceTrendPoint],
            summary="Monthly avg price/sqft per city")
def price_trends(
    city_name: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    # Direct query (always works, even before views are populated)
    conds  = ["l.price_sqft > 0", "l.price_sqft < 100000",
              "l.register_date IS NOT NULL", "l.transact_type = 1"]
    params: dict = {}
    if city_name: conds.append("c.city_name = :city_name"); params["city_name"] = city_name
    if date_from: conds.append("l.register_date >= :date_from::date"); params["date_from"] = date_from
    if date_to:   conds.append("l.register_date <= :date_to::date");   params["date_to"]   = date_to
    where = " AND ".join(conds)

    rows = _safe_query(db, f"""
        SELECT c.city_name,
               TO_CHAR(DATE_TRUNC('month', l.register_date), 'YYYY-MM') AS month,
               COUNT(*)                              AS listing_count,
               ROUND(AVG(l.price_sqft)::NUMERIC, 2) AS avg_price_sqft,
               ROUND(AVG(l.price_inr)::NUMERIC,  2) AS avg_price_inr
        FROM listings l JOIN cities c ON c.city_id = l.city_id
        WHERE {where}
        GROUP BY c.city_name, DATE_TRUNC('month', l.register_date)
        ORDER BY month, c.city_name
    """, params)

    return [schemas.PriceTrendPoint(city_name=r[0], month=r[1], listing_count=int(r[2] or 0),
                                    avg_price_sqft=r[3], avg_price_inr=r[4]) for r in rows]


@router.get("/locality-demand", response_model=list[schemas.LocalityDemandPoint],
            summary="Listing count + avg price per locality")
def locality_demand(
    city_name:     Optional[str] = Query(None),
    property_type: Optional[str] = Query(None),
    top_n:         int = Query(20, ge=5, le=100),
    date_from:     Optional[str] = Query(None),
    date_to:       Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    conds  = ["l.price_sqft > 0", "l.price_sqft < 100000",
              "l.is_active = TRUE", "loc.locality_id IS NOT NULL"]
    params: dict = {"top_n": top_n}
    if city_name:     conds.append("c.city_name = :city_name");              params["city_name"]     = city_name
    if property_type: conds.append("l.property_type ILIKE :ptype");          params["ptype"]         = f"%{property_type}%"
    if date_from: conds.append("l.register_date >= :date_from::date"); params["date_from"] = date_from
    if date_to:   conds.append("l.register_date <= :date_to::date");   params["date_to"]   = date_to
    where = " AND ".join(conds)

    rows = _safe_query(db, f"""
        SELECT c.city_name, loc.locality_name, loc.locality_id,
               l.property_type, COUNT(*) AS listing_count,
               ROUND(AVG(l.price_sqft)::NUMERIC, 2)   AS avg_price_sqft,
               ROUND(AVG(l.price_inr)::NUMERIC,  2)   AS avg_price_inr,
               ROUND(AVG(l.min_area_sqft)::NUMERIC, 1) AS avg_area_sqft,
               loc.latitude, loc.longitude
        FROM listings l
        JOIN cities c       ON c.city_id       = l.city_id
        JOIN localities loc ON loc.locality_id = l.locality_id
        WHERE {where}
        GROUP BY c.city_name, loc.locality_name, loc.locality_id,
                 loc.latitude, loc.longitude, l.property_type
        ORDER BY listing_count DESC LIMIT :top_n
    """, params)

    return [schemas.LocalityDemandPoint(
        city_name=r[0], locality_name=r[1], locality_id=r[2],
        property_type=r[3], listing_count=int(r[4] or 0),
        avg_price_sqft=r[5], avg_price_inr=r[6], avg_area_sqft=r[7],
        latitude=r[8], longitude=r[9]
    ) for r in rows]


@router.get("/property-distribution", response_model=list[schemas.PropertyDistPoint],
            summary="Listing count + avg price per property type")
def property_distribution(
    city_name: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    conds  = ["l.price_sqft > 0", "l.price_sqft < 100000",
              "l.is_active = TRUE", "l.property_type IS NOT NULL"]
    params: dict = {}
    if city_name: conds.append("c.city_name = :city_name"); params["city_name"] = city_name
    if date_from: conds.append("l.register_date >= :date_from::date"); params["date_from"] = date_from
    if date_to:   conds.append("l.register_date <= :date_to::date");   params["date_to"]   = date_to
    where = " AND ".join(conds)

    rows = _safe_query(db, f"""
        SELECT c.city_name, l.property_type,
               COUNT(*)                              AS listing_count,
               ROUND(AVG(l.price_sqft)::NUMERIC, 2) AS avg_price_sqft,
               ROUND(AVG(l.price_inr)::NUMERIC,  2) AS avg_price_inr
        FROM listings l JOIN cities c ON c.city_id = l.city_id
        WHERE {where}
        GROUP BY c.city_name, l.property_type
        ORDER BY listing_count DESC
    """, params)

    return [schemas.PropertyDistPoint(city_name=r[0], property_type=r[1],
             listing_count=int(r[2] or 0), avg_price_sqft=r[3], avg_price_inr=r[4])
            for r in rows]


@router.get("/agent-performance", response_model=list[schemas.AgentPerfPoint],
            summary="Top agents by transaction value")
def agent_performance(
    city_name: Optional[str] = Query(None),
    top_n:     int = Query(15, ge=5, le=50),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    conds  = ["a.is_active = TRUE"]
    params: dict = {"top_n": top_n}
    if city_name: conds.append("c.city_name = :city_name"); params["city_name"] = city_name
    if date_from: conds.append("(t.transaction_date >= :date_from::date OR l.register_date >= :date_from::date)"); params["date_from"] = date_from
    if date_to:   conds.append("(t.transaction_date <= :date_to::date OR l.register_date <= :date_to::date)");   params["date_to"]   = date_to
    where = " AND ".join(conds)

    rows = _safe_query(db, f"""
        SELECT a.agent_id, a.contact_name, a.company_name,
               MAX(c.city_name)                             AS city_name,
               COUNT(DISTINCT l.listing_id)                 AS total_listings,
               COUNT(DISTINCT t.txn_id)                     AS total_transactions,
               ROUND(SUM(t.sale_price)::NUMERIC, 2)         AS total_sales_value,
               ROUND(AVG(t.sale_price)::NUMERIC, 2)         AS avg_sale_price
        FROM agents a
        LEFT JOIN listings l     ON l.agent_id   = a.agent_id
        LEFT JOIN cities c       ON c.city_id    = l.city_id
        LEFT JOIN transactions t ON t.listing_id = l.listing_id
        WHERE {where}
        GROUP BY a.agent_id, a.contact_name, a.company_name
        HAVING COUNT(DISTINCT l.listing_id) > 0
        ORDER BY COALESCE(COUNT(DISTINCT t.txn_id), 0) DESC,
                 COALESCE(SUM(t.sale_price), 0) DESC
        LIMIT :top_n
    """, params)

    return [schemas.AgentPerfPoint(
        agent_id=r[0], contact_name=r[1], company_name=r[2], city_name=r[3],
        total_listings=int(r[4] or 0), total_transactions=int(r[5] or 0),
        total_sales_value=r[6], avg_sale_price=r[7]
    ) for r in rows]


@router.get("/bedroom-price", summary="Avg price per sqft by bedroom count")
def bedroom_vs_price(
    city_name: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    conds  = ["l.price_sqft > 0", "l.price_sqft < 100000",
              "l.bedroom_num BETWEEN 1 AND 6", "l.is_active = TRUE"]
    params: dict = {}
    if city_name: conds.append("c.city_name = :city_name"); params["city_name"] = city_name
    if date_from: conds.append("l.register_date >= :date_from::date"); params["date_from"] = date_from
    if date_to:   conds.append("l.register_date <= :date_to::date");   params["date_to"]   = date_to
    where = " AND ".join(conds)

    rows = _safe_query(db, f"""
        SELECT c.city_name, l.bedroom_num, COUNT(*),
               ROUND(AVG(l.price_sqft)::NUMERIC, 2),
               ROUND(AVG(l.price_inr)::NUMERIC,  2)
        FROM listings l JOIN cities c ON c.city_id = l.city_id
        WHERE {where}
        GROUP BY c.city_name, l.bedroom_num
        ORDER BY c.city_name, l.bedroom_num
    """, params)

    return [{"city_name": r[0], "bedroom_num": r[1], "listing_count": int(r[2] or 0),
             "avg_price_sqft": r[3], "avg_price_inr": r[4]} for r in rows]


@router.get("/cities", response_model=list[schemas.CityOut], summary="List all cities")
def list_cities(db: Session = Depends(get_db),
                _: models.User = Depends(auth.get_current_user)):
    rows = _safe_query(db, "SELECT city_id, city_name FROM cities ORDER BY city_name")
    return [{"city_id": r[0], "city_name": r[1]} for r in rows]


@router.get("/localities", response_model=list[schemas.LocalityOut],
            summary="List localities, optionally filtered by city")
def list_localities(
    city_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    if city_id:
        rows = _safe_query(db, """
            SELECT loc.locality_id, loc.locality_name, loc.city_id, c.city_name,
                   loc.latitude, loc.longitude
            FROM localities loc JOIN cities c ON c.city_id = loc.city_id
            WHERE loc.city_id = :city_id ORDER BY loc.locality_name LIMIT 500
        """, {"city_id": city_id})
    else:
        rows = _safe_query(db, """
            SELECT loc.locality_id, loc.locality_name, loc.city_id, c.city_name,
                   loc.latitude, loc.longitude
            FROM localities loc JOIN cities c ON c.city_id = loc.city_id
            ORDER BY loc.locality_name LIMIT 500
        """)
    return [{"locality_id": r[0], "locality_name": r[1], "city_id": r[2],
             "city_name": r[3], "latitude": r[4], "longitude": r[5]} for r in rows]


@router.post("/refresh-views", summary="Refresh materialized views (admin only)")
def refresh_views(db: Session = Depends(get_db),
                  _: models.User = Depends(auth.require_admin)):
    refreshed, failed = [], []
    for view in ("mv_price_trends", "mv_locality_demand", "mv_agent_performance"):
        try:
            db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
            db.commit()
            refreshed.append(view)
        except Exception as e:
            db.rollback()
            try:
                db.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))
                db.commit()
                refreshed.append(view)
            except Exception as e2:
                db.rollback()
                failed.append(f"{view}: {e2}")
    return {"refreshed": refreshed, "failed": failed}
