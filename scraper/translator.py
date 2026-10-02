import re
import logging
import urllib.parse
import difflib
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger(__name__)

# Japanese character regex range (Hiragana, Katakana, Kanji)
JAPANESE_REGEX = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]")

# Common JDM automotive dictionary for instant 0ms resolution
AUTOMOTIVE_MAP = {
    # Core Brands
    "toyota": "トヨタ",
    "subaru": "スバル",
    "nissan": "日産",
    "honda": "ホンダ",
    "mazda": "マツダ",
    "mitsubishi": "三菱",
    "suzuki": "スズキ",
    "jeep": "ジープ",
    "benz": "ベンツ",
    "mercedes": "ベンツ",
    "bmw": "BMW",
    "audi": "アウディ",

    # Land Cruiser Family
    "land cruiser 80": "ランドクルーザー 80",
    "land cruiser 70": "ランドクルーザー 70",
    "land cruiser 60": "ランドクルーザー 60",
    "land cruiser 100": "ランドクルーザー 100",
    "land cruiser 200": "ランドクルーザー 200",
    "land cruiser 250": "ランドクルーザー 250",
    "land cruiser 300": "ランドクルーザー 300",
    "land cruiser cygnus": "ランドクルーザー シグナス",
    "cygnus": "シグナス",
    "land cruiser prado": "ランドクルーザー プラド",
    "land cruiser": "ランドクルーザー",
    "landcruiser": "ランドクルーザー",
    "150 prado": "150 プラド",
    "120 prado": "120 プラド",
    "90 prado": "90 プラド",
    "70 prado": "70 プラド",
    "prado": "プラド",
    "fj cruiser": "FJ クルーザー",
    "fj": "FJ",

    # Hiace & Van Family
    "hiace van": "ハイエース バン",
    "hiace wagon": "ハイエース ワゴン",
    "hiace commuter": "ハイエース コミューター",
    "hiace": "ハイエース",
    "regius ace": "レジアスエース",
    "regiusace": "レジアスエース",
    "finetech tourer": "ファインテックツアラー",
    "finetech": "ファインテック",
    "granace": "グランエース",
    "grand cabin": "グランドキャビン",
    "campervan": "キャンピングカー",
    "camper": "キャンピングカー",

    # Compact Workhorses & Pickups
    "probox": "プロボックス",
    "succeed": "サクシード",
    "townace": "タウンエース",
    "town ace": "タウンエース",
    "hilux surf": "ハイラックスサーフ",
    "hilux": "ハイラックス",
    "surf": "サーフ",
    "us toyota": "US トヨタ",
    "tacoma": "タコマ",
    "tundra": "タンドラ",
    "4runner": "4ランナー",
    "sequoia": "セコイア",

    # 4WD & Offroad Models
    "jimny sierra": "ジムニーシエラ",
    "jimny": "ジムニー",
    "sierra": "シエラ",
    "delica d5": "デリカ D:5",
    "delica d:5": "デリカ D:5",
    "delica": "デリカ",
    "wrangler": "ラングラー",

    # Trims, Specs & Options
    "super gl": "スーパーGL",
    "dark prime": "ダークプライム",
    "round headlights": "丸目",
    "round eyes": "丸目",
    "square headlights": "角目",
    "square eyes": "角目",
    "lifted": "リフトアップ",
    "sunroof": "サンルーフ",
    "leather seats": "本革シート",
    "leather": "本革",
    "bed kit": "ベッドキット",
    "cold weather": "寒冷地仕様",
    "all paint": "オールペイント",
    "custom": "カスタム",
    "wide": "ワイド",
    "high roof": "ハイルーフ",
    "van": "バン",
    "wagon": "ワゴン",
    "commuter": "コミューター",

    # Fuel & Colors
    "diesel": "ディーゼル",
    "gasoline": "ガソリン",
    "hybrid": "ハイブリッド",
    "white": "白",
    "black": "黒",
    "nardo gray": "ナルドグレー",
}

# Proprietary Flexnet & Renoca brand models
# These MUST NEVER be sent to an online dictionary translator because they get
# mistranslated into generic Japanese words (e.g. Wonder -> 驚異 'miracle', Coast Lines -> 海岸線 'shoreline').
# Flexnet natively indexes all these model names in Romaji / English!
RENOCA_AND_PROPRIETARY_TERMS = {
    "wonder",
    "coast lines",
    "coastlines",
    "color bomb",
    "colorbomb",
    "phoenix",
    "euro box",
    "eurobox",
    "mol",
    "renoca",
    "wood village",
    "woodvillage",
    "american classic",
    "106",
    "roy",
    "army",
    "delfinoline",
    "delfino line",
    "deeps",
    "flex",
    "flex custom",
    "re classic",
    "reclassic",
    "knot",
    "windansea",
}

