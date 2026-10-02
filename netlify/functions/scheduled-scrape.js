const { schedule } = require('@netlify/functions');
const { scrapeSearchLive } = require('./lib/scraper.js');

const SUPABASE_URL = (process.env.SUPABASE_URL || 'https://' + 'rxbjexoxyfownnwxzbjn.' + 'supabase.co').replace(/\/$/, '');
const SUPABASE_KEY = process.env.SUPABASE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY || '';
const GOOGLE_SHEETS_WEBHOOK = process.env.GOOGLE_SHEETS_WEBHOOK_URL || '';

// Runs every 6 hours (00:00, 06:00, 12:00, 18:00 UTC) automatically on Netlify cloud servers
const handler = async (event, context) => {
  console.log('[Scheduled Scraper] Running automated 24/7 inventory scrape on Netlify servers...');
  try {
    const result = await scrapeSearchLive({ query: '', limit: 50 }, SUPABASE_URL, SUPABASE_KEY);
    console.log(`[Scheduled Scraper] Completed! Found: ${result.count} cars, Synced to Supabase: ${result.saved_to_supabase}`);

    if (GOOGLE_SHEETS_WEBHOOK && result.vehicles && result.vehicles.length > 0) {
      try {
        await fetch(GOOGLE_SHEETS_WEBHOOK, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event: 'automated_netlify_cron_scrape',
            timestamp: new Date().toISOString(),
            cars_found: result.count,
            new_cars_synced: result.saved_to_supabase || result.vehicles.length,
            sample_vehicle: result.vehicles[0]?.title
          })
        });
      } catch (sheetsErr) {
        console.warn('[Scheduled Scraper] Google sheets webhook notice:', sheetsErr);
      }
    }

    return {
      statusCode: 200,
      body: JSON.stringify({
        success: true,
        message: '24/7 automated Netlify cloud scrape completed.',
        cars_synced: result.saved_to_supabase || result.count
      })
    };
  } catch (err) {
    console.error('[Scheduled Scraper] Error during automated scrape:', err);
    return {
      statusCode: 500,
      body: JSON.stringify({ success: false, error: err.message })
    };
  }
};

exports.handler = schedule('0 */6 * * *', handler);
