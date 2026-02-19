import logging

from src.use_cases.get_health import GetHealthUseCase


def test_get_health_use_case_returns_ok_status() -> None:
    use_case = GetHealthUseCase(service_name="datamaq-communications-api", logger=logging.getLogger("test"))

    result = use_case.execute()

    assert result.service == "datamaq-communications-api"
    assert result.status == "ok"