# Preserve technical drive/specs and brand terms as-is
PRESERVE_TERMS = {
    "4wd", "2wd", "awd", "at", "mt", "cvt", "v6", "v8", "turbo",
    "lc80", "lc100", "lc200", "lc300", "lc70", "trd", "gr",
} | RENOCA_AND_PROPRIETARY_TERMS

# Common automotive shorthands, concatenations & typo patterns
SHORTHAND_EXPANSIONS = {
    r"\blc\s*80\b": "land cruiser 80",
    r"\blc\s*70\b": "land cruiser 70",
    r"\blc\s*60\b": "land cruiser 60",
    r"\blc\s*100\b": "land cruiser 100",
    r"\blc\s*200\b": "land cruiser 200",
    r"\blc\s*250\b": "land cruiser 250",
    r"\blc\s*300\b": "land cruiser 300",
    r"\bfjcruiser\b": "fj cruiser",
    r"\bfj\b(?!\s*cruiser)": "fj cruiser",
    r"\bland\s*cruiser\s*prado\b": "land cruiser prado",
    r"\blandcruiser\b": "land cruiser",
    r"\blandcruser\b": "land cruiser",
    r"\blandcruzer\b": "land cruiser",
    r"\bhiluxsurf\b": "hilux surf",
    r"\bcoast\s*lines?\b": "CoastLines",
    r"\bcolor\s*bombs?\b": "ColorBomb",
    r"\beuro\s*box\b": "EuroBox",
    r"\bwood\s*village\b": "WoodVillage",
    r"\bdelfino\s*line\b": "DelfinoLine",
    r"\bre\s*classic\b": "ReClassic",
    r"\bregiusace\b": "regius ace",
    r"\btown\s*ace\b": "townace",
    r"\bhiacevan\b": "hiace van",
    r"\bhiacewagon\b": "hiace wagon",
    r"\bdelica\s*d\s*[:\.]?\s*5\b": "delica",
    r"\bprado\s*150\b": "150 prado",
    r"\bprado\s*120\b": "120 prado",
    r"\bprado\s*90\b": "90 prado",
    r"\bprado\s*70\b": "70 prado",
}

# In-memory translation cache to avoid duplicate API calls
_TRANSLATION_CACHE: Dict[str, str] = {}

def normalize_and_fuzzy_correct(query: str) -> str:
    """
    Normalizes casing, removes punctuation/underscores, splits concatenated numbers,
    and applies fuzzy typo correction against the known automotive vocabulary.
    """
    if not query or not query.strip():
        return ""

    # 1. Clean spacing, hyphens, underscores, lower-case
    cleaned = re.sub(r"[-_]+", " ", query.lower().strip())
    cleaned = re.sub(r"\s+", " ", cleaned)

    # 2. Split concatenated letter-number boundaries: "prado150" -> "prado 150", "lc80" -> "lc 80"
    cleaned = re.sub(r"([a-z]+)(\d+)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(\d+)([a-z]+)", r"\1 \2", cleaned)

    # 3. Apply regex shorthand expansions
    for pattern, repl in SHORTHAND_EXPANSIONS.items():
        cleaned = re.sub(pattern, repl, cleaned)

    # 4. If exact match in dictionary or preserve terms, return immediately
    if cleaned in AUTOMOTIVE_MAP or cleaned in PRESERVE_TERMS:
        return cleaned

    # 5. Whole-phrase fuzzy match against known dictionary & preserve terms
    all_candidates = list(AUTOMOTIVE_MAP.keys()) + list(PRESERVE_TERMS)
    matches = difflib.get_close_matches(cleaned, all_candidates, n=1, cutoff=0.74)
    if matches:
        return matches[0]

    # 6. Word-by-word fuzzy correction for multi-word queries (e.g. "hiac van" -> "hiace van")
    words = cleaned.split()
    single_candidates = [k for k in all_candidates if " " not in k and not k.isdigit()]
    corrected_words = []
    for w in words:
        if w.isdigit():
            corrected_words.append(w)
            continue
        w_matches = difflib.get_close_matches(w, single_candidates, n=1, cutoff=0.75)
        corrected_words.append(w_matches[0] if w_matches else w)

    reconstructed = " ".join(corrected_words)
    if reconstructed in AUTOMOTIVE_MAP or reconstructed in PRESERVE_TERMS:
        return reconstructed

    matches2 = difflib.get_close_matches(reconstructed, all_candidates, n=1, cutoff=0.74)
    if matches2:
        return matches2[0]

    return reconstructed


