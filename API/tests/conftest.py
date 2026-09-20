import os

# helpers/time_functions.py reads these at import time (module-level), so
# they must be set before any test module pulls in app code.
os.environ.setdefault("TIMEZONE", "UTC")
os.environ.setdefault("TRACK_COLOUR", "#e5d486")
os.environ.setdefault("EVENT_DETAIL", "main")

import pytest
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend


@pytest.fixture(autouse=True)
def _fresh_cache():
    # Endpoints under test use fixed cache keys (e.g. "f1:next_race"). A new
    # InMemoryBackend() looks like a fresh store but isn't - fastapi_cache's
    # InMemoryBackend keeps its `_store` dict as a CLASS attribute, shared by
    # every instance, so re-init() alone would leak one test's cached
    # response into the next. Clear it explicitly.
    InMemoryBackend._store.clear()
    FastAPICache.init(InMemoryBackend())
    yield
