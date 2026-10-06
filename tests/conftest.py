from collections import defaultdict, deque

import pytest

from backend.main import app


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    app.state.rate_limit_window_seconds = 60
    app.state.rate_limit_max_requests = 30
    app.state.rate_limit_buckets = defaultdict(deque)
    yield
    app.state.rate_limit_window_seconds = 60
    app.state.rate_limit_max_requests = 30
    app.state.rate_limit_buckets = defaultdict(deque)
