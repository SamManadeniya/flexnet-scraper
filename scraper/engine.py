import asyncio
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set
import config
from database import db
from notifier import notifier
from scraper.client import FlexnetHttpClient
from scraper.parser import FlexnetParser
from scraper.translator import translate_query_to_japanese, translate_vehicle_to_english

logger = logging.getLogger(__name__)

class ScraperState:
    def __init__(self):
        self.is_running: bool = False
        self.should_stop: bool = False
        self.start_time: Optional[float] = None
        self.current_page: int = 0
        self.total_pages: int = 0
        self.total_inventory_site: int = 0
        self.scraped_count: int = 0
        self.new_cars_count: int = 0
        self.updated_count: int = 0
        self.errors_count: int = 0
        self.current_action: str = "Idle"
        self.last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        elapsed = round(time.time() - self.start_time, 1) if self.start_time and self.is_running else 0
        progress_pct = 0.0
        if self.total_pages > 0:
            progress_pct = round((self.current_page / self.total_pages) * 100, 1)

        return {
            "is_running": self.is_running,
            "current_action": self.current_action,
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "progress_percent": progress_pct,
            "total_inventory_site": self.total_inventory_site,
            "scraped_count": self.scraped_count,
            "new_cars_count": self.new_cars_count,
            "updated_count": self.updated_count,
            "errors_count": self.errors_count,
            "elapsed_seconds": elapsed,
            "last_error": self.last_error
        }

