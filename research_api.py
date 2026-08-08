"""Shared FastAPI router for anonymous research session/event logging."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)

from core.research_storage import (
    ALLOWED_EVENT_TYPES,
    INTENTIONAL_BREAK_CLIENT_EVENT_TYPES,
    INTENTIONAL_BREAK_INTENTIONS,
    INTENTIONAL_BREAK_MOOD_VALUES,
    INTENTIONAL_BREAK_OVERRIDE_REASONS,
    INTENTIONAL_BREAK_VIDEO_COUNTS,
    INTENTIONAL_BREAK_WORTHWHILE_VALUES,
    IntentionalBreakStorageError,
    ResearchConflictError,
    ResearchNotFoundError,
    append_intentional_break_client_events,
    authenticate_participant,
    cancel_intentional_break_plan,
    confirm_intentional_break_override,
    complete_session,
    create_intentional_break_plan,
    create_participant,
    finish_intentional_break_early,
    get_current_intentional_break_journey,
    get_feed_session,
    get_session,
    insert_event_batch,
    read_intentional_break_items,
    reconcile_intentional_break_cooldown,
    record_feed_items,
    start_intentional_break_override,
    start_intentional_break_session,
    start_session,
    submit_intentional_break_checkout,
)
from core.ranking.research_policies import build_research_feed_payload


POST_EVENT_TYPES = frozenset(event for event in ALLOWED_EVENT_TYPES if event.startswith("post_"))
CLIENT_BATCH_EVENT_TYPES = ALLOWED_EVENT_TYPES - {"session_started", "session_completed"}
CONTENT_CATEGORIES = frozenset({
    "healthy", "positive", "regular", "perspective", "reduced", "blocked", "unknown",
})
ALLOWED_METADATA_KEYS = frozenset({
    "position",
    "visibility_ratio",
    "visible_ms",
    "reason_code",
    "threshold_min",
    "break_min",
    "interaction_source",
    "impression_event_id",
    "source_type",
    "feed_request_id",
    "feed_position",
    "feed_policy_version",
    "selection_bucket",
    "selection_reason",
})
MAX_METADATA_BYTES = 2048
INTENTIONAL_BREAK_CONTRACT_VERSION = "intentional-break-v1"
INTENTIONAL_BREAK_POLICY_VERSION = "balanced-v1"
INTENTIONAL_BREAK_API_PREFIX = "/intentional-break/v1"

logger = logging.getLogger(__name__)


def _aware_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value


class StartSessionRequest(BaseModel):
    application_version: str = Field(min_length=1, max_length=120)
    client_timestamp: datetime

    _timestamp_timezone = field_validator("client_timestamp")(_aware_timestamp)


class ResearchEventRequest(BaseModel):
    event_id: UUID
    sequence_number: int = Field(ge=1)
    event_type: str
    post_id: str | None = Field(default=None, min_length=1, max_length=200)
    content_category: str | None = None
    client_timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    _timestamp_timezone = field_validator("client_timestamp")(_aware_timestamp)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        if value not in CLIENT_BATCH_EVENT_TYPES:
            raise ValueError(f"event_type must be one of {sorted(CLIENT_BATCH_EVENT_TYPES)}")
        return value

    @field_validator("content_category")
    @classmethod
    def validate_content_category(cls, value: str | None) -> str | None:
        if value is not None and value not in CONTENT_CATEGORIES:
            raise ValueError(f"content_category must be one of {sorted(CONTENT_CATEGORIES)}")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        unsupported = set(value) - ALLOWED_METADATA_KEYS
        if unsupported:
            raise ValueError(f"unsupported metadata keys: {sorted(unsupported)}")
        if len(json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")) > MAX_METADATA_BYTES:
            raise ValueError("metadata is too large")
        for item in value.values():
            if isinstance(item, (dict, list)):
                raise ValueError("metadata values must be scalar")
        return value

    @model_validator(mode="after")
    def validate_post_fields(self):
        if self.event_type in POST_EVENT_TYPES and not self.post_id:
            raise ValueError("post_id is required for post events")
        return self


class EventBatchRequest(BaseModel):
    session_id: UUID
    events: list[ResearchEventRequest] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_batch_fields(self):
        ids = [event.event_id for event in self.events]
        sequences = [event.sequence_number for event in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("event_id values must be unique within a batch")
        if len(sequences) != len(set(sequences)):
            raise ValueError("sequence_number values must be unique within a batch")
        return self


class CompleteSessionRequest(BaseModel):
    event_id: UUID
    sequence_number: int = Field(ge=1)
    client_timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    _timestamp_timezone = field_validator("client_timestamp")(_aware_timestamp)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value:
            raise ValueError("session completion metadata is not collected in this milestone")
        return value


class _IntentionalBreakRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntentionalBreakPlanRequest(_IntentionalBreakRequest):
    intention: str
    planned_video_count: StrictInt
    selected_cooldown_seconds: StrictInt
    idempotency_key: UUID
    previous_session_id: UUID | None = None
    participant_notice_version: str
    participant_notice_acknowledged: StrictBool

    @field_validator("intention")
    @classmethod
    def validate_intention(cls, value: str) -> str:
        if value not in INTENTIONAL_BREAK_INTENTIONS:
            raise ValueError("unsupported intention")
        return value

    @field_validator("planned_video_count")
    @classmethod
    def validate_video_count(cls, value: int) -> int:
        if isinstance(value, bool) or value not in INTENTIONAL_BREAK_VIDEO_COUNTS:
            raise ValueError("planned_video_count must be 5, 10, 20, or 40")
        return value

    @field_validator("selected_cooldown_seconds")
    @classmethod
    def validate_cooldown(cls, value: int) -> int:
        if (
            isinstance(value, bool)
            or value < 300
            or value > 7200
            or value % 300
        ):
            raise ValueError("selected cooldown must be a 5-minute increment from 5 to 120 minutes")
        return value

    @field_validator("participant_notice_version")
    @classmethod
    def validate_notice_version(cls, value: str) -> str:
        if value != INTENTIONAL_BREAK_CONTRACT_VERSION:
            raise ValueError("participant notice version is not supported")
        return value

    @field_validator("participant_notice_acknowledged")
    @classmethod
    def validate_notice_acknowledgement(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("participant notice acknowledgement is required")
        return value


class IntentionalBreakIdempotencyRequest(_IntentionalBreakRequest):
    idempotency_key: UUID


class IntentionalBreakFinishEarlyRequest(IntentionalBreakIdempotencyRequest):
    current_position: StrictInt | None = None


class IntentionalBreakClientEventRequest(_IntentionalBreakRequest):
    client_event_id: UUID
    client_sequence_number: StrictInt | None = Field(default=None, ge=0)
    event_type: str
    post_id: str | None = Field(default=None, min_length=1, max_length=200)
    client_timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    _timestamp_timezone = field_validator("client_timestamp")(_aware_timestamp)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        if value not in INTENTIONAL_BREAK_CLIENT_EVENT_TYPES:
            raise ValueError("unsupported client event type")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        unsupported = set(value) - ALLOWED_METADATA_KEYS
        if unsupported:
            raise ValueError(f"unsupported metadata keys: {sorted(unsupported)}")
        encoded = json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")
        if len(encoded) > MAX_METADATA_BYTES:
            raise ValueError("metadata is too large")
        for item in value.values():
            if isinstance(item, (dict, list)):
                raise ValueError("metadata values must be scalar")
        return value

    @model_validator(mode="after")
    def validate_post_id(self):
        if self.event_type.startswith("post_") and not self.post_id:
            raise ValueError("post_id is required for post events")
        return self


class IntentionalBreakEventBatchRequest(_IntentionalBreakRequest):
    events: list[IntentionalBreakClientEventRequest] = Field(min_length=1, max_length=100)


class IntentionalBreakCheckoutRequest(IntentionalBreakIdempotencyRequest):
    worthwhile: str
    perceived_control: StrictInt | Literal["prefer_not_to_answer"]
    mood: str
    checkout_version: str

    @field_validator("worthwhile")
    @classmethod
    def validate_worthwhile(cls, value: str) -> str:
        if value not in INTENTIONAL_BREAK_WORTHWHILE_VALUES:
            raise ValueError("unsupported worthwhile answer")
        return value

    @field_validator("perceived_control")
    @classmethod
    def validate_perceived_control(cls, value):
        if value != "prefer_not_to_answer" and value not in {1, 2, 3, 4, 5}:
            raise ValueError("unsupported perceived-control answer")
        return value

    @field_validator("mood")
    @classmethod
    def validate_mood(cls, value: str) -> str:
        if value not in INTENTIONAL_BREAK_MOOD_VALUES:
            raise ValueError("unsupported mood answer")
        return value

    @field_validator("checkout_version")
    @classmethod
    def validate_checkout_version(cls, value: str) -> str:
        if value != INTENTIONAL_BREAK_CONTRACT_VERSION:
            raise ValueError("checkout version is not supported")
        return value


class IntentionalBreakOverrideConfirmRequest(IntentionalBreakIdempotencyRequest):
    reason_code: str

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str) -> str:
        if value not in INTENTIONAL_BREAK_OVERRIDE_REASONS:
            raise ValueError("unsupported override reason")
        return value


def _bearer_token(authorization: str | None) -> str:
    scheme, _, token = str(authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="A participant bearer token is required.")
    return token.strip()


class _IntentionalBreakAPIError(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict | None = None,
        flatten_details: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
        self.flatten_details = flatten_details


def _intentional_break_model(model_type, payload):
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise _IntentionalBreakAPIError(
            400,
            "invalid_request",
            "The request does not match the Intentional Break Loop contract.",
            details={
                "validation_errors": exc.errors(
                    include_url=False,
                    include_context=False,
                    include_input=False,
                )
            },
        ) from exc


def _intentional_break_uuid(value: str, *, field_name: str = "session_id") -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise _IntentionalBreakAPIError(
            400, "invalid_request", f"{field_name} must be a valid UUID."
        ) from exc


def _intentional_break_supported_actions(snapshot: dict) -> list[str]:
    state = snapshot.get("journey_state")
    if state == "planned":
        return ["start", "cancel"]
    if state == "active":
        return ["read_items", "append_events", "finish_early"]
    if state == "checkout":
        return ["submit_checkout"]
    if state == "cooldown":
        actions = ["read_cooldown"]
        actions.append(
            "confirm_override" if snapshot.get("override_started_at") else "start_override"
        )
        return actions
    return []


def _serialize_intentional_break_journey(snapshot: dict | None) -> dict | None:
    if snapshot is None:
        return None
    public_fields = (
        "session_id",
        "journey_version",
        "journey_state",
        "intention",
        "planned_video_count",
        "estimated_duration_seconds",
        "suggested_cooldown_seconds",
        "selected_cooldown_seconds",
        "highest_reached_position",
        "finish_reason",
        "checkout_status",
        "checkout_submitted",
        "checkout_version",
        "plan_version",
        "plan_created_at",
        "session_started_at",
        "boundary_reached_at",
        "checkout_entered_at",
        "cooldown_started_at",
        "cooldown_ends_at",
        "cooldown_outcome",
        "cooldown_completed_at",
        "override_started_at",
        "override_available_at",
        "override_reason",
        "previous_session_id",
        "completed_at",
        "cancelled_at",
        "feed_condition",
        "feed_policy_version",
    )
    result = {field: snapshot.get(field) for field in public_fields}
    result["remaining_seconds"] = snapshot.get("cooldown_remaining_seconds")
    result["supported_actions"] = _intentional_break_supported_actions(snapshot)
    return result


def _serialize_intentional_break_item(item: dict) -> dict:
    return {
        "post_id": item["post_id"],
        "session_position": item["session_position"],
        "content_category": item["content_category"],
        "feed_policy_version": item["feed_policy_version"],
        "selection_bucket": item["selection_bucket"],
        "selection_reason": item["selection_reason"],
        "first_issued_at": item["first_issued_at"],
    }


def _private_intentional_break_seed(
    *, participant_id: str, access_token: str, plan_idempotency_key: str
) -> str:
    configured_secret = (
        os.getenv("INTENTIONAL_BREAK_PLAN_SEED_SECRET")
        or os.getenv("CHRYSALIS_RESEARCH_SEED_SECRET")
        or os.getenv("SECRET_KEY")
    )
    if configured_secret:
        key = configured_secret.encode("utf-8")
    else:
        token_hash = hashlib.sha256(access_token.encode("utf-8")).digest()
        key = hashlib.sha256(
            b"daybreak:intentional-break:v1:selection|" + token_hash
        ).digest()
    material = f"{participant_id}|{plan_idempotency_key}|balanced-v1".encode("utf-8")
    return hmac.new(key, material, hashlib.sha256).hexdigest()


def _intentional_break_reserved_item(item: dict, *, position: int) -> dict:
    post_id = str(item.get("post_id") or "")
    source_type = str(item.get("source_type") or "feed_videos")
    source_reference = str(
        item.get("source_query")
        or item.get("youtube_id")
        or item.get("video_id")
        or post_id
    )
    return {
        "post_id": post_id,
        "content_category": item.get("content_category") or "unknown",
        "source_type": source_type,
        "source_reference": source_reference,
        "feed_policy_version": INTENTIONAL_BREAK_POLICY_VERSION,
        "selection_bucket": item["selection_bucket"],
        "selection_reason": item["selection_reason"],
        "ranking_snapshot": {
            "policy_version": INTENTIONAL_BREAK_POLICY_VERSION,
            "policy_position": int(item.get("feed_position", position - 1)),
            "selection_bucket": item["selection_bucket"],
            "selection_reason": item["selection_reason"],
        },
        "provenance_metadata": {
            "source_type": source_type,
            "source_reference": source_reference,
            "inventory_table": "feed_videos",
        },
    }


def _intentional_break_plan_summary(items: list[dict]) -> dict:
    return {
        "reserved_count": len(items),
        "ordered_positions": list(range(1, len(items) + 1)),
        "category_counts": {
            category: sum(
                1 for item in items if (item.get("content_category") or "unknown") == category
            )
            for category in sorted({
                item.get("content_category") or "unknown" for item in items
            })
        },
    }


def _storage_failure_is_retryable(exc: Exception) -> bool:
    cause = exc
    while cause is not None:
        if isinstance(cause, sqlite3.OperationalError):
            message = str(cause).lower()
            if "locked" in message or "busy" in message:
                return True
        pgcode = getattr(cause, "pgcode", None)
        if pgcode in {"40001", "40P01", "55P03", "57014"}:
            return True
        if (
            cause.__class__.__name__ == "OperationalError"
            and cause.__class__.__module__.startswith(("psycopg", "psycopg2"))
        ):
            return True
        cause = cause.__cause__
    return False


def _intentional_break_storage_error(exc: IntentionalBreakStorageError, now: datetime):
    if _storage_failure_is_retryable(exc):
        return _IntentionalBreakAPIError(
            503,
            "storage_temporarily_unavailable",
            "The research store is temporarily unavailable.",
            retryable=True,
        )
    status_by_code = {
        "participant_not_found": 401,
        "participant_inactive": 403,
        "session_not_found": 404,
        "session_not_owned": 404,
        "invalid_plan": 400,
        "event_not_allowed": 400,
        "existing_nonterminal_session": 409,
        "invalid_transition": 409,
        "invalid_reserved_batch": 409,
        "event_provenance_invalid": 409,
        "checkout_invalid": 409,
        "cooldown_not_ready": 409,
        "override_not_started": 409,
        "override_pause_active": 409,
        "idempotency_conflict": 409,
    }
    details = dict(exc.details)
    if "journey" in details:
        details["journey"] = _serialize_intentional_break_journey(details["journey"])
    flatten_details = exc.code == "override_pause_active"
    if exc.code == "override_pause_active" and details.get("override_available_at"):
        available = datetime.fromisoformat(
            str(details["override_available_at"]).replace("Z", "+00:00")
        )
        details["remaining_pause_seconds"] = max(
            0, math.ceil((available - now).total_seconds())
        )
    public_code = "session_not_found" if exc.code == "session_not_owned" else exc.code
    public_message = "Session not found." if exc.code == "session_not_owned" else str(exc)
    status_code = status_by_code.get(exc.code, 500)
    if status_code == 500:
        return _IntentionalBreakAPIError(
            500,
            "internal_error",
            "An unexpected internal error occurred.",
            retryable=True,
        )
    return _IntentionalBreakAPIError(
        status_code,
        public_code,
        public_message,
        retryable=False,
        details=details,
        flatten_details=flatten_details,
    )


def create_research_router(
    *,
    get_connection: Callable[[], Any],
    backend: str,
    load_feed_source: Callable[[Any], tuple[list[dict], Any]] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/research", tags=["research"])

    def intentional_break_now() -> datetime:
        value = clock() if clock else datetime.now(timezone.utc)
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def intentional_break_success(data: dict, *, now: datetime) -> dict:
        return {
            "ok": True,
            "data": data,
            "server_timestamp": now.isoformat(),
            "contract_version": INTENTIONAL_BREAK_CONTRACT_VERSION,
        }

    def intentional_break_error(error: _IntentionalBreakAPIError) -> JSONResponse:
        now = intentional_break_now()
        content = {
            "ok": False,
            "error_code": error.error_code,
            "message": error.message,
            "retryable": error.retryable,
            "server_timestamp": now.isoformat(),
            "contract_version": INTENTIONAL_BREAK_CONTRACT_VERSION,
        }
        if error.details:
            content["details"] = error.details
            if error.flatten_details:
                content.update(error.details)
        return JSONResponse(status_code=error.status_code, content=content)

    def intentional_break_endpoint(handler):
        @wraps(handler)
        def protected(*args, **kwargs):
            try:
                return handler(*args, **kwargs)
            except _IntentionalBreakAPIError as exc:
                return intentional_break_error(exc)
            except IntentionalBreakStorageError as exc:
                return intentional_break_error(
                    _intentional_break_storage_error(exc, intentional_break_now())
                )
            except Exception as exc:
                logger.exception(
                    "Unexpected Intentional Break API failure in %s",
                    handler.__name__,
                )
                if _storage_failure_is_retryable(exc):
                    return intentional_break_error(_IntentionalBreakAPIError(
                        503,
                        "storage_temporarily_unavailable",
                        "The research store is temporarily unavailable.",
                        retryable=True,
                    ))
                return intentional_break_error(_IntentionalBreakAPIError(
                    500,
                    "internal_error",
                    "An unexpected internal error occurred.",
                    retryable=True,
                ))

        return protected

    def intentional_break_participant(conn, authorization: str | None):
        scheme, _, token = str(authorization or "").partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            raise _IntentionalBreakAPIError(
                401,
                "authentication_required",
                "A participant bearer token is required.",
            )
        try:
            participant = authenticate_participant(
                conn, backend=backend, access_token=token
            )
        except ResearchNotFoundError as exc:
            raise _IntentionalBreakAPIError(
                401, "invalid_credential", "The participant credential is invalid."
            ) from exc
        if participant["status"] != "active":
            raise _IntentionalBreakAPIError(
                403, "participant_inactive", "The research participant is not active."
            )
        return participant, token

    def participant_for_request(authorization: str | None):
        token = _bearer_token(authorization)
        conn = get_connection()
        try:
            return authenticate_participant(conn, backend=backend, access_token=token)
        except ResearchNotFoundError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        finally:
            conn.close()

    @router.post("/participants", status_code=201)
    def new_participant():
        conn = get_connection()
        try:
            return create_participant(conn, backend=backend)
        finally:
            conn.close()

    @router.post("/sessions", status_code=201)
    def new_session(
        request: StartSessionRequest,
        authorization: str | None = Header(default=None),
    ):
        participant = participant_for_request(authorization)
        conn = get_connection()
        try:
            return start_session(
                conn,
                backend=backend,
                participant=participant,
                application_version=request.application_version,
                client_timestamp=request.client_timestamp,
            )
        except ResearchConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        finally:
            conn.close()

    @router.get("/sessions/{session_id}")
    def read_session(
        session_id: UUID,
        authorization: str | None = Header(default=None),
    ):
        participant = participant_for_request(authorization)
        conn = get_connection()
        try:
            return get_session(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=str(session_id),
            )
        except ResearchNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        finally:
            conn.close()

    @router.get("/sessions/{session_id}/feed")
    def read_research_feed(
        session_id: UUID,
        response: Response,
        k: int = Query(default=12, ge=1, le=50),
        exclude_ids: str | None = None,
        condition: str | None = None,
        feed_policy_version: str | None = None,
        seed: str | None = None,
        authorization: str | None = Header(default=None),
    ):
        if condition is not None or feed_policy_version is not None or seed is not None:
            raise HTTPException(
                status_code=400,
                detail="Research feed condition, policy, and seed are server-owned.",
            )
        participant = participant_for_request(authorization)
        if participant["status"] != "active":
            raise HTTPException(status_code=409, detail="Research participant is not active.")

        conn = get_connection()
        try:
            session = get_feed_session(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=str(session_id),
            )
            if session["status"] != "active":
                raise ResearchConflictError(
                    f"Research session is {session['status']} and cannot serve a feed"
                )
            rows, public_signal_context = (
                load_feed_source(conn) if load_feed_source else ([], None)
            )
            payload = build_research_feed_payload(
                rows,
                policy_version=session["feed_policy_version"],
                k=k,
                seed=session["feed_seed"],
                exclude_ids=_parse_exclude_ids(exclude_ids),
                public_signal_context=public_signal_context,
            )
            feed_request_id = str(uuid4())
            items = [
                {**item, "feed_request_id": feed_request_id}
                for item in payload["items"]
            ]
            record_feed_items(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=str(session_id),
                feed_request_id=feed_request_id,
                items=items,
            )
            if os.getenv("CHRYSALIS_RESEARCH_DEBUG", "").lower() in {"1", "true", "yes"}:
                response.headers["X-Chrysalis-Research-Policy"] = session["feed_policy_version"]
                print(
                    "[research_feed] "
                    f"session={session_id} policy={session['feed_policy_version']} "
                    f"request={feed_request_id} items={len(items)}"
                )
            return {**payload, "items": items, "feed_request_id": feed_request_id}
        except ResearchNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ResearchConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        finally:
            conn.close()

    @router.post("/events/batch")
    def write_events(
        request: EventBatchRequest,
        authorization: str | None = Header(default=None),
    ):
        participant = participant_for_request(authorization)
        events = [
            {
                **event.model_dump(),
                "event_id": str(event.event_id),
            }
            for event in request.events
        ]
        conn = get_connection()
        try:
            result = insert_event_batch(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=str(request.session_id),
                events=events,
            )
            return {
                "ok": True,
                "accepted": result["accepted"],
                "duplicate_event_ids": result["duplicates"],
            }
        except ResearchNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ResearchConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        finally:
            conn.close()

    @router.post("/sessions/{session_id}/complete")
    def finish_session(
        session_id: UUID,
        request: CompleteSessionRequest,
        authorization: str | None = Header(default=None),
    ):
        participant = participant_for_request(authorization)
        conn = get_connection()
        try:
            return complete_session(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=str(session_id),
                event={
                    **request.model_dump(),
                    "event_id": str(request.event_id),
                },
            )
        except ResearchNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ResearchConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        finally:
            conn.close()

    @router.get(f"{INTENTIONAL_BREAK_API_PREFIX}/current")
    @intentional_break_endpoint
    def read_current_intentional_break(
        authorization: str | None = Header(default=None),
    ):
        request_time = intentional_break_now()
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            journey = get_current_intentional_break_journey(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                now=request_time,
            )
            return intentional_break_success(
                {"journey": _serialize_intentional_break_journey(journey)},
                now=request_time,
            )
        finally:
            conn.close()

    @router.get(f"{INTENTIONAL_BREAK_API_PREFIX}/sessions/{{session_id}}")
    @intentional_break_endpoint
    def read_intentional_break_session(
        session_id: str,
        authorization: str | None = Header(default=None),
    ):
        request_time = intentional_break_now()
        validated_session_id = _intentional_break_uuid(session_id)
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            journey = reconcile_intentional_break_cooldown(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=validated_session_id,
                now=request_time,
            )
            return intentional_break_success(
                {"journey": _serialize_intentional_break_journey(journey)},
                now=request_time,
            )
        finally:
            conn.close()

    @router.post(f"{INTENTIONAL_BREAK_API_PREFIX}/plans", status_code=201)
    @intentional_break_endpoint
    def create_intentional_break_api_plan(
        payload: Any = Body(default=None),
        authorization: str | None = Header(default=None),
    ):
        request = _intentional_break_model(IntentionalBreakPlanRequest, payload)
        request_time = intentional_break_now()
        conn = get_connection()
        try:
            participant, token = intentional_break_participant(conn, authorization)
            if load_feed_source is None:
                raise _IntentionalBreakAPIError(
                    503,
                    "inventory_unavailable",
                    "The active feed inventory is temporarily unavailable.",
                    retryable=True,
                )
            seed = _private_intentional_break_seed(
                participant_id=participant["participant_id"],
                access_token=token,
                plan_idempotency_key=str(request.idempotency_key),
            )
            try:
                rows, public_signal_context = load_feed_source(conn)
                ranked = build_research_feed_payload(
                    list(rows),
                    policy_version=INTENTIONAL_BREAK_POLICY_VERSION,
                    k=request.planned_video_count,
                    seed=seed,
                    exclude_ids=None,
                    public_signal_context=public_signal_context,
                )
            except Exception as exc:
                raise _IntentionalBreakAPIError(
                    503,
                    "inventory_unavailable",
                    "The active feed inventory is temporarily unavailable.",
                    retryable=True,
                ) from exc
            selected_items = list(ranked.get("items") or [])
            unique_post_ids = {
                str(item.get("post_id") or "") for item in selected_items
                if str(item.get("post_id") or "")
            }
            if (
                len(selected_items) != request.planned_video_count
                or len(unique_post_ids) != request.planned_video_count
            ):
                available_count = len(unique_post_ids)
                raise _IntentionalBreakAPIError(
                    409,
                    "insufficient_inventory",
                    "There are not enough unique eligible posts for this plan.",
                    retryable=False,
                    details={
                        "available_count": available_count,
                        "requested_count": request.planned_video_count,
                    },
                    flatten_details=True,
                )
            reserved_items = [
                _intentional_break_reserved_item(item, position=position)
                for position, item in enumerate(selected_items, start=1)
            ]
            journey = create_intentional_break_plan(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                intention=request.intention,
                planned_video_count=request.planned_video_count,
                selected_cooldown_seconds=request.selected_cooldown_seconds,
                reserved_items=reserved_items,
                plan_idempotency_key=str(request.idempotency_key),
                previous_session_id=(
                    str(request.previous_session_id)
                    if request.previous_session_id is not None
                    else None
                ),
                now=request_time,
            )
            serialized = _serialize_intentional_break_journey(journey)
            return intentional_break_success({
                "journey": serialized,
                "plan_summary": _intentional_break_plan_summary(selected_items),
                "planned_video_count": serialized["planned_video_count"],
                "estimated_duration_seconds": serialized["estimated_duration_seconds"],
                "suggested_cooldown_seconds": serialized["suggested_cooldown_seconds"],
                "selected_cooldown_seconds": serialized["selected_cooldown_seconds"],
                "supported_next_action": "start",
                "participant_notice_version": request.participant_notice_version,
            }, now=request_time)
        finally:
            conn.close()

    @router.post(f"{INTENTIONAL_BREAK_API_PREFIX}/sessions/{{session_id}}/cancel")
    @intentional_break_endpoint
    def cancel_intentional_break_api_plan(
        session_id: str,
        payload: Any = Body(default=None),
        authorization: str | None = Header(default=None),
    ):
        request = _intentional_break_model(IntentionalBreakIdempotencyRequest, payload)
        request_time = intentional_break_now()
        validated_session_id = _intentional_break_uuid(session_id)
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            journey = cancel_intentional_break_plan(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=validated_session_id,
                idempotency_key=str(request.idempotency_key),
                now=request_time,
            )
            return intentional_break_success(
                {"journey": _serialize_intentional_break_journey(journey)},
                now=request_time,
            )
        finally:
            conn.close()

    @router.post(f"{INTENTIONAL_BREAK_API_PREFIX}/sessions/{{session_id}}/start")
    @intentional_break_endpoint
    def start_intentional_break_api_session(
        session_id: str,
        payload: Any = Body(default=None),
        authorization: str | None = Header(default=None),
    ):
        request = _intentional_break_model(IntentionalBreakIdempotencyRequest, payload)
        request_time = intentional_break_now()
        validated_session_id = _intentional_break_uuid(session_id)
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            journey = start_intentional_break_session(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=validated_session_id,
                idempotency_key=str(request.idempotency_key),
                now=request_time,
            )
            return intentional_break_success(
                {"journey": _serialize_intentional_break_journey(journey)},
                now=request_time,
            )
        finally:
            conn.close()

    @router.get(f"{INTENTIONAL_BREAK_API_PREFIX}/sessions/{{session_id}}/items")
    @intentional_break_endpoint
    def read_intentional_break_api_items(
        session_id: str,
        start_position: str = Query(default="1"),
        limit: str = Query(default="12"),
        exclude_ids: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ):
        request_time = intentional_break_now()
        validated_session_id = _intentional_break_uuid(session_id)
        if exclude_ids is not None:
            raise _IntentionalBreakAPIError(
                400,
                "invalid_request",
                "Intentional Break items do not accept exclusion lists.",
            )
        try:
            page_start = int(start_position)
            page_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise _IntentionalBreakAPIError(
                400, "invalid_request", "Item pagination values must be integers."
            ) from exc
        if page_start < 1 or page_limit < 1 or page_limit > 20:
            raise _IntentionalBreakAPIError(
                400,
                "invalid_request",
                "start_position must be positive and limit must be between 1 and 20.",
            )
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            result = read_intentional_break_items(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=validated_session_id,
                start_position=page_start,
                requested_limit=page_limit,
                now=request_time,
            )
            return intentional_break_success({
                "items": [
                    _serialize_intentional_break_item(item) for item in result["items"]
                ],
                "planned_total": result["planned_total"],
                "start_position": page_start,
                "next_position": result["next_position"],
                "has_more": result["has_more"],
                "journey_state": "active",
            }, now=request_time)
        finally:
            conn.close()

    @router.post(f"{INTENTIONAL_BREAK_API_PREFIX}/sessions/{{session_id}}/events")
    @intentional_break_endpoint
    def append_intentional_break_api_events(
        session_id: str,
        payload: Any = Body(default=None),
        authorization: str | None = Header(default=None),
    ):
        request = _intentional_break_model(IntentionalBreakEventBatchRequest, payload)
        request_time = intentional_break_now()
        validated_session_id = _intentional_break_uuid(session_id)
        events = []
        for event in request.events:
            event_payload = event.model_dump()
            event_payload["client_event_id"] = str(event.client_event_id)
            events.append(event_payload)
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            result = append_intentional_break_client_events(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=validated_session_id,
                events=events,
                now=request_time,
            )
            accepted = [{
                "client_event_id": item["client_event_id"],
                "server_sequence_number": item["server_sequence_number"],
                "newly_accepted": not item["duplicate"],
                "idempotent_replay": bool(item["duplicate"]),
            } for item in result["accepted"]]
            return intentional_break_success({
                "events": accepted,
                "journey": _serialize_intentional_break_journey(result["journey"]),
                "resulting_lifecycle_events": result["lifecycle_events"],
            }, now=request_time)
        finally:
            conn.close()

    @router.post(f"{INTENTIONAL_BREAK_API_PREFIX}/sessions/{{session_id}}/finish-early")
    @intentional_break_endpoint
    def finish_intentional_break_api_early(
        session_id: str,
        payload: Any = Body(default=None),
        authorization: str | None = Header(default=None),
    ):
        request = _intentional_break_model(IntentionalBreakFinishEarlyRequest, payload)
        request_time = intentional_break_now()
        validated_session_id = _intentional_break_uuid(session_id)
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            journey = finish_intentional_break_early(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=validated_session_id,
                idempotency_key=str(request.idempotency_key),
                current_position=request.current_position,
                now=request_time,
            )
            return intentional_break_success(
                {"journey": _serialize_intentional_break_journey(journey)},
                now=request_time,
            )
        finally:
            conn.close()

    @router.post(f"{INTENTIONAL_BREAK_API_PREFIX}/sessions/{{session_id}}/checkout")
    @intentional_break_endpoint
    def submit_intentional_break_api_checkout(
        session_id: str,
        payload: Any = Body(default=None),
        authorization: str | None = Header(default=None),
    ):
        request = _intentional_break_model(IntentionalBreakCheckoutRequest, payload)
        request_time = intentional_break_now()
        validated_session_id = _intentional_break_uuid(session_id)
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            journey = submit_intentional_break_checkout(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=validated_session_id,
                worthwhile_answer=request.worthwhile,
                perceived_control_answer=request.perceived_control,
                mood_answer=request.mood,
                checkout_version=request.checkout_version,
                submission_idempotency_key=str(request.idempotency_key),
                now=request_time,
            )
            serialized = _serialize_intentional_break_journey(journey)
            return intentional_break_success({
                "journey": serialized,
                "cooldown_started_at": serialized["cooldown_started_at"],
                "cooldown_ends_at": serialized["cooldown_ends_at"],
                "remaining_seconds": serialized["remaining_seconds"],
                "supported_next_action": "read_cooldown",
            }, now=request_time)
        finally:
            conn.close()

    @router.get(f"{INTENTIONAL_BREAK_API_PREFIX}/sessions/{{session_id}}/cooldown")
    @intentional_break_endpoint
    def read_intentional_break_api_cooldown(
        session_id: str,
        authorization: str | None = Header(default=None),
    ):
        request_time = intentional_break_now()
        validated_session_id = _intentional_break_uuid(session_id)
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            journey = reconcile_intentional_break_cooldown(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=validated_session_id,
                now=request_time,
            )
            serialized = _serialize_intentional_break_journey(journey)
            return intentional_break_success({
                "journey": serialized,
                "journey_state": serialized["journey_state"],
                "cooldown_outcome": serialized["cooldown_outcome"],
                "cooldown_started_at": serialized["cooldown_started_at"],
                "cooldown_ends_at": serialized["cooldown_ends_at"],
                "remaining_seconds": serialized["remaining_seconds"],
                "override_started_at": serialized["override_started_at"],
                "override_available_at": serialized["override_available_at"],
                "supported_actions": serialized["supported_actions"],
            }, now=request_time)
        finally:
            conn.close()

    @router.post(f"{INTENTIONAL_BREAK_API_PREFIX}/sessions/{{session_id}}/override/start")
    @intentional_break_endpoint
    def start_intentional_break_api_override(
        session_id: str,
        payload: Any = Body(default=None),
        authorization: str | None = Header(default=None),
    ):
        request = _intentional_break_model(IntentionalBreakIdempotencyRequest, payload)
        request_time = intentional_break_now()
        validated_session_id = _intentional_break_uuid(session_id)
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            journey = start_intentional_break_override(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=validated_session_id,
                idempotency_key=str(request.idempotency_key),
                now=request_time,
            )
            serialized = _serialize_intentional_break_journey(journey)
            remaining_pause = 0
            if serialized["override_available_at"] and serialized["journey_state"] == "cooldown":
                available = datetime.fromisoformat(
                    serialized["override_available_at"].replace("Z", "+00:00")
                )
                remaining_pause = max(
                    0, math.ceil((available - request_time).total_seconds())
                )
            return intentional_break_success({
                "journey": serialized,
                "journey_state": serialized["journey_state"],
                "override_started_at": serialized["override_started_at"],
                "override_available_at": serialized["override_available_at"],
                "remaining_pause_seconds": remaining_pause,
            }, now=request_time)
        finally:
            conn.close()

    @router.post(f"{INTENTIONAL_BREAK_API_PREFIX}/sessions/{{session_id}}/override/confirm")
    @intentional_break_endpoint
    def confirm_intentional_break_api_override(
        session_id: str,
        payload: Any = Body(default=None),
        authorization: str | None = Header(default=None),
    ):
        request = _intentional_break_model(IntentionalBreakOverrideConfirmRequest, payload)
        request_time = intentional_break_now()
        validated_session_id = _intentional_break_uuid(session_id)
        conn = get_connection()
        try:
            participant, _token = intentional_break_participant(conn, authorization)
            journey = confirm_intentional_break_override(
                conn,
                backend=backend,
                participant_id=participant["participant_id"],
                session_id=validated_session_id,
                reason_code=request.reason_code,
                confirmation_idempotency_key=str(request.idempotency_key),
                now=request_time,
            )
            return intentional_break_success(
                {"journey": _serialize_intentional_break_journey(journey)},
                now=request_time,
            )
        finally:
            conn.close()

    return router


def _parse_exclude_ids(raw: str | None, *, limit: int = 500) -> list[str]:
    if not raw:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in str(raw).split(","):
        post_id = value.strip()
        if not post_id or post_id in seen:
            continue
        seen.add(post_id)
        result.append(post_id)
        if len(result) >= limit:
            break
    return result
