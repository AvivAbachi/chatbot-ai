import base64
import uuid

from app.config import get_settings
from app.monitoring import get_logger
from app.schemas import (
    ChatResponse,
    FilePart,
    IntentClassifer,
    Message,
    PlanNotPendingError,
    State,
    ToolResult,
)
from app.tools import (
    calucator,
    datetime_tool,
    rag_search_tool,
    web_fetch_tool,
    web_search_tool,
)
from app.utils import prompts
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, interrupt

settings = get_settings()
logger = get_logger()

model = ChatOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    model=settings.llm_model,
    temperature=0.2,
)
tools = [calucator, datetime_tool, web_fetch_tool, web_search_tool, rag_search_tool]


async def classify_intent(state: State):
    structured = model.with_structured_output(IntentClassifer)
    result = await structured.ainvoke([prompts.INTENT_PROMPT, *state["messages"]])
    return {"message_intent": result.message_intent}


def route_intent(state: State):
    return state["message_intent"]


async def chat(state: State):
    result = await model.bind_tools(tools).ainvoke(
        [prompts.CHAT_PROMPT, *state["messages"]]
    )
    return {"messages": [result]}


async def bad_intent(state: State):
    result = await model.ainvoke([prompts.BAD_INTENT_PROMPT, *state["messages"]])
    return {"messages": [result]}


async def small_code(state: State):
    result = await model.bind_tools(tools).ainvoke(
        [prompts.SMALL_CODE_PROMPT, *state["messages"]]
    )
    return {"messages": [result]}


async def code_plan(state: State):
    messages = [prompts.CODE_PLAN_PROMPT, *state["messages"]]
    if state.get("plan_feedback"):
        messages.append(
            HumanMessage(
                content=f"Previous plan:\n{state['code_plan']}\n\n"
                f"Requested changes:\n{state['plan_feedback']}"
            )
        )
    result = await model.ainvoke(messages)
    return {"code_plan": result.text, "plan_feedback": ""}


def code_plan_review(state: State):
    result = interrupt({"plan": state["code_plan"]})
    return {
        "plan_decision": result["decision"],
        "plan_feedback": result.get("feedback", ""),
    }


def route_plan(state: State):
    return "code_write" if state["plan_decision"] == "approve" else "code_plan"


async def code_write(state: State):
    result = await model.ainvoke(
        [
            prompts.CODE_WRITE_PROMPT,
            *state["messages"],
            HumanMessage(content=f"Implementation plan:\n{state['code_plan']}"),
        ]
    )
    return {"generated_code": result}


async def code_review(state: State):
    result = await model.ainvoke(
        [
            prompts.CODE_REVIEW_PROMPT,
            *state["messages"],
            HumanMessage(content=f"Implementation plan:\n{state['code_plan']}"),
            state["generated_code"],
        ]
    )
    return {"code_review": result.text}


def route_review(state: State):
    return (
        "code_finish" if state["code_review"].strip() == "NO_FIX_NEEDED" else "code_fix"
    )


async def code_finish(state: State):
    return {"messages": [state["generated_code"]]}


async def code_fix(state: State):
    result = await model.ainvoke(
        [
            prompts.CODE_FIX_PROMPT,
            *state["messages"],
            HumanMessage(content=f"Implementation plan:\n{state['code_plan']}"),
            state["generated_code"],
            HumanMessage(content=f"Code review findings:\n{state['code_review']}"),
        ]
    )
    return {"messages": [result]}


checkpointer = InMemorySaver()
graph_builder = StateGraph(State)

graph_builder.add_node(classify_intent)
graph_builder.add_node(chat)
graph_builder.add_node(bad_intent)
graph_builder.add_node(small_code)
graph_builder.add_node(code_plan)
graph_builder.add_node(code_plan_review)
graph_builder.add_node(code_write)
graph_builder.add_node(code_review)
graph_builder.add_node(code_finish)
graph_builder.add_node(code_fix)
graph_builder.add_node("tools", ToolNode(tools))