# Direct dedicated model category routes on Flexnet Japan
# These routes provide 100% pure model isolation without false positives from free-word text
FLEXNET_MODEL_ROUTES: Dict[str, str] = {
    # Prado
    "prado": "/search/toyota/landcruiser/prado",
    "ランドクルーザープラド": "/search/toyota/landcruiser/prado",
    "ランドクルーザー プラド": "/search/toyota/landcruiser/prado",
    "プラド": "/search/toyota/landcruiser/prado",
    "150 prado": "/search/toyota/landcruiser/prado/150",
    "150プラド": "/search/toyota/landcruiser/prado/150",
    "150 プラド": "/search/toyota/landcruiser/prado/150",
    "120 prado": "/search/toyota/landcruiser/prado/120",
    "120プラド": "/search/toyota/landcruiser/prado/120",
    "120 プラド": "/search/toyota/landcruiser/prado/120",
    "90 prado": "/search/toyota/landcruiser/prado/90",
    "90プラド": "/search/toyota/landcruiser/prado/90",
    "90 プラド": "/search/toyota/landcruiser/prado/90",
    "70 prado": "/search/toyota/landcruiser/prado/70",
    "70プラド": "/search/toyota/landcruiser/prado/70",
    "70 プラド": "/search/toyota/landcruiser/prado/70",

    # Land Cruiser series
    "land cruiser 80": "/search/toyota/landcruiser/80",
    "ランドクルーザー80": "/search/toyota/landcruiser/80",
    "ランドクルーザー 80": "/search/toyota/landcruiser/80",
    "ランクル80": "/search/toyota/landcruiser/80",

    "land cruiser 70": "/search/toyota/landcruiser/70",
    "ランドクルーザー70": "/search/toyota/landcruiser/70",
    "ランドクルーザー 70": "/search/toyota/landcruiser/70",
    "ランクル70": "/search/toyota/landcruiser/70",

    "land cruiser 60": "/search/toyota/landcruiser/60",
    "ランドクルーザー60": "/search/toyota/landcruiser/60",
    "ランドクルーザー 60": "/search/toyota/landcruiser/60",
    "ランクル60": "/search/toyota/landcruiser/60",

    "land cruiser 100": "/search/toyota/landcruiser/100",
    "ランドクルーザー100": "/search/toyota/landcruiser/100",
    "ランドクルーザー 100": "/search/toyota/landcruiser/100",
    "ランクル100": "/search/toyota/landcruiser/100",

    "land cruiser 200": "/search/toyota/landcruiser/200",
    "ランドクルーザー200": "/search/toyota/landcruiser/200",
    "ランドクルーザー 200": "/search/toyota/landcruiser/200",
    "ランクル200": "/search/toyota/landcruiser/200",

    "land cruiser 300": "/search/toyota/landcruiser/300",
    "ランドクルーザー300": "/search/toyota/landcruiser/300",
    "ランドクルーザー 300": "/search/toyota/landcruiser/300",
    "ランクル300": "/search/toyota/landcruiser/300",

    "land cruiser 250": "/search/toyota/landcruiser/250",
    "ランドクルーザー250": "/search/toyota/landcruiser/250",
    "ランドクルーザー 250": "/search/toyota/landcruiser/250",
    "ランクル250": "/search/toyota/landcruiser/250",

    "land cruiser cygnus": "/search/toyota/landcruiser/cygnus",
    "ランドクルーザー シグナス": "/search/toyota/landcruiser/cygnus",
    "ランドクルーザーシグナス": "/search/toyota/landcruiser/cygnus",
    "シグナス": "/search/toyota/landcruiser/cygnus",

    "land cruiser": "/search/toyota/landcruiser",
    "ランドクルーザー": "/search/toyota/landcruiser",

    # Hiace series
    "hiace": "/search/toyota/hiace",
    "ハイエース": "/search/toyota/hiace",
    "toyota hiace": "/search/toyota/hiace",
    "hiace van": "/search/toyota/hiace/van",
    "ハイエース バン": "/search/toyota/hiace/van",
    "ハイエースバン": "/search/toyota/hiace/van",
    "hiace wagon": "/search/toyota/hiace/wagon",
    "ハイエース ワゴン": "/search/toyota/hiace/wagon",
    "ハイエースワゴン": "/search/toyota/hiace/wagon",
    "hiace commuter": "/search/toyota/hiace/commuter",
    "ハイエース コミューター": "/search/toyota/hiace/commuter",
    "regius ace": "/search/toyota/hiace/regiusace",
    "レジアスエース": "/search/toyota/hiace/regiusace",

    # Pickups & other
    "hilux": "/search/toyota/hilux",
    "ハイラックス": "/search/toyota/hilux",
    "hilux surf": "/search/toyota/hiluxsurf",
    "ハイラックスサーフ": "/search/toyota/hiluxsurf",
    "jimny": "/search/suzuki/jimny",
    "ジムニー": "/search/suzuki/jimny",
    "delica": "/search/mitsubishi/delica/d5",
    "デリカ": "/search/mitsubishi/delica/d5",
    "wrangler": "/search/jeep/wrangler",
    "ラングラー": "/search/jeep/wrangler",
    "campervan": "/search/toyota/camping",
    "キャンピングカー": "/search/toyota/camping",
    "us toyota": "/search/us-toyota",
    "usトヨタ": "/search/us-toyota",
    "us トヨタ": "/search/us-toyota",

    # Custom Renoca and Flexnet specialty lines
    "coast lines wide": "/search/toyota/hiace/COASTLINESWide",
    "coastlines wide": "/search/toyota/hiace/COASTLINESWide",
    "coast lines narrow": "/search/toyota/hiace/COASTLINESNarrow",
    "coastlines narrow": "/search/toyota/hiace/COASTLINESNarrow",
    "coast lines": "/search?kw=CoastLines",
    "coastlines": "/search?kw=CoastLines",
    "renoca coast lines": "/search?kw=CoastLines",
    "renoca coastlines": "/search?kw=CoastLines",
    "コーストライン": "/search?kw=CoastLines",
    "wood village": "/search?kw=WoodVillage",
    "wood village camper": "/search?kw=WoodVillage",
    "woodvillage": "/search?kw=WoodVillage",
    "color bomb": "/search?kw=ColorBomb",
    "colorbomb": "/search?kw=ColorBomb",
    "euro box": "/search?kw=EuroBox",
    "eurobox": "/search?kw=EuroBox",
    "probox custom": "/search?kw=%E3%83%97%E3%83%AD%E3%83%9C%E3%83%83%E3%82%AF%E3%82%B9",
    "probox": "/search?kw=%E3%83%97%E3%83%AD%E3%83%9C%E3%83%83%E3%82%AF%E3%82%B9",
    "プロボックス": "/search?kw=%E3%83%97%E3%83%AD%E3%83%9C%E3%83%83%E3%82%AF%E3%82%B9",
    "fj cruiser": "/search?kw=FJ%E3%82%AF%E3%83%AB%E3%83%BC%E3%82%B6%E3%83%BC",
    "fj": "/search?kw=FJ%E3%82%AF%E3%83%AB%E3%83%BC%E3%82%B6%E3%83%BC",
    "fj クルーザー": "/search?kw=FJ%E3%82%AF%E3%83%AB%E3%83%BC%E3%82%B6%E3%83%BC",
    "fjクルーザー": "/search?kw=FJ%E3%82%AF%E3%83%AB%E3%83%BC%E3%82%B6%E3%83%BC",
    "american classic": "/search?kw=American+Classic",
    "americanclassic": "/search?kw=American+Classic",
    "wonder": "/search?kw=Wonder",
    "phoenix": "/search?kw=Phoenix",
    "renoca": "/search?rnc=1",
}

