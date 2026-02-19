from src.use_cases.get_health import HealthStatus


def present_health(status: HealthStatus) -> dict[str, str]:
    return {
        "service": status.service,
        "status": status.status,
    }
