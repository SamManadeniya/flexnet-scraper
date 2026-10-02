const cheerio = require('cheerio');

// English to Japanese search term dictionary for querying Flexnet Japan
const SEARCH_QUERY_MAP = {
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
  'hiace van': 'ハイエース バン',
  'hiace wagon': 'ハイエース ワゴン',
  'hiace commuter': 'ハイエース コミューター',
  'hiace': 'ハイエース',
  'regius ace': 'レジアスエース',
  'regiusace': 'レジアスエース',
  'campervan': 'キャンピングカー',
  'camper': 'キャンピングカー',
  'hilux surf': 'ハイラックスサーフ',
  'hilux': 'ハイラックス',
  'jimny sierra': 'ジムニーシエラ',
  'jimny': 'ジムニー',
  'delica': 'デリカ',
  'toyota': 'トヨタ',
  'nissan': '日産',
  'subaru': 'スバル',
  'mitsubishi': '三菱',
  'suzuki': 'スズキ',
  'honda': 'ホンダ',
  'mazda': 'マツダ'
};

function translateSearchQuery(query) {
  if (!query) return '';
  const clean = query.trim().toLowerCase();
  if (SEARCH_QUERY_MAP[clean]) return SEARCH_QUERY_MAP[clean];
  for (const [en, jp] of Object.entries(SEARCH_QUERY_MAP)) {
    if (clean.includes(en)) return jp;
  }
  return query.trim();
}

// Japanese to English terms mapping
const TERM_MAP = {
  // Brands
  'トヨタ': 'Toyota',
  'スバル': 'Subaru',
  '日産': 'Nissan',
  'ホンダ': 'Honda',
  'マツダ': 'Mazda',
  '三菱': 'Mitsubishi',
  'スズキ': 'Suzuki',
  'ジープ': 'Jeep',
  'ベンツ': 'Mercedes-Benz',
  'BMW': 'BMW',
  'アウディ': 'Audi',

  // Models
  'ランドクルーザー': 'Land Cruiser',
  'プラド': 'Prado',
  'ハイエース': 'Hiace',
  'ハイエースバン': 'Hiace Van',
  'ハイエースワゴン': 'Hiace Wagon',
  'レジアスエース': 'Regius Ace',
  'ハイラックスサーフ': 'Hilux Surf',
  'ハイラックス': 'Hilux',
  'ジムニー': 'Jimny',
  'ジムニーシエラ': 'Jimny Sierra',
  'デリカ': 'Delica',

  // Specs & Options
  'スーパーGL': 'Super GL',
  'ダークプライム': 'Dark Prime',
  '丸目': 'Round Headlights',
  '角目': 'Square Headlights',
  'リフトアップ': 'Lifted Suspension',
  'サンルーフ': 'Sunroof',
  '本革シート': 'Leather Seats',
  'ベッドキット': 'Bed Kit',
  'キャンピングカー': 'Campervan',
  '4WD': '4WD (Full-Time / Part-Time)',
  '2WD': '2WD',
  'オートマ': 'Automatic (AT)',
  'AT': 'Automatic (AT)',
  'MT': 'Manual (MT)',
  'マニュアル': 'Manual (MT)',
  'ガソリン': 'Gasoline',
  'ディーゼル': 'Diesel Turbo',
  'なし': 'None',
  'あり': 'Yes',
  '修復歴なし': 'None (Clean / No Accident History)',
  '車検整備付': 'Inspection & Maintenance Included',
  '車検付': 'Inspection Valid',
  'リサイクル料込': 'Recycle Fee Included',
  '保証付': 'Warranty Included (Free Coverage on All Functional Parts)',
  '法定整備付': 'Maintenance Included (24-Month Statutory Inspection with Service Records)'
};

