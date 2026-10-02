import json
import re
import logging
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class FlexnetParser:

    @staticmethod
    def parse_yen(text: Optional[str]) -> Optional[int]:
        """Convert Japanese currency strings like '449.8万円', '449.8', '4,498,000' to integer Yen."""
        if not text:
            return None
        clean = text.replace(",", "").replace("円", "").replace("(税込)", "").strip()
        
        # Check if in "万円" format (e.g. 449.8万 or 449.8)
        if "万" in clean:
            match = re.search(r"([\d\.]+)\s*万", clean)
            if match:
                try:
                    return int(float(match.group(1)) * 10000)
                except ValueError:
                    pass
        
        # Check if direct numeric (e.g. 4498000)
        digits_only = re.sub(r"[^\d\.]", "", clean)
        if digits_only:
            try:
                val = float(digits_only)
                # If small number like 449.8 without explicit 万
                if val < 5000:
                    return int(val * 10000)
                return int(val)
            except ValueError:
                pass
        return None

    @staticmethod
    def parse_mileage(text: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
        """Parse mileage string into (raw_text, km_integer)."""
        if not text:
            return None, None
        raw = text.strip()
        # e.g. 19.9万km, 3.8万km, 500km
        match_man = re.search(r"([\d\.]+)\s*万\s*km", raw, re.IGNORECASE)
        if match_man:
            try:
                km = int(float(match_man.group(1)) * 10000)
                return raw, km
            except ValueError:
                pass
        
        match_km = re.search(r"([\d\,]+)\s*km", raw, re.IGNORECASE)
        if match_km:
            try:
                km = int(match_km.group(1).replace(",", ""))
                return raw, km
            except ValueError:
                pass
                
        return raw, None

    @staticmethod
    def parse_displacement(text: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
        """Parse displacement string into (raw_text, cc_integer)."""
        if not text:
            return None, None
        raw = text.strip()
        match = re.search(r"(\d+)\s*cc", raw, re.IGNORECASE)
        if match:
            try:
                return raw, int(match.group(1))
            except ValueError:
                pass
        return raw, None

    @staticmethod
    def parse_search_page(html: str) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Parses search result catalog page.
        Returns (total_items_count, list_of_vehicle_previews).
        """
        soup = BeautifulSoup(html, "lxml")
        
        # 1. Total inventory count
        total_items = 0
        total_match = re.search(r'class="redtxt bold">\s*([\d\,]+)', html)
        if not total_match:
            total_match = re.search(r"([\d\,]+)\s*件中", html)
        if total_match:
            try:
                total_items = int(total_match.group(1).replace(",", ""))
            except ValueError:
                pass

        vehicles = []
        cards = soup.select(".zaiko_box")
        
        for card in cards:
            vehicle = {}
            
            # kanri_code (Unique car ID)
            kanri_code = None
            wish_elem = card.select_one("a.marketo_wish, a.wish")
            if wish_elem and wish_elem.get("data-id"):
                kanri_code = wish_elem["data-id"].strip()
            
            # Detail Link & Title
            title_elem = card.select_one(".useditem__ttl dt h3 a")
            photo_link = card.select_one("a.bl-bigger")
            detail_url = ""
            if title_elem and title_elem.get("href"):
                detail_url = title_elem["href"]
            elif photo_link and photo_link.get("href"):
                detail_url = photo_link["href"]

            if not kanri_code and detail_url:
                code_match = re.search(r"used-(\d+)\.html", detail_url)
                if code_match:
                    kanri_code = code_match.group(1)

            if not kanri_code:
                continue

            vehicle["kanri_code"] = kanri_code
            vehicle["detail_url"] = detail_url if detail_url.startswith("http") else f"https://www.flexnet.co.jp{detail_url}"
            vehicle["title"] = title_elem.get_text(strip=True) if title_elem else "FLEX Vehicle"

            # Dynamically extract official brand and model from URL slug
            # Flexnet structure: /detail/{brand}-{model}-(used|new)-{kanri_code}.html
            try:
                decoded_url = urllib.parse.unquote(vehicle["detail_url"])
                slug_match = re.search(r'/detail/([^/]+?)-(?:used|new)-\d+\.html', decoded_url)
                if slug_match:
                    slug_parts = slug_match.group(1).split('-', 1)
                    vehicle["brand"] = slug_parts[0]
                    if len(slug_parts) > 1:
                        vehicle["model"] = slug_parts[1]
            except Exception:
                pass
            
            # Thumbnail
            img_elem = card.select_one(".usd_phbox img")
            if img_elem and img_elem.get("src"):
                vehicle["thumbnail_url"] = img_elem["src"]
            elif img_elem and img_elem.get("data-src"):
                vehicle["thumbnail_url"] = img_elem["data-src"]

            # Badges (NEW, Renoca, etc.)
            badges = [b.get_text(strip=True) for b in card.select(".useditem__ttl dd span") if b.get_text(strip=True)]
            vehicle["badge_tags"] = badges

            # Tagline / Subtitle
            tagline_elem = card.select_one(".useditem__ttl p.txt14")
            vehicle["tagline"] = tagline_elem.get_text(strip=True) if tagline_elem else None

            # Pricing on card
            hontai_elem = card.select_one(".kakakutxt_hontai")
            syouhiyou_elem = card.select_one(".kakakutxt_syouhiyou")
            total_elem = card.select_one(".kakakutxt")

            vehicle["vehicle_price"] = FlexnetParser.parse_yen(hontai_elem.get_text(strip=True)) if hontai_elem else None
            vehicle["expenses"] = FlexnetParser.parse_yen(syouhiyou_elem.get_text(strip=True)) if syouhiyou_elem else None
            vehicle["total_price"] = FlexnetParser.parse_yen(total_elem.get_text(strip=True)) if total_elem else None

            # Quick spec boxes
            spec_items = card.select(".usd_detailbox li")
            for item in spec_items:
                ttl = item.select_one(".usd_detail_ttl")
                val = item.select_one(".detail_atai")
                if not ttl or not val:
                    continue
                ttl_text = ttl.get_text(strip=True)
                val_text = val.get_text(" ", strip=True)

                if "年式" in ttl_text:
                    vehicle["model_year"] = val_text
                elif "走行" in ttl_text:
                    vehicle["mileage_raw"], vehicle["mileage_km"] = FlexnetParser.parse_mileage(val_text)
                elif "排気" in ttl_text:
                    vehicle["displacement_raw"], vehicle["displacement_cc"] = FlexnetParser.parse_displacement(val_text)
                elif "修復" in ttl_text:
                    vehicle["repair_history"] = val_text
                elif "車検" in ttl_text:
                    vehicle["inspection"] = val_text
                elif "駆動" in ttl_text:
                    vehicle["drive_system"] = val_text
                elif "色" in ttl_text:
                    vehicle["color"] = val_text
                elif "エンジン" in ttl_text:
                    vehicle["engine_type"] = val_text
                elif "シフト" in ttl_text:
                    vehicle["transmission"] = val_text
                elif "型式" in ttl_text:
                    vehicle["model_code"] = val_text

            # Dealer / Store info on card
            pref_elem = card.select_one(".shop_bottom_box .bkknpref")
            shop_elem = card.select_one(".shop_bottom_box a")
            tel_elem = card.select_one(".shop_bottom_box .telbox")

            vehicle["store_prefecture"] = pref_elem.get_text(strip=True) if pref_elem else None
            if shop_elem:
                vehicle["store_name"] = shop_elem.get_text(strip=True)
                vehicle["store_url"] = shop_elem.get("href")
            if tel_elem:
                vehicle["store_tel"] = tel_elem.get_text(strip=True).replace("無料通話", "").strip()

            vehicle["status"] = "available"
            vehicles.append(vehicle)

        return total_items, vehicles

    @staticmethod
    def parse_detail_page(html: str, kanri_code: str, fallback_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parses full vehicle detail page:
        Combines Schema.org JSON-LD, spec tables, equipment, gallery images, and dealer notes.
        """
        data = fallback_data.copy() if fallback_data else {}
        data["kanri_code"] = kanri_code
        if not data.get("detail_url"):
            data["detail_url"] = f"https://www.flexnet.co.jp/detail/{kanri_code}.html"
        soup = BeautifulSoup(html, "lxml")

        # 1. Parse Schema.org JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script.string or "")
                if isinstance(ld, dict) and ld.get("@type") == "Product":
                    if ld.get("sku"):
                        data["sku"] = ld["sku"]
                    if ld.get("name") and not data.get("title"):
                        data["title"] = ld["name"].strip()
                    if ld.get("brand") and isinstance(ld["brand"], dict):
                        data["brand"] = ld["brand"].get("name")
                    if ld.get("model"):
                        data["model"] = ld["model"]
                    
                    offers = ld.get("offers")
                    if isinstance(offers, dict):
                        if offers.get("price"):
                            data["vehicle_price"] = int(offers["price"])
                        seller = offers.get("seller")
                        if isinstance(seller, dict):
                            data["store_name"] = seller.get("name")
                            data["store_tel"] = seller.get("telephone")
                            data["store_url"] = seller.get("url")
                            addr = seller.get("address")
                            if isinstance(addr, dict):
                                data["store_prefecture"] = addr.get("addressRegion")
                                data["store_address"] = f"{addr.get('addressRegion', '')}{addr.get('addressLocality', '')}{addr.get('streetAddress', '')}"

                    # Additional properties from JSON-LD
                    for prop in ld.get("additionalProperty", []):
                        pname = prop.get("name")
                        pval = str(prop.get("value", "")).strip()
                        if pname == "支払総額":
                            data["total_price"] = FlexnetParser.parse_yen(pval)
                        elif pname == "年式":
                            data["model_year"] = pval
                        elif pname == "走行距離":
                            data["mileage_raw"], data["mileage_km"] = FlexnetParser.parse_mileage(pval)
                        elif pname == "車検":
                            data["inspection"] = pval
                        elif pname == "修復歴":
                            data["repair_history"] = pval
                        elif pname == "排気量":
                            data["displacement_raw"], data["displacement_cc"] = FlexnetParser.parse_displacement(pval)
                        elif pname == "ミッション":
                            data["transmission"] = pval
            except Exception as e:
                logger.debug(f"JSON-LD parse notice: {e}")

        # Fallback extraction of brand and model from detail_url slug if missing
        if not data.get("brand") or not data.get("model"):
            try:
                decoded_url = urllib.parse.unquote(data.get("detail_url", ""))
                slug_match = re.search(r'/detail/([^/]+?)-(?:used|new)-\d+\.html', decoded_url)
                if slug_match:
                    slug_parts = slug_match.group(1).split('-', 1)
                    if not data.get("brand"):
                        data["brand"] = slug_parts[0]
                    if len(slug_parts) > 1 and not data.get("model"):
                        data["model"] = slug_parts[1]
            except Exception:
                pass

        # 2. Parse Spec Tables (Detailed Specs, Condition, Warranty)
        spec_tables = soup.select("table.usdtable")
        for table in spec_tables:
            rows = table.select("tr")
            for row in rows:
                th_list = row.select("th")
                td_list = row.select("td")
                
                # Rows can have 2 pairs: [th1, td1, th2, td2] or 1 pair: [th1, td1]
                for i in range(min(len(th_list), len(td_list))):
                    label = th_list[i].get_text(strip=True)
                    val = td_list[i].get_text(" ", strip=True)

                    if "支払総額" in label and not data.get("total_price"):
                        data["total_price"] = FlexnetParser.parse_yen(val)
                    elif "車両価格" in label and not data.get("vehicle_price"):
                        data["vehicle_price"] = FlexnetParser.parse_yen(val)
                    elif "諸費用" in label:
                        data["expenses"] = FlexnetParser.parse_yen(val)
                    elif "排気量" in label:
                        data["displacement_raw"], data["displacement_cc"] = FlexnetParser.parse_displacement(val)
                    elif "ボディタイプ" in label:
                        data["body_type"] = val
                    elif "過給機" in label:
                        data["has_supercharger"] = val
                    elif "定員" in label:
                        data["seating_capacity"] = val
                    elif "走行距離" in label:
                        data["mileage_raw"], data["mileage_km"] = FlexnetParser.parse_mileage(val)
                    elif "エンジン種別" in label:
                        data["engine_type"] = val
                    elif "年式" in label:
                        data["model_year"] = val
                    elif "駆動方式" in label:
                        data["drive_system"] = val
                    elif "型式" in label:
                        data["model_code"] = val
                    elif "車体色" in label:
                        data["color"] = val
                    elif "内装色" in label and val != "-":
                        data["interior_color"] = val
                    elif "ハンドル" in label:
                        data["steering"] = val
                    elif "ドア数" in label:
                        door_match = re.search(r"(\d+)", val)
                        if door_match:
                            data["doors"] = int(door_match.group(1))
                    elif "車体末尾番号" in label:
                        data["chassis_last_digits"] = val
                    elif "シフト" in label and not data.get("transmission"):
                        data["transmission"] = val
                    elif "修復歴" in label:
                        data["repair_history"] = val
                    elif "禁煙車" in label:
                        data["is_non_smoking"] = "◯" in val or "○" in val
                    elif "ワンオーナー" in label:
                        data["is_one_owner"] = "◯" in val or "○" in val or "あり" in val
                    elif "メーター交換歴" in label:
                        data["odometer_replaced"] = val
                    elif "車検" in label:
                        data["inspection"] = val
                    elif "保証" in label:
                        data["warranty"] = val
                    elif "法定整備" in label:
                        data["legal_maintenance"] = val
                    elif "スライドドア" in label and val != "-":
                        data["sliding_doors"] = val
                    elif "リサイクル料" in label and val != "-":
                        data["recycle_fee"] = val
                    elif "記録簿" in label and val != "-":
                        data["service_records"] = val
                    elif "登録済未使用車" in label:
                        data["is_unused_car"] = "◯" in val or "○" in val or "あり" in val
                    elif "キャンピングカー" in label:
                        data["is_campervan"] = "◯" in val or "○" in val or "あり" in val
                    elif "ご成約特典" in label or "フェア名" in label:
                        prev_campaign = data.get("campaign_info", "")
                        data["campaign_info"] = f"{prev_campaign}\n{label}: {val}".strip()

        # 3. Parse Sales Points / Dealer Story
        sales_points_parts = []
        sales_section = soup.select_one("#usd_sectbox")
        if sales_section:
            for item in sales_section.select(".__items__content"):
                text = item.get_text(separator="\n", strip=True)
                if text and text not in sales_points_parts:
                    sales_points_parts.append(text)
        if sales_points_parts:
            data["sales_points"] = "\n\n".join(sales_points_parts)

        # 4. Parse Active Equipment & Features (.speclst_mn_on)
        equipment_list = []
        for eq in soup.select("li.speclst_mn_on, li.speclst.speclst_mn_on"):
            eq_name = eq.get_text(strip=True)
            if eq_name and eq_name not in equipment_list:
                equipment_list.append(eq_name)
        data["equipment"] = equipment_list

        # 5. Extract all Gallery Images (high-res JPGs)
        images = []
        img_pattern = re.compile(r"https?://img2\.flexnet\.co\.jp/images/[A-Z0-9]+/[A-Z0-9]+/[A-Z0-9]+.*?\.(?:jpg|jpeg|png|webp)", re.IGNORECASE)
        found_urls = set(img_pattern.findall(html))

        for url in found_urls:
            # Strip thumbnail resizing suffixes (_160, _640, etc.) to get pristine high-res original
            clean_url = re.sub(r"_\d+\.(?:jpg|jpeg|png|webp)$", ".JPG", url, flags=re.IGNORECASE)
            if clean_url not in images:
                images.append(clean_url)

        # Sort images so cover photo (L.JPG) comes first, followed by numerical order (1.JPG, 2.JPG, ..., 20.JPG)
        def image_sort_key(u: str) -> tuple:
            parts = u.split("/")
            if len(parts) >= 2:
                sku = parts[-2]
                name = parts[-1]
                if name.startswith(sku):
                    tag = name[len(sku):].split(".")[0].upper()
                    if tag == "L":
                        return (0, 0)
                    try:
                        return (1, int(tag))
                    except ValueError:
                        return (2, tag)
            return (3, u)

        images.sort(key=image_sort_key)
        data["image_urls"] = images
        if images and not data.get("thumbnail_url"):
            data["thumbnail_url"] = images[0]

        data["status"] = "available"
        return data
