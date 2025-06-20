from prometheus_client import start_http_server, Gauge, Counter, Summary
from loguru import logger
import os
import psutil
import threading
import time
from typing import Dict

from src.services.monitoring_service import MonitoringService


class MetricsService:
    """Expose Prometheus metrics for the bot"""

    def __init__(self):
        self.games_by_status = Gauge(
            "pryton_games_status_total",
            "Number of games by status",
            ["status"],
        )
        self.scheduler_jobs = Gauge(
            "pryton_scheduler_jobs_total",
            "Number of scheduled jobs",
        )
        self.errors = Counter("pryton_errors_total", "Total bot errors")
        self.request_latency = Summary(
            "pryton_request_latency_seconds",
            "Time spent processing updates",
        )
        self.request_count = Counter(
            "pryton_request_count_total",
            "Total number of requests",
            ["update_type"],
        )
        self.cpu_usage = Gauge(
            "pryton_cpu_usage_percent",
            "CPU usage percentage",
        )
        self.memory_usage = Gauge(
            "pryton_memory_usage_bytes",
            "Memory usage in bytes",
        )
        self._stop_event = threading.Event()
        self._system_thread = None
        self.port = int(os.getenv("METRICS_PORT", "8000"))

    def start(self) -> None:
        """Start metrics HTTP server"""
        start_http_server(self.port)
        logger.info(f"Metrics server started on port {self.port}")
        self.update_games_metrics()
        self._system_thread = threading.Thread(
            target=self._system_metrics_loop, daemon=True
        )
        self._system_thread.start()

    def update_games_metrics(self) -> None:
        """Update gauges for games"""
        stats: Dict[str, Dict[str, int]] = MonitoringService.get_active_games_stats()
        for status, count in stats.get("games_by_status", {}).items():
            self.games_by_status.labels(status=status).set(count)

    def update_scheduler_jobs(self, count: int) -> None:
        self.scheduler_jobs.set(count)

    def record_error(self) -> None:
        self.errors.inc()

    def update_system_metrics(self) -> None:
        self.cpu_usage.set(psutil.cpu_percent())
        self.memory_usage.set(psutil.virtual_memory().used)

    def _system_metrics_loop(self) -> None:
        while not self._stop_event.is_set():
            self.update_system_metrics()
            time.sleep(5)

    def stop(self) -> None:
        self._stop_event.set()
    def record_request(self, update_type: str) -> None:
        try:
            self.request_count.labels(update_type=update_type).inc()
        except Exception as e:
            logger.error(f"Не удалось записать request_count: {e}")

    def observe_latency(self, duration: float) -> None:
        try:
            # у вас нет лейблов на Summary, поэтому просто наблюдаем
            self.request_latency.observe(duration)
        except Exception as e:
            logger.error(f"Не удалось записать latency: {e}")

metrics_service = MetricsService()
