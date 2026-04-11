"""
Real Estate DB Seeder
Reads gurgaon_10k.csv, hyderabad.csv, kolkata.csv, mumbai.csv
and populates all 6 tables in PostgreSQL.

Usage:
    pip install pandas psycopg2-binary python-dotenv passlib[bcrypt]
    python scripts/seed_db.py --data-dir /path/to/csvs
"""
import os
import sys
import re
import ast
import random
import argparse
import logging
from datetime import date, timedelta, datetime
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

DATABASE_URL = "postgresql://admin:1234@127.0.0.1:5433/real_estate"

FURNISH_MAP = {0: "Unknown", 1: "Furnished", 2: "Semi-Furnished", 3: "Semi-Furnished", 4: "Unfurnished"}
OWNERSHIP_TYPES = ["Freehold", "Leasehold", "Co-operative Society", "Power of Attorney"]
BUYER_FIRST = ["Amit", "Priya", "Rahul", "Sneha", "Vikram", "Pooja", "Suresh", "Kavitha",
               "Arjun", "Divya", "Rajan", "Meera", "Anil", "Sunita", "Deepak", "Swati"]
BUYER_LAST  = ["Sharma", "Patel", "Singh", "Gupta", "Verma", "Nair", "Reddy", "Iyer",
               "Kumar", "Joshi", "Mehta", "Shah", "Das", "Bose", "Pillai", "Mishra"]


# ──────────────────────────────────────────────
# Price parsing  (handles "2.63 Cr", "69.25 L",
#  "85,000", "Price on Request", "1.17  - 1.18 Cr")
# ──────────────────────────────────────────────
def parse_price(raw) -> float | None:
    if pd.isna(raw) or str(raw).strip().lower() in ("", "price on request", "nan"):
        return None
    s = str(raw).strip()
    # Range → take midpoint
    if " - " in s:
        parts = s.split(" - ")
        p1, p2 = parse_price(parts[0].strip()), parse_price(parts[1].strip())
        if p1 and p2:
            return (p1 + p2) / 2
        return p1 or p2
    # Remove /Bedroom or /Bed suffixes (rent per bedroom)
    s = re.sub(r'/Bed(room)?.*', '', s).strip()
    mult = 1
    if "Cr" in s:
        mult = 1e7
        s = s.replace("Cr", "").strip()
    elif " L" in s or s.endswith("L"):
        mult = 1e5
        s = re.sub(r'\s*L\s*', '', s).strip()
    s = s.replace(",", "").replace("Onwards", "").strip()
    try:
        return float(s) * mult
    except ValueError:
        return None