graph_builder.add_edge(START, "classify_intent")
graph_builder.add_conditional_edges(
    "classify_intent",
    route_intent,
    {
        "chat": "chat",
        "bad_intent": "bad_intent",
        "code_plan": "code_plan",
        "small_code": "small_code",
    },
)
graph_builder.add_conditional_edges(
    "chat", tools_condition, {"tools": "tools", END: END}
)
graph_builder.add_conditional_edges(
    "small_code", tools_condition, {"tools": "tools", END: END}
)
graph_builder.add_conditional_edges(
    "tools", route_intent, {"chat": "chat", "small_code": "small_code"}
)
graph_builder.add_edge("code_plan", "code_plan_review")
graph_builder.add_conditional_edges(
    "code_plan_review",
    route_plan,
    ["code_plan", "code_write"],
)
graph_builder.add_edge("code_write", "code_review")
graph_builder.add_conditional_edges(
    "code_review",
    route_review,
    ["code_finish", "code_fix"],
)
graph_builder.add_edge("bad_intent", END)
graph_builder.add_edge("code_finish", END)
graph_builder.add_edge("code_fix", END)

graph = graph_builder.compile(checkpointer=checkpointer)


def model_content(message: Message) -> str:
    if isinstance(message.content, str):
        return message.content
    return "\n\n".join(
        base64.b64decode(part.base64).decode("utf-8")
        if isinstance(part, FilePart)
        else part.text
        for part in message.content
    )


async def ask_llm(message: Message, thread_id: str | None = None) -> ChatResponse:
    response = ChatResponse(thread_id=thread_id or str(uuid.uuid4()))
    try:
        config = {"configurable": {"thread_id": response.thread_id}}
        content = model_content(message)
        state = await graph.aget_state(config)
        previous = state.values.get("messages", [])
        pending = previous[-1] if previous else None
        message_id = (
            pending.id
            if isinstance(pending, HumanMessage) and pending.content == content
            else None
        )
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=content, id=message_id)]},
            config=config,
        )
        return graph_response(result, response.thread_id)
    except Exception:
        logger.exception("Chat generation failed")
        response.status = "failed"
    return response


def graph_response(result: dict, thread_id: str) -> ChatResponse:
    response = ChatResponse(thread_id=thread_id)
    if result.get("__interrupt__"):
        response.response = result["__interrupt__"][0].value["plan"]
        response.status = "awaiting_approval"
        return response
    answer = result["messages"][-1]
    if not isinstance(answer, AIMessage) or not answer.text.strip():
        raise ValueError("The model returned an empty answer")
    response.response = answer.text
    for message in reversed(result["messages"][:-1]):
        if isinstance(message, HumanMessage):
            break
        if isinstance(message, ToolMessage):
            response.tool_results.insert(
                0, ToolResult(name=message.name or "tool", content=message.text)
            )
    usage = answer.usage_metadata or {}
    response.input_tokens = usage.get("input_tokens") or 0
    response.output_tokens = usage.get("output_tokens") or 0
    response.total_tokens = usage.get(
        "total_tokens", response.input_tokens + response.output_tokens
    )
    response.status = "completed"
    return response


async def restor_thread(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    messages = state.values.get("messages", [])
    restored = []
    tools = []
    for message in messages:
        if isinstance(message, ToolMessage):
            tools.append({"name": message.name or "tool", "content": message.text})
        elif isinstance(message, HumanMessage):
            if tools:
                restored.append(
                    {"role": "assistant", "content": "", "tool_results": tools}
                )
                tools = []
            if message.text:
                restored.append({"role": "user", "content": message.text})
        elif isinstance(message, AIMessage) and message.text:
            usage = message.usage_metadata or {}
            restored.append(
                {
                    "role": "assistant",
                    "content": message.text,
                    "tool_results": tools,
                    **(
                        {
                            "input_tokens": usage["input_tokens"],
                            "output_tokens": usage["output_tokens"],
                            "total_tokens": usage.get(
                                "total_tokens",
                                usage["input_tokens"] + usage["output_tokens"],
                            ),
                        }
                        if "input_tokens" in usage and "output_tokens" in usage
                        else {}
                    ),
                }
            )
            tools = []
    if tools:
        restored.append({"role": "assistant", "content": "", "tool_results": tools})
    return restored


async def pending_plan(thread_id: str) -> str | None:
    state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    if "code_plan_review" in state.next:
        return state.values.get("code_plan")
    return None


def delete_thread(thread_id: str):
    checkpointer.delete_thread(thread_id)


async def approve_plan(thread_id: str):
    return await resume_plan(thread_id, {"decision": "approve"})


async def deny_plan(thread_id: str, message: str):
    return await resume_plan(thread_id, {"decision": "deny", "feedback": message})


async def resume_plan(thread_id: str, decision: dict) -> ChatResponse:
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    if "code_plan_review" not in state.next:
        raise PlanNotPendingError("Thread is not awaiting plan approval")

    result = await graph.ainvoke(Command(resume=decision), config=config)
    return graph_response(result, thread_id)
