import sys

from ..db import init_db
from . import run

init_db()
added = run(demo="--no-demo" not in sys.argv)
print("norms and types synced" + ("; demo desks, employees and shifts added" if added else ""))
