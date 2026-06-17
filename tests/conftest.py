import os
import sys

import pytest
import storage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def _reset_storage_transaction():
    yield
    storage.rollback_transaction()
    try:
        import simulation.event_logger as event_logger
        event_logger._event_buffer.clear()
    except Exception:
        pass