async def probe_flexnet_live(query_keyword: str) -> int:
    """
    Future-Proof Probe: Queries Flexnet Japan live in real-time.
    If Flexnet returns > 0 results for an unmapped English model name,
    it proves Flexnet natively indexes that model in English!
    """
    try:
        url = f"https://www.flexnet.co.jp/search?kw={urllib.parse.quote(query_keyword)}"
        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, timeout=2.5) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                match = re.search(r'(\d+)\s*件', resp.text)
                if match:
                    return int(match.group(1))
    except Exception as e:
        logger.debug(f"Live Flexnet probe skipped: {e}")
    return 0


async def translate_query_to_japanese(query: Optional[str]) -> Optional[str]:
    """
    Robust, fault-tolerant & future-proof vehicle search translation for Flexnet.
    1. Japanese text -> pass through 100% as-is.
    2. Case/Typo/Shorthand normalization -> fuzzy matches against JDM vocabulary.
    3. Dictionary resolution -> instant 0ms lookup.
    4. Proprietary Renoca/Flexnet lines -> preserved in Romaji/English.
    5. Future-proof probe:
       - Probes Flexnet in English: if >0 results, uses English directly!
       - If 0 results in English, dynamically translates to Japanese via API.
    """
    if not query or not query.strip():
        return None

    raw = query.strip()

    # 1. If it already contains Japanese characters, no translation needed
    if JAPANESE_REGEX.search(raw):
        return raw

    # 2. Normalize casing, whitespace, concatenated words, and correct typos
    norm = normalize_and_fuzzy_correct(raw)
    low = norm.lower()

    # 3. Check memory cache for instant response
    if low in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[low]

    # 4. Check direct dictionary match (e.g. "land cruiser 80" -> "ランドクルーザー 80")
    if low in AUTOMOTIVE_MAP:
        res = AUTOMOTIVE_MAP[low]
        _TRANSLATION_CACHE[low] = res
        return res

    # 5. Check if it's a known preserved term (e.g. "Wonder", "4WD", "Coast Lines")
    if low in PRESERVE_TERMS:
        res = norm.title() if len(norm) > 3 else norm.upper()
        _TRANSLATION_CACHE[low] = res
        return res

    # 6. Check if query contains any proprietary Renoca/Flexnet terms
    is_proprietary = any(term in low for term in RENOCA_AND_PROPRIETARY_TERMS)
    if is_proprietary:
        res = norm
        for eng in sorted(AUTOMOTIVE_MAP.keys(), key=len, reverse=True):
            if eng not in RENOCA_AND_PROPRIETARY_TERMS:
                pattern = re.compile(rf"\b{re.escape(eng)}\b", re.IGNORECASE)
                res = pattern.sub(AUTOMOTIVE_MAP[eng], res)
        _TRANSLATION_CACHE[low] = res
        logger.info(f"Preserved proprietary Renoca/Flexnet query: '{raw}' -> '{res}'")
        return res

    # 7. Substitute known sub-phrases (e.g. "Toyota Hiace 4WD")
    translated = norm
    for eng in sorted(AUTOMOTIVE_MAP.keys(), key=len, reverse=True):
        pattern = re.compile(rf"\b{re.escape(eng)}\b", re.IGNORECASE)
        translated = pattern.sub(AUTOMOTIVE_MAP[eng], translated)

    if JAPANESE_REGEX.search(translated):
        _TRANSLATION_CACHE[low] = translated
        return translated

    # 8. FUTURE-PROOF LIVE PROBE:
    # Check if Flexnet already indexes this new model in English natively!
    live_hits = await probe_flexnet_live(norm)
    if live_hits > 0:
        logger.info(f"Future-proof probe found {live_hits} vehicles for '{norm}' directly in English on Flexnet!")
        _TRANSLATION_CACHE[low] = norm
        return norm

    # 9. Dynamic Online Translation for arbitrary English queries (e.g. "matte green", "red leather")
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote_plus(norm)}&langpair=en|ja"
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                t = data.get("responseData", {}).get("translatedText")
                if t and t.strip():
                    clean = t.strip()
                    # Remove parenthetical English artifacts like "ディーゼル（Diesel）"
                    clean = re.sub(r"（[A-Za-z\s]+）", "", clean).strip()
                    logger.info(f"Dynamic translation: '{norm}' -> '{clean}'")
                    _TRANSLATION_CACHE[low] = clean
                    return clean
    except Exception as e:
        logger.warning(f"Dynamic translation request skipped due to network notice: {e}")

    # 10. Fallback to normalized text
    return norm


