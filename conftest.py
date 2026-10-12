import os
import tempfile

# Configure before the app is imported: a throwaway SQLite DB and the in-process mock CBK.
_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "root@finoworks.com")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "Root-Pass-2026")
os.environ.setdefault("CBK_TOKEN_URL", "http://mock-cbk/oauth2/v1/token")
os.environ.setdefault("CBK_UAT_BASE", "http://mock-cbk/preprod")
os.environ.setdefault("JWT_SECRET", "test-secret")
