const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { scrapeSearchLive, scrapeSingleLive } = require('./lib/scraper.js');

const SUPABASE_URL = (process.env.SUPABASE_URL || 'https://' + 'rxbjexoxyfownnwxzbjn.' + 'supabase.co').replace(/\/$/, '');
const SUPABASE_KEY = process.env.SUPABASE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY || '';
const JWT_SECRET = process.env.JWT_SECRET_KEY || 'b39f7a81d4e04918e4726c92736184a51e5927b2a951c68f237190d7e48b59ac';

const HEADERS = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, PATCH, DELETE'
};

function jsonResponse(statusCode, data) {
  return {
    statusCode,
    headers: HEADERS,
    body: JSON.stringify(data)
  };
}

function getSupabaseHeaders() {
  return {
    'apikey': SUPABASE_KEY,
    'Authorization': `Bearer ${SUPABASE_KEY}`,
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
  };
}

async function getUserByUsername(username) {
  if (!username) return null;
  const clean = username.trim().toLowerCase();
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/users?username=eq.${encodeURIComponent(clean)}&limit=1`, {
      headers: getSupabaseHeaders()
    });
    if (!res.ok) return null;
    const users = await res.json();
    return (users && users.length > 0) ? users[0] : null;
  } catch (err) {
    console.error('Error fetching user:', err);
    return null;
  }
}

exports.handler = async (event, context) => {
  // Handle CORS preflight
  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 204,
      headers: HEADERS,
      body: ''
    };
  }

  // Normalize path
  let path = (event.path || '').replace(/^\/\.netlify\/functions\/server/, '');
  if (!path || path === '') path = '/';
  if (path.startsWith('/api/api/')) {
    path = path.replace('/api/api/', '/api/');
  }
  if (!path.startsWith('/api/') && path !== '/health' && path !== '/') {
    path = '/api/' + path.replace(/^\//, '');
  }

  const method = event.httpMethod.toUpperCase();
  let body = {};
  if (event.body) {
    try {
      body = typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
    } catch (e) {
      body = {};
    }
  }

  // -------------------------------------------------------------
  // Route: GET /health
  // -------------------------------------------------------------
  if (path === '/health' || path === '/api/health' || path === '/') {
    return jsonResponse(200, {
      status: 'healthy',
      version: '2.0.0',
      runtime: 'Netlify Serverless Node.js',
      service: 'flexnet-hunter-api'
    });
  }

  // -------------------------------------------------------------
  // Route: POST /api/auth/register
  // -------------------------------------------------------------
  if (path === '/api/auth/register' && method === 'POST') {
    const username = (body.username || '').trim().toLowerCase();
    const password = body.password || '';
    const role = body.role || 'admin';

    if (username.length < 3) {
      return jsonResponse(400, { detail: 'Username must be at least 3 characters long.' });
    }
    if (password.length < 6) {
      return jsonResponse(400, { detail: 'Password must be at least 6 characters long.' });
    }

    const existing = await getUserByUsername(username);
    if (existing) {
      return jsonResponse(409, { detail: 'A user with this username or email already exists.' });
    }

    const passwordHash = bcrypt.hashSync(password, 12);
    try {
      const createRes = await fetch(`${SUPABASE_URL}/rest/v1/users`, {
        method: 'POST',
        headers: getSupabaseHeaders(),
        body: JSON.stringify({
          username,
          password_hash: passwordHash,
          role
        })
      });
      if (!createRes.ok) {
        const errText = await createRes.text();
        return jsonResponse(500, { detail: `Database failed to create user: ${errText}` });
      }
      const createdUsers = await createRes.json();
      const newUser = (createdUsers && createdUsers.length > 0) ? createdUsers[0] : { username, role, id: 'user' };

      const token = jwt.sign(
        { sub: newUser.username, uid: newUser.id, role: newUser.role || 'admin' },
        JWT_SECRET,
        { expiresIn: '7d' }
      );

      return jsonResponse(200, {
        success: true,
        message: 'User registered successfully',
        token,
        user: {
          id: newUser.id,
          username: newUser.username,
          role: newUser.role || 'admin'
        }
      });
    } catch (err) {
      return jsonResponse(500, { detail: `Error registering user: ${err.message}` });
    }
  }

  // -------------------------------------------------------------
  // Route: POST /api/auth/login
  // -------------------------------------------------------------
  if (path === '/api/auth/login' && method === 'POST') {
    const username = (body.username || '').trim().toLowerCase();
    const password = body.password || '';

    if (!username || !password) {
      return jsonResponse(400, { detail: 'Username and password are required.' });
    }

    const user = await getUserByUsername(username);
    if (!user || !user.password_hash) {
      return jsonResponse(401, { detail: 'Invalid username or password.' });
    }

    const isValid = bcrypt.compareSync(password, user.password_hash);
    if (!isValid) {
      return jsonResponse(401, { detail: 'Invalid username or password.' });
    }

    const token = jwt.sign(
      { sub: user.username, uid: user.id, role: user.role || 'admin' },
      JWT_SECRET,
      { expiresIn: '7d' }
    );

    return jsonResponse(200, {
      success: true,
      message: 'Login successful',
      token,
      user: {
        id: user.id,
        username: user.username,
        role: user.role || 'admin'
      }
    });
  }

  // -------------------------------------------------------------
  // Route: POST /api/auth/reset-password
  // -------------------------------------------------------------
  if (path === '/api/auth/reset-password' && method === 'POST') {
    const username = (body.username || '').trim().toLowerCase();
    const hint = (body.recovery_hint || '').trim();
    const newPassword = body.new_password || '';

    if (!username) {
      return jsonResponse(400, { detail: 'Username is required.' });
    }
    if (newPassword.length < 6) {
      return jsonResponse(400, { detail: 'New password must be at least 6 characters long.' });
    }

    const user = await getUserByUsername(username);

    // If user does not exist yet, allow initializing account with master recovery key
    if (!user) {
      if (hint !== 'admin123') {
        return jsonResponse(403, { detail: "User not found. Use master recovery key 'admin123' to initialize this account." });
      }
      const newHash = bcrypt.hashSync(newPassword, 12);
      try {
        const createRes = await fetch(`${SUPABASE_URL}/rest/v1/users`, {
          method: 'POST',
          headers: getSupabaseHeaders(),
          body: JSON.stringify({
            username,
            password_hash: newHash,
            role: 'admin'
          })
        });
        if (!createRes.ok) {
          const errText = await createRes.text();
          return jsonResponse(500, { detail: `Database failed to initialize account: ${errText}` });
        }
        return jsonResponse(200, {
          success: true,
          message: `Account '${username}' initialized and password set. You can now sign in.`
        });
      } catch (err) {
        return jsonResponse(500, { detail: `Error creating user: ${err.message}` });
      }
    }

    // User exists: verify hint
    const isValidHint = (hint === 'admin123') || bcrypt.compareSync(hint, user.password_hash);
    if (!isValidHint) {
      return jsonResponse(403, { detail: "Invalid recovery hint. Master key is 'admin123'." });
    }

    const newHash = bcrypt.hashSync(newPassword, 12);
    try {
      const updateRes = await fetch(`${SUPABASE_URL}/rest/v1/users?username=eq.${encodeURIComponent(username)}`, {
        method: 'PATCH',
        headers: getSupabaseHeaders(),
        body: JSON.stringify({ password_hash: newHash })
      });
      if (!updateRes.ok) {
        return jsonResponse(500, { detail: 'Database failed to update password.' });
      }
      return jsonResponse(200, {
        success: true,
        message: `Password for '${username}' was successfully updated. You can now sign in.`
      });
    } catch (err) {
      return jsonResponse(500, { detail: `Error updating password: ${err.message}` });
    }
  }

  // -------------------------------------------------------------
  // Route: GET /api/auth/me
  // -------------------------------------------------------------
  if (path === '/api/auth/me' && method === 'GET') {
    const authHeader = event.headers.authorization || event.headers.Authorization || '';
    if (!authHeader.startsWith('Bearer ')) {
      return jsonResponse(401, { detail: 'Missing or invalid authentication token.' });
    }
    const token = authHeader.substring(7).trim();
    try {
      const decoded = jwt.verify(token, JWT_SECRET);
      return jsonResponse(200, {
        authenticated: true,
        user: {
          username: decoded.sub,
          id: decoded.uid,
          role: decoded.role || 'admin'
        }
      });
    } catch (err) {
      return jsonResponse(401, { detail: 'Invalid or expired token.' });
    }
  }

  // -------------------------------------------------------------
  // Route: POST /api/auth/logout
  // -------------------------------------------------------------
  if (path === '/api/auth/logout' && method === 'POST') {
    return jsonResponse(200, { success: true, message: 'Logged out successfully.' });
  }

  // -------------------------------------------------------------
  // Route: GET /api/auth/users
  // -------------------------------------------------------------
  if (path === '/api/auth/users' && method === 'GET') {
    const authHeader = event.headers.authorization || event.headers.Authorization || '';
    if (!authHeader.startsWith('Bearer ')) {
      return jsonResponse(401, { detail: 'Missing or invalid authentication token.' });
    }
    const token = authHeader.substring(7).trim();
    try {
      jwt.verify(token, JWT_SECRET);
      const res = await fetch(`${SUPABASE_URL}/rest/v1/users?select=id,username,role,created_at&order=created_at.desc`, {
        headers: getSupabaseHeaders()
      });
      const users = await res.json();
      return jsonResponse(200, {
        success: true,
        users: Array.isArray(users) ? users : []
      });
    } catch (err) {
      return jsonResponse(401, { detail: 'Invalid or expired token.' });
    }
  }

  // -------------------------------------------------------------
  // Route: GET /api/stats
  // -------------------------------------------------------------
  if (path === '/api/stats' && method === 'GET') {
    try {
      const totalRes = await fetch(`${SUPABASE_URL}/rest/v1/flexnet_vehicles?select=id`, {
        headers: { ...getSupabaseHeaders(), 'Prefer': 'count=exact' }
      });
      const totalCount = parseInt(totalRes.headers.get('content-range')?.split('/')[1] || '0', 10);

      const availRes = await fetch(`${SUPABASE_URL}/rest/v1/flexnet_vehicles?select=id&status=eq.available`, {
        headers: { ...getSupabaseHeaders(), 'Prefer': 'count=exact' }
      });
      const availCount = parseInt(availRes.headers.get('content-range')?.split('/')[1] || '0', 10);

      const soldRes = await fetch(`${SUPABASE_URL}/rest/v1/flexnet_vehicles?select=id&status=eq.sold`, {
        headers: { ...getSupabaseHeaders(), 'Prefer': 'count=exact' }
      });
      const soldCount = parseInt(soldRes.headers.get('content-range')?.split('/')[1] || '0', 10);

      return jsonResponse(200, {
        connected: true,
        total_vehicles: totalCount,
        available_vehicles: availCount,
        sold_vehicles: soldCount,
        table: 'flexnet_vehicles'
      });
    } catch (err) {
      return jsonResponse(200, {
        connected: false,
        total_vehicles: 0,
        available_vehicles: 0,
        sold_vehicles: 0,
        error: err.message
      });
    }
  }

  // -------------------------------------------------------------
  // Route: GET /api/scrape/status
  // -------------------------------------------------------------
  if (path === '/api/scrape/status' && method === 'GET') {
    return jsonResponse(200, {
      is_running: false,
      current_action: 'Cloud Ready (Netlify 24/7 Serverless)',
      current_page: 1,
      total_pages: 1,
      progress_percent: 100,
      scraped_count: 0,
      new_cars_count: 0,
      updated_count: 0,
      errors_count: 0,
      elapsed_seconds: 0,
      last_error: null
    });
  }

  // -------------------------------------------------------------
  // Route: POST /api/scrape/start
  // -------------------------------------------------------------
  if (path === '/api/scrape/start' && method === 'POST') {
    return jsonResponse(200, {
      message: 'Scraper operates 24/7 automatically via Netlify Scheduled Functions (every 6 hours). For on-demand search, use POST /api/scrape/search.',
      params: body
    });
  }

  // -------------------------------------------------------------
  // Route: POST /api/scrape/stop
  // -------------------------------------------------------------
  if (path === '/api/scrape/stop' && method === 'POST') {
    return jsonResponse(200, {
      message: 'Scraper runs in serverless event mode. No background process needed.'
    });
  }

  // -------------------------------------------------------------
  // Route: POST /api/scrape/search
  // -------------------------------------------------------------
  if (path === '/api/scrape/search' && method === 'POST') {
    const q = (body.query || '').trim();
    const limit = parseInt(body.limit || '40', 10);
    const searchStartTime = Date.now();

    // 1. Attempt live scrape directly from Flexnet Japan with full criteria payload
    try {
      const liveResult = await scrapeSearchLive(body, SUPABASE_URL, SUPABASE_KEY);
      if (liveResult.success && liveResult.vehicles && liveResult.vehicles.length > 0) {
        return jsonResponse(200, {
          success: true,
          count: liveResult.vehicles.length,
          total_found: liveResult.total_found || liveResult.vehicles.length,
          vehicles: liveResult.vehicles,
          query: liveResult.query,
          translated_query: liveResult.translated_query,
          search_url: liveResult.search_url,
          saved_to_supabase: liveResult.saved_to_supabase || 0,
          elapsed_seconds: liveResult.elapsed_seconds || 0,
          source: 'live_flexnet'
        });
      }
    } catch (err) {
      console.warn('Live search fallback to Supabase:', err);
    }

    // 2. Fallback to Supabase database
    let supabaseQuery = `${SUPABASE_URL}/rest/v1/flexnet_vehicles?select=*&order=id.desc&limit=${limit}`;
    if (q) {
      const qNoSpace = q.replace(/\s+/g, '');
      const orClauses = [
        `title.ilike.*${encodeURIComponent(q)}*`,
        `tagline.ilike.*${encodeURIComponent(q)}*`,
        `model.ilike.*${encodeURIComponent(q)}*`
      ];
      if (qNoSpace !== q) {
        orClauses.push(
          `title.ilike.*${encodeURIComponent(qNoSpace)}*`,
          `tagline.ilike.*${encodeURIComponent(qNoSpace)}*`,
          `model.ilike.*${encodeURIComponent(qNoSpace)}*`
        );
      }
      supabaseQuery += `&or=(${orClauses.join(',')})`;
    }

    try {
      const res = await fetch(supabaseQuery, { headers: getSupabaseHeaders() });
      let vehicles = await res.json();
      if (!Array.isArray(vehicles)) vehicles = [];

      const elapsed = Number(((Date.now() - searchStartTime) / 1000).toFixed(1));
      return jsonResponse(200, {
        success: true,
        count: vehicles.length,
        total_found: vehicles.length,
        vehicles,
        query: q,
        elapsed_seconds: elapsed,
        source: 'supabase'
      });
    } catch (err) {
      return jsonResponse(500, { detail: `Search error: ${err.message}` });
    }
  }

  // -------------------------------------------------------------
  // Route: POST /api/scrape/single
  // -------------------------------------------------------------
  if (path === '/api/scrape/single' && method === 'POST') {
    const kanri = (body.kanri_code || '').trim();
    const url = (body.url || '').trim();

    // 1. Attempt live scraping of the vehicle URL
    if (url) {
      try {
        const liveSingle = await scrapeSingleLive(url, kanri, SUPABASE_URL, SUPABASE_KEY);
        if (liveSingle.success && liveSingle.vehicle) {
          return jsonResponse(200, {
            success: true,
            vehicle: liveSingle.vehicle,
            saved_to_database: liveSingle.saved_to_database,
            source: 'live_flexnet'
          });
        }
      } catch (err) {
        console.warn('Live single scrape error, checking database:', err);
      }
    }

    // 2. Fallback to Supabase database
    try {
      let q = `${SUPABASE_URL}/rest/v1/flexnet_vehicles?select=*&limit=1`;
      if (kanri) q += `&kanri_code=eq.${encodeURIComponent(kanri)}`;
      else if (url) q += `&detail_url=eq.${encodeURIComponent(url)}`;

      const res = await fetch(q, { headers: getSupabaseHeaders() });
      const cars = await res.json();
      if (cars && cars.length > 0) {
        return jsonResponse(200, { success: true, vehicle: cars[0], source: 'supabase' });
      }
      return jsonResponse(404, { detail: 'Vehicle not found on Flexnet or in database.' });
    } catch (err) {
      return jsonResponse(500, { detail: err.message });
    }
  }


  // Default Fallback
  return jsonResponse(404, { detail: `Not found: ${method} ${path}` });
};
