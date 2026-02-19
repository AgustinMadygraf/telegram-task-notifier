from src.interface_adapters.presenters.health_presenter import present_health
from src.use_cases.get_health import GetHealthUseCase


class HealthController:
    def __init__(self, get_health_use_case: GetHealthUseCase) -> None:
        self._get_health_use_case = get_health_use_case

    def handle_get_health(self) -> dict[str, str]:
        return present_health(self._get_health_use_case.execute())
