import logging
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from src.entities.contact import ContactMessage, EmailAddress
from src.infrastructure.fastapi.request_metadata import get_client_ip, get_x_forwarded_for
from src.infrastructure.fastapi.schemas import AcceptedResponseModel, ContactRequestModel, ErrorResponseModel
from src.shared.log_safety import mask_email, mask_identifier
from src.use_cases.errors import HoneypotTriggeredError, RateLimitExceededError
from src.use_cases.send_mail import SendMailUseCase
from src.use_cases.submit_contact import SubmitContactUseCase


def create_contact_router(
    submit_contact_use_case: SubmitContactUseCase,
    send_mail_use_case: SendMailUseCase,
    logger: logging.Logger,
    debug_observability: bool = False,
    mask_sensitive_ids: bool = True,
) -> APIRouter:
    router = APIRouter()

    def _safe_request_id(request_id: str) -> str:
        if not mask_sensitive_ids:
            return request_id
        return mask_identifier(request_id, prefix=3, suffix=3)

    def _safe_client_ip(client_ip: str) -> str:
        if not mask_sensitive_ids:
            return client_ip
        return mask_identifier(client_ip, prefix=3, suffix=2)

    def _model_dump(payload: ContactRequestModel) -> dict[str, object]:
        if hasattr(payload, "model_dump"):
            return payload.model_dump()  # type: ignore[no-any-return]
        return payload.dict()  # type: ignore[no-any-return]

    def _payload_signals(payload: ContactRequestModel) -> dict[str, object]:
        raw = _model_dump(payload)
        serialized = json.dumps(raw, ensure_ascii=False, default=str)
        attribution = raw.get("attribution") if isinstance(raw.get("attribution"), dict) else {}
        return {
            "payload_size_bytes": len(serialized.encode("utf-8")),
            "name_length": len(str(raw.get("name", ""))),
            "message_length": len(str(raw.get("message", ""))),
            "meta_keys": sorted(raw.get("meta", {}).keys()) if isinstance(raw.get("meta"), dict) else [],
            "attribution_keys": sorted(attribution.keys()),
            "has_honeypot_value": bool(str(attribution.get("website", "")).strip()) if attribution else False,
            "email_masked": mask_email(str(raw.get("email", ""))),
        }

    @router.post(
        "/contact",
        status_code=202,
        response_model=AcceptedResponseModel,
        responses={
            400: {"model": ErrorResponseModel},
            422: {"model": ErrorResponseModel},
            429: {"model": ErrorResponseModel},
            500: {"model": ErrorResponseModel},
        },
    )
    async def contact(
        payload: ContactRequestModel,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict[str, str]:
        return _handle_contact_like_request(
            payload=payload,
            request=request,
            background_tasks=background_tasks,
            endpoint_key="contact",
            success_message="Contact request accepted for processing",
        )

    @router.post(
        "/mail",
        status_code=202,
        response_model=AcceptedResponseModel,
        responses={
            400: {"model": ErrorResponseModel},
            422: {"model": ErrorResponseModel},
            429: {"model": ErrorResponseModel},
            500: {"model": ErrorResponseModel},
        },
    )
    async def mail(
        payload: ContactRequestModel,
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict[str, str]:
        return _handle_contact_like_request(
            payload=payload,
            request=request,
            background_tasks=background_tasks,
            endpoint_key="mail",
            success_message="Mail request accepted for processing",
        )

    def _handle_contact_like_request(
        payload: ContactRequestModel,
        request: Request,
        background_tasks: BackgroundTasks,
        endpoint_key: str,
        success_message: str,
    ) -> dict[str, str]:
        try:
            if debug_observability:
                logger.debug(
                    "contact_payload_signals",
                    extra={
                        "event": "contact_payload_signals",
                        "request_id": _safe_request_id(getattr(request.state, "request_id", "")),
                        "endpoint": endpoint_key,
                        **_payload_signals(payload),
                    },
                )
            contact_message = ContactMessage(
                name=payload.name,
                email=EmailAddress(payload.email),
                message=payload.message,
                meta=payload.meta,
                attribution=payload.attribution,
            )
            client_host = get_client_ip(request)
            result = submit_contact_use_case.submit(
                contact_message=contact_message,
                client_identifier=client_host,
                endpoint_key=endpoint_key,
                success_message=success_message,
            )
            background_tasks.add_task(
                send_mail_use_case.execute,
                contact_message,
                result.request_id,
            )
            logger.info(
                "contact_request_accepted",
                extra={
                    "event": "contact_request_accepted",
                    "request_id": _safe_request_id(result.request_id),
                    "endpoint": endpoint_key,
                    "client_ip_real": _safe_client_ip(client_host),
                    "x_forwarded_for": get_x_forwarded_for(request),
                },
            )
            return {
                "request_id": result.request_id,
                "status": result.status,
                "message": result.message,
            }
        except HoneypotTriggeredError as exc:
            logger.warning(
                "contact_honeypot_triggered",
                extra={
                    "event": "contact_honeypot_triggered",
                    "request_id": _safe_request_id(getattr(request.state, "request_id", "")),
                    "endpoint": endpoint_key,
                    "client_ip_real": _safe_client_ip(get_client_ip(request)),
                    "x_forwarded_for": get_x_forwarded_for(request),
                },
            )
            raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(exc)}) from exc
        except RateLimitExceededError as exc:
            logger.warning(
                "contact_rate_limited",
                extra={
                    "event": "contact_rate_limited",
                    "request_id": _safe_request_id(getattr(request.state, "request_id", "")),
                    "endpoint": endpoint_key,
                    "client_ip_real": _safe_client_ip(get_client_ip(request)),
                    "x_forwarded_for": get_x_forwarded_for(request),
                },
            )
            raise HTTPException(
                status_code=429,
                detail={"code": "RATE_LIMIT_EXCEEDED", "message": str(exc)},
            ) from exc
        except ValueError as exc:
            logger.warning(
                "contact_validation_error",
                extra={
                    "event": "contact_validation_error",
                    "request_id": _safe_request_id(getattr(request.state, "request_id", "")),
                    "endpoint": endpoint_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": str(exc)}) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "contact_unexpected_error",
                extra={
                    "event": "contact_unexpected_error",
                    "request_id": _safe_request_id(getattr(request.state, "request_id", "")),
                    "endpoint": endpoint_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise HTTPException(
                status_code=500,
                detail={"code": "INTERNAL_ERROR", "message": "Unexpected internal error"},
            ) from exc

    return router
