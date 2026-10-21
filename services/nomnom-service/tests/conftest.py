"""Test configuration: isolate each test run's SQLite DB from the dev/seed database.

Must set the env var before any test module imports ``nomnom_service.db`` (which reads
it at import time), so this happens here at conftest collection time.
"""

import os
import tempfile

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ.setdefault("NOMNOM_SERVICE_DB", _tmp_db.name)
