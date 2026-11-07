import os
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from langchain.messages import AIMessage, HumanMessage, ToolMessage

from app.schemas import ChatResponse, Message

os.environ.setdefault("LLM_BASE_URL", "http://localhost:8888/v1")
os.environ.setdefault("LLM_API_KEY", "test")

from app import agent, api, tools


def chat_model(invoke):
    fake = Mock(
        ainvoke=invoke,
        with_structured_output=Mock(
            return_value=Mock(
                ainvoke=AsyncMock(
                    return_value=agent.IntentClassifer(message_intent="chat")
                )
            )
        ),
    )
    fake.bind_tools.return_value = fake
    return fake


@pytest.fixture
def client():
    with TestClient(api.app) as client:
        yield client


def test_chat_passes_message_and_thread_to_model(client, monkeypatch):
    result = ChatResponse(response="Answer")
    result.status = "completed"
    generate = AsyncMock(return_value=result)
    monkeypatch.setattr(api, "ask_llm", generate)
    message = {"role": "user", "content": "Next"}
    response = client.post("/chat", json={"message": message, "thread_id": "thread"})
    assert response.status_code == 200
    assert response.json()["response"] == "Answer"
    assert generate.await_args.args[0].model_dump() == message
    assert generate.await_args.args[1] == "thread"


def test_metrics_use_public_token_fields(client, monkeypatch):
    result = ChatResponse(response="Answer", input_tokens=11, output_tokens=51)
    result.status = "completed"
    monkeypatch.setattr(api, "ask_llm", AsyncMock(return_value=result))
    client.post("/chat", json={"message": {"role": "user", "content": "Hi"}})
    metrics = client.get("/metrics").json()
    assert metrics["total_input_tokens"] == 11
    assert metrics["total_output_tokens"] == 51


def test_chat_timeout_returns_504_and_records_error(client, monkeypatch):
    import asyncio

    cancelled = []

    async def generate(*args):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    monkeypatch.setattr(api, "ask_llm", generate)
    monkeypatch.setattr(api, "CHAT_TIMEOUT_SECONDS", 0.01)
    response = client.post("/chat", json={"message": {"role": "user", "content": "Hi"}})
    assert response.status_code == 504
    assert cancelled == [True]
    assert client.get("/metrics").json()["total_errors"] == 1


def test_missing_token_counts_do_not_break_metrics(client, monkeypatch):
    result = ChatResponse(response="Answer", input_tokens=None, output_tokens=-1)
    result.status = "completed"
    monkeypatch.setattr(api, "ask_llm", AsyncMock(return_value=result))
    response = client.post("/chat", json={"message": {"role": "user", "content": "Hi"}})
    assert response.status_code == 200
    metrics = client.get("/metrics").json()
    assert metrics["total_input_tokens"] == metrics["total_output_tokens"] == 0


@pytest.mark.parametrize(
    "message",
    [
        None,
        {"role": "system", "content": "Hi"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": ""},
    ],
)
def test_invalid_message_is_rejected(client, message):
    assert client.post("/chat", json={"message": message}).status_code == 422


def test_failure_and_health(client, monkeypatch):
    monkeypatch.setattr(api, "ask_llm", AsyncMock(return_value=ChatResponse()))
    assert (
        client.post(
            "/chat", json={"message": {"role": "user", "content": "Hi"}}
        ).status_code
        == 502
    )
    assert client.get("/health").json()["status"] == "healthy"
    assert client.get("/metrics").json()["total_errors"] == 1
    assert client.post("/threads").status_code == 404


def test_restore_and_delete_thread(client, monkeypatch):
    monkeypatch.setattr(
        agent, "model", chat_model(AsyncMock(return_value=AIMessage(content="Answer")))
    )
    response = client.post(
        "/chat", json={"message": {"role": "user", "content": "Hello"}}
    )
    thread_id = response.json()["thread_id"]
    assert client.get(f"/threads/{thread_id}").json() == {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Answer", "tool_results": []},
        ]
    }
    assert client.delete(f"/threads/{thread_id}").status_code == 204
    assert client.get(f"/threads/{thread_id}").status_code == 404


def test_restore_includes_tool_results(client, monkeypatch):
    messages = [
        HumanMessage(content="Question"),
        AIMessage(content=""),
        ToolMessage(content="Found it", name="search", tool_call_id="call-1"),
        AIMessage(content="Answer"),
    ]
    monkeypatch.setattr(
        agent,
        "graph",
        Mock(
            aget_state=AsyncMock(
                return_value=Mock(values={"messages": messages}, next=())
            )
        ),
    )
    assert client.get("/threads/test").json() == {
        "messages": [
            {"role": "user", "content": "Question"},
            {
                "role": "assistant",
                "content": "Answer",
                "tool_results": [{"name": "search", "content": "Found it"}],
            },
        ]
    }