# ==============================================================================
# JDM AUTOMOTIVE DICTIONARY (JAPANESE -> ENGLISH FOR DATABASE & UI)
# ==============================================================================

BRANDS_JA_TO_EN = {
    "トヨタ": "Toyota",
    "日産": "Nissan",
    "ホンダ": "Honda",
    "スバル": "Subaru",
    "マツダ": "Mazda",
    "三菱": "Mitsubishi",
    "スズキ": "Suzuki",
    "ダイハツ": "Daihatsu",
    "レクサス": "Lexus",
    "ジープ": "Jeep",
    "アウディ": "Audi",
    "BMW": "BMW",
    "メルセデス": "Mercedes-Benz",
    "ベンツ": "Mercedes-Benz",
}

MODELS_JA_TO_EN = {
    "サクシードバン": "Succeed Van",
    "サクシード ワゴン": "Succeed Wagon",
    "サクシード": "Succeed",
    "プロボックスバン": "Probox Van",
    "プロボックス ワゴン": "Probox Wagon",
    "プロボックス": "Probox",
    "ハイエースバン": "Hiace Van",
    "ハイエースワゴン": "Hiace Wagon",
    "ハイエース コミューター": "Hiace Commuter",
    "ハイエース": "Hiace",
    "レジアスエースバン": "Regius Ace Van",
    "レジアスエース": "Regius Ace",
    "ランドクルーザープラド": "Land Cruiser Prado",
    "ランドクルーザー プラド": "Land Cruiser Prado",
    "ランドクルーザー70": "Land Cruiser 70",
    "ランドクルーザー80": "Land Cruiser 80",
    "ランドクルーザー100": "Land Cruiser 100",
    "ランドクルーザー200": "Land Cruiser 200",
    "ランドクルーザー250": "Land Cruiser 250",
    "ランドクルーザー300": "Land Cruiser 300",
    "ランドクルーザー": "Land Cruiser",
    "ハイラックスサーフ": "Hilux Surf",
    "ハイラックス サーフ": "Hilux Surf",
    "ハイラックス": "Hilux",
    "FJクルーザー": "FJ Cruiser",
    "ジムニーシエラ": "Jimny Sierra",
    "ジムニー シエラ": "Jimny Sierra",
    "ジムニー": "Jimny",
    "タウンエース": "TownAce",
    "ラングラー": "Wrangler",
    "デリカ": "Delica",
}

