"""Apply the schema to the E2E stack's throwaway database, once (compose.yaml).

Never pointed at a shared runtime: the URL is the compose file's own `db`.
"""

from __future__ import annotations

import os
import sys

from alembic import command
from alembic.config import Config

url = os.environ.get("POSTGRES_RUNTIME_URL", "")
if "@db:5432/agent_e2e" not in url:
    sys.exit("refusing: this migrates only the E2E stack's throwaway database")
config = Config("alembic.ini")
config.set_main_option("sqlalchemy.url", url)
command.upgrade(config, "head")
print("schema at head on the throwaway database")
