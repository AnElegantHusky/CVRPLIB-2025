from mimetypes import init
from test_one_run import init_db
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent

path = EXPERIMENT_DIR / "tmp" / "test.db"
init_db(path)