TITLE_TERMS_JA_TO_EN = {
    # Models & Brands
    "トヨタ": "Toyota",
    "スズキ": "Suzuki",
    "三菱": "Mitsubishi",
    "日産": "Nissan",
    "ホンダ": "Honda",
    "ジープ": "Jeep",
    "マツダ": "Mazda",
    "スバル": "Subaru",
    "サクシードバン": "Succeed Van",
    "サクシード": "Succeed",
    "プロボックスバン": "Probox Van",
    "プロボックス": "Probox",
    "ハイエースバン": "Hiace Van",
    "ハイエースワゴン": "Hiace Wagon",
    "ハイエース": "Hiace",
    "レジアスエース": "Regius Ace",
    "ランドクルーザープラド": "Land Cruiser Prado",
    "ランドクルーザー プラド": "Land Cruiser Prado",
    "ランドクルーザー70": "Land Cruiser 70",
    "ランドクルーザー80": "Land Cruiser 80",
    "ランドクルーザー100": "Land Cruiser 100",
    "ランドクルーザー200": "Land Cruiser 200",
    "ランドクルーザー250": "Land Cruiser 250",
    "ランドクルーザー300": "Land Cruiser 300",
    "ランドクルーザー": "Land Cruiser",
    "ハイラックスサーフ": "Hilux Surf",
    "ハイラックス": "Hilux",
    "FJクルーザー": "FJ Cruiser",
    "ジムニーシエラ": "Jimny Sierra",
    "ジムニー": "Jimny",
    "タウンエース": "TownAce",
    "ラングラー": "Wrangler",
    "デリカ": "Delica",

    # Trims & Packages
    "VXリミテッド": "VX Limited",
    "GXリミテッド": "GX Limited",
    "TXリミテッド": "TX Limited",
    "リミテッド": "Limited",
    "カラーパッケージ": "Color Package",
    "GRスポーツ": "GR Sport",
    "GR スポーツ": "GR Sport",
    "アクティブバケーションII": "Active Vacation II",
    "アクティブバケーション": "Active Vacation",
    "ブラックラリーエディション": "Black Rally Edition",
    "ブラック ラリー エディション": "Black Rally Edition",
    "ラリーエディション": "Rally Edition",
    "エディション": "Edition",
    "パッケージ": "Package",
    "ベースグレード": "Base Grade",
    "ワンダー": "Wonder",
    "コーストライン": "Coast Lines",
    "コーストラインズ": "Coast Lines",
    "カラーボム": "Color Bomb",
    "フェニックス": "Phoenix",
    "ユーロボックス": "Euro Box",
    "リノカ": "Renoca",
    "モル": "MOL",
    "アメリカンクラシック": "American Classic",
    "ウッドヴィレッジ": "Wood Village",
    "デルフィーノライン": "DelfinoLine",

    # Trims & Body specs
    "スーパーGL": "Super GL",
    "プライムセレクション": "Prime Selection",
    "ダークプライムⅡ": "Dark Prime II",
    "ダークプライムII": "Dark Prime II",
    "ダークプライム2": "Dark Prime II",
    "ダークプライム": "Dark Prime",
    "グランドキャビン": "Grand Cabin",
    "コミューター": "Commuter",
    "ミドルルーフ": "Middle Roof",
    "ハイルーフ": "High Roof",
    "ロングボディ": "Long Body",
    "スーパーロング": "Super Long",
    "ロング": "Long",
    "ワイド": "Wide",
    "標準ボディ": "Standard Body",
    "標準": "Standard",
    "バン": "Van",
    "ワゴン": "Wagon",
    "リフトアップ": "Lifted",
    "キャンピングカー": "Campervan",
    "キャンパー": "Camper",
    "カスタム": "Custom",
    "オールペイント": "All Paint",
    "角目": "Square Headlights",
    "丸目": "Round Headlights",
    "寒冷地仕様": "Cold Weather Spec",
    "ベッドキット": "Bed Kit",
    "ディーゼルターボ": "Diesel Turbo",
    "ディーゼル": "Diesel",
    "ガソリン": "Gasoline",
    "ハイブリッド": "Hybrid",
    "新車": "New Car",
    "登録済未使用車": "Unused Car",
    "車検整備付": "Inspection Included",
    "車検付": "Inspection Included",
    "本革シート": "Leather Seats",
    "サンルーフ": "Sunroof",
    "ステーションワゴン": "Station Wagon",
    "クロカン・ＳＵＶ": "SUV / 4WD",
    "クロカン・SUV": "SUV / 4WD",
}

BODY_TYPE_MAP = {
    "ステーションワゴン": "Station Wagon",
    "クロカン・ＳＵＶ": "SUV / 4WD",
    "クロカン・SUV": "SUV / 4WD",
    "クロカン": "SUV / 4WD",
    "バン": "Van",
    "ミニバン・ワンボックス": "Minivan / 1-Box",
    "ピックアップトラック": "Pickup Truck",
    "ハッチバック": "Hatchback",
    "セダン": "Sedan",
    "オープンカー": "Convertible",
    "軽自動車": "Kei Car",
}

ENGINE_TYPE_MAP = {
    "ガソリン": "Gasoline",
    "ディーゼル": "Diesel",
    "ハイブリッド": "Hybrid",
    "電気": "EV",
    "LPG": "LPG",
}

DRIVE_SYSTEM_MAP = {
    "2WD": "2WD",
    "4WD": "4WD",
    "パートタイム4WD": "Part-Time 4WD",
    "フルタイム4WD": "Full-Time 4WD",
    "前輪駆動": "FWD",
    "後輪駆動": "RWD",
}

TRANSMISSION_MAP = {
    "CVTフロア": "Floor CVT",
    "CVTインパネ": "Dash CVT",
    "CVT": "CVT",
    "6ATインパネ（MTモード付AT）": "6-Speed AT (with Manual Mode)",
    "6ATフロア（MTモード付AT）": "6-Speed AT (with Manual Mode)",
    "4ATフロア": "4-Speed Floor AT",
    "4ATインパネ": "4-Speed Dash AT",
    "5ATフロア": "5-Speed Floor AT",
    "5ATインパネ": "5-Speed Dash AT",
    "10ATフロア": "10-Speed Floor AT",
    "6AT": "6-Speed AT",
    "5AT": "5-Speed AT",
    "4AT": "4-Speed AT",
    "10AT": "10-Speed AT",
    "5MTフロア": "5-Speed Manual",
    "6MTフロア": "6-Speed Manual",
    "5MT": "5-Speed Manual",
    "6MT": "6-Speed Manual",
    "AT": "Automatic",
    "MT": "Manual",
}

