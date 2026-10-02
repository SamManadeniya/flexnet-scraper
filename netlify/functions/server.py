import sys
from pathlib import Path

# Add possible root directories to sys.path for Netlify/Lambda
current_file = Path(__file__).resolve()
candidates = [
    current_file.parent.parent.parent,  # local dev: <root>/netlify/functions/server.py
    current_file.parent.parent,         # netlify lambda: /var/task/netlify/functions -> /var/task
    current_file.parent,                # lambda root: /var/task
    Path.cwd()
]
for p in candidates:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from api import app
from mangum import Mangum

_mangum_handler = Mangum(app)

def handler(event, context):
    """Resilient AWS Lambda / Netlify Serverless handler for FastAPI."""
    if isinstance(event, dict) and "path" in event:
        # Strip Netlify function prefix if redirected
        prefix = "/.netlify/functions/server"
        if event["path"].startswith(prefix):
            event["path"] = event["path"][len(prefix):] or "/"
            if "requestContext" in event and isinstance(event["requestContext"], dict) and "path" in event["requestContext"]:
                event["requestContext"]["path"] = event["path"]
    return _mangum_handler(event, context)