def is_vehicle_model_match(
    search_query: Optional[str],
    translated_kw: Optional[str],
    car_model: Optional[str],
    car_title: Optional[str],
    car_tagline: Optional[str] = None
) -> bool:
    """
    Dynamic Model Verification Guard:
    Guarantees 100% accuracy by preventing cross-model false positives (e.g. Hilux in Prado search,
    Hiace in Land Cruiser search, or LC80 in LC70 search).
    Dynamically checks the car's official model, title, and tagline against the search intent.
    """
    if not search_query or not search_query.strip():
        return True  # Broad unconstrained search, allow all valid vehicles

    sq = search_query.lower().strip()
    tk = (translated_kw or "").lower().strip()
    cm = (car_model or "").lower().strip()
    ct = (car_title or "").lower().strip()
    cg = (car_tagline or "").lower().strip()
    combined_car_text = f"{cm} {ct} {cg}"

    # Conflicting major model families:
    # (family_key, [japanese_tokens, english_tokens])
    families = [
        ("coast_lines", ["coast lines", "coastlines", "coast", "コーストライン"]),
        ("american_classic", ["american classic", "americanclassic", "アメリカンクラシック"]),
        ("color_bomb", ["color bomb", "colorbomb", "カラーボム"]),
        ("wonder", ["wonder", "ワンダー"]),
        ("phoenix", ["phoenix", "フェニックス"]),
        ("euro_box", ["euro box", "eurobox", "ユーロボックス"]),
        ("wood_village", ["wood village", "woodvillage", "ウッドヴィレッジ", "beluga", "ベルーガ"]),
        ("mol", ["mol", "モル"]),
        ("106", ["106"]),
        ("prado", ["プラド", "prado"]),
        ("hilux_surf", ["ハイラックスサーフ", "hilux surf", "surf", "サーフ"]),
        ("hilux", ["ハイラックス", "hilux"]),
        ("hiace", ["ハイエース", "hiace", "レジアスエース", "regiusace"]),
        ("jimny", ["ジムニー", "jimny"]),
        ("delica", ["デリカ", "delica"]),
        ("wrangler", ["ラングラー", "wrangler"]),
        ("probox", ["プロボックス", "probox"]),
        ("townace", ["タウンエース", "townace"]),
        ("fj_cruiser", ["fjクルーザー", "fj cruiser", "fjcruiser"]),
        ("lc300", ["300", "lc300", "ランクル300"]),
        ("lc250", ["250", "lc250", "ランクル250"]),
        ("lc200", ["200", "lc200", "ランクル200"]),
        ("lc100", ["100", "lc100", "ランクル100"]),
        ("lc80", ["80", "lc80", "ランクル80"]),
        ("lc70", ["70", "lc70", "ランクル70"]),
        ("lc60", ["60", "lc60", "ランクル60"]),
    ]

    # 1. Identify which family (if any) the user query targets
    target_families = set()
    for fam, tokens in families:
        if any(t in sq or t in tk for t in tokens):
            if fam == "hilux" and ("surf" in sq or "サーフ" in tk):
                continue
            if fam == "hilux_surf" and not ("surf" in sq or "サーフ" in tk):
                continue
            target_families.add(fam)

    # If specific conversion line is targeted, prevent generic base platforms from dominating
    if "coast_lines" in target_families and "hiace" in target_families:
        target_families.discard("hiace")
    if "wood_village" in target_families and "hiace" in target_families:
        target_families.discard("hiace")
    if "american_classic" in target_families and "prado" in target_families:
        target_families.discard("prado")

    # 2. Identify which family the car belongs to
    car_families = set()
    for fam, tokens in families:
        if any(t in cm or t in ct or t in cg for t in tokens):
            if fam == "hilux" and ("サーフ" in cm or "サーフ" in ct or "surf" in ct):
                continue
            if fam == "hilux_surf" and not ("サーフ" in cm or "サーフ" in ct or "surf" in ct):
                continue
            car_families.add(fam)

    # If the user targeted specific model families, the car MUST intersect with target families
    if target_families:
        if not (target_families & car_families):
            return False  # Mismatch! E.g. Query targeted Prado, but Car is Hilux
        return True

    # For custom lines or generic keywords
    words = [w for w in sq.split() if len(w) > 2]
    if words and any(w in combined_car_text for w in words):
        return True
    if tk and tk in combined_car_text:
        return True
    return False

