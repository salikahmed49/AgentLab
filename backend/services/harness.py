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
    """Run one pipeline step and only retry transient HTTP 429/5xx failures."""
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
            logger.info("stage %s took %.2f s", step_name, seconds)
            if callback:
                callback(step_name, "completed")
            return result

        except Exception as error:
            seconds = time.perf_counter() - started
            logger.warning(
                "step=%s attempt=%d status=failed seconds=%.2f error=%s",
                step_name, attempt, seconds, type(error).__name__,
            )
            logger.info("stage %s took %.2f s before failure", step_name, seconds)

            response = getattr(error, "response", None)
            status = (
                getattr(error, "status_code", None)
                or getattr(error, "code", None)
                or getattr(response, "status_code", None)
            )
            try:
                status = int(status)
            except (TypeError, ValueError):
                status = None
            retryable = status == 429 or (
                status is not None and 500 <= status <= 599
            )
            is_last_attempt = attempt == total_attempts
            if is_last_attempt or not retryable:
                if callback:
                    callback(step_name, "failed")
                raise StepFailedError(step_name, error) from error

            time.sleep(min(wait_seconds * (2 ** (attempt - 1)), 1.0))
