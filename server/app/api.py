import asyncio
from contextlib import asynccontextmanager

from app.agent import (
    PlanNotPendingError,
    approve_plan,
    ask_llm,
    delete_thread,
    deny_plan,
    pending_plan,
    restor_thread,
)
from app.config import get_settings
from app.monitoring import MetricsCollector, RequestTimer, get_logger
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DenyPlanRequest,
    HealthResponse,
    MetricsResponse,
)
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv()

logger = get_logger()
metrics: MetricsCollector = None
CHAT_TIMEOUT_SECONDS = 300


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "Starting production API...",
        extra={
            "extra_data": {
                "environment": settings.app_env,
                "primary_model": settings.llm_model,
            }
        },
    )
    global metrics
    metrics = MetricsCollector()
    try:
        logger.info("All components initialized. Ready to serve requests.")
        yield
    finally:
        logger.info("Shutting down...", extra={"extra_data": metrics.summary})


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    logger.warning(
        "Rate limit exceeded",
        extra={
            "extra_data": {
                "client_ip": get_remote_address(request),
            }
        },
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": "Too many requests. Please slow down.",
        },
    )


@app.post("/chat")
@limiter.limit(get_settings().rate_limit)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    response = None
    timer = RequestTimer()
    try:
        with timer:
            try:
                generated = await asyncio.wait_for(
                    ask_llm(body.message, body.thread_id), timeout=CHAT_TIMEOUT_SECONDS
                )
            except TimeoutError as exc:
                raise HTTPException(
                    status_code=504, detail="Chat generation timed out"
                ) from exc
            if generated.status not in ("completed", "awaiting_approval"):
                raise HTTPException(status_code=502, detail="Chat generation failed")
            response = generated
        response.processing_time_ms = timer.elapsed_ms
        return response
    finally:
        metrics.record_request(
            timer.elapsed_ms,
            input_tokens=max(0, response.input_tokens or 0)
            if response is not None
            else 0,
            output_tokens=max(0, response.output_tokens or 0)
            if response is not None
            else 0,
            error=response is None,
        )


@app.post("/threads/{thread_id}/plan/approve", response_model=ChatResponse)
async def approve_thread_plan(thread_id: str) -> ChatResponse:
    try:
        return await approve_plan(thread_id)
    except PlanNotPendingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/threads/{thread_id}/plan/deny", response_model=ChatResponse)
async def deny_thread_plan(thread_id: str, body: DenyPlanRequest) -> ChatResponse:
    try:
        return await deny_plan(thread_id, body.message)
    except PlanNotPendingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/health")
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        environment=settings.app_env,
        checks={},
    )


@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    messages = await restor_thread(thread_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")
    plan = await pending_plan(thread_id)
    return {"messages": messages, **({"pending_plan": plan} if plan else {})}


@app.delete("/threads/{thread_id}", status_code=204)
async def remove_thread(thread_id: str):
    delete_thread(thread_id)
    return Response(status_code=204)


@app.get("/metrics")
def get_metrics() -> MetricsResponse:
    summary = metrics.summary
    return MetricsResponse(**summary)
