const cheerio = require('cheerio');

// ==============================================================================
// 1. CLIENT EMULATION & HEADERS (PORTED FROM scraper/client.py)
// ==============================================================================

const USER_AGENTS = [
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0'
];

function getRandomUserAgent() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

function getBrowserHeaders(referer = 'https://www.flexnet.co.jp/search') {
  return {
    'User-Agent': getRandomUserAgent(),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Sec-Ch-Ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"macOS"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Upgrade-Insecure-Requests': '1',
    'Referer': referer
  };
}

// ==============================================================================
// 2. MODEL CATEGORY ROUTES & ACCURACY VERIFICATION (PORTED FROM scraper/engine.py)
// ==============================================================================

const FLEXNET_MODEL_ROUTES = {
  'prado': '/search/toyota/landcruiser/prado',
  'ランドクルーザープラド': '/search/toyota/landcruiser/prado',
  'ランドクルーザー プラド': '/search/toyota/landcruiser/prado',
  'プラド': '/search/toyota/landcruiser/prado',
  '150 prado': '/search/toyota/landcruiser/prado/150',
  '150プラド': '/search/toyota/landcruiser/prado/150',
  '150 プラド': '/search/toyota/landcruiser/prado/150',
  '120 prado': '/search/toyota/landcruiser/prado/120',
  '120プラド': '/search/toyota/landcruiser/prado/120',
  '120 プラド': '/search/toyota/landcruiser/prado/120',
  '90 prado': '/search/toyota/landcruiser/prado/90',
  '90プラド': '/search/toyota/landcruiser/prado/90',
  '90 プラド': '/search/toyota/landcruiser/prado/90',
  '70 prado': '/search/toyota/landcruiser/prado/70',
  '70プラド': '/search/toyota/landcruiser/prado/70',
  '70 プラド': '/search/toyota/landcruiser/prado/70',

  'land cruiser 80': '/search/toyota/landcruiser/80',
  'ランドクルーザー80': '/search/toyota/landcruiser/80',
  'ランドクルーザー 80': '/search/toyota/landcruiser/80',
  'ランクル80': '/search/toyota/landcruiser/80',

  'land cruiser 70': '/search/toyota/landcruiser/70',
  'ランドクルーザー70': '/search/toyota/landcruiser/70',
  'ランドクルーザー 70': '/search/toyota/landcruiser/70',
  'ランクル70': '/search/toyota/landcruiser/70',

  'land cruiser 60': '/search/toyota/landcruiser/60',
  'ランドクルーザー60': '/search/toyota/landcruiser/60',
  'ランドクルーザー 60': '/search/toyota/landcruiser/60',
  'ランクル60': '/search/toyota/landcruiser/60',

  'land cruiser 100': '/search/toyota/landcruiser/100',
  'ランドクルーザー100': '/search/toyota/landcruiser/100',
  'ランドクルーザー 100': '/search/toyota/landcruiser/100',
  'ランクル100': '/search/toyota/landcruiser/100',

  'land cruiser 200': '/search/toyota/landcruiser/200',
  'ランドクルーザー200': '/search/toyota/landcruiser/200',
  'ランドクルーザー 200': '/search/toyota/landcruiser/200',
  'ランクル200': '/search/toyota/landcruiser/200',

  'land cruiser 300': '/search/toyota/landcruiser/300',
  'ランドクルーザー300': '/search/toyota/landcruiser/300',
  'ランドクルーザー 300': '/search/toyota/landcruiser/300',
  'ランクル300': '/search/toyota/landcruiser/300',

  'land cruiser 250': '/search/toyota/landcruiser/250',
  'ランドクルーザー250': '/search/toyota/landcruiser/250',
  'ランドクルーザー 250': '/search/toyota/landcruiser/250',
  'ランクル250': '/search/toyota/landcruiser/250',

  'land cruiser cygnus': '/search/toyota/landcruiser/cygnus',
  'ランドクルーザー シグナス': '/search/toyota/landcruiser/cygnus',
  'ランドクルーザーシグナス': '/search/toyota/landcruiser/cygnus',
  'シグナス': '/search/toyota/landcruiser/cygnus',

  'land cruiser': '/search/toyota/landcruiser',
  'ランドクルーザー': '/search/toyota/landcruiser',

  'hiace': '/search/toyota/hiace',
  'ハイエース': '/search/toyota/hiace',
  'toyota hiace': '/search/toyota/hiace',
  'hiace van': '/search/toyota/hiace/van',
  'ハイエース バン': '/search/toyota/hiace/van',
  'ハイエースバン': '/search/toyota/hiace/van',
  'hiace wagon': '/search/toyota/hiace/wagon',
  'ハイエース ワゴン': '/search/toyota/hiace/wagon',
  'ハイエースワゴン': '/search/toyota/hiace/wagon',
  'hiace commuter': '/search/toyota/hiace/commuter',
  'ハイエース コミューター': '/search/toyota/hiace/commuter',
  'regius ace': '/search/toyota/hiace/regiusace',
  'レジアスエース': '/search/toyota/hiace/regiusace',

  'hilux': '/search/toyota/hilux',
  'ハイラックス': '/search/toyota/hilux',
  'hilux surf': '/search/toyota/hiluxsurf',
  'ハイラックスサーフ': '/search/toyota/hiluxsurf',
  'jimny': '/search/suzuki/jimny',
  'ジムニー': '/search/suzuki/jimny',
  'delica': '/search/mitsubishi/delica/d5',
  'デリカ': '/search/mitsubishi/delica/d5',
  'wrangler': '/search/jeep/wrangler',
  'ラングラー': '/search/jeep/wrangler',
  'campervan': '/search/toyota/camping',
  'キャンピングカー': '/search/toyota/camping',
  'us toyota': '/search/us-toyota',
  'usトヨタ': '/search/us-toyota'
};

