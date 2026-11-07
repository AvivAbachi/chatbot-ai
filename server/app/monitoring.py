import json
import logging
import threading
import time
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)
        return json.dumps(log_obj)


def get_logger(name: str = "chatbot-api") -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


class MetricsCollector:
    def __init__(self):
        self._lock = threading.Lock()
        self._requests_total = 0
        self._errors_total = 0
        self._latency_sum = 0.0
        self._latency_count = 0
        self._tokens_input = 0
        self._tokens_output = 0

    def record_request(
        self,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        error: bool = False,
    ):
        with self._lock:
            self._requests_total += 1
            self._latency_sum += latency_ms
            self._latency_count += 1
            self._tokens_input += input_tokens
            self._tokens_output += output_tokens

            if error:
                self._errors_total += 1

    @property
    def summary(self) -> dict:
        avg_latency = (
            self._latency_sum / self._latency_count if self._latency_count > 0 else 0.0
        )
        error_rate = (
            self._errors_total / self._requests_total
            if self._requests_total > 0
            else 0.0
        )

        return {
            "total_requests": self._requests_total,
            "total_errors": self._errors_total,
            "error_rate": f"{error_rate:.2%}",
            "avg_latency_ms": round(avg_latency, 2),
            "total_input_tokens": self._tokens_input,
            "total_output_tokens": self._tokens_output,
        }


class RequestTimer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self.start) * 1000