COLOR_MAP = {
    "グリーン": "Green",
    "オリーブグリーン": "Olive Green",
    "アーミーグリーン": "Army Green",
    "ホワイト": "White",
    "白": "White",
    "ホワイトパール": "White Pearl",
    "ホワイトパールマイカ": "White Pearl Mica",
    "ホワイトパールクリスタルシャイン": "White Pearl Crystal Shine",
    "ブラック": "Black",
    "黒": "Black",
    "ブラックマイカ": "Black Mica",
    "ベージュ": "Beige",
    "サンドベージュ": "Sand Beige",
    "シルバー": "Silver",
    "シルバーマイカメタリック": "Silver Mica Metallic",
    "シルバーメタリック": "Silver Metallic",
    "グレー": "Gray",
    "グレーメタリック": "Gray Metallic",
    "ナルドグレー": "Nardo Gray",
    "アウディ純正ナルドグレー": "Audi Nardo Gray",
    "ブルー": "Blue",
    "ネイビー": "Navy Blue",
    "ライトブルー": "Light Blue",
    "レッド": "Red",
    "ワインレッド": "Wine Red",
    "ブラウン": "Brown",
    "ダークブラウン": "Dark Brown",
    "イエロー": "Yellow",
    "オレンジ": "Orange",
    "ゴールド": "Gold",
    "ガンメタリック": "Gunmetal",
}

REPAIR_HISTORY_MAP = {
    "なし": "None (Clean / No Accident History)",
    "無": "None (Clean / No Accident History)",
    "あり": "Yes (Repaired / Accident History)",
    "有": "Yes (Repaired / Accident History)",
}

INSPECTION_MAP = {
    "車検整備付": "Inspection & Maintenance Included",
    "車検整備無": "No Inspection",
    "車検残": "Valid Inspection Remaining",
}

STEERING_MAP = {
    "右": "RHD (Right Hand Drive)",
    "左": "LHD (Left Hand Drive)",
}

EQUIPMENT_MAP = {
    "ナビ": "Navigation",
    "バックカメラ": "Backup Camera",
    "ETC": "ETC Card Reader",
    "エアコン": "Air Conditioning",
    "パワステ": "Power Steering",
    "パワーウィンドウ": "Power Windows",
    "ABS": "ABS",
    "エアバッグ": "Airbags",
    "キーレス": "Keyless Entry",
    "スマートキー": "Smart Key / Push Start",
    "アルミホイール": "Alloy Wheels",
    "アルミ": "Alloy Wheels",
    "革シート": "Leather Seats",
    "本革シート": "Leather Seats",
    "サンルーフ": "Sunroof",
    "LEDヘッドランプ": "LED Headlights",
    "ディスチャージドランプ": "HID / Xenon Headlights",
    "クルーズコントロール": "Cruise Control",
    "両側スライドドア": "Dual Sliding Doors",
    "パワースライドドア": "Power Sliding Door",
    "フルセグTV": "Full-Segment Digital TV",
    "Bluetooth接続": "Bluetooth Audio",
    "衝突被害軽減ブレーキ": "Collision Avoidance Braking",
    "ドライブレコーダー": "Dashcam Recorder",
    "ルーフラック": "Roof Rack",
    "リフトアップ": "Lifted Suspension",
    "ベッドキット": "Bed Kit / Camper Interior",
    "寒冷地仕様": "Cold Weather Package",
    "横滑り防止装置": "Electronic Stability Control (ESC)",
    "盗難防止装置": "Anti-Theft Immobilizer",
}

