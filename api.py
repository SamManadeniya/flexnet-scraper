import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from mangum import Mangum
import config
from database import db
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_current_user,
    get_current_user_optional,
)
from scraper.client import FlexnetHttpClient
from scraper.parser import FlexnetParser
from scraper.translator import translate_vehicle_to_english
from scraper.engine import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Flexnet Japan Scraper Service",
    description="High-performance web service to scrape vehicles from Flexnet Japan into Supabase and notify Google Sheets.",
    version="1.0.0"
)

# Enable CORS for JdmCarHunter frontend and Netlify
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchScrapeRequest(BaseModel):
    query: Optional[str] = Field(None, description="Car model, keyword, or name (e.g. 'Toyota Hiace', 'Land Cruiser 80')")
    limit: int = Field(10, description="Max vehicles to scrape and return (default 10)")
    min_year: Optional[int] = Field(None, description="Minimum model year (e.g. 1995)")
    max_year: Optional[int] = Field(None, description="Maximum model year (e.g. 2024)")
    min_price: Optional[int] = Field(None, description="Minimum price in JPY (e.g. 2000000)")
    max_price: Optional[int] = Field(None, description="Maximum price in JPY (e.g. 6000000)")
    min_km: Optional[int] = Field(None, description="Minimum mileage in km (e.g. 10000)")
    max_km: Optional[int] = Field(None, description="Maximum mileage in km (e.g. 100000)")
    drive_system: Optional[str] = Field(None, description="Drive system: '4WD' or '2WD'")
    fuel_type: Optional[str] = Field(None, description="Fuel: '1' (Gasoline), '2' (Diesel), '3' (Hybrid), '4' (EV)")
    no_repair_history: bool = Field(False, description="修復歴なし (No repair history)")
    inspection_included: bool = Field(False, description="車検付き (Vehicle inspection included)")
    is_new_car: bool = Field(False, description="新車 (New car)")
    is_used_car: bool = Field(False, description="中古車 (Used car)")
    is_renoca: bool = Field(False, description="Renoca custom vehicle")
    is_campervan: bool = Field(False, description="キャンピングカー (Campervan)")
    save_to_supabase: bool = Field(True, description="Save scraped vehicles directly to Supabase")
    notify_sheets: bool = Field(True, description="Send scrape notification to Google Sheets webhook")

class ScrapeStartRequest(BaseModel):
    max_pages: Optional[int] = Field(None, description="Max search catalog pages to crawl (100 cars/page)")
    max_cars: Optional[int] = Field(None, description="Max vehicle details to scrape")
    incremental: bool = Field(False, description="Skip vehicles already present in Supabase")
    scrape_details: bool = Field(True, description="Fetch full detail pages with all gallery photos and specs")
    concurrency: Optional[int] = Field(None, description="Concurrent request workers (default 5)")

class SingleScrapeRequest(BaseModel):
    url: str = Field(..., description="Full Flexnet car detail URL (e.g. https://www.flexnet.co.jp/detail/...html)")
    kanri_code: Optional[str] = Field(None, description="Optional kanriCode if already known")
    save_to_supabase: bool = Field(True, description="Save scraped vehicle directly to Supabase")

class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or Email")
    password: str = Field(..., description="Password (minimum 6 characters)")

class RegisterRequest(BaseModel):
    username: str = Field(..., description="Username or Email (minimum 3 characters)")
    password: str = Field(..., description="Password (minimum 6 characters)")
    role: Optional[str] = Field("admin", description="User role (admin or viewer)")

# -------------------------------------------------------------
# Authentication Endpoints
# -------------------------------------------------------------

@app.post("/api/auth/register")
async def register_user(req: RegisterRequest):
    """Register a new user account with securely hashed password in Supabase."""
    username = req.username.strip().lower()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    # Check if user already exists
    existing = db.get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="A user with this username or email already exists.")

    try:
        # Securely hash password with bcrypt (or PBKDF2 fallback)
        password_hash = hash_password(req.password)
        new_user = db.create_user(username=username, password_hash=password_hash, role=req.role or "admin")
        if not new_user:
            raise HTTPException(status_code=500, detail="Failed to create user record in database.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error during registration: {str(e)}")

    token = create_access_token({
        "sub": new_user["username"],
        "uid": str(new_user["id"]),
        "role": new_user.get("role", "admin")
    })

    return {
        "success": True,
        "message": "User registered successfully",
        "token": token,
        "user": {
            "id": new_user["id"],
            "username": new_user["username"],
            "role": new_user.get("role", "admin")
        }
    }

@app.post("/api/auth/login")
async def login_user(req: LoginRequest):
    """Authenticate user with password hash comparison and return a signed JWT token."""
    username = req.username.strip().lower()
    user = db.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    stored_hash = user.get("password_hash", "")
    if not verify_password(req.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_access_token({
        "sub": user["username"],
        "uid": str(user["id"]),
        "role": user.get("role", "admin")
    })

    return {
        "success": True,
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user.get("role", "admin")
        }
    }