@pytest.mark.asyncio
async def test_model_receives_history_and_returns_answer(monkeypatch):
    invoke = AsyncMock(return_value=AIMessage(content="Answer"))
    monkeypatch.setattr(agent, "model", chat_model(invoke))
    result = await agent.ask_llm(Message(role="user", content="Question"))
    assert invoke.await_args.args[0][1].content == "Question"
    assert result.response == "Answer"
    assert result.status == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("intent", ["chat", "small_code"])
async def test_tool_calls_execute_and_return_to_same_model_node(monkeypatch, intent):
    invoke = AsyncMock(
        side_effect=[
            AIMessage(content="", tool_calls=[{
                "name": "calucator", "args": {"expression": "2 + 2"}, "id": "call-1"
            }]),
            AIMessage(content="4"),
        ]
    )
    fake = chat_model(invoke)
    fake.with_structured_output.return_value.ainvoke.return_value = (
        agent.IntentClassifer(message_intent=intent)
    )
    monkeypatch.setattr(agent, "model", fake)

    result = await agent.ask_llm(Message(role="user", content="What is 2 + 2?"))

    assert result.response == "4"
    assert [(item.name, item.content) for item in result.tool_results] == [
        ("calucator", "4.0")
    ]
    assert isinstance(invoke.await_args.args[0][-1], ToolMessage)
    assert (await agent.restor_thread(result.thread_id))[-1]["tool_results"] == [
        {"name": "calucator", "content": "4.0"}
    ]


@pytest.mark.asyncio
async def test_token_usage_is_returned_and_restored(monkeypatch):
    invoke = AsyncMock(
        return_value=AIMessage(
            content="Answer",
            usage_metadata={
                "input_tokens": 11,
                "output_tokens": 51,
                "total_tokens": 62,
            },
        )
    )
    monkeypatch.setattr(agent, "model", chat_model(invoke))
    result = await agent.ask_llm(Message(role="user", content="Question"))
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (
        11,
        51,
        62,
    )
    restored = await agent.restor_thread(result.thread_id)
    assert {
        key: restored[-1][key]
        for key in ("input_tokens", "output_tokens", "total_tokens")
    } == {
        "input_tokens": 11,
        "output_tokens": 51,
        "total_tokens": 62,
    }


@pytest.mark.asyncio
async def test_conversation_memory_and_thread_isolation(monkeypatch):
    invoke = AsyncMock(return_value=AIMessage(content="Answer"))
    monkeypatch.setattr(agent, "model", chat_model(invoke))
    first = await agent.ask_llm(Message(role="user", content="First"))
    second = await agent.ask_llm(Message(role="user", content="Next"), first.thread_id)
    await agent.ask_llm(Message(role="user", content="Separate"))
    assert second.thread_id == first.thread_id
    assert [m.content for m in invoke.await_args_list[1].args[0][1:]] == [
        "First",
        "Answer",
        "Next",
    ]
    assert [m.content for m in invoke.await_args_list[2].args[0][1:]] == ["Separate"]


@pytest.mark.asyncio
async def test_retry_does_not_duplicate_failed_user_message(monkeypatch):
    invoke = AsyncMock(
        side_effect=[RuntimeError("unavailable"), AIMessage(content="Answer")]
    )
    monkeypatch.setattr(agent, "model", chat_model(invoke))
    message = Message(role="user", content="Retry")
    first = await agent.ask_llm(message)
    result = await agent.ask_llm(message, first.thread_id)
    assert result.response == "Answer"
    assert [item.content for item in invoke.await_args_list[1].args[0][1:]] == ["Retry"]


def test_text_file_parts_are_accepted_and_invalid_files_rejected(client, monkeypatch):
    result = ChatResponse(response="Answer")
    result.status = "completed"
    generate = AsyncMock(return_value=result)
    monkeypatch.setattr(api, "ask_llm", generate)
    parts = [
        {"type": "text", "text": "Describe"},
        {"type": "file", "base64": "SGVsbG8=", "mime_type": "text/plain"},
    ]
    assert (
        client.post(
            "/chat", json={"message": {"role": "user", "content": parts}}
        ).status_code
        == 200
    )
    assert agent.model_content(generate.await_args.args[0]) == "Describe\n\nHello"
    parts[1]["mime_type"] = "application/pdf"
    assert (
        client.post(
            "/chat", json={"message": {"role": "user", "content": parts}}
        ).status_code
        == 422
    )
    parts[1]["mime_type"] = "text/plain"
    parts[1]["base64"] = "invalid!"
    assert (
        client.post(
            "/chat", json={"message": {"role": "user", "content": parts}}
        ).status_code
        == 422
    )


