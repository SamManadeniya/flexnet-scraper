import logging
from typing import Any, Dict, List, Optional, Set
from supabase import create_client, Client
from datetime import datetime, timezone
import config

logger = logging.getLogger(__name__)

def map_to_matched_vehicle(v: Dict[str, Any]) -> Dict[str, Any]:
    """Maps a Flexnet vehicle dict to the schema expected by public.matched_vehicles."""
    price_val = v.get("total_price") or v.get("vehicle_price")
    fob_str = f"¥ {int(price_val):,} JPY" if price_val else None
    
    options_list = v.get("equipment") or []
    options_str = ", ".join(options_list) if isinstance(options_list, list) else str(options_list or "")
    
    cond_parts = []
    if v.get("repair_history"):
        cond_parts.append(f"修復歴: {v['repair_history']}")
    if v.get("inspection"):
        cond_parts.append(f"車検: {v['inspection']}")
    if v.get("warranty"):
        cond_parts.append(f"保証: {v['warranty']}")
    if v.get("service_records"):
        cond_parts.append(f"記録簿: {v['service_records']}")
    if v.get("sliding_doors"):
        cond_parts.append(f"スライドドア: {v['sliding_doors']}")
    if v.get("recycle_fee"):
        cond_parts.append(f"リサイクル料: {v['recycle_fee']}")
    cond_str = " | ".join(cond_parts) if cond_parts else None

    engine_parts = []
    if v.get("displacement_raw"):
        engine_parts.append(v["displacement_raw"])
    if v.get("engine_type"):
        engine_parts.append(v["engine_type"])
    engine_str = " ".join(engine_parts) if engine_parts else None

    images = v.get("image_urls") or []
    if not images and v.get("thumbnail_url"):
        images = [v["thumbnail_url"]]

    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "source_portal": "flexnet",
        "status": "Found",
        "stock_ref": v.get("kanri_code") or v.get("sku") or "FLEX",
        "country_code": "JP",
        "title": v.get("title") or "FLEX Vehicle",
        "year_of_registration": v.get("model_year"),
        "make": v.get("brand") or "Toyota",
        "model": v.get("model") or "Hiace",
        "variant": v.get("tagline"),
        "km": v.get("mileage_raw"),
        "colour": v.get("color"),
        "engine": engine_str,
        "chassis": v.get("model_code"),
        "transmission": v.get("transmission"),
        "notes": v.get("sales_points"),
        "options": options_str,
        "condition": cond_str,
        "fuel": v.get("engine_type"),
        "drive_type": v.get("drive_system"),
        "fob_price": fob_str,
        "url": v.get("detail_url"),
        "images": images,
        "photo_count": len(images),
        "first_seen": now_iso,
        "last_updated": now_iso
    }

