"""
Integration tests for the Real Estate API.

Run with:
    pip install pytest httpx
    pytest tests/ -v
"""
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

from main import app

client = TestClient(app)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_token(username="analyst", password="analyst123"):
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]

def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ─── Auth Tests ───────────────────────────────────────────────────────────────
class TestAuth:
    def test_login_valid(self):
        r = client.post("/auth/login", data={"username": "admin", "password": "admin123"})
        assert r.status_code == 200
        assert "access_token" in r.json()
        assert r.json()["token_type"] == "bearer"

    def test_login_invalid(self):
        r = client.post("/auth/login", data={"username": "admin", "password": "wrongpass"})
        assert r.status_code == 401

    def test_me_authenticated(self):
        token = get_token()
        r = client.get("/auth/me", headers=auth_header(token))
        assert r.status_code == 200
        assert r.json()["username"] == "analyst"

    def test_me_unauthenticated(self):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_protected_endpoint_without_token(self):
        r = client.get("/listings")
        assert r.status_code == 401


# ─── Health ───────────────────────────────────────────────────────────────────
class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["version"] == "1.0.0"
        assert "database" in data


# ─── Analytics Tests ──────────────────────────────────────────────────────────
class TestAnalytics:
    token = None

    @classmethod
    def setup_class(cls):
        cls.token = get_token()

    def test_summary(self):
        r = client.get("/analytics/summary", headers=auth_header(self.token))
        assert r.status_code == 200
        s = r.json()
        assert "total_listings" in s
        assert "active_listings" in s
        assert "total_transactions" in s
        assert "cities_covered" in s

    def test_price_trends(self):
        r = client.get("/analytics/price-trends", headers=auth_header(self.token))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "city_name" in data[0]
            assert "month" in data[0]
            assert "avg_price_sqft" in data[0]

    def test_price_trends_city_filter(self):
        r = client.get("/analytics/price-trends?city_name=Gurgaon", headers=auth_header(self.token))
        assert r.status_code == 200
        data = r.json()
        for row in data:
            assert row["city_name"] == "Gurgaon"

    def test_locality_demand(self):
        r = client.get("/analytics/locality-demand?top_n=10", headers=auth_header(self.token))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "locality_name" in data[0]
            assert "listing_count" in data[0]

    def test_property_distribution(self):
        r = client.get("/analytics/property-distribution", headers=auth_header(self.token))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "property_type" in data[0]
            assert "listing_count" in data[0]

    def test_agent_performance(self):
        r = client.get("/analytics/agent-performance", headers=auth_header(self.token))
        assert r.status_code == 200

    def test_bedroom_price(self):
        r = client.get("/analytics/bedroom-price", headers=auth_header(self.token))
        assert r.status_code == 200

    def test_cities_list(self):
        r = client.get("/analytics/cities", headers=auth_header(self.token))
        assert r.status_code == 200
        cities = r.json()
        assert isinstance(cities, list)
        city_names = [c["city_name"] for c in cities]
        for expected in ["Gurgaon", "Hyderabad", "Kolkata", "Mumbai"]:
            assert expected in city_names

    def test_localities_by_city(self):
        cities = client.get("/analytics/cities", headers=auth_header(self.token)).json()
        if cities:
            cid = cities[0]["city_id"]
            r = client.get(f"/analytics/localities?city_id={cid}", headers=auth_header(self.token))
            assert r.status_code == 200
            locs = r.json()
            assert isinstance(locs, list)
            for loc in locs:
                assert loc["city_id"] == cid


