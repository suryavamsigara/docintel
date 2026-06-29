import os
import uuid
import libsql_client
from dotenv import load_dotenv

# Force load environment variables from the .env file
load_dotenv()

TURSO_DB_URL = os.getenv("TURSO_DATABASE_URL", "sqlite:///local.db")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

# Safety check: libsql-client prefers libsql:// or https://
if TURSO_DB_URL.startswith("wss://"):
    TURSO_DB_URL = TURSO_DB_URL.replace("wss://", "libsql://", 1)

# Hold the client globally, but don't initialize it yet
_client = None

def get_client():
    """Lazy-load the Turso client to ensure the asyncio event loop is running."""
    global _client
    if _client is None:
        if not TURSO_AUTH_TOKEN and "turso.io" in TURSO_DB_URL:
            print("WARNING: Connecting to a remote Turso DB but no AUTH TOKEN was found!")
            
        _client = libsql_client.create_client(url=TURSO_DB_URL, auth_token=TURSO_AUTH_TOKEN)
    return _client

async def init_db():
    client = get_client()
    await client.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    await client.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'processing',
            file_url TEXT,
            analysis_data TEXT, 
            content_hash TEXT,
            crm_status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    try:
        await client.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT")
        await client.execute("ALTER TABLE documents ADD COLUMN crm_status TEXT DEFAULT 'pending'")
    except:
        pass

def generate_id(prefix=""):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"