def parse_date(raw) -> date | None:
    if pd.isna(raw):
        return None
    s = str(raw).strip()
    for fmt in ("%dth %b, %Y", "%dst %b, %Y", "%dnd %b, %Y", "%drd %b, %Y",
                "%d %b, %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            s_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', s)
            return datetime.strptime(s_clean, fmt).date()
        except ValueError:
            pass
    return None


def parse_location_json(raw) -> dict:
    """Parse the stringified JSON in the 'location' column."""
    if pd.isna(raw):
        return {}
    try:
        return ast.literal_eval(str(raw))
    except Exception:
        return {}


def parse_map_details(raw) -> tuple[float | None, float | None]:
    d = parse_location_json(raw)
    try:
        return float(d.get("LATITUDE") or 0) or None, float(d.get("LONGITUDE") or 0) or None
    except (TypeError, ValueError):
        return None, None


# ──────────────────────────────────────────────
# Normalize each city CSV into a unified frame
# ──────────────────────────────────────────────
CITY_FILE_MAP = {
    "Gurgaon":   "gurgaon_10k.csv",
    "Hyderabad": "hyderabad.csv",
    "Kolkata":   "kolkata.csv",
    "Mumbai":    "mumbai.csv",
}


def normalize_df(df: pd.DataFrame, city_label: str) -> pd.DataFrame:
    out = pd.DataFrame()

    out["prop_id"]       = df.get("PROP_ID", pd.Series(dtype=str)).astype(str).str.strip()
    out["property_type"] = df.get("PROPERTY_TYPE", pd.Series(dtype=str))
    out["transact_type"] = pd.to_numeric(df.get("TRANSACT_TYPE", 1), errors="coerce").fillna(1).astype(int)
    out["bedroom_num"]   = pd.to_numeric(df.get("BEDROOM_NUM"), errors="coerce")
    out["bathroom_num"]  = pd.to_numeric(df.get("BATHROOM_NUM"), errors="coerce")
    out["balcony_num"]   = pd.to_numeric(df.get("BALCONY_NUM"), errors="coerce")
    out["furnish_id"]    = pd.to_numeric(df.get("FURNISH", 0), errors="coerce").fillna(0).astype(int)
    out["age"]           = pd.to_numeric(df.get("AGE"), errors="coerce")
    out["floor_num"]     = pd.to_numeric(df.get("FLOOR_NUM"), errors="coerce")
    out["total_floor"]   = pd.to_numeric(df.get("TOTAL_FLOOR"), errors="coerce")
    out["price_sqft"]    = pd.to_numeric(df.get("PRICE_SQFT"), errors="coerce")
    out["prop_name"]     = df.get("PROP_NAME", pd.Series(dtype=str))
    out["amenities"]     = df.get("AMENITIES", pd.Series(dtype=str))
    out["description"]   = df.get("DESCRIPTION", pd.Series(dtype=str))

    # Area
    if "MIN_AREA_SQFT" in df.columns:
        out["min_area_sqft"] = pd.to_numeric(df["MIN_AREA_SQFT"], errors="coerce")
        out["max_area_sqft"] = pd.to_numeric(df.get("MAX_AREA_SQFT", df["MIN_AREA_SQFT"]), errors="coerce")
    elif "AREA" in df.columns:
        out["min_area_sqft"] = pd.to_numeric(df["AREA"], errors="coerce")
        out["max_area_sqft"] = out["min_area_sqft"]
    else:
        out["min_area_sqft"] = None
        out["max_area_sqft"] = None

    # Price
    out["price_raw"]  = df.get("PRICE", pd.Series(dtype=str))
    out["price_inr"]  = out["price_raw"].apply(parse_price)

    # Verified
    if "VERIFIED" in df.columns:
        out["verified"] = df["VERIFIED"].isin([1, "1", True, "Y", "Yes"])
    else:
        out["verified"] = False

    # Dates
    out["register_date"] = df.get("REGISTER_DATE", pd.Series(dtype=str)).apply(parse_date)
    out["expiry_date"]   = df.get("EXPIRY_DATE",   pd.Series(dtype=str)).apply(parse_date)

    # Synthesise register_date for CSVs that lack it (e.g. Kolkata)
    # Spread dates across Oct 2022 – Oct 2023 to match the range of other cities
    missing_mask = out["register_date"].isna()
    n_missing = missing_mask.sum()
    if n_missing > 0:
        start = date(2022, 10, 1)
        end   = date(2023, 10, 31)
        span  = (end - start).days
        synthetic_dates = [start + timedelta(days=random.randint(0, span)) for _ in range(n_missing)]
        out.loc[missing_mask, "register_date"] = synthetic_dates

    # Location from JSON
    loc_data = df.get("location", pd.Series(dtype=str)).apply(parse_location_json)
    out["locality_name"]  = loc_data.apply(lambda d: d.get("LOCALITY_NAME", "")).str.strip()
    out["building_id_raw"]= loc_data.apply(lambda d: d.get("BUILDING_ID", "0"))
    out["building_name"]  = loc_data.apply(lambda d: d.get("BUILDING_NAME", ""))
    out["society_name"]   = loc_data.apply(lambda d: d.get("SOCIETY_NAME", ""))
    out["city_name"]      = city_label

    # Lat/Lng from MAP_DETAILS
    map_parsed = df.get("MAP_DETAILS", pd.Series(dtype=str)).apply(parse_location_json)
    out["latitude"]  = map_parsed.apply(lambda d: float(d["LATITUDE"])  if "LATITUDE"  in d and d["LATITUDE"]  else None)
    out["longitude"] = map_parsed.apply(lambda d: float(d["LONGITUDE"]) if "LONGITUDE" in d and d["LONGITUDE"] else None)

    # Agent info (only Gurgaon has these columns)
    out["contact_name"]    = df.get("CONTACT_NAME",         pd.Series(dtype=str))
    out["company_name"]    = df.get("CONTACT_COMPANY_NAME", pd.Series(dtype=str))

    # Total floors from building if present
    out["total_floors_bld"] = pd.to_numeric(df.get("TOTAL_FLOOR"), errors="coerce")

    return out


# ──────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(DATABASE_URL)


def upsert_cities(conn, city_names: list[str]) -> dict[str, int]:
    cur = conn.cursor()
    mapping = {}
    for name in city_names:
        cur.execute(
            "INSERT INTO cities(city_name) VALUES (%s) ON CONFLICT(city_name) DO UPDATE SET city_name=EXCLUDED.city_name RETURNING city_id",
            (name,)
        )
        mapping[name] = cur.fetchone()[0]
    conn.commit()
    return mapping


def upsert_localities(conn, rows: list[dict], city_map: dict[str, int]) -> dict[tuple, int]:
    cur = conn.cursor()
    mapping = {}
    seen = set()
    for r in rows:
        key = (r["locality_name"], r["city_name"])
        if key in seen or not r["locality_name"]:
            continue
        seen.add(key)
        cid = city_map.get(r["city_name"])
        if not cid:
            continue
        lat, lng = r.get("latitude"), r.get("longitude")
        cur.execute("""
            INSERT INTO localities(locality_name, city_id, latitude, longitude)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(locality_name, city_id) DO UPDATE
              SET latitude  = COALESCE(EXCLUDED.latitude,  localities.latitude),
                  longitude = COALESCE(EXCLUDED.longitude, localities.longitude)
            RETURNING locality_id
        """, (r["locality_name"], cid, lat, lng))
        mapping[(r["locality_name"], cid)] = cur.fetchone()[0]
    conn.commit()
    # Re-fetch all to cover conflicts
    cur.execute("SELECT locality_id, locality_name, city_id FROM localities")
    for lid, lname, cid in cur.fetchall():
        mapping[(lname, cid)] = lid
    return mapping


def upsert_buildings(conn, rows: list[dict], locality_map: dict, city_map: dict) -> set[int]:
    cur = conn.cursor()
    inserted = set()
    seen = set()
    batch = []
    for r in rows:
        bid_raw = r.get("building_id_raw", "0")
        try:
            bid = int(float(str(bid_raw))) if bid_raw else 0
        except (ValueError, TypeError):
            bid = 0
        if bid <= 0 or bid in seen:
            continue
        seen.add(bid)
        cid = city_map.get(r["city_name"])
        lid = locality_map.get((r["locality_name"], cid)) if cid else None
        floors_raw = r.get("total_floors_bld")
        try:
            floors = int(float(str(floors_raw))) if floors_raw and str(floors_raw).strip() not in ("", "nan") else None
        except (ValueError, TypeError):
            floors = None
        if floors is not None and (floors < 0 or floors > 32767):
            floors = None
        batch.append((bid, r.get("building_name") or None, r.get("society_name") or None,
                      lid, floors))

    if batch:
        execute_values(cur, """
            INSERT INTO buildings(building_id, building_name, society_name, locality_id, total_floors)
            VALUES %s ON CONFLICT(building_id) DO NOTHING
        """, batch)
        inserted = {b[0] for b in batch}
    conn.commit()
    return inserted


def upsert_agents(conn, rows: list[dict]) -> dict[str, int]:
    cur = conn.cursor()
    mapping = {}
    seen = {}
    for r in rows:
        name = str(r.get("contact_name") or "").strip()
        company = str(r.get("company_name") or "").strip()
        if not name or name.lower() in ("nan", "none", ""):
            continue
        key = (name.lower(), company.lower())
        if key in seen:
            mapping[name] = seen[key]
            continue
        cur.execute("""
            INSERT INTO agents(contact_name, company_name)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            RETURNING agent_id
        """, (name or None, company or None))
        row = cur.fetchone()
        if row:
            seen[key] = row[0]
            mapping[name] = row[0]
    conn.commit()
    # fill gaps from existing
    cur.execute("SELECT agent_id, contact_name, company_name FROM agents")
    for aid, aname, _ in cur.fetchall():
        if aname and aname not in mapping:
            mapping[aname] = aid
    return mapping


def insert_listings(conn, df: pd.DataFrame, city_map, locality_map, building_ids, agent_map) -> list[int]:
    cur = conn.cursor()
    batch = []
    for _, r in df.iterrows():
        price = r.get("price_inr")
        if price is None or price <= 0:
            continue
        cid = city_map.get(r["city_name"])
        if not cid:
            continue
        lid  = locality_map.get((r["locality_name"], cid))
        bid_raw = r.get("building_id_raw", 0)
        try:
            bid = int(float(str(bid_raw))) if bid_raw else 0
        except (ValueError, TypeError):
            bid = 0
        bid  = bid if bid in building_ids else None
        aid  = agent_map.get(str(r.get("contact_name") or "").strip())
        furnish = int(r.get("furnish_id") or 0)
        furnish = furnish if furnish in (0, 1, 2, 4) else 0
        batch.append((
            str(r["prop_id"]),
            str(r.get("property_type") or "")[:100] or None,
            int(r.get("transact_type") or 1),
            int(r["bedroom_num"])  if pd.notna(r.get("bedroom_num"))  else None,
            int(r["bathroom_num"]) if pd.notna(r.get("bathroom_num")) else None,
            int(r["balcony_num"])  if pd.notna(r.get("balcony_num"))  else None,
            furnish,
            int(r["age"])          if pd.notna(r.get("age"))          else None,
            int(r["floor_num"])    if pd.notna(r.get("floor_num"))    else None,
            int(r["total_floor"])  if pd.notna(r.get("total_floor"))  else None,
            float(r["min_area_sqft"]) if pd.notna(r.get("min_area_sqft")) else None,
            float(r["max_area_sqft"]) if pd.notna(r.get("max_area_sqft")) else None,
            float(price),
            float(r["price_sqft"]) if pd.notna(r.get("price_sqft")) and float(r.get("price_sqft") or 0) > 0 else None,
            str(r.get("description") or "")[:2000] or None,
            str(r.get("prop_name") or "")[:400] or None,
            float(r["latitude"])  if pd.notna(r.get("latitude"))  else None,
            float(r["longitude"]) if pd.notna(r.get("longitude")) else None,
            r.get("register_date") if pd.notna(r.get("register_date")) else None,
            r.get("expiry_date") if pd.notna(r.get("expiry_date")) else None,
            bool(r.get("verified", False)),
            bid, aid, cid, lid,
            str(r.get("amenities") or "")[:500] or None,
        ))

    if not batch:
        return []

    result_ids = []
    chunk = 500
    for i in range(0, len(batch), chunk):
        execute_values(cur, """
            INSERT INTO listings (
                prop_id, property_type, transact_type,
                bedroom_num, bathroom_num, balcony_num, furnish_id,
                age, floor_num, total_floor,
                min_area_sqft, max_area_sqft, price_inr, price_sqft,
                description, prop_name, latitude, longitude,
                register_date, expiry_date, verified,
                building_id, agent_id, city_id, locality_id, amenities
            ) VALUES %s
            ON CONFLICT(prop_id) DO NOTHING
            RETURNING listing_id
        """, batch[i:i+chunk])
        result_ids.extend([row[0] for row in cur.fetchall()])

    conn.commit()
    return result_ids


def insert_transactions(conn, listing_ids: list[int], n_per_listing_prob: float = 0.12):
    """Synthesize realistic transactions from a sample of sale listings."""
    if not listing_ids:
        return
    cur = conn.cursor()
    sample = [lid for lid in listing_ids if random.random() < n_per_listing_prob]
    if len(sample) < 200:
        sample = random.sample(listing_ids, min(len(listing_ids), max(200, int(len(listing_ids) * 0.12))))

    # Fetch prices for sampled listings
    cur.execute("SELECT listing_id, price_inr, register_date FROM listings WHERE listing_id = ANY(%s)", (sample,))
    rows = cur.fetchall()

    batch = []
    for lid, price, reg_date in rows:
        if not price or price <= 0:
            continue
        variance = random.uniform(0.92, 1.08)
        sale_price = round(float(price) * variance, 2)
        if reg_date:
            offset = random.randint(30, 365)
            txn_date = reg_date + timedelta(days=offset)
        else:
            txn_date = date(random.randint(2022, 2023), random.randint(1, 12), random.randint(1, 28))
        buyer = f"{random.choice(BUYER_FIRST)} {random.choice(BUYER_LAST)}"
        ownership = random.choice(OWNERSHIP_TYPES)
        status = random.choices(["Completed", "Pending", "Cancelled"], weights=[80, 15, 5])[0]
        batch.append((lid, sale_price, txn_date, buyer, ownership, status))

    if batch:
        execute_values(cur, """
            INSERT INTO transactions(listing_id, sale_price, transaction_date, buyer_name, ownership_type, status)
            VALUES %s ON CONFLICT DO NOTHING
        """, batch)
    conn.commit()
    log.info(f"Inserted {len(batch)} synthetic transactions")


def insert_default_users(conn):
    cur = conn.cursor()
    users = [
        ("admin",   "admin@realestate.com",   pwd_ctx.hash("admin123"),   "admin"),
        ("analyst", "analyst@realestate.com", pwd_ctx.hash("analyst123"), "analyst"),
    ]
    for username, email, hashed, role in users:
        cur.execute("""
            INSERT INTO users(username, email, hashed_pw, role)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(username) DO NOTHING
        """, (username, email, hashed, role))
    conn.commit()
    log.info("Default users created: admin / admin123  |  analyst / analyst123")


def refresh_materialized_views(conn):
    cur = conn.cursor()
    for view in ("mv_price_trends", "mv_locality_demand", "mv_agent_performance"):
        log.info(f"Refreshing {view}…")
        cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
    conn.commit()
    log.info("All materialized views refreshed")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main(data_dir: str):
    random.seed(42)
    data_path = Path(data_dir)

    log.info("Loading CSVs…")
    all_frames = []
    for city, fname in CITY_FILE_MAP.items():
        fpath = data_path / fname
        if not fpath.exists():
            log.warning(f"{fpath} not found, skipping {city}")
            continue
        df = pd.read_csv(fpath, low_memory=False)
        log.info(f"  {city}: {len(df)} rows")
        norm = normalize_df(df, city)
        all_frames.append(norm)

    if not all_frames:
        log.error("No CSV files found. Check --data-dir path.")
        sys.exit(1)

    combined = pd.concat(all_frames, ignore_index=True)
    # Drop rows with no price or no prop_id
    combined = combined[combined["price_inr"].notna() & (combined["price_inr"] > 0)]
    combined = combined[combined["prop_id"].notna() & (combined["prop_id"] != "nan")]
    combined = combined.drop_duplicates(subset=["prop_id"])
    log.info(f"Total usable rows after cleaning: {len(combined)}")

    rows = combined.to_dict("records")
    conn = get_conn()

    log.info("Inserting cities…")
    city_map = upsert_cities(conn, list(CITY_FILE_MAP.keys()))
    log.info(f"  {len(city_map)} cities")

    log.info("Inserting localities…")
    locality_map = upsert_localities(conn, rows, city_map)
    log.info(f"  {len(locality_map)} localities")

    log.info("Inserting buildings…")
    building_ids = upsert_buildings(conn, rows, locality_map, city_map)
    log.info(f"  {len(building_ids)} buildings")

    log.info("Inserting agents…")
    agent_map = upsert_agents(conn, rows)
    log.info(f"  {len(agent_map)} agents")

    log.info("Inserting listings…")
    listing_ids = insert_listings(conn, combined, city_map, locality_map, building_ids, agent_map)
    log.info(f"  {len(listing_ids)} listings inserted")

    log.info("Generating synthetic transactions…")
    insert_transactions(conn, listing_ids)

    log.info("Creating default users…")
    insert_default_users(conn)

    log.info("Refreshing materialized views…")
    try:
        refresh_materialized_views(conn)
    except Exception as e:
        log.warning(f"Could not refresh views (might need data): {e}")
        conn.rollback()

    conn.close()
    log.info("✅ Seeding complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the real estate DB")
    parser.add_argument("--data-dir", default=".", help="Directory containing the CSV files")
    args = parser.parse_args()
    main(args.data_dir)
