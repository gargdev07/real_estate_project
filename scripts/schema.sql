-- ============================================================
-- Real Estate Listing & Market Analysis System
-- PostgreSQL Schema
-- ============================================================

-- Lookup: cities
CREATE TABLE IF NOT EXISTS cities (
    city_id     SERIAL PRIMARY KEY,
    city_name   VARCHAR(100) NOT NULL UNIQUE,
    city_code   VARCHAR(20),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Lookup: localities
CREATE TABLE IF NOT EXISTS localities (
    locality_id   SERIAL PRIMARY KEY,
    locality_name VARCHAR(200) NOT NULL,
    city_id       INTEGER NOT NULL REFERENCES cities(city_id) ON DELETE CASCADE,
    latitude      NUMERIC(10, 7),
    longitude     NUMERIC(10, 7),
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(locality_name, city_id)
);

-- Buildings / Societies
CREATE TABLE IF NOT EXISTS buildings (
    building_id       INTEGER PRIMARY KEY,
    building_name     VARCHAR(300),
    society_name      VARCHAR(300),
    locality_id       INTEGER REFERENCES localities(locality_id) ON DELETE SET NULL,
    total_floors      SMALLINT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Agents / Dealers
CREATE TABLE IF NOT EXISTS agents (
    agent_id       SERIAL PRIMARY KEY,
    contact_name   VARCHAR(200),
    company_name   VARCHAR(300),
    phone          VARCHAR(30),
    email          VARCHAR(200),
    is_active      BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Furnish lookup: 1=Furnished, 2=Semi-Furnished, 4=Unfurnished, 0=Unknown
CREATE TABLE IF NOT EXISTS furnish_types (
    furnish_id   SMALLINT PRIMARY KEY,
    label        VARCHAR(50) NOT NULL
);
INSERT INTO furnish_types VALUES
    (0, 'Unknown'),
    (1, 'Furnished'),
    (2, 'Semi-Furnished'),
    (4, 'Unfurnished')
ON CONFLICT DO NOTHING;

-- Core listings table
CREATE TABLE IF NOT EXISTS listings (
    listing_id        SERIAL PRIMARY KEY,
    prop_id           VARCHAR(50) NOT NULL UNIQUE,
    property_type     VARCHAR(100),
    transact_type     SMALLINT,           -- 1=Buy/Sell, 2=Rent
    bedroom_num       SMALLINT,
    bathroom_num      SMALLINT,
    balcony_num       SMALLINT,
    furnish_id        SMALLINT REFERENCES furnish_types(furnish_id),
    age               SMALLINT,           -- building age in years
    floor_num         SMALLINT,
    total_floor       SMALLINT,
    min_area_sqft     NUMERIC(12, 4),
    max_area_sqft     NUMERIC(12, 4),
    price_inr         NUMERIC(18, 2),     -- price in INR (parsed from Cr/L strings)
    price_sqft        NUMERIC(12, 2),
    description       TEXT,
    prop_name         VARCHAR(400),
    latitude          NUMERIC(10, 7),
    longitude         NUMERIC(10, 7),
    register_date     DATE,
    expiry_date       DATE,
    verified          BOOLEAN DEFAULT FALSE,
    is_active         BOOLEAN DEFAULT TRUE,
    building_id       INTEGER REFERENCES buildings(building_id) ON DELETE SET NULL,
    agent_id          INTEGER REFERENCES agents(agent_id) ON DELETE SET NULL,
    city_id           INTEGER NOT NULL REFERENCES cities(city_id),
    locality_id       INTEGER REFERENCES localities(locality_id) ON DELETE SET NULL,
    amenities         TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Transactions (closed deals)
CREATE TABLE IF NOT EXISTS transactions (
    txn_id            SERIAL PRIMARY KEY,
    listing_id        INTEGER NOT NULL REFERENCES listings(listing_id) ON DELETE CASCADE,
    sale_price        NUMERIC(18, 2) NOT NULL,
    transaction_date  DATE NOT NULL,
    buyer_name        VARCHAR(200),
    ownership_type    VARCHAR(100),       -- Freehold, Leasehold etc.
    status            VARCHAR(30) DEFAULT 'Completed',  -- Completed, Cancelled, Pending
    notes             TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Users (for API auth)
CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(100) NOT NULL UNIQUE,
    email         VARCHAR(200) NOT NULL UNIQUE,
    hashed_pw     VARCHAR(300) NOT NULL,
    role          VARCHAR(20) DEFAULT 'analyst',  -- admin, analyst
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Indexes for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_listings_city       ON listings(city_id);
CREATE INDEX IF NOT EXISTS idx_listings_locality   ON listings(locality_id);
CREATE INDEX IF NOT EXISTS idx_listings_type       ON listings(property_type);
CREATE INDEX IF NOT EXISTS idx_listings_transact   ON listings(transact_type);
CREATE INDEX IF NOT EXISTS idx_listings_price      ON listings(price_inr);
CREATE INDEX IF NOT EXISTS idx_listings_price_sqft ON listings(price_sqft);
CREATE INDEX IF NOT EXISTS idx_listings_bedrooms   ON listings(bedroom_num);
CREATE INDEX IF NOT EXISTS idx_listings_reg_date   ON listings(register_date);
CREATE INDEX IF NOT EXISTS idx_listings_active     ON listings(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_transactions_date   ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_listing ON transactions(listing_id);
CREATE INDEX IF NOT EXISTS idx_localities_city     ON localities(city_id);

-- ============================================================
-- Trigger: auto-update updated_at on listings
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_listings_updated_at ON listings;
CREATE TRIGGER trg_listings_updated_at
    BEFORE UPDATE ON listings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- Materialized Views for dashboard analytics (fast reads)
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_price_trends AS
SELECT
    c.city_name,
    DATE_TRUNC('month', l.register_date) AS month,
    COUNT(*)                              AS listing_count,
    ROUND(AVG(l.price_sqft)::NUMERIC, 2) AS avg_price_sqft,
    ROUND(AVG(l.price_inr)::NUMERIC, 2)  AS avg_price_inr,
    ROUND(MIN(l.price_inr)::NUMERIC, 2)  AS min_price_inr,
    ROUND(MAX(l.price_inr)::NUMERIC, 2)  AS max_price_inr
FROM listings l
JOIN cities c ON c.city_id = l.city_id
WHERE l.price_sqft > 0 AND l.price_sqft < 100000
  AND l.register_date IS NOT NULL
  AND l.transact_type = 1
GROUP BY c.city_name, DATE_TRUNC('month', l.register_date)
ORDER BY c.city_name, month;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_price_trends
    ON mv_price_trends(city_name, month);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_locality_demand AS
SELECT
    c.city_name,
    loc.locality_name,
    loc.locality_id,
    loc.latitude,
    loc.longitude,
    l.property_type,
    COUNT(*)                               AS listing_count,
    ROUND(AVG(l.price_sqft)::NUMERIC, 2)  AS avg_price_sqft,
    ROUND(AVG(l.price_inr)::NUMERIC, 2)   AS avg_price_inr,
    ROUND(AVG(l.min_area_sqft)::NUMERIC,1) AS avg_area_sqft
FROM listings l
JOIN cities c    ON c.city_id    = l.city_id
JOIN localities loc ON loc.locality_id = l.locality_id
WHERE l.price_sqft > 0 AND l.price_sqft < 100000
  AND l.is_active = TRUE
GROUP BY c.city_name, loc.locality_name, loc.locality_id,
         loc.latitude, loc.longitude, l.property_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_agent_performance AS
SELECT
    a.agent_id,
    a.contact_name,
    a.company_name,
    c.city_name,
    COUNT(DISTINCT l.listing_id)    AS total_listings,
    COUNT(DISTINCT t.txn_id)        AS total_transactions,
    ROUND(SUM(t.sale_price)::NUMERIC, 2) AS total_sales_value,
    ROUND(AVG(t.sale_price)::NUMERIC, 2) AS avg_sale_price
FROM agents a
LEFT JOIN listings l     ON l.agent_id  = a.agent_id
LEFT JOIN cities c       ON c.city_id   = l.city_id
LEFT JOIN transactions t ON t.listing_id = l.listing_id
GROUP BY a.agent_id, a.contact_name, a.company_name, c.city_name;
