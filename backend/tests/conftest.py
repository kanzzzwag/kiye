import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_tmp = tempfile.mkdtemp(prefix="forte-test-")
os.environ.setdefault("API_KEY", "test-key-0123456789abcdef")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["QUEUE_MODE"] = "thread"
os.environ["STORAGE_DIR"] = os.path.join(_tmp, "storage")
os.environ["SEED_DEMO"] = "true"
os.environ["RATE_LIMIT_PER_MIN"] = "1000"
os.chdir(_tmp)  # sqlite helper creates ./data relative to cwd