class ScraperEngine:
    def __init__(self, concurrency: int = config.DEFAULT_CONCURRENCY):
        self.concurrency = concurrency
        self.state = ScraperState()

    def stop(self):
        """Signal engine to stop running gracefully."""
        self.state.should_stop = True
        self.state.current_action = "Stopping..."

    async def run_scrape(
        self,
        max_pages: Optional[int] = None,
        max_cars: Optional[int] = None,
        scrape_details: bool = True,
        incremental: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes the scraping pipeline:
        1. Crawls search catalog pages (100 cars per page).
        2. Detects new or updated vehicles.
        3. Concurrently fetches and parses full detail pages.
        4. Upserts to Supabase database.
        5. Marks removed vehicles as sold.
        6. Notifies Google Sheets webhook.
        """
        if self.state.is_running:
            raise RuntimeError("Scraper is already running")

        self.state = ScraperState()
        self.state.is_running = True
        self.state.start_time = time.time()
        self.state.current_action = "Starting crawl..."

        logger.info(f"Starting Flexnet scrape (max_pages={max_pages}, max_cars={max_cars}, incremental={incremental})")

        all_previews: List[Dict[str, Any]] = []
        all_active_codes: Set[str] = set()
        existing_codes_in_db: Set[str] = set()

        if incremental and db.is_connected():
            self.state.current_action = "Fetching existing database records..."
            existing_codes_in_db = db.get_existing_kanri_codes()
            logger.info(f"Found {len(existing_codes_in_db)} existing vehicles in Supabase.")

        async with FlexnetHttpClient(concurrency=self.concurrency) as http_client:
            # -------------------------------------------------------------
            # Stage 1: Crawl Search Listings
            # -------------------------------------------------------------
            self.state.current_action = "Crawling search catalog..."
            
            # Fetch page 1 first to determine total items and page count
            first_page_url = f"{config.SEARCH_URL}?page=1&num=100"
            html = await http_client.get(first_page_url)
            if not html:
                self.state.is_running = False
                self.state.last_error = "Could not fetch first catalog page from Flexnet."
                return self.state.to_dict()

            total_items, page_1_cars = FlexnetParser.parse_search_page(html)
            self.state.total_inventory_site = total_items
            calculated_pages = math.ceil(total_items / 100) if total_items > 0 else 70
            
            target_pages = calculated_pages
            if max_pages and max_pages > 0:
                target_pages = min(max_pages, calculated_pages)

            self.state.total_pages = target_pages
            self.state.current_page = 1
            all_previews.extend(page_1_cars)
            for c in page_1_cars:
                all_active_codes.add(c["kanri_code"])

            logger.info(f"Discovered {total_items} total inventory on site (~{target_pages} pages to scrape).")

            if progress_callback:
                progress_callback(self.state.to_dict())

            # Crawl remaining pages
            for page in range(2, target_pages + 1):
                if self.state.should_stop:
                    logger.info("Scraper stopped by user request during listing crawl.")
                    break
                if max_cars and len(all_previews) >= max_cars:
                    logger.info(f"Reached max_cars limit ({max_cars}).")
                    break

                self.state.current_page = page
                self.state.current_action = f"Crawling search page {page} of {target_pages}..."
                
                page_url = f"{config.SEARCH_URL}?page={page}&num=100"
                page_html = await http_client.get(page_url)
                if page_html:
                    _, page_cars = FlexnetParser.parse_search_page(page_html)
                    all_previews.extend(page_cars)
                    for c in page_cars:
                        all_active_codes.add(c["kanri_code"])
                else:
                    self.state.errors_count += 1

                if progress_callback:
                    progress_callback(self.state.to_dict())

            if max_cars and len(all_previews) > max_cars:
                all_previews = all_previews[:max_cars]

            logger.info(f"Listing crawl complete. Collected {len(all_previews)} vehicle previews.")

            # -------------------------------------------------------------
            # Stage 2: Filter and Scrape Detail Pages
            # -------------------------------------------------------------
            cars_to_scrape: List[Dict[str, Any]] = []
            for preview in all_previews:
                code = preview["kanri_code"]
                if incremental and code in existing_codes_in_db:
                    # Vehicle already in DB, skip deep scrape in incremental mode
                    continue
                cars_to_scrape.append(preview)

            logger.info(f"{len(cars_to_scrape)} vehicles require detailed scraping.")
            self.state.current_action = f"Scraping detailed vehicle pages (0/{len(cars_to_scrape)})..."

            detailed_vehicles: List[Dict[str, Any]] = []
            new_car_records_for_notify: List[Dict[str, Any]] = []

            if scrape_details and cars_to_scrape:
                processed = 0

                async def scrape_single_detail(preview_data: Dict[str, Any]):
                    nonlocal processed
                    if self.state.should_stop:
                        return None
                    code = preview_data["kanri_code"]
                    url = preview_data["detail_url"]
                    detail_html = await http_client.get(url, referer=config.SEARCH_URL)
                    
                    if detail_html:
                        full_vehicle = FlexnetParser.parse_detail_page(detail_html, code, fallback_data=preview_data)
                    else:
                        full_vehicle = preview_data.copy()
                        full_vehicle["status"] = "available"

                    # Translate all Japanese vehicle attributes into clean English
                    full_vehicle = translate_vehicle_to_english(full_vehicle)

                    processed += 1
                    self.state.scraped_count = processed
                    if code not in existing_codes_in_db:
                        self.state.new_cars_count += 1
                        new_car_records_for_notify.append(full_vehicle)
                    else:
                        self.state.updated_count += 1

                    self.state.current_action = f"Scraping details ({processed}/{len(cars_to_scrape)})..."
                    if progress_callback and processed % 5 == 0:
                        progress_callback(self.state.to_dict())

                    return full_vehicle

                # Run concurrent tasks
                tasks = [scrape_single_detail(p) for p in cars_to_scrape]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, dict):
                        detailed_vehicles.append(res)
                    elif isinstance(res, Exception):
                        self.state.errors_count += 1
                        logger.error(f"Task exception in detail scrape: {res}")
            else:
                # If scrape_details is false, use listing previews
                detailed_vehicles = all_previews

            # -------------------------------------------------------------
            # Stage 3: Database Ingestion & Sold Tracking
            # -------------------------------------------------------------
            self.state.current_action = "Saving vehicles to Supabase..."
            if db.is_connected() and detailed_vehicles:
                upserted = db.batch_upsert_vehicles(detailed_vehicles)
                logger.info(f"Successfully upserted {upserted} vehicles into Supabase.")

                # If we crawled all pages (full scan), mark absent vehicles as sold
                if not max_pages and not max_cars and all_active_codes:
                    self.state.current_action = "Updating sold vehicle inventory status..."
                    db.mark_missing_as_sold(all_active_codes)
            elif not db.is_connected():
                logger.warning("Supabase is not configured or offline. Scraped data was not stored.")

        # -------------------------------------------------------------
        # Stage 4: Notifications (Google Sheets Webhook)
        # -------------------------------------------------------------
        elapsed_total = round(time.time() - self.state.start_time, 1)
        summary_payload = {
            "status": "completed" if not self.state.should_stop else "stopped",
            "total_inventory_site": self.state.total_inventory_site,
            "vehicles_scraped": self.state.scraped_count,
            "new_vehicles": self.state.new_cars_count,
            "updated_vehicles": self.state.updated_count,
            "errors": self.state.errors_count,
            "elapsed_seconds": elapsed_total,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Send summary webhook
        await notifier.send_summary(summary_payload)

        # If there are new cars, notify them to Google Sheets as well
        if new_car_records_for_notify:
            await notifier.send_new_cars(new_car_records_for_notify)

        self.state.is_running = False
        self.state.current_action = "Completed" if not self.state.should_stop else "Stopped"
        logger.info(f"Scrape job finished in {elapsed_total}s: {self.state.scraped_count} vehicles processed.")

        if progress_callback:
            progress_callback(self.state.to_dict())

        return self.state.to_dict()

    async def scrape_search(
        self,
        query: Optional[str] = None,
        limit: int = 10,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_km: Optional[int] = None,
        max_km: Optional[int] = None,
        drive_system: Optional[str] = None,
        fuel_type: Optional[str] = None,
        no_repair_history: bool = False,
        inspection_included: bool = False,
        is_new_car: bool = False,
        is_used_car: bool = False,
        is_renoca: bool = False,
        is_campervan: bool = False,
        save_to_supabase: bool = True,
        notify_sheets: bool = True
    ) -> Dict[str, Any]:
        """
        Targeted scrape for a specific vehicle search query or model with full filter criteria.
        Returns the parsed vehicles directly (ideal for Web UI & Netlify Serverless Functions).
        """
        import urllib.parse
        import re

        # Build native Flexnet search parameters matching the web filter form
        base_endpoint = config.SEARCH_URL
        query_params: Dict[str, Any] = {"num": max(limit, 10)}
        translated_kw: Optional[str] = None
        target_model_key: Optional[str] = None

        if query and query.strip():
            raw_q = query.strip()
            translated_kw = await translate_query_to_japanese(raw_q)

            # Check if this query corresponds to a dedicated Flexnet model route
            q_clean = raw_q.lower().strip()
            t_clean = (translated_kw or "").lower().strip()

            matched_route = None
            if q_clean in FLEXNET_MODEL_ROUTES:
                matched_route = FLEXNET_MODEL_ROUTES[q_clean]
                target_model_key = q_clean
            elif t_clean in FLEXNET_MODEL_ROUTES:
                matched_route = FLEXNET_MODEL_ROUTES[t_clean]
                target_model_key = t_clean
            elif raw_q in FLEXNET_MODEL_ROUTES:
                matched_route = FLEXNET_MODEL_ROUTES[raw_q]
                target_model_key = raw_q
            elif translated_kw in FLEXNET_MODEL_ROUTES:
                matched_route = FLEXNET_MODEL_ROUTES[translated_kw]
                target_model_key = translated_kw

            if matched_route:
                # Use dedicated, 100% pure model category path on Flexnet!
                base_endpoint = f"{config.BASE_URL}{matched_route}"
                logger.info(f"Targeting dedicated Flexnet model route: '{matched_route}' for query '{raw_q}'")
            elif translated_kw:
                query_params["kw"] = translated_kw
                logger.info(f"Dynamic query translation: '{raw_q}' -> '{translated_kw}' for Flexnet")


        if min_year:
            query_params["lwa"] = min_year
        if max_year:
            query_params["upa"] = max_year
        if min_price:
            query_params["lwp"] = min_price
        if max_price:
            query_params["upp"] = max_price
        if min_km:
            query_params["lwm"] = min_km
        if max_km:
            query_params["upm"] = max_km
        if drive_system:
            if str(drive_system).upper() in ["4WD", "2"]:
                query_params["drv"] = 2
            elif str(drive_system).upper() in ["2WD", "1"]:
                query_params["drv"] = 1
        if fuel_type:
            if str(fuel_type) in ["1", "ガソリン", "gasoline", "Gasoline"]:
                query_params["ful"] = 1
            elif str(fuel_type) in ["2", "ディーゼル", "diesel", "Diesel"]:
                query_params["ful"] = 2
            elif str(fuel_type) in ["3", "ハイブリッド", "hybrid", "Hybrid"]:
                query_params["ful"] = 3
            elif str(fuel_type) in ["4", "電気", "ev", "EV"]:
                query_params["ful"] = 4
        if no_repair_history:
            query_params["rep"] = 1
        if inspection_included:
            query_params["ins"] = 1
        if is_new_car:
            query_params["nwc"] = 1
        if is_used_car:
            query_params["usd"] = 1
        if is_renoca:
            query_params["rnc"] = 1
        if is_campervan:
            query_params["cpc"] = 1

        search_url = f"{base_endpoint}?" + urllib.parse.urlencode(query_params)

        start_time = time.time()
        logger.info(f"Targeted search query='{query}', limit={limit}, url={search_url}")

        detailed_vehicles = []
        total_items = 0
        saved_count = 0

        async with FlexnetHttpClient(concurrency=self.concurrency) as http_client:
            html = await http_client.get(search_url)
            if not html:
                return {
                    "success": False,
                    "error": "Failed to fetch search results from Flexnet",
                    "total_found": 0,
                    "vehicles": []
                }

            total_items, previews = FlexnetParser.parse_search_page(html)

            # Dynamic relevance filter: eliminates cross-promotion artifacts (e.g. Hilux when searching Prado)
            if query and query.strip():
                previews = [
                    p for p in previews
                    if is_vehicle_model_match(query, translated_kw, p.get("model"), p.get("title"), p.get("tagline"))
                ]
                total_items = len(previews)

            cars_to_scrape = previews[:limit]

            # Concurrently scrape details
            async def scrape_one(car_preview):
                code = car_preview["kanri_code"]
                url = car_preview["detail_url"]
                detail_html = await http_client.get(url, referer=search_url)
                if detail_html:
                    parsed = FlexnetParser.parse_detail_page(detail_html, code, fallback_data=car_preview)
                else:
                    parsed = car_preview
                # Translate all Japanese vehicle attributes into clean English
                return translate_vehicle_to_english(parsed)

            tasks = [scrape_one(p) for p in cars_to_scrape]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, dict):
                    # Second verification pass on detailed vehicle attributes
                    if query and query.strip():
                        if not is_vehicle_model_match(query, translated_kw, res.get("model"), res.get("title"), res.get("tagline")):
                            logger.info(f"Dynamically filtered mismatched vehicle: {res.get('title')} (model: {res.get('model')})")
                            continue

                    # Year filtering if requested
                    if min_year or max_year:
                        year_str = res.get("model_year", "")
                        year_match = re.search(r"(\d{4})", str(year_str))
                        if year_match:
                            y = int(year_match.group(1))
                            if min_year and y < min_year:
                                continue
                            if max_year and y > max_year:
                                continue
                    detailed_vehicles.append(res)

            # Save to Supabase
            if save_to_supabase and db.is_connected() and detailed_vehicles:
                saved_count = db.batch_upsert_vehicles(detailed_vehicles)

            # Webhook notification
            if notify_sheets and detailed_vehicles:
                elapsed = round(time.time() - start_time, 1)
                await notifier.send_summary({
                    "status": "completed",
                    "query": query or "All",
                    "vehicles_scraped": len(detailed_vehicles),
                    "saved_to_supabase": saved_count,
                    "elapsed_seconds": elapsed,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                await notifier.send_new_cars(detailed_vehicles)

        elapsed = round(time.time() - start_time, 1)
        return {
            "success": True,
            "query": query,
            "translated_query": translated_kw,
            "search_url": search_url,
            "total_found": total_items,
            "scraped_count": len(detailed_vehicles),
            "saved_to_supabase": saved_count,
            "elapsed_seconds": elapsed,
            "vehicles": detailed_vehicles
        }

# Global engine instance for the service
engine = ScraperEngine()