class DatabaseClient:
    def __init__(self):
        self.client: Optional[Client] = None
        self._target_table: Optional[str] = None
        if config.SUPABASE_URL and config.SUPABASE_KEY:
            try:
                self.client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
                logger.info("Connected to Supabase successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
        else:
            logger.warning("SUPABASE_URL or SUPABASE_KEY is missing. Database operations will be skipped.")

    def is_connected(self) -> bool:
        return self.client is not None

    def get_target_table(self) -> str:
        """Determines whether to write to 'flexnet_vehicles', 'vehicles', or fallback to 'matched_vehicles'."""
        if self._target_table:
            return self._target_table

        if not self.client:
            return "flexnet_vehicles"

        # 1. Check if 'flexnet_vehicles' table exists (Recommended dedicated table)
        try:
            self.client.table("flexnet_vehicles").select("id").limit(1).execute()
            self._target_table = "flexnet_vehicles"
            logger.info("Target table resolved to 'flexnet_vehicles'.")
            return "flexnet_vehicles"
        except Exception:
            pass

        # 2. Check if 'vehicles' table exists
        try:
            self.client.table("vehicles").select("id").limit(1).execute()
            self._target_table = "vehicles"
            logger.info("Target table resolved to 'vehicles'.")
            return "vehicles"
        except Exception:
            pass

        # 3. Check if 'matched_vehicles' table exists (JdmCarHunter shared table)
        try:
            self.client.table("matched_vehicles").select("id").limit(1).execute()
            self._target_table = "matched_vehicles"
            logger.info("Target table resolved to 'matched_vehicles' (JdmCarHunter table).")
            return "matched_vehicles"
        except Exception:
            pass

        self._target_table = "flexnet_vehicles"
        return "flexnet_vehicles"

    def get_table_columns(self, table_name: str) -> Optional[Set[str]]:
        """Fetch known columns for a table to prevent PGRST204 errors when new fields are added."""
        if not hasattr(self, "_columns_cache"):
            self._columns_cache = {}
        if table_name in self._columns_cache and self._columns_cache[table_name]:
            return self._columns_cache[table_name]

        if not self.client:
            return None

        try:
            res = self.client.table(table_name).select("*").limit(1).execute()
            if res.data and len(res.data) > 0:
                cols = set(res.data[0].keys())
                self._columns_cache[table_name] = cols
                logger.info(f"Discovered {len(cols)} columns in Supabase table '{table_name}'.")
                return cols
        except Exception as e:
            logger.debug(f"Could not inspect columns for {table_name}: {e}")
        return None

    def filter_to_table_columns(self, record: Dict[str, Any], table_name: str) -> Dict[str, Any]:
        """Strip keys that do not exist yet in the target table in Supabase."""
        cols = self.get_table_columns(table_name)
        if cols:
            return {k: v for k, v in record.items() if k in cols}
        return record

    def upsert_vehicle(self, vehicle: Dict[str, Any]) -> bool:
        """Upsert a single vehicle into active Supabase table."""
        if not self.client:
            return False

        table_name = self.get_target_table()
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            if table_name in ["flexnet_vehicles", "vehicles"]:
                vehicle_data = self.filter_to_table_columns(vehicle, table_name)
                vehicle_data["last_scraped_at"] = now_iso
                self.client.table(table_name).upsert(
                    vehicle_data, on_conflict="kanri_code"
                ).execute()
                return True
            else:
                # matched_vehicles table
                mapped = map_to_matched_vehicle(vehicle)
                stock_ref = mapped["stock_ref"]
                existing = self.client.table("matched_vehicles").select("id").eq("stock_ref", stock_ref).execute()
                if existing.data:
                    record_id = existing.data[0]["id"]
                    self.client.table("matched_vehicles").update(mapped).eq("id", record_id).execute()
                else:
                    self.client.table("matched_vehicles").insert(mapped).execute()
                return True
        except Exception as e:
            logger.error(f"Error saving vehicle {vehicle.get('kanri_code')} to {table_name}: {e}")
            return False

    def batch_upsert_vehicles(self, vehicles: List[Dict[str, Any]], chunk_size: int = 40) -> int:
        """Batch upsert vehicles with chunking for optimal Supabase API throughput."""
        if not self.client or not vehicles:
            return 0

        table_name = self.get_target_table()
        now_iso = datetime.now(timezone.utc).isoformat()
        total_upserted = 0

        if table_name in ["flexnet_vehicles", "vehicles"]:
            sanitized_vehicles = []
            for v in vehicles:
                cleaned = self.filter_to_table_columns(v, table_name)
                cleaned["last_scraped_at"] = now_iso
                sanitized_vehicles.append(cleaned)

            for i in range(0, len(sanitized_vehicles), chunk_size):
                chunk = sanitized_vehicles[i:i + chunk_size]
                try:
                    self.client.table(table_name).upsert(
                        chunk, on_conflict="kanri_code"
                    ).execute()
                    total_upserted += len(chunk)
                except Exception as e:
                    logger.error(f"Error in batch upsert to '{table_name}': {e}")
                    for v in chunk:
                        try:
                            self.client.table(table_name).upsert(
                                v, on_conflict="kanri_code"
                            ).execute()
                            total_upserted += 1
                        except Exception as err:
                            logger.error(f"Failed to upsert car {v.get('kanri_code')}: {err}")

        else:
            # Fallback to matched_vehicles
            mapped_records = [map_to_matched_vehicle(v) for v in vehicles]
            
            # Fetch all existing stock_refs to know which to update vs insert
            existing_codes = self.get_existing_kanri_codes()
            to_insert = []
            to_update = []

            for r in mapped_records:
                if r["stock_ref"] in existing_codes:
                    to_update.append(r)
                else:
                    to_insert.append(r)

            # Insert new records in batches
            for i in range(0, len(to_insert), chunk_size):
                chunk = to_insert[i:i + chunk_size]
                try:
                    self.client.table("matched_vehicles").insert(chunk).execute()
                    total_upserted += len(chunk)
                except Exception as e:
                    logger.error(f"Error batch inserting to matched_vehicles: {e}")

            # Update existing records individually
            for r in to_update:
                try:
                    self.client.table("matched_vehicles").update(r).eq("stock_ref", r["stock_ref"]).execute()
                    total_upserted += 1
                except Exception as e:
                    logger.warning(f"Error updating car {r['stock_ref']}: {e}")

        return total_upserted

    def get_existing_kanri_codes(self) -> Set[str]:
        """Fetch all existing vehicle codes to avoid redundant detail page scrapes."""
        if not self.client:
            return set()
        table_name = self.get_target_table()
        try:
            if table_name in ["flexnet_vehicles", "vehicles"]:
                response = self.client.table(table_name).select("kanri_code").execute()
                return {item["kanri_code"] for item in response.data if item.get("kanri_code")}
            else:
                response = self.client.table("matched_vehicles").select("stock_ref").eq("source_portal", "flexnet").execute()
                return {item["stock_ref"] for item in response.data if item.get("stock_ref")}
        except Exception as e:
            logger.warning(f"Could not fetch existing vehicle codes from {table_name}: {e}")
            return set()

    def mark_missing_as_sold(self, current_active_codes: Set[str]) -> int:
        """Mark vehicles no longer listed on Flexnet as 'sold'."""
        if not self.client or not current_active_codes:
            return 0
        table_name = self.get_target_table()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            if table_name in ["flexnet_vehicles", "vehicles"]:
                response = self.client.table(table_name).select("kanri_code").eq("status", "available").execute()
                db_available = {item["kanri_code"] for item in response.data if item.get("kanri_code")}
                sold_codes = db_available - current_active_codes
                sold_list = list(sold_codes)
                for i in range(0, len(sold_list), 50):
                    batch = sold_list[i:i + 50]
                    self.client.table(table_name).update({
                        "status": "sold",
                        "last_scraped_at": now_iso
                    }).in_("kanri_code", batch).execute()
                return len(sold_codes)
            else:
                response = self.client.table("matched_vehicles").select("stock_ref").eq("source_portal", "flexnet").eq("status", "Found").execute()
                db_available = {item["stock_ref"] for item in response.data if item.get("stock_ref")}
                sold_codes = db_available - current_active_codes
                sold_list = list(sold_codes)
                for i in range(0, len(sold_list), 50):
                    batch = sold_list[i:i + 50]
                    self.client.table("matched_vehicles").update({
                        "status": "Sold",
                        "last_updated": now_iso
                    }).in_("stock_ref", batch).execute()
                return len(sold_codes)
        except Exception as e:
            logger.error(f"Error marking missing vehicles as sold: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get inventory summary counts from Supabase."""
        if not self.client:
            return {"status": "disconnected"}
        table_name = self.get_target_table()
        try:
            if table_name in ["flexnet_vehicles", "vehicles"]:
                total_res = self.client.table(table_name).select("id", count="exact").execute()
                available_res = self.client.table(table_name).select("id", count="exact").eq("status", "available").execute()
                sold_res = self.client.table(table_name).select("id", count="exact").eq("status", "sold").execute()
                return {
                    "table": table_name,
                    "total_vehicles": total_res.count or 0,
                    "available_vehicles": available_res.count or 0,
                    "sold_vehicles": sold_res.count or 0,
                    "connected": True
                }
            else:
                total_res = self.client.table("matched_vehicles").select("id", count="exact").eq("source_portal", "flexnet").execute()
                found_res = self.client.table("matched_vehicles").select("id", count="exact").eq("source_portal", "flexnet").eq("status", "Found").execute()
                return {
                    "table": "matched_vehicles",
                    "total_vehicles": total_res.count or 0,
                    "available_vehicles": found_res.count or 0,
                    "sold_vehicles": (total_res.count or 0) - (found_res.count or 0),
                    "connected": True
                }
        except Exception as e:
            return {"error": str(e), "connected": False}

    # ---------------------------------------------------------
    # User Authentication & Management
    # ---------------------------------------------------------
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user by username or email from Supabase public.users table."""
        if not self.client or not username:
            return None
        try:
            res = self.client.table("users").select("*").eq("username", username.strip().lower()).limit(1).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            logger.error(f"Error fetching user by username '{username}': {e}")
        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user by primary key ID."""
        if not self.client or not user_id:
            return None
        try:
            res = self.client.table("users").select("*").eq("id", str(user_id)).limit(1).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            logger.error(f"Error fetching user by ID '{user_id}': {e}")
        return None

    def create_user(self, username: str, password_hash: str, role: str = "admin") -> Optional[Dict[str, Any]]:
        """Insert a newly registered user into public.users."""
        if not self.client or not username or not password_hash:
            return None
        try:
            user_payload = {
                "username": username.strip().lower(),
                "password_hash": password_hash,
                "role": role
            }
            res = self.client.table("users").insert(user_payload).execute()
            if res.data:
                logger.info(f"User '{username}' registered successfully.")
                return res.data[0]
        except Exception as e:
            logger.error(f"Error creating user '{username}': {e}")
            raise e
        return None

    def list_users(self) -> List[Dict[str, Any]]:
        """List registered users (excluding sensitive password hash)."""
        if not self.client:
            return []
        try:
            res = self.client.table("users").select("id, username, role, created_at").order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []

# Singleton instance
db = DatabaseClient()