function isVehicleModelMatch(searchQuery, translatedKw, carModel, carTitle, carTagline) {
  if (!searchQuery || !searchQuery.trim()) return true;

  const sq = searchQuery.toLowerCase().trim();
  const tk = (translatedKw || '').toLowerCase().trim();
  const cm = (carModel || '').toLowerCase().trim();
  const ct = (carTitle || '').toLowerCase().trim();
  const cg = (carTagline || '').toLowerCase().trim();
  const combined = `${cm} ${ct} ${cg}`;

  const families = [
    ['prado', ['プラド', 'prado']],
    ['hilux_surf', ['ハイラックスサーフ', 'hilux surf', 'surf', 'サーフ']],
    ['hilux', ['ハイラックス', 'hilux']],
    ['hiace', ['ハイエース', 'hiace', 'レジアスエース', 'regiusace']],
    ['jimny', ['ジムニー', 'jimny']],
    ['delica', ['デリカ', 'delica']],
    ['wrangler', ['ラングラー', 'wrangler']],
    ['probox', ['プロボックス', 'probox']],
    ['townace', ['タウンエース', 'townace']],
    ['fj_cruiser', ['fjクルーザー', 'fj cruiser', 'fjcruiser']],
    ['lc300', ['300', 'lc300', 'ランクル300']],
    ['lc250', ['250', 'lc250', 'ランクル250']],
    ['lc200', ['200', 'lc200', 'ランクル200']],
    ['lc100', ['100', 'lc100', 'ランクル100']],
    ['lc80', ['80', 'lc80', 'ランクル80']],
    ['lc70', ['70', 'lc70', 'ランクル70']],
    ['lc60', ['60', 'lc60', 'ランクル60']]
  ];

  const targetFamilies = new Set();
  for (const [fam, tokens] of families) {
    if (tokens.some(t => sq.includes(t) || tk.includes(t))) {
      if (fam === 'hilux' && (sq.includes('surf') || tk.includes('サーフ'))) continue;
      if (fam === 'hilux_surf' && !(sq.includes('surf') || tk.includes('サーフ'))) continue;
      targetFamilies.add(fam);
    }
  }

  const carFamilies = new Set();
  for (const [fam, tokens] of families) {
    if (tokens.some(t => cm.includes(t) || ct.includes(t))) {
      if (fam === 'hilux' && (cm.includes('サーフ') || ct.includes('サーフ') || ct.includes('surf'))) continue;
      if (fam === 'hilux_surf' && !(cm.includes('サーフ') || ct.includes('サーフ') || ct.includes('surf'))) continue;
      carFamilies.add(fam);
    }
  }

  if (targetFamilies.size > 0) {
    for (const f of targetFamilies) {
      if (carFamilies.has(f)) return true;
    }
    return false; // Mismatch
  }

  const words = sq.split(/\s+/).filter(w => w.length > 2);
  if (words.length > 0 && words.some(w => combined.includes(w))) return true;
  if (tk && combined.includes(tk)) return true;
  return false;
}

// ==============================================================================
// 3. DICTIONARY & AUTOMOTIVE TRANSLATOR (PORTED FROM scraper/translator.py)
// ==============================================================================

const AUTOMOTIVE_MAP = {
  // Brands
  'toyota': 'トヨタ',
  'subaru': 'スバル',
  'nissan': '日産',
  'honda': 'ホンダ',
  'mazda': 'マツダ',
  'mitsubishi': '三菱',
  'suzuki': 'スズキ',
  'jeep': 'ジープ',
  'benz': 'ベンツ',
  'mercedes': 'ベンツ',
  'bmw': 'BMW',
  'audi': 'アウディ',

  // Land Cruiser Family
  'land cruiser 80': 'ランドクルーザー 80',
  'land cruiser 70': 'ランドクルーザー 70',
  'land cruiser 60': 'ランドクルーザー 60',
  'land cruiser 100': 'ランドクルーザー 100',
  'land cruiser 200': 'ランドクルーザー 200',
  'land cruiser 250': 'ランドクルーザー 250',
  'land cruiser 300': 'ランドクルーザー 300',
  'land cruiser cygnus': 'ランドクルーザー シグナス',
  'land cruiser prado': 'ランドクルーザー プラド',
  'land cruiser': 'ランドクルーザー',
  'landcruiser': 'ランドクルーザー',
  '150 prado': '150 プラド',
  '120 prado': '120 プラド',
  '90 prado': '90 プラド',
  '70 prado': '70 プラド',
  'prado': 'プラド',
  'fj cruiser': 'FJ クルーザー',
  'fj': 'FJ',

  // Hiace & Van Family
  'hiace van': 'ハイエース バン',
  'hiace wagon': 'ハイエース ワゴン',
  'hiace commuter': 'ハイエース コミューター',
  'hiace': 'ハイエース',
  'regius ace': 'レジアスエース',
  'regiusace': 'レジアスエース',
  'finetech tourer': 'ファインテックツアラー',
  'granace': 'グランエース',
  'grand cabin': 'グランドキャビン',
  'campervan': 'キャンピングカー',
  'camper': 'キャンピングカー',

  // Workhorses & Pickups
  'probox': 'プロボックス',
  'succeed': 'サクシード',
  'townace': 'タウンエース',
  'hilux surf': 'ハイラックスサーフ',
  'hilux': 'ハイラックス',
  'surf': 'サーフ',
  'tacoma': 'タコマ',
  'tundra': 'タンドラ',
  '4runner': '4ランナー',
  'sequoia': 'セコイア',

  // 4WD & Offroad Models
  'jimny sierra': 'ジムニーシエラ',
  'jimny': 'ジムニー',
  'delica d5': 'デリカ D:5',
  'delica': 'デリカ',
  'wrangler': 'ラングラー',

  // Trims & Options
  'super gl': 'スーパーGL',
  'dark prime': 'ダークプライム',
  'round headlights': '丸目',
  'square headlights': '角目',
  'lifted': 'リフトアップ',
  'sunroof': 'サンルーフ',
  'leather seats': '本革シート',
  'bed kit': 'ベッドキット',
  'cold weather': '寒冷地仕様',
  'all paint': 'オールペイント',
  'custom': 'カスタム',
  'diesel': 'ディーゼル',
  'gasoline': 'ガソリン',
  'hybrid': 'ハイブリッド'
};

