const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

// Configuration & Secrets
const SUPABASE_URL = (process.env.SUPABASE_URL || 'https://rxbjexoxyfownnwxzbjn.supabase.co').replace(/\/$/, '');
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
  // Route: POST /api/scrape/search
  // -------------------------------------------------------------
  if (path === '/api/scrape/search' && method === 'POST') {
    const q = (body.query || '').trim();
    const limit = parseInt(body.limit || '40', 10);

    let supabaseQuery = `${SUPABASE_URL}/rest/v1/flexnet_vehicles?select=*&order=id.desc&limit=${limit}`;
    if (q) {
      supabaseQuery += `&or=(title.ilike.*${encodeURIComponent(q)}*,tagline.ilike.*${encodeURIComponent(q)}*,model.ilike.*${encodeURIComponent(q)}*)`;
    }

    try {
      const res = await fetch(supabaseQuery, { headers: getSupabaseHeaders() });
      let vehicles = await res.json();
      if (!Array.isArray(vehicles)) vehicles = [];

      return jsonResponse(200, {
        success: true,
        count: vehicles.length,
        total_found: vehicles.length,
        vehicles,
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
    try {
      let q = `${SUPABASE_URL}/rest/v1/flexnet_vehicles?select=*&limit=1`;
      if (kanri) q += `&kanri_code=eq.${encodeURIComponent(kanri)}`;
      else if (url) q += `&detail_url=eq.${encodeURIComponent(url)}`;

      const res = await fetch(q, { headers: getSupabaseHeaders() });
      const cars = await res.json();
      if (cars && cars.length > 0) {
        return jsonResponse(200, { success: true, vehicle: cars[0] });
      }
      return jsonResponse(404, { detail: 'Vehicle not found in database.' });
    } catch (err) {
      return jsonResponse(500, { detail: err.message });
    }
  }

  // Default Fallback
  return jsonResponse(404, { detail: `Not found: ${method} ${path}` });
};
