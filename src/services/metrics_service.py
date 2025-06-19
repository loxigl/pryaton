from prometheus_client import start_http_server, Gauge, Counter
from loguru import logger
import os
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
        self.port = int(os.getenv("METRICS_PORT", "8000"))

    def start(self) -> None:
        """Start metrics HTTP server"""
        start_http_server(self.port)
        logger.info(f"Metrics server started on port {self.port}")
        self.update_games_metrics()

    def update_games_metrics(self) -> None:
        """Update gauges for games"""
        stats: Dict[str, Dict[str, int]] = MonitoringService.get_active_games_stats()
        for status, count in stats.get("games_by_status", {}).items():
            self.games_by_status.labels(status=status).set(count)

    def update_scheduler_jobs(self, count: int) -> None:
        self.scheduler_jobs.set(count)

    def record_error(self) -> None:
        self.errors.inc()


metrics_service = MetricsService()