const RENOCA_AND_PROPRIETARY_TERMS = new Set([
  'wonder', 'coast lines', 'coastlines', 'color bomb', 'colorbomb',
  'phoenix', 'euro box', 'eurobox', 'mol', 'renoca', 'wood village',
  'woodvillage', 'american classic', '106', 'roy', 'army', 'delfinoline',
  'delfino line', 'deeps', 'flex', 'flex custom', 're classic', 'reclassic',
  'knot', 'windansea'
]);

const SHORTHAND_EXPANSIONS = [
  [/\blc\s*80\b/gi, 'land cruiser 80'],
  [/\blc\s*70\b/gi, 'land cruiser 70'],
  [/\blc\s*60\b/gi, 'land cruiser 60'],
  [/\blc\s*100\b/gi, 'land cruiser 100'],
  [/\blc\s*200\b/gi, 'land cruiser 200'],
  [/\blc\s*250\b/gi, 'land cruiser 250'],
  [/\blc\s*300\b/gi, 'land cruiser 300'],
  [/\bfjcruiser\b/gi, 'fj cruiser'],
  [/\bfj\b(?!\s*cruiser)/gi, 'fj cruiser'],
  [/\bland\s*cruiser\s*prado\b/gi, 'land cruiser prado'],
  [/\blandcruiser\b/gi, 'land cruiser'],
  [/\bhiluxsurf\b/gi, 'hilux surf'],
  [/\bregiusace\b/gi, 'regius ace'],
  [/\bhiacevan\b/gi, 'hiace van'],
  [/\bhiacewagon\b/gi, 'hiace wagon'],
  [/\bprado\s*150\b/gi, '150 prado'],
  [/\bprado\s*120\b/gi, '120 prado'],
  [/\bprado\s*90\b/gi, '90 prado'],
  [/\bprado\s*70\b/gi, '70 prado']
];

