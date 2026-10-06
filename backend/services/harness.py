import logging
import time
from typing import Callable


logger = logging.getLogger("agentlab")
CURRENT_PROGRESS_CALLBACK: Callable[[str, str], None] | None = None


def set_progress_callback(callback: Callable[[str, str], None] | None):
    global CURRENT_PROGRESS_CALLBACK
    CURRENT_PROGRESS_CALLBACK = callback


def get_progress_callback():
    return CURRENT_PROGRESS_CALLBACK


class StepFailedError(Exception):
    """Raised when a pipeline step still fails after all retries."""

    def __init__(self, step_name: str, original_error: Exception):
        self.step_name = step_name
        self.original_error = original_error
        super().__init__(f"Step '{step_name}' failed: {original_error}")


def run_step(
    step_name,
    function,
    retries: int = 2,
    wait_seconds: float = 1.0,
    on_step: Callable[[str, str], None] | None = None,
    on_result: Callable[[str, object], None] | None = None,
):
    """Run function(). Retry on failure. Log timing. Raise StepFailedError at the end."""
    callback = on_step if on_step is not None else CURRENT_PROGRESS_CALLBACK
    total_attempts = retries + 1

    if callback:
        callback(step_name, "processing")

    for attempt in range(1, total_attempts + 1):
        started = time.perf_counter()

        try:
            result = function()
            if on_result is not None:
                on_result(step_name, result)
            seconds = time.perf_counter() - started
            logger.info(
                "step=%s attempt=%d status=ok seconds=%.2f",
                step_name, attempt, seconds,
            )
            if callback:
                callback(step_name, "completed")
            return result

        except Exception as error:
            seconds = time.perf_counter() - started
            logger.warning(
                "step=%s attempt=%d status=failed seconds=%.2f error=%s",
                step_name, attempt, seconds, type(error).__name__,
            )

            # A missing API key will never fix itself, so do not retry it.
            is_last_attempt = attempt == total_attempts
            if is_last_attempt or isinstance(error, RuntimeError):
                if callback:
                    callback(step_name, "failed")
                raise StepFailedError(step_name, error) from error

            time.sleep(wait_seconds * attempt)
