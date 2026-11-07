import base64
import binascii
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, TypedDict

from langchain.messages import AIMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlanNotPendingError(Exception):
    pass


class TextPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["text"]
    text: str = Field(min_length=1)


class FilePart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["file"]
    base64: str = Field(min_length=1, max_length=1024**2)
    mime_type: str

    @field_validator("mime_type")
    @classmethod
    def text_mime_type(cls, value: str) -> str:
        if not value.lower().startswith("text/") or not value[5:]:
            raise ValueError("Only text files are supported")
        return value

    @field_validator("base64")
    @classmethod
    def utf8_base64(cls, value: str) -> str:
        try:
            base64.b64decode(value, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
            raise ValueError("File must contain base64-encoded UTF-8 text") from exc
        return value


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str | list[TextPart | FilePart] = Field(min_length=1)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Message
    thread_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("message")
    @classmethod
    def user_message(cls, value: Message) -> Message:
        if value.role != "user":
            raise ValueError("Only user messages are accepted")
        return value


class DenyPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1)


class ToolResult(BaseModel):
    name: str
    content: str


class ChatResponse(BaseModel):
    response: str = ""
    thread_id: str | None = None
    tool_results: list[ToolResult] = Field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    processing_time_ms: float = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = Field(default="in_progress")


class IntentClassifer(BaseModel):
    message_intent: Literal["chat", "code_plan", "small_code", "bad_intent"]


class State(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    message_intent: str
    code_plan: str
    plan_decision: str
    plan_feedback: str
    generated_code: AIMessage
    code_review: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    checks: dict[str, Any]


class MetricsResponse(BaseModel):
    total_requests: int
    total_errors: int
    error_rate: str
    avg_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int


class ModelInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    created: int
    object: str
    owned_by: str
    shutdown_date: int | None = None
