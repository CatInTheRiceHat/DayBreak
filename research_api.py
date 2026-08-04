"""Shared FastAPI router for anonymous research session/event logging."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from core.research_storage import (
    ALLOWED_EVENT_TYPES,
    ResearchConflictError,
    ResearchNotFoundError,
    authenticate_participant,
    complete_session,
    create_participant,
    get_feed_session,
    get_session,
    insert_event_batch,
    record_feed_items,
    start_session,
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


def _bearer_token(authorization: str | None) -> str:
    scheme, _, token = str(authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="A participant bearer token is required.")
    return token.strip()


def create_research_router(
    *,
    get_connection: Callable[[], Any],
    backend: str,
    load_feed_source: Callable[[Any], tuple[list[dict], Any]] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/research", tags=["research"])

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