@pytest.mark.asyncio
async def test_generation_failure_logs_exception(monkeypatch):
    import json
    import logging

    from app.monitoring import JSONFormatter

    monkeypatch.setattr(
        agent,
        "model",
        chat_model(AsyncMock(side_effect=RuntimeError("provider unavailable"))),
    )
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(json.loads(JSONFormatter().format(record)))

    handler = Capture()
    agent.logger.addHandler(handler)
    try:
        result = await agent.ask_llm(Message(role="user", content="Question"))
    finally:
        agent.logger.removeHandler(handler)
    assert result.status == "failed"
    assert "RuntimeError: provider unavailable" in records[-1]["exception"]


def test_search_failure_returns_a_tool_result(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("DNS unavailable")

    from unittest.mock import Mock

    monkeypatch.setattr(tools, "DDGS", Mock(return_value=Mock(text=fail)))
    result = tools.web_search_tool.invoke({"query": "example"})
    assert "error" in result.lower()
    assert "DNS unavailable" in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "intent,prompt",
    [
        ("chat", agent.prompts.CHAT_PROMPT),
        ("bad_intent", agent.prompts.BAD_INTENT_PROMPT),
    ],
)
async def test_intent_routes_to_prompt(monkeypatch, intent, prompt):
    invoke = AsyncMock(return_value=AIMessage(content="Answer"))
    fake = chat_model(invoke)
    fake.with_structured_output.return_value.ainvoke.return_value = (
        agent.IntentClassifer(message_intent=intent)
    )
    monkeypatch.setattr(agent, "model", fake)
    result = await agent.ask_llm(Message(role="user", content="Question"))
    assert result.response == "Answer"
    assert invoke.await_args.args[0][0] == prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "review,expected", [("NO_FIX_NEEDED", "Code"), ("ISSUES_FOUND", "Fixed")]
)
async def test_code_pipeline(monkeypatch, review, expected):
    invoke = AsyncMock(
        side_effect=[AIMessage(content=x) for x in ["Plan", "Code", review, "Fixed"]]
    )
    fake = chat_model(invoke)
    fake.with_structured_output.return_value.ainvoke.return_value = (
        agent.IntentClassifer(message_intent="code_plan")
    )
    monkeypatch.setattr(agent, "model", fake)
    result = await agent.ask_llm(Message(role="user", content="Write code"))
    assert result.status == "awaiting_approval"
    assert result.response == "Plan"
    result = await agent.approve_plan(result.thread_id)
    assert result.response == expected
    expected_prompts = [
        agent.prompts.CODE_PLAN_PROMPT,
        agent.prompts.CODE_WRITE_PROMPT,
        agent.prompts.CODE_REVIEW_PROMPT,
    ]
    if review != "NO_FIX_NEEDED":
        expected_prompts.append(agent.prompts.CODE_FIX_PROMPT)
    assert [call.args[0][0] for call in invoke.await_args_list] == expected_prompts
    assert [m["content"] for m in await agent.restor_thread(result.thread_id)] == [
        "Write code",
        expected,
    ]


@pytest.mark.asyncio
async def test_deny_plan_passes_feedback_and_pauses_again(monkeypatch):
    invoke = AsyncMock(
        side_effect=[AIMessage(content="Plan"), AIMessage(content="Revised")]
    )
    fake = chat_model(invoke)
    fake.with_structured_output.return_value.ainvoke.return_value = (
        agent.IntentClassifer(message_intent="code_plan")
    )
    monkeypatch.setattr(agent, "model", fake)
    initial = await agent.ask_llm(Message(role="user", content="Write code"))
    revised = await agent.deny_plan(initial.thread_id, "Use Python")
    assert revised.status == "awaiting_approval"
    assert revised.response == "Revised"
    assert "Use Python" in invoke.await_args.args[0][-1].text


@pytest.mark.asyncio
async def test_small_code_intent_returns_answer_without_plan(monkeypatch):
    invoke = AsyncMock(return_value=AIMessage(content="Fixed code"))
    fake = chat_model(invoke)
    fake.with_structured_output.return_value.ainvoke.return_value = (
        agent.IntentClassifer(message_intent="small_code")
    )
    monkeypatch.setattr(agent, "model", fake)
    result = await agent.ask_llm(Message(role="user", content="Fix this bug"))
    assert result.status == "completed"
    assert result.response == "Fixed code"
    assert invoke.await_count == 1
    assert invoke.await_args.args[0][0] == agent.prompts.SMALL_CODE_PROMPT


def test_restore_pending_plan(client, monkeypatch):
    fake = chat_model(AsyncMock(return_value=AIMessage(content="Plan")))
    fake.with_structured_output.return_value.ainvoke.return_value = (
        agent.IntentClassifer(message_intent="code_plan")
    )
    monkeypatch.setattr(agent, "model", fake)
    response = client.post(
        "/chat", json={"message": {"role": "user", "content": "Write code"}}
    )
    restored = client.get(f"/threads/{response.json()['thread_id']}")
    assert restored.json()["pending_plan"] == "Plan"
