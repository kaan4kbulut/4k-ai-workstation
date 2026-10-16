import os
import tempfile
from pathlib import Path

# Testler kullanıcının gerçek ~/.4k dizinine dokunmasın.
os.environ["FOURK_HOME"] = tempfile.mkdtemp(prefix="4k-test-")

import pytest

from workstation.db import Database


@pytest.fixture
def db(tmp_path: Path):
    d = Database(tmp_path / "state.db")
    yield d
    d.close()