function translateText(text) {
  if (!text) return text;
  let res = String(text);
  for (const [jp, en] of Object.entries(TERM_MAP)) {
    res = res.split(jp).join(en);
  }
  return res;
}

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

    const vehicle = {
      kanri_code: kanriCode,
      detail_url: detailUrl,
      title: translateText(title),
      brand,
      model,
      thumbnail_url: thumbnail,
      badge_tags: badges,
      tagline: translateText(tagline),
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
      } else if (ttl.includes('修復')) vehicle.repair_history = translateText(val);
      else if (ttl.includes('車検')) vehicle.inspection = translateText(val);
      else if (ttl.includes('駆動')) vehicle.drive_system = translateText(val);
      else if (ttl.includes('色')) vehicle.color = val;
      else if (ttl.includes('エンジン')) vehicle.engine_type = translateText(val);
      else if (ttl.includes('シフト')) vehicle.transmission = translateText(val);
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

    // Default image array
    if (thumbnail) {
      const highRes = thumbnail.replace(/_\d+\.(jpg|jpeg|png|webp)$/i, '.JPG');
      vehicle.image_urls = [highRes];
      vehicle.image_1 = highRes;
    }

    vehicles.push(vehicle);
  });

  return vehicles;
}

function parseDetailPage(html, url, kanriCodeFallback) {
  const $ = cheerio.load(html);
  const data = {
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
      else if (label.includes('定員')) data.seating_capacity = val;
      else if (label.includes('走行距離')) {
        const [raw, km] = parseMileage(val);
        data.mileage_raw = raw;
        data.mileage_km = km;
      } else if (label.includes('エンジン種別')) data.engine_type = translateText(val);
      else if (label.includes('年式')) data.model_year = val;
      else if (label.includes('駆動方式')) data.drive_system = translateText(val);
      else if (label.includes('型式')) data.model_code = val;
      else if (label.includes('車体色')) data.color = val;
      else if (label.includes('ドア数')) data.doors = parseInt(val.replace(/\D/g, '') || '0', 10);
      else if (label.includes('車体末尾番号')) data.chassis_last_digits = val;
      else if (label.includes('シフト')) data.transmission = translateText(val);
      else if (label.includes('修復歴')) data.repair_history = translateText(val);
      else if (label.includes('禁煙車')) data.is_non_smoking = val.includes('◯') || val.includes('○');
      else if (label.includes('車検')) data.inspection = translateText(val);
      else if (label.includes('保証')) data.warranty = translateText(val);
      else if (label.includes('法定整備')) data.legal_maintenance = translateText(val);
      else if (label.includes('ご成約特典') || label.includes('フェア名')) {
        const prev = data.campaign_info ? data.campaign_info + '\n' : '';
        data.campaign_info = prev + `${label}: ${val}`;
      }
    }
  });

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
  for (let i = 1; i <= Math.min(cleanImages.length, 5); i++) {
    data[`image_${i}`] = cleanImages[i - 1];
  }

  if (data.title) data.title = translateText(data.title);
  return data;
}

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

async function scrapeSearchLive(options = {}, supabaseUrl, supabaseKey) {
  const rawQuery = (options.query || '').trim();
  const limit = parseInt(options.limit || '40', 10);
  const jpQuery = translateSearchQuery(rawQuery);

  let searchUrl = 'https://www.flexnet.co.jp/search';
  if (jpQuery) {
    searchUrl += `?keyword=${encodeURIComponent(jpQuery)}`;
  }

  try {
    const res = await fetch(searchUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    });
    if (!res.ok) throw new Error(`Flexnet search returned status ${res.status}`);
    const html = await res.text();
    let vehicles = parseSearchPage(html);

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
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
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
  TERM_MAP,
  SEARCH_QUERY_MAP,
  translateSearchQuery,
  translateText,
  parseYen,
  parseMileage,
  parseDisplacement,
  parseSearchPage,
  parseDetailPage,
  upsertVehiclesToSupabase,
  scrapeSearchLive,
  scrapeSingleLive
};
