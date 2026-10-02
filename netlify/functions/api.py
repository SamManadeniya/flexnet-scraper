import sys
from pathlib import Path

# Add project root directory to Python path for Netlify serverless execution
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from api import app
from mangum import Mangum

_mangum_handler = Mangum(app)

def handler(event, context):
    """Resilient AWS Lambda / Netlify Serverless handler for FastAPI."""
    if isinstance(event, dict) and "path" in event:
        # Strip /.netlify/functions/api prefix if redirected by Netlify
        prefix = "/.netlify/functions/api"
        if event["path"].startswith(prefix):
            event["path"] = event["path"][len(prefix):] or "/"
            if "requestContext" in event and isinstance(event["requestContext"], dict) and "path" in event["requestContext"]:
                event["requestContext"]["path"] = event["path"]
    return _mangum_handler(event, context)