def translate_vehicle_to_english(v: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translates all Japanese vehicle specs and descriptions into pristine, standard English.
    Operates on a copy of the dictionary so the original data is preserved if needed.
    """
    if not v:
        return v

    out = dict(v)

    # 1. Brand (e.g. トヨタ -> Toyota)
    brand = str(out.get("brand") or "").strip()
    if brand in BRANDS_JA_TO_EN:
        out["brand"] = BRANDS_JA_TO_EN[brand]
    elif not brand:
        out["brand"] = "Toyota"

    # 2. Model (e.g. サクシードバン -> Succeed Van)
    model = str(out.get("model") or "").strip()
    for ja, en in sorted(MODELS_JA_TO_EN.items(), key=lambda x: len(x[0]), reverse=True):
        if ja in model:
            out["model"] = en
            break

    # 3. Title (e.g. トヨタ サクシードバン 1.5 TX -> Toyota Succeed Van 1.5 TX)
    title = str(out.get("title") or "").strip()
    if title:
        trans_title = title
        for ja, en in sorted(TITLE_TERMS_JA_TO_EN.items(), key=lambda x: len(x[0]), reverse=True):
            trans_title = trans_title.replace(ja, f" {en} ")
        # Clean extra spaces
        trans_title = re.sub(r"\s+", " ", trans_title).strip()

        # Enrich title with Renoca conversion model if confirmed in tagline or badges
        tagline_lower = str(out.get("tagline") or "").lower()
        badges = out.get("badge_tags") or []
        badge_str = " ".join(str(b) for b in badges).lower() if isinstance(badges, list) else str(badges).lower()
        cur_title_lower = trans_title.lower()

        renoca_conversions = [
            (re.compile(r"coast\s*lines|コーストライン", re.I), "Renoca Coast Lines"),
            (re.compile(r"color\s*bomb|カラーボム", re.I), "Renoca Color Bomb"),
            (re.compile(r"euro\s*box|ユーロボックス", re.I), "Renoca Euro Box"),
            (re.compile(r"wood\s*village|ウッドヴィレッジ", re.I), "Renoca Wood Village"),
            (re.compile(r"american\s*classic|アメリカンクラシック", re.I), "Renoca American Classic"),
            (re.compile(r"wonder|ワンダー", re.I), "Renoca Wonder"),
            (re.compile(r"phoenix|フェニックス", re.I), "Renoca Phoenix"),
            (re.compile(r"windansea", re.I), "Renoca Windansea"),
            (re.compile(r"106", re.I), "Renoca 106"),
            (re.compile(r"mol|モル", re.I), "Renoca MOL"),
        ]

        for pattern, model_name in renoca_conversions:
            if (pattern.search(tagline_lower) or pattern.search(badge_str)) and not pattern.search(cur_title_lower):
                base_match = re.match(
                    r"^(Toyota|Nissan|Mitsubishi|Suzuki|Subaru|Honda)\s+(Land\s+Cruiser\s+Prado|Land\s+Cruiser\s+\d+|Land\s+Cruiser|Hiace\s+Van|Hiace\s+Wagon|Hiace|Probox\s+Van|Probox|Succeed\s+Van|Succeed|Hilux\s+Surf|Hilux|TownAce|Jimny\s+Sierra|Jimny|Delica\s+D:?5|Delica)",
                    trans_title,
                    re.I
                )
                if base_match:
                    prefix = base_match.group(0)
                    remainder = trans_title[len(prefix):].strip()
                    trans_title = re.sub(r"\s+", " ", f"{prefix} {model_name} {remainder}").strip()
                else:
                    trans_title = f"{model_name} {trans_title}".strip()
                break

        out["title"] = trans_title

    # 4. Model Year (e.g. 2020年(R02年) -> 2020)
    year_raw = str(out.get("model_year") or "").strip()
    year_match = re.search(r"(\d{4})", year_raw)
    if year_match:
        out["model_year"] = year_match.group(1)

    # 5. Mileage Raw (e.g. 1.8万km -> 18,000 km)
    km_val = out.get("mileage_km")
    if km_val and isinstance(km_val, int):
        out["mileage_raw"] = f"{km_val:,} km"

    # 6. Engine Type (e.g. ガソリン -> Gasoline)
    engine_val = str(out.get("engine_type") or "").strip()
    for ja, en in ENGINE_TYPE_MAP.items():
        if ja in engine_val:
            out["engine_type"] = en
            break

    # 7. Drive System (e.g. 4WD -> 4WD, パートタイム4WD -> Part-Time 4WD)
    drive_val = str(out.get("drive_system") or "").strip()
    if drive_val in DRIVE_SYSTEM_MAP:
        out["drive_system"] = DRIVE_SYSTEM_MAP[drive_val]

    # 8. Transmission (e.g. CVTフロア -> Floor CVT)
    trans_val = str(out.get("transmission") or "").strip()
    if trans_val in TRANSMISSION_MAP:
        out["transmission"] = TRANSMISSION_MAP[trans_val]
    else:
        for ja, en in TRANSMISSION_MAP.items():
            if ja in trans_val:
                out["transmission"] = en
                break

    # 9. Body Type (e.g. ステーションワゴン -> Station Wagon)
    body_val = str(out.get("body_type") or "").strip()
    for ja, en in BODY_TYPE_MAP.items():
        if ja in body_val:
            out["body_type"] = en
            break

    # 10. Color (e.g. グリーン -> Green, ホワイトパール -> White Pearl)
    color_val = str(out.get("color") or "").strip()
    for ja, en in sorted(COLOR_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if ja in color_val:
            out["color"] = en
            break

    # 11. Repair History (e.g. なし -> None (Clean / No Accident History))
    repair_val = str(out.get("repair_history") or "").strip()
    if repair_val in REPAIR_HISTORY_MAP:
        out["repair_history"] = REPAIR_HISTORY_MAP[repair_val]
    elif "なし" in repair_val or "無" in repair_val:
        out["repair_history"] = "None (Clean / No Accident History)"
    elif "あり" in repair_val or "有" in repair_val:
        out["repair_history"] = "Yes (Repaired / Accident History)"

    # 12. Inspection (e.g. 車検整備付 -> Inspection & Maintenance Included)
    insp_val = str(out.get("inspection") or "").strip()
    if insp_val in INSPECTION_MAP:
        out["inspection"] = INSPECTION_MAP[insp_val]
    elif "車検整備付" in insp_val:
        out["inspection"] = "Inspection & Maintenance Included"

    # 13. Steering (e.g. 右 -> RHD (Right Hand Drive))
    steer_val = str(out.get("steering") or "").strip()
    if steer_val in STEERING_MAP:
        out["steering"] = STEERING_MAP[steer_val]

    # 14. Supercharger (e.g. なし -> None)
    sc_val = str(out.get("has_supercharger") or "").strip()
    if "なし" in sc_val or "無" in sc_val or sc_val == "-":
        out["has_supercharger"] = "None"
    elif "ターボ" in sc_val:
        out["has_supercharger"] = "Turbo"

    # 15. Warranty
    warr_val = str(out.get("warranty") or "").strip()
    if "保証付" in warr_val:
        if "新車メーカー保証" in warr_val:
            out["warranty"] = "Warranty Included (New Car Manufacturer Warranty Covered)"
        elif "安心プラン" in warr_val or "FLEX" in warr_val:
            out["warranty"] = "Warranty Included (FLEX Drive Plan - Up to 5 Years Coverage)"
        else:
            out["warranty"] = "Warranty Included (Free Coverage on All Functional Parts)"
    elif "保証無" in warr_val or "なし" in warr_val:
        out["warranty"] = "No Warranty"

    # 16. Legal Maintenance
    maint_val = str(out.get("legal_maintenance") or "").strip()
    if "整備込み" in maint_val or "２４ヶ月点検" in maint_val or "12ヶ月点検" in maint_val:
        out["legal_maintenance"] = "Maintenance Included (24-Month Statutory Inspection with Service Records)"
    elif "法定整備付" in maint_val:
        out["legal_maintenance"] = "Maintenance Included (Statutory Inspection Included)"
    elif "法定整備無" in maint_val or "なし" in maint_val:
        out["legal_maintenance"] = "No Maintenance Included"

    # 17. Sliding doors & recycle fee
    sliding_val = str(out.get("sliding_doors") or "").strip()
    if "両側電動" in sliding_val:
        out["sliding_doors"] = "Dual Power Sliding Doors"
    elif "片側電動" in sliding_val:
        out["sliding_doors"] = "Single Power Sliding Door"

    recycle_val = str(out.get("recycle_fee") or "").strip()
    if "リ済込" in recycle_val:
        out["recycle_fee"] = "Recycle Fee Included"
    elif "リ未" in recycle_val:
        out["recycle_fee"] = "Recycle Fee Not Included"

    # 18. Equipment List (e.g. ["ナビ", "バックカメラ"] -> ["Navigation", "Backup Camera"])
    eq_list = out.get("equipment") or []
    if isinstance(eq_list, list):
        out["equipment"] = [EQUIPMENT_MAP.get(e, e) for e in eq_list]

    # 19. Populate Top 5 Images (image_1 through image_5)
    img_list = out.get("image_urls") or []
    if not img_list and out.get("thumbnail_url"):
        img_list = [out["thumbnail_url"]]
    for i in range(1, 6):
        out[f"image_{i}"] = img_list[i - 1] if len(img_list) >= i else None

    return out