async function translateQueryToJapanese(query) {
  if (!query || !query.trim()) return '';
  let raw = query.trim();

  // If already Japanese
  if (/[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]/.test(raw)) {
    return raw;
  }

  let cleaned = raw.toLowerCase().replace(/[-_]+/g, ' ').replace(/\s+/g, ' ');
  for (const [pat, repl] of SHORTHAND_EXPANSIONS) {
    cleaned = cleaned.replace(pat, repl);
  }

  if (AUTOMOTIVE_MAP[cleaned]) {
    return AUTOMOTIVE_MAP[cleaned];
  }

  // Preserve proprietary lines
  if (Array.from(RENOCA_AND_PROPRIETARY_TERMS).some(t => cleaned.includes(t))) {
    return raw;
  }

  for (const [en, jp] of Object.entries(AUTOMOTIVE_MAP)) {
    if (cleaned.includes(en)) {
      return jp;
    }
  }

  // Dynamic online translation for unmapped arbitrary phrases (e.g. "matte green", "red leather")
  try {
    const url = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(cleaned)}&langpair=en|ja`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2000);
    const resp = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    if (resp.ok) {
      const data = await resp.json();
      const t = data.responseData?.translatedText;
      if (t && t.trim()) {
        return t.replace(/（[A-Za-z\s]+）/g, '').trim();
      }
    }
  } catch (e) {}

  return raw;
}

const BRANDS_JA_TO_EN = {
  'トヨタ': 'Toyota',
  '日産': 'Nissan',
  'ホンダ': 'Honda',
  'スバル': 'Subaru',
  'マツダ': 'Mazda',
  '三菱': 'Mitsubishi',
  'スズキ': 'Suzuki',
  'ダイハツ': 'Daihatsu',
  'レクサス': 'Lexus',
  'ジープ': 'Jeep',
  'アウディ': 'Audi',
  'BMW': 'BMW',
  'メルセデス': 'Mercedes-Benz',
  'ベンツ': 'Mercedes-Benz'
};

const MODELS_JA_TO_EN = {
  'サクシードバン': 'Succeed Van',
  'サクシード ワゴン': 'Succeed Wagon',
  'サクシード': 'Succeed',
  'プロボックスバン': 'Probox Van',
  'プロボックス ワゴン': 'Probox Wagon',
  'プロボックス': 'Probox',
  'ハイエースバン': 'Hiace Van',
  'ハイエースワゴン': 'Hiace Wagon',
  'ハイエース コミューター': 'Hiace Commuter',
  'ハイエース': 'Hiace',
  'レジアスエースバン': 'Regius Ace Van',
  'レジアスエース': 'Regius Ace',
  'ランドクルーザープラド': 'Land Cruiser Prado',
  'ランドクルーザー プラド': 'Land Cruiser Prado',
  'ランドクルーザー70': 'Land Cruiser 70',
  'ランドクルーザー80': 'Land Cruiser 80',
  'ランドクルーザー100': 'Land Cruiser 100',
  'ランドクルーザー200': 'Land Cruiser 200',
  'ランドクルーザー250': 'Land Cruiser 250',
  'ランドクルーザー300': 'Land Cruiser 300',
  'ランドクルーザー': 'Land Cruiser',
  'ハイラックスサーフ': 'Hilux Surf',
  'ハイラックス サーフ': 'Hilux Surf',
  'ハイラックス': 'Hilux',
  'FJクルーザー': 'FJ Cruiser',
  'ジムニーシエラ': 'Jimny Sierra',
  'ジムニー シエラ': 'Jimny Sierra',
  'ジムニー': 'Jimny',
  'タウンエース': 'TownAce',
  'ラングラー': 'Wrangler',
  'デリカ': 'Delica'
};

const TITLE_TERMS_JA_TO_EN = {
  'トヨタ': 'Toyota',
  'スズキ': 'Suzuki',
  '三菱': 'Mitsubishi',
  '日産': 'Nissan',
  'ホンダ': 'Honda',
  'ジープ': 'Jeep',
  'マツダ': 'Mazda',
  'スバル': 'Subaru',
  'サクシードバン': 'Succeed Van',
  'サクシード': 'Succeed',
  'プロボックスバン': 'Probox Van',
  'プロボックス': 'Probox',
  'ハイエースバン': 'Hiace Van',
  'ハイエースワゴン': 'Hiace Wagon',
  'ハイエース': 'Hiace',
  'レジアスエース': 'Regius Ace',
  'ランドクルーザープラド': 'Land Cruiser Prado',
  'ランドクルーザー プラド': 'Land Cruiser Prado',
  'ランドクルーザー70': 'Land Cruiser 70',
  'ランドクルーザー80': 'Land Cruiser 80',
  'ランドクルーザー100': 'Land Cruiser 100',
  'ランドクルーザー200': 'Land Cruiser 200',
  'ランドクルーザー250': 'Land Cruiser 250',
  'ランドクルーザー300': 'Land Cruiser 300',
  'ランドクルーザー': 'Land Cruiser',
  'ハイラックスサーフ': 'Hilux Surf',
  'ハイラックス': 'Hilux',
  'FJクルーザー': 'FJ Cruiser',
  'ジムニーシエラ': 'Jimny Sierra',
  'ジムニー': 'Jimny',
  'タウンエース': 'TownAce',
  'ラングラー': 'Wrangler',
  'デリカ': 'Delica',
  'VXリミテッド': 'VX Limited',
  'GXリミテッド': 'GX Limited',
  'TXリミテッド': 'TX Limited',
  'リミテッド': 'Limited',
  'カラーパッケージ': 'Color Package',
  'GRスポーツ': 'GR Sport',
  'ブラックラリーエディション': 'Black Rally Edition',
  'ラリーエディション': 'Rally Edition',
  'エディション': 'Edition',
  'パッケージ': 'Package',
  'ベースグレード': 'Base Grade',
  'ワンダー': 'Wonder',
  'コーストライン': 'Coast Lines',
  'コーストラインズ': 'Coast Lines',
  'カラーボム': 'Color Bomb',
  'フェニックス': 'Phoenix',
  'ユーロボックス': 'Euro Box',
  'リノカ': 'Renoca',
  'モル': 'MOL',
  'アメリカンクラシック': 'American Classic',
  'ウッドヴィレッジ': 'Wood Village',
  'デルフィーノライン': 'DelfinoLine',
  'スーパーGL': 'Super GL',
  'ダークプライムⅡ': 'Dark Prime II',
  'ダークプライム': 'Dark Prime',
  'ミドルルーフ': 'Middle Roof',
  'ハイルーフ': 'High Roof',
  'ロングボディ': 'Long Body',
  'スーパーロング': 'Super Long',
  'ロング': 'Long',
  'ワイド': 'Wide',
  '標準ボディ': 'Standard Body',
  '標準': 'Standard',
  'バン': 'Van',
  'ワゴン': 'Wagon',
  'リフトアップ': 'Lifted',
  'キャンピングカー': 'Campervan',
  'カスタム': 'Custom',
  'オールペイント': 'All Paint',
  '角目': 'Square Headlights',
  '丸目': 'Round Headlights',
  '寒冷地仕様': 'Cold Weather Spec',
  'ベッドキット': 'Bed Kit',
  'ディーゼルターボ': 'Diesel Turbo',
  'ディーゼル': 'Diesel',
  'ガソリン': 'Gasoline',
  'ハイブリッド': 'Hybrid',
  '新車': 'New Car',
  '本革シート': 'Leather Seats',
  'サンルーフ': 'Sunroof'
};

const BODY_TYPE_MAP = {
  'ステーションワゴン': 'Station Wagon',
  'クロカン・ＳＵＶ': 'SUV / 4WD',
  'クロカン・SUV': 'SUV / 4WD',
  'クロカン': 'SUV / 4WD',
  'バン': 'Van',
  'ミニバン・ワンボックス': 'Minivan / 1-Box',
  'ミニバン': 'Minivan / 1-Box',
  'ピックアップトラック': 'Pickup Truck',
  'ハッチバック': 'Hatchback',
  'セダン': 'Sedan'
};

const ENGINE_TYPE_MAP = {
  'ガソリン': 'Gasoline',
  'ディーゼル': 'Diesel Turbo',
  'ハイブリッド': 'Hybrid',
  '電気': 'EV',
  'LPG': 'LPG'
};

const DRIVE_SYSTEM_MAP = {
  '2WD': '2WD',
  '4WD': '4WD (Full-Time / Part-Time)',
  'パートタイム4WD': 'Part-Time 4WD',
  'フルタイム4WD': 'Full-Time 4WD',
  '前輪駆動': 'FWD',
  '後輪駆動': 'RWD'
};

const TRANSMISSION_MAP = {
  'CVTフロア': 'Floor CVT',
  'CVTインパネ': 'Dash CVT',
  'CVT': 'CVT',
  '6ATインパネ（MTモード付AT）': '6-Speed AT (with Manual Mode)',
  '6ATフロア（MTモード付AT）': '6-Speed AT (with Manual Mode)',
  '4ATフロア': '4-Speed Floor AT',
  '4ATインパネ': '4-Speed Dash AT',
  '5ATフロア': '5-Speed Floor AT',
  '5ATインパネ': '5-Speed Dash AT',
  '10ATフロア': '10-Speed Floor AT',
  '6AT': '6-Speed AT',
  '5AT': '5-Speed AT',
  '4AT': '4-Speed AT',
  '10AT': '10-Speed AT',
  '5MTフロア': '5-Speed Manual',
  '6MTフロア': '6-Speed Manual',
  '5MT': '5-Speed Manual',
  '6MT': '6-Speed Manual',
  'AT': 'Automatic (AT)',
  'MT': 'Manual (MT)'
};

const COLOR_MAP = {
  'グリーン': 'Green',
  'オリーブグリーン': 'Olive Green',
  'アーミーグリーン': 'Army Green',
  'ホワイト': 'White',
  '白': 'White',
  'ホワイトパール': 'White Pearl',
  'ホワイトパールクリスタルシャイン': 'White Pearl Crystal Shine',
  'ブラック': 'Black',
  '黒': 'Black',
  'ブラックマイカ': 'Black Mica',
  'ベージュ': 'Beige',
  'サンドベージュ': 'Sand Beige',
  'シルバー': 'Silver',
  'シルバーマイカメタリック': 'Silver Mica Metallic',
  'グレー': 'Gray',
  'グレーメタリック': 'Gray Metallic',
  'ナルドグレー': 'Nardo Gray',
  'アウディ純正ナルドグレー': 'Audi Nardo Gray',
  'ブルー': 'Blue',
  'ネイビー': 'Navy Blue',
  'レッド': 'Red',
  'ブラウン': 'Brown',
  'イエロー': 'Yellow'
};

const REPAIR_HISTORY_MAP = {
  'なし': 'None (Clean / No Accident History)',
  '無': 'None (Clean / No Accident History)',
  'あり': 'Yes (Repaired / Accident History)',
  '有': 'Yes (Repaired / Accident History)'
};

const INSPECTION_MAP = {
  '車検整備付': 'Inspection & Maintenance Included',
  '車検整備無': 'No Inspection',
  '車検残': 'Valid Inspection Remaining',
  '車検付': 'Valid Inspection Remaining'
};

const EQUIPMENT_MAP = {
  'ナビ': 'Navigation',
  'バックカメラ': 'Backup Camera',
  'ETC': 'ETC Card Reader',
  'エアコン': 'Air Conditioning',
  'パワステ': 'Power Steering',
  'パワーウィンドウ': 'Power Windows',
  'ABS': 'ABS',
  'エアバッグ': 'Airbags',
  'キーレス': 'Keyless Entry',
  'スマートキー': 'Smart Key / Push Start',
  'アルミホイール': 'Alloy Wheels',
  'アルミ': 'Alloy Wheels',
  '革シート': 'Leather Seats',
  '本革シート': 'Leather Seats',
  'サンルーフ': 'Sunroof',
  'LEDヘッドランプ': 'LED Headlights',
  'クルーズコントロール': 'Cruise Control',
  '両側スライドドア': 'Dual Sliding Doors',
  'パワースライドドア': 'Power Sliding Door',
  'フルセグTV': 'Full-Segment Digital TV',
  'Bluetooth接続': 'Bluetooth Audio',
  '衝突被害軽減ブレーキ': 'Collision Avoidance Braking',
  'ドライブレコーダー': 'Dashcam Recorder',
  'ルーフラック': 'Roof Rack',
  'リフトアップ': 'Lifted Suspension',
  'ベッドキット': 'Bed Kit / Camper Interior',
  '寒冷地仕様': 'Cold Weather Package',
  '横滑り防止装置': 'Electronic Stability Control (ESC)',
  '盗難防止装置': 'Anti-Theft Immobilizer'
};

const STEERING_MAP = {
  '右': 'RHD (Right Hand Drive)',
  '左': 'LHD (Left Hand Drive)'
};

function translateVehicleToEnglish(v) {
  if (!v) return v;
  const out = { ...v };

  // Brand
  const b = String(out.brand || '').trim();
  if (BRANDS_JA_TO_EN[b]) out.brand = BRANDS_JA_TO_EN[b];
  else if (!b) out.brand = 'Toyota';

  // Model
  const m = String(out.model || '').trim();
  for (const [ja, en] of Object.entries(MODELS_JA_TO_EN)) {
    if (m.includes(ja)) {
      out.model = en;
      break;
    }
  }

  // Title
  let title = String(out.title || '').trim();
  if (title) {
    for (const [ja, en] of Object.entries(TITLE_TERMS_JA_TO_EN)) {
      title = title.split(ja).join(` ${en} `);
    }
    out.title = title.replace(/\s+/g, ' ').trim();
  }

  // Model Year
  const yMatch = String(out.model_year || '').match(/(\d{4})/);
  if (yMatch) out.model_year = yMatch[1];

  // Mileage Raw
  if (out.mileage_km && typeof out.mileage_km === 'number') {
    out.mileage_raw = `${out.mileage_km.toLocaleString()} km`;
  }

  // Engine
  const eng = String(out.engine_type || '').trim();
  for (const [ja, en] of Object.entries(ENGINE_TYPE_MAP)) {
    if (eng.includes(ja)) {
      out.engine_type = en;
      break;
    }
  }

  // Drive
  const drv = String(out.drive_system || '').trim();
  if (DRIVE_SYSTEM_MAP[drv]) out.drive_system = DRIVE_SYSTEM_MAP[drv];

  // Transmission
  const tr = String(out.transmission || '').trim();
  if (TRANSMISSION_MAP[tr]) out.transmission = TRANSMISSION_MAP[tr];
  else {
    for (const [ja, en] of Object.entries(TRANSMISSION_MAP)) {
      if (tr.includes(ja)) {
        out.transmission = en;
        break;
      }
    }
  }

  // Body
  const bd = String(out.body_type || '').trim();
  for (const [ja, en] of Object.entries(BODY_TYPE_MAP)) {
    if (bd.includes(ja)) {
      out.body_type = en;
      break;
    }
  }

  // Color
  const col = String(out.color || '').trim();
  for (const [ja, en] of Object.entries(COLOR_MAP)) {
    if (col.includes(ja)) {
      out.color = en;
      break;
    }
  }

  // Repair
  const rep = String(out.repair_history || '').trim();
  if (REPAIR_HISTORY_MAP[rep]) out.repair_history = REPAIR_HISTORY_MAP[rep];
  else if (rep.includes('なし') || rep.includes('無')) out.repair_history = 'None (Clean / No Accident History)';
  else if (rep.includes('あり') || rep.includes('有')) out.repair_history = 'Yes (Repaired / Accident History)';

  // Inspection
  const insp = String(out.inspection || '').trim();
  if (INSPECTION_MAP[insp]) out.inspection = INSPECTION_MAP[insp];

  // Warranty
  const warr = String(out.warranty || '').trim();
  if (warr.includes('保証付')) out.warranty = 'Warranty Included (Free Coverage on All Functional Parts)';
  else if (warr.includes('保証無') || warr.includes('なし')) out.warranty = 'No Warranty';

  // Legal Maintenance
  const maint = String(out.legal_maintenance || '').trim();
  if (maint.includes('整備込み') || maint.includes('法定整備付')) {
    out.legal_maintenance = 'Maintenance Included (24-Month Statutory Inspection with Service Records)';
  }

  // Steering
  const str = String(out.steering || '').trim();
  if (STEERING_MAP[str]) out.steering = STEERING_MAP[str];

  // Supercharger
  const sc = String(out.has_supercharger || '').trim();
  if (sc.includes('なし') || sc.includes('無') || sc === '-') out.has_supercharger = 'None';
  else if (sc.includes('ターボ')) out.has_supercharger = 'Turbo';

  // Sliding doors
  const sld = String(out.sliding_doors || '').trim();
  if (sld.includes('両側電動')) out.sliding_doors = 'Dual Power Sliding Doors';
  else if (sld.includes('片側電動')) out.sliding_doors = 'Single Power Sliding Door';

  // Recycle fee
  const rec = String(out.recycle_fee || '').trim();
  if (rec.includes('リ済込')) out.recycle_fee = 'Recycle Fee Included';
  else if (rec.includes('リ未')) out.recycle_fee = 'Recycle Fee Not Included';

  // Equipment array
  if (Array.isArray(out.equipment)) {
    out.equipment = out.equipment.map(e => {
      for (const [ja, en] of Object.entries(EQUIPMENT_MAP)) {
        if (e.includes(ja)) return en;
      }
      return e;
    });
  }

  // Assign Top 5 images
  const imgs = out.image_urls || (out.thumbnail_url ? [out.thumbnail_url] : []);
  for (let i = 1; i <= 5; i++) {
    out[`image_${i}`] = imgs[i - 1] || null;
  }

  return out;
}

// ==============================================================================
// 4. HTML PARSER (PORTED FROM scraper/parser.py)
// ==============================================================================

function parseYen(text) {
  if (!text) return null;
  const clean = text.replace(/,/g, '').replace(/円/g, '').replace(/\(税込\)/g, '').trim();
  if (clean.includes('万')) {
    const m = clean.match(/([\d\.]+)\s*万/);
    if (m) {
      try {
        return Math.round(parseFloat(m[1]) * 10000);
      } catch (e) {}
    }
  }
  const digits = clean.replace(/[^\d\.]/g, '');
  if (digits) {
    try {
      const val = parseFloat(digits);
      if (val < 5000) return Math.round(val * 10000);
      return Math.round(val);
    } catch (e) {}
  }
  return null;
}

function parseMileage(text) {
  if (!text) return [null, null];
  const raw = text.trim();
  const mMan = raw.match(/([\d\.]+)\s*万\s*km/i);
  if (mMan) {
    try {
      return [raw, Math.round(parseFloat(mMan[1]) * 10000)];
    } catch (e) {}
  }
  const mKm = raw.match(/([\d\,]+)\s*km/i);
  if (mKm) {
    try {
      return [raw, parseInt(mKm[1].replace(/,/g, ''), 10)];
    } catch (e) {}
  }
  return [raw, null];
}

function parseDisplacement(text) {
  if (!text) return [null, null];
  const raw = text.trim();
  const m = raw.match(/(\d+)\s*cc/i);
  if (m) {
    try {
      return [raw, parseInt(m[1], 10)];
    } catch (e) {}
  }
  return [raw, null];
}

function parseSearchPage(html) {
  const $ = cheerio.load(html);
  const vehicles = [];
  const cards = $('.zaiko_box');

  cards.each((i, el) => {
    const card = $(el);
    const wish = card.find('a.marketo_wish, a.wish');
    let kanriCode = wish.attr('data-id')?.trim();

    const titleElem = card.find('.useditem__ttl dt h3 a');
    const photoLink = card.find('a.bl-bigger');
    let detailUrl = titleElem.attr('href') || photoLink.attr('href') || '';

    if (!kanriCode && detailUrl) {
      const m = detailUrl.match(/used-(\d+)\.html/);
      if (m) kanriCode = m[1];
    }
    if (!kanriCode) return;

    if (!detailUrl.startsWith('http')) {
      detailUrl = 'https://www.flexnet.co.jp' + (detailUrl.startsWith('/') ? detailUrl : '/' + detailUrl);
    }

    const title = titleElem.text().trim() || 'FLEX Vehicle';
    const imgElem = card.find('.usd_phbox img');
    let thumbnail = imgElem.attr('src') || imgElem.attr('data-src') || '';

    let brand = 'Toyota';
    let model = 'Land Cruiser';
    try {
      const decoded = decodeURIComponent(detailUrl);
      const slugMatch = decoded.match(/\/detail\/([^\/]+?)-(?:used|new)-\d+\.html/);
      if (slugMatch) {
        const parts = slugMatch[1].split('-');
        brand = parts[0];
        if (parts.length > 1) model = parts.slice(1).join('-');
      }
    } catch (e) {}

    const badges = [];
    card.find('.useditem__ttl dd span').each((_, b) => {
      const t = $(b).text().trim();
      if (t) badges.push(t);
    });

    const tagline = card.find('.useditem__ttl p.txt14').text().trim() || null;
    const vehiclePrice = parseYen(card.find('.kakakutxt_hontai').text());
    const expenses = parseYen(card.find('.kakakutxt_syouhiyou').text());
    const totalPrice = parseYen(card.find('.kakakutxt').text());

    let vehicle = {
      kanri_code: kanriCode,
      detail_url: detailUrl,
      title,
      brand,
      model,
      thumbnail_url: thumbnail,
      badge_tags: badges,
      tagline,
      vehicle_price: vehiclePrice,
      expenses,
      total_price: totalPrice,
      status: 'available',
      first_seen_at: new Date().toISOString(),
      last_scraped_at: new Date().toISOString()
    };

    // Quick spec boxes
    card.find('.usd_detailbox li').each((_, item) => {
      const ttl = $(item).find('.usd_detail_ttl').text().trim();
      const val = $(item).find('.detail_atai').text().trim();
      if (!ttl || !val) return;

      if (ttl.includes('年式')) vehicle.model_year = val;
      else if (ttl.includes('走行')) {
        const [raw, km] = parseMileage(val);
        vehicle.mileage_raw = raw;
        vehicle.mileage_km = km;
      } else if (ttl.includes('排気')) {
        const [raw, cc] = parseDisplacement(val);
        vehicle.displacement_raw = raw;
        vehicle.displacement_cc = cc;
      } else if (ttl.includes('修復')) vehicle.repair_history = val;
      else if (ttl.includes('車検')) vehicle.inspection = val;
      else if (ttl.includes('駆動')) vehicle.drive_system = val;
      else if (ttl.includes('色')) vehicle.color = val;
      else if (ttl.includes('エンジン')) vehicle.engine_type = val;
      else if (ttl.includes('シフト')) vehicle.transmission = val;
      else if (ttl.includes('型式')) vehicle.model_code = val;
    });

    const pref = card.find('.shop_bottom_box .bkknpref').text().trim();
    const shop = card.find('.shop_bottom_box a');
    const tel = card.find('.shop_bottom_box .telbox').text().replace(/無料通話/g, '').trim();

    if (pref) vehicle.store_prefecture = pref;
    if (shop.length) {
      vehicle.store_name = shop.text().trim();
      vehicle.store_url = shop.attr('href');
    }
    if (tel) vehicle.store_tel = tel;

    if (thumbnail) {
      const highRes = thumbnail.replace(/_\d+\.(jpg|jpeg|png|webp)$/i, '.JPG');
      vehicle.image_urls = [highRes];
      vehicle.image_1 = highRes;
    }

    vehicle = translateVehicleToEnglish(vehicle);
    vehicles.push(vehicle);
  });

  return vehicles;
}

function parseDetailPage(html, url, kanriCodeFallback) {
  const $ = cheerio.load(html);
  let data = {
    detail_url: url,
    kanri_code: kanriCodeFallback || '',
    status: 'available',
    last_scraped_at: new Date().toISOString()
  };

  if (!data.kanri_code) {
    const m = url.match(/used-(\d+)\.html/);
    if (m) data.kanri_code = m[1];
  }

  // 1. JSON-LD Product Schema
  $('script[type="application/ld+json"]').each((_, s) => {
    try {
      const ld = JSON.parse($(s).html() || '{}');
      if (ld['@type'] === 'Product') {
        if (ld.name) data.title = ld.name.trim();
        if (ld.brand?.name) data.brand = ld.brand.name;
        if (ld.model) data.model = ld.model;
        if (ld.offers?.price) data.vehicle_price = parseInt(ld.offers.price, 10);
        if (ld.offers?.seller) {
          data.store_name = ld.offers.seller.name;
          data.store_tel = ld.offers.seller.telephone;
          data.store_url = ld.offers.seller.url;
          if (ld.offers.seller.address) {
            data.store_prefecture = ld.offers.seller.address.addressRegion;
            data.store_address = (ld.offers.seller.address.addressRegion || '') + (ld.offers.seller.address.addressLocality || '') + (ld.offers.seller.address.streetAddress || '');
          }
        }
      }
    } catch (e) {}
  });

  // 2. Spec tables
  $('table.usdtable tr').each((_, tr) => {
    const ths = $(tr).find('th');
    const tds = $(tr).find('td');
    for (let i = 0; i < Math.min(ths.length, tds.length); i++) {
      const label = $(ths[i]).text().trim();
      const val = $(tds[i]).text().trim();
      if (!label || !val) continue;

      if (label.includes('支払総額')) data.total_price = parseYen(val);
      else if (label.includes('車両価格')) data.vehicle_price = parseYen(val);
      else if (label.includes('諸費用')) data.expenses = parseYen(val);
      else if (label.includes('排気量')) {
        const [raw, cc] = parseDisplacement(val);
        data.displacement_raw = raw;
        data.displacement_cc = cc;
      } else if (label.includes('ボディタイプ')) data.body_type = val;
      else if (label.includes('過給機')) data.has_supercharger = val;
      else if (label.includes('定員')) data.seating_capacity = val;
      else if (label.includes('走行距離')) {
        const [raw, km] = parseMileage(val);
        data.mileage_raw = raw;
        data.mileage_km = km;
      } else if (label.includes('エンジン種別')) data.engine_type = val;
      else if (label.includes('年式')) data.model_year = val;
      else if (label.includes('駆動方式')) data.drive_system = val;
      else if (label.includes('型式')) data.model_code = val;
      else if (label.includes('車体色')) data.color = val;
      else if (label.includes('内装色') && val !== '-') data.interior_color = val;
      else if (label.includes('ハンドル')) data.steering = val;
      else if (label.includes('ドア数')) data.doors = parseInt(val.replace(/\D/g, '') || '0', 10);
      else if (label.includes('車体末尾番号')) data.chassis_last_digits = val;
      else if (label.includes('シフト')) data.transmission = val;
      else if (label.includes('修復歴')) data.repair_history = val;
      else if (label.includes('禁煙車')) data.is_non_smoking = val.includes('◯') || val.includes('○');
      else if (label.includes('ワンオーナー')) data.is_one_owner = val.includes('◯') || val.includes('○') || val.includes('あり');
      else if (label.includes('メーター交換歴')) data.odometer_replaced = val;
      else if (label.includes('車検')) data.inspection = val;
      else if (label.includes('保証')) data.warranty = val;
      else if (label.includes('法定整備')) data.legal_maintenance = val;
      else if (label.includes('スライドドア') && val !== '-') data.sliding_doors = val;
      else if (label.includes('リサイクル料') && val !== '-') data.recycle_fee = val;
      else if (label.includes('記録簿') && val !== '-') data.service_records = val;
      else if (label.includes('登録済未使用車')) data.is_unused_car = val.includes('◯') || val.includes('○') || val.includes('あり');
      else if (label.includes('キャンピングカー')) data.is_campervan = val.includes('◯') || val.includes('○') || val.includes('あり');
      else if (label.includes('ご成約特典') || label.includes('フェア名')) {
        const prev = data.campaign_info ? data.campaign_info + '\n' : '';
        data.campaign_info = prev + `${label}: ${val}`;
      }
    }
  });

  // 3. Sales Points / Dealer Story
  const salesPoints = [];
  $('#usd_sectbox .__items__content').each((_, el) => {
    const text = $(el).text().trim();
    if (text && !salesPoints.includes(text)) salesPoints.push(text);
  });
  if (salesPoints.length > 0) {
    data.sales_points = salesPoints.join('\n\n');
  }

  // 3. Equipment tags
  const equipment = [];
  $('li.speclst_mn_on, li.speclst.speclst_mn_on').each((_, li) => {
    const eq = $(li).text().trim();
    if (eq && !equipment.includes(eq)) equipment.push(eq);
  });
  data.equipment = equipment;

  // 4. Gallery Images (High-Res)
  const imgRegex = /https?:\/\/img2\.flexnet\.co\.jp\/images\/[A-Z0-9]+\/[A-Z0-9]+\/[A-Z0-9]+.*?\.(?:jpg|jpeg|png|webp)/gi;
  const matches = html.match(imgRegex) || [];
  const cleanImages = [];
  matches.forEach(m => {
    const high = m.replace(/_\d+\.(?:jpg|jpeg|png|webp)$/i, '.JPG');
    if (!cleanImages.includes(high)) cleanImages.push(high);
  });
  cleanImages.sort((a, b) => {
    if (a.endsWith('L.JPG')) return -1;
    if (b.endsWith('L.JPG')) return 1;
    return a.localeCompare(b);
  });

  data.image_urls = cleanImages;
  data.thumbnail_url = cleanImages[0] || null;

  data = translateVehicleToEnglish(data);
  return data;
}

// ==============================================================================
// 5. DATABASE UPSERT & REPOSITORY INTERACTION
// ==============================================================================

async function upsertVehiclesToSupabase(vehicles, supabaseUrl, supabaseKey) {
  if (!vehicles || vehicles.length === 0 || !supabaseUrl || !supabaseKey) return 0;
  try {
    const res = await fetch(`${supabaseUrl}/rest/v1/flexnet_vehicles?on_conflict=kanri_code`, {
      method: 'POST',
      headers: {
        'apikey': supabaseKey,
        'Authorization': `Bearer ${supabaseKey}`,
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates'
      },
      body: JSON.stringify(vehicles)
    });
    return res.ok ? vehicles.length : 0;
  } catch (err) {
    console.error('Error upserting to Supabase:', err);
    return 0;
  }
}

// ==============================================================================
// 6. LIVE SEARCH & SINGLE CAR EXTRACTION WITH DEDICATED ROUTES
// ==============================================================================

async function scrapeSearchLive(options = {}, supabaseUrl, supabaseKey) {
  const rawQuery = (options.query || '').trim();
  const limit = parseInt(options.limit || '40', 10);
  const lowQuery = rawQuery.toLowerCase();
  const jpQuery = await translateQueryToJapanese(rawQuery);

  // Dedicated direct category routes on Flexnet Japan
  let targetPath = '/search';
  if (FLEXNET_MODEL_ROUTES[lowQuery]) {
    targetPath = FLEXNET_MODEL_ROUTES[lowQuery];
  } else if (FLEXNET_MODEL_ROUTES[jpQuery]) {
    targetPath = FLEXNET_MODEL_ROUTES[jpQuery];
  }

  let searchUrl = `https://www.flexnet.co.jp${targetPath}`;
  if (targetPath === '/search' && jpQuery) {
    searchUrl += `?keyword=${encodeURIComponent(jpQuery)}`;
  }

  try {
    const res = await fetch(searchUrl, {
      headers: getBrowserHeaders()
    });
    if (!res.ok) throw new Error(`Flexnet search returned status ${res.status}`);
    const html = await res.text();
    let vehicles = parseSearchPage(html);

    // Apply isVehicleModelMatch guard for 100% precision
    if (rawQuery) {
      const filtered = vehicles.filter(v => isVehicleModelMatch(rawQuery, jpQuery, v.model, v.title, v.tagline));
      if (filtered.length > 0) {
        vehicles = filtered;
      }
    }

    if (limit && vehicles.length > limit) {
      vehicles = vehicles.slice(0, limit);
    }

    let saved = 0;
    if (supabaseUrl && supabaseKey && vehicles.length > 0) {
      saved = await upsertVehiclesToSupabase(vehicles, supabaseUrl, supabaseKey);
    }

    return {
      success: true,
      count: vehicles.length,
      total_found: vehicles.length,
      vehicles,
      query: rawQuery,
      translated_query: jpQuery,
      search_url: searchUrl,
      saved_to_supabase: saved,
      source: 'live_flexnet'
    };
  } catch (err) {
    console.error('Live search error:', err);
    return {
      success: false,
      error: err.message
    };
  }
}

async function scrapeSingleLive(url, kanriCode, supabaseUrl, supabaseKey) {
  if (!url) throw new Error('Vehicle URL is required.');
  try {
    const res = await fetch(url, {
      headers: getBrowserHeaders(url)
    });
    if (!res.ok) throw new Error(`Vehicle page returned status ${res.status}`);
    const html = await res.text();
    const vehicle = parseDetailPage(html, url, kanriCode);

    let saved = false;
    if (supabaseUrl && supabaseKey && vehicle.kanri_code) {
      const count = await upsertVehiclesToSupabase([vehicle], supabaseUrl, supabaseKey);
      saved = count > 0;
    }

    return {
      success: true,
      vehicle,
      saved_to_database: saved
    };
  } catch (err) {
    console.error('Single vehicle scrape error:', err);
    return {
      success: false,
      error: err.message
    };
  }
}

module.exports = {
  FLEXNET_MODEL_ROUTES,
  isVehicleModelMatch,
  translateQueryToJapanese,
  translateVehicleToEnglish,
  parseYen,
  parseMileage,
  parseDisplacement,
  parseSearchPage,
  parseDetailPage,
  upsertVehiclesToSupabase,
  scrapeSearchLive,
  scrapeSingleLive
};