@app.get("/api/auth/me")
async def get_current_user_profile(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns the authenticated user profile verified from Bearer JWT token."""
    return {
        "authenticated": True,
        "user": {
            "username": user.get("sub"),
            "id": user.get("uid"),
            "role": user.get("role", "admin")
        }
    }

@app.post("/api/auth/logout")
async def logout():
    """Client session termination confirmation."""
    return {"success": True, "message": "Logged out successfully"}

@app.get("/api/auth/users")
async def get_users_list(user: Dict[str, Any] = Depends(get_current_user)):
    """List registered users (admin-only, password hash omitted)."""
    return {
        "success": True,
        "users": db.list_users()
    }

# -------------------------------------------------------------
# System & Scraper Endpoints
# -------------------------------------------------------------

@app.get("/health")
def health_check():
    db_stats = db.get_stats()
    return {
        "status": "healthy",
        "database": db_stats,
        "scraper_running": engine.state.is_running
    }

@app.get("/api/stats")
def get_stats():
    return db.get_stats()

@app.get("/api/scrape/status")
def get_scrape_status():
    return engine.state.to_dict()

@app.post("/api/scrape/search")
async def scrape_by_criteria(req: SearchScrapeRequest):
    """
    Search and scrape matching vehicles on-demand from the Web Form.
    Directly returns the parsed vehicles, their specs, and all gallery photos.
    """
    try:
        result = await engine.scrape_search(
            query=req.query,
            limit=req.limit,
            min_year=req.min_year,
            max_year=req.max_year,
            min_price=req.min_price,
            max_price=req.max_price,
            min_km=req.min_km,
            max_km=req.max_km,
            drive_system=req.drive_system,
            fuel_type=req.fuel_type,
            no_repair_history=req.no_repair_history,
            inspection_included=req.inspection_included,
            is_new_car=req.is_new_car,
            is_used_car=req.is_used_car,
            is_renoca=req.is_renoca,
            is_campervan=req.is_campervan,
            save_to_supabase=req.save_to_supabase,
            notify_sheets=req.notify_sheets
        )
        return result
    except Exception as e:
        logger.error(f"Error in search scrape: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _background_scrape_task(req: ScrapeStartRequest):
    try:
        if req.concurrency:
            engine.concurrency = req.concurrency
        await engine.run_scrape(
            max_pages=req.max_pages,
            max_cars=req.max_cars,
            scrape_details=req.scrape_details,
            incremental=req.incremental
        )
    except Exception as e:
        logger.error(f"Background scrape encountered error: {e}", exc_info=True)

@app.post("/api/scrape/start")
def start_scrape(req: ScrapeStartRequest, background_tasks: BackgroundTasks):
    if engine.state.is_running:
        raise HTTPException(
            status_code=409,
            detail="A scrape job is already currently running. Check /api/scrape/status or send POST /api/scrape/stop."
        )

    background_tasks.add_task(_background_scrape_task, req)
    return {
        "message": "Scrape job initiated successfully in background.",
        "params": req.dict()
    }

@app.post("/api/scrape/stop")
def stop_scrape():
    if not engine.state.is_running:
        return {"message": "No active scrape job is running."}

    engine.stop()
    return {"message": "Stop signal sent to scraper. Gracefully shutting down..."}

@app.post("/api/scrape/single")
async def scrape_single_car(req: SingleScrapeRequest):
    """Scrape and save a single vehicle URL to Supabase on-demand."""
    async with FlexnetHttpClient(concurrency=1) as client:
        html = await client.get(req.url)
        if not html:
            raise HTTPException(status_code=404, detail="Could not retrieve the vehicle page from Flexnet.")

        kanri_code = req.kanri_code
        if not kanri_code:
            import re
            m = re.search(r"used-(\d+)\.html", req.url)
            if m:
                kanri_code = m.group(1)
            else:
                kanri_code = "UNKNOWN"

        vehicle_data = FlexnetParser.parse_detail_page(html, kanri_code, fallback_data={"detail_url": req.url})
        vehicle_data = translate_vehicle_to_english(vehicle_data)
        
        saved = False
        if req.save_to_supabase and db.is_connected():
            saved = db.upsert_vehicle(vehicle_data)

        return {
            "success": True,
            "saved_to_database": saved,
            "vehicle": vehicle_data
        }

# -------------------------------------------------------------
# Static Frontend (Web UI Form)
# -------------------------------------------------------------
public_dir = Path(__file__).resolve().parent / "public"

@app.get("/")
async def serve_index():
    index_path = public_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "service": "Flexnet Japan Scraper API",
        "status": "online",
        "docs": "/docs"
    }

@app.api_route("/favicon.svg", methods=["GET", "HEAD"], tags=["UI"])
async def serve_favicon():
    path = public_dir / "favicon.svg"
    if path.exists():
        return FileResponse(path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")

@app.api_route("/favicon.ico", methods=["GET", "HEAD"], tags=["UI"])
async def serve_favicon_ico():
    path = public_dir / "favicon.svg"
    if path.exists():
        return FileResponse(path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")

@app.api_route("/logo.svg", methods=["GET", "HEAD"], tags=["UI"])
async def serve_logo():
    path = public_dir / "logo.svg"
    if path.exists():
        return FileResponse(path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Logo not found")

if public_dir.exists():
    app.mount("/static", StaticFiles(directory=str(public_dir)), name="static")

# Mangum handler for Netlify Serverless Functions
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host=config.API_HOST, port=config.API_PORT, reload=True)
