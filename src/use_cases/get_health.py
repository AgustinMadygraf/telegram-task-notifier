from dataclasses import dataclass
import logging


@dataclass(frozen=True)
class HealthStatus:
    service: str
    status: str


class GetHealthUseCase:
    def __init__(self, service_name: str, logger: logging.Logger) -> None:
        self._service_name = service_name.strip() or "unknown-service"
        self._logger = logger

    def execute(self) -> HealthStatus:
        self._logger.debug("Health check requested for service=%s", self._service_name)
        return HealthStatus(service=self._service_name, status="ok")
