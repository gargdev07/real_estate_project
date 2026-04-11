from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os


from database import check_db_connection
from routers import auth_router, listings, agents, transactions, analytics

# ── CREATE APP ─────────────────────────────────────────────
app = FastAPI(
    title="Real Estate Listing & Market Analysis API",
    description="""
## Real Estate Listing & Market Analysis System

A complete backend for managing Indian real estate listings, agents, buyers, and transactions
across **Gurgaon, Hyderabad, Kolkata, and Mumbai** (~180k listings).

### Features
- 🏠 Full CRUD for **Listings**, **Agents**, and **Transactions**
- 📊 5 analytical endpoints powering the dashboard visualizations
- 🔐 JWT-based authentication (Bearer token)
- ⚡ Materialized views for sub-100ms analytics queries
- 📈 Price trends, locality demand heatmap, property distribution, agent leaderboard

### Quick Start
1. `POST /auth/login` with `username=admin` / `password=admin123`
2. Copy the `access_token` and click **Authorize** above
3. Explore all endpoints

### Default Users
| Username | Password | Role |
|---|---|---|
| admin | admin123 | admin |
| analyst | analyst123 | analyst |
    """,
    version="1.0.0",
    contact={"name": "Real Estate Analytics Team"},
    license_info={"name": "MIT"},
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler — ensures CORS headers are always present even on 500s
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(listings.router)
app.include_router(agents.router)
app.include_router(transactions.router)
app.include_router(analytics.router)

# ── Static files (serve frontend) ────────────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="API health check")
def health():
    db_ok = check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "version": "1.0.0",
    }


@app.get("/", tags=["Health"], include_in_schema=False)
def root():
    return {
        "message": "Real Estate API is running",
        "docs": "/docs",
        "health": "/health",
        "frontend": "/app",
    }
