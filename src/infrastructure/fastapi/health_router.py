from fastapi import APIRouter

from src.interface_adapters.controllers.health_controller import HealthController
from src.infrastructure.fastapi.schemas import HealthResponseModel


def create_health_router(health_controller: HealthController) -> APIRouter:
    router = APIRouter()

    @router.get("/", response_model=HealthResponseModel)
    async def root() -> dict[str, str]:
        return health_controller.handle_get_health()

    @router.get("/health", response_model=HealthResponseModel)
    async def health() -> dict[str, str]:
        return health_controller.handle_get_health()

    return router