# ─── Listings CRUD Tests ──────────────────────────────────────────────────────
class TestListingsCRUD:
    token = None
    created_id = None

    @classmethod
    def setup_class(cls):
        cls.token = get_token("admin", "admin123")

    def _headers(self):
        return auth_header(self.token)

    def test_list_listings(self):
        r = client.get("/listings?page=1&size=5", headers=self._headers())
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "pages" in data

    def test_list_listings_filter_city(self):
        cities = client.get("/analytics/cities", headers=self._headers()).json()
        if cities:
            cid = cities[0]["city_id"]
            r = client.get(f"/listings?city_id={cid}&size=5", headers=self._headers())
            assert r.status_code == 200

    def test_create_listing(self):
        cities = client.get("/analytics/cities", headers=self._headers()).json()
        assert cities, "No cities found — seed the database first"
        cid = cities[0]["city_id"]
        payload = {
            "prop_id":      "TEST_CRUD_001",
            "property_type":"Residential Apartment",
            "transact_type": 1,
            "bedroom_num":   3,
            "bathroom_num":  2,
            "min_area_sqft": 1200.0,
            "max_area_sqft": 1400.0,
            "price_inr":     8500000.0,
            "price_sqft":    6250.0,
            "city_id":       cid,
            "prop_name":    "Test Apartment — CRUD Validation",
            "furnish_id":   2,
            "verified":     True,
        }
        r = client.post("/listings", json=payload, headers=self._headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["prop_id"] == "TEST_CRUD_001"
        assert data["price_inr"] == "8500000.00"
        TestListingsCRUD.created_id = data["listing_id"]

    def test_create_listing_duplicate_prop_id(self):
        cities = client.get("/analytics/cities", headers=self._headers()).json()
        cid = cities[0]["city_id"]
        r = client.post("/listings", json={
            "prop_id": "TEST_CRUD_001", "price_inr": 1000000, "city_id": cid,
            "transact_type": 1,
        }, headers=self._headers())
        assert r.status_code == 400

    def test_create_listing_invalid_price(self):
        cities = client.get("/analytics/cities", headers=self._headers()).json()
        cid = cities[0]["city_id"]
        r = client.post("/listings", json={
            "prop_id": "TEST_BAD_PRICE", "price_inr": -500, "city_id": cid,
            "transact_type": 1,
        }, headers=self._headers())
        assert r.status_code == 422   # Pydantic validation error

    def test_read_listing(self):
        if not self.created_id:
            pytest.skip("Create test did not run")
        r = client.get(f"/listings/{self.created_id}", headers=self._headers())
        assert r.status_code == 200
        assert r.json()["listing_id"] == self.created_id

    def test_update_listing(self):
        if not self.created_id:
            pytest.skip("Create test did not run")
        r = client.put(f"/listings/{self.created_id}",
                       json={"price_inr": 9000000.0, "verified": True},
                       headers=self._headers())
        assert r.status_code == 200
        assert float(r.json()["price_inr"]) == 9000000.0

    def test_update_nonexistent(self):
        r = client.put("/listings/9999999", json={"price_inr": 100000},
                       headers=self._headers())
        assert r.status_code == 404

    def test_delete_listing(self):
        if not self.created_id:
            pytest.skip("Create test did not run")
        r = client.delete(f"/listings/{self.created_id}", headers=self._headers())
        assert r.status_code == 204

    def test_deleted_listing_not_in_active_list(self):
        if not self.created_id:
            pytest.skip("Create test did not run")
        r = client.get(f"/listings?is_active=true&search=CRUD+Validation",
                       headers=self._headers())
        assert r.status_code == 200
        ids = [item["listing_id"] for item in r.json()["items"]]
        assert self.created_id not in ids


# ─── Agents CRUD Tests ────────────────────────────────────────────────────────
class TestAgentsCRUD:
    token = None
    created_id = None

    @classmethod
    def setup_class(cls):
        cls.token = get_token()

    def _headers(self):
        return auth_header(self.token)

    def test_list_agents(self):
        r = client.get("/agents", headers=self._headers())
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_agent(self):
        r = client.post("/agents", json={
            "contact_name": "Test Agent CRUD",
            "company_name": "Test Realty Ltd",
            "phone":        "+91 9000000001",
            "email":        "testagent@example.com",
        }, headers=self._headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["contact_name"] == "Test Agent CRUD"
        TestAgentsCRUD.created_id = data["agent_id"]

    def test_read_agent(self):
        if not self.created_id:
            pytest.skip()
        r = client.get(f"/agents/{self.created_id}", headers=self._headers())
        assert r.status_code == 200

    def test_update_agent(self):
        if not self.created_id:
            pytest.skip()
        r = client.put(f"/agents/{self.created_id}",
                       json={"phone": "+91 9000000099"},
                       headers=self._headers())
        assert r.status_code == 200
        assert r.json()["phone"] == "+91 9000000099"


# ─── Transactions CRUD Tests ──────────────────────────────────────────────────
class TestTransactionsCRUD:
    token = None
    created_id = None

    @classmethod
    def setup_class(cls):
        cls.token = get_token()

    def _headers(self):
        return auth_header(self.token)

    def test_list_transactions(self):
        r = client.get("/transactions?limit=5", headers=self._headers())
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_transaction(self):
        listings = client.get("/listings?size=1&is_active=true", headers=self._headers()).json()
        if not listings["items"]:
            pytest.skip("No listings available")
        lid = listings["items"][0]["listing_id"]
        r = client.post("/transactions", json={
            "listing_id":       lid,
            "sale_price":       7500000.0,
            "transaction_date": "2024-03-15",
            "buyer_name":       "Test Buyer CRUD",
            "ownership_type":   "Freehold",
            "status":           "Completed",
        }, headers=self._headers())
        assert r.status_code == 201, r.text
        TestTransactionsCRUD.created_id = r.json()["txn_id"]

    def test_update_transaction(self):
        if not self.created_id:
            pytest.skip()
        r = client.put(f"/transactions/{self.created_id}",
                       json={"status": "Pending", "notes": "Under review"},
                       headers=self._headers())
        assert r.status_code == 200
        assert r.json()["status"] == "Pending"

    def test_invalid_status(self):
        if not self.created_id:
            pytest.skip()
        r = client.put(f"/transactions/{self.created_id}",
                       json={"status": "InvalidStatus"},
                       headers=self._headers())
        assert r.status_code == 422
