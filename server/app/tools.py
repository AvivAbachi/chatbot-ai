import ast
import json
import math
import operator
from datetime import UTC, datetime

import httpx
from app.config import get_settings
from app.monitoring import get_logger
from app.rag import embeddings, qdrantClient
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain_core.tools import tool
from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    Prefetch,
    TextQuery,
)

settings = get_settings()
logger = get_logger()


def _format_document(doc) -> str:
    payload = doc.payload or {}
    metadata = payload.get("metadata") or {}
    lines = [
        f"{key}: {metadata[key]}"
        for key in ("doc_id", "title", "source", "h1", "h2", "h3")
        if metadata.get(key)
    ]
    lines.append(payload.get("page_content") or "")
    return "\n".join(lines)


operations = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

functions = {
    # Basic
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    # Rounding
    "ceil": math.ceil,
    "floor": math.floor,
    "trunc": math.trunc,
    # Powers and roots
    "sqrt": math.sqrt,
    "isqrt": math.isqrt,
    "exp": math.exp,
    # Logarithms
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    # Trigonometry
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    # Angle conversion
    "degrees": math.degrees,
    "radians": math.radians,
    # Hyperbolic
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    # Other
    "hypot": math.hypot,
    "gcd": math.gcd,
    "lcm": math.lcm,
    "copysign": math.copysign,
}

constants = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


@tool(parse_docstring=True)
def calucator(expression: str) -> str:
    """Calculate mathematical expressions using standard order of operations.

    Args:
        expression: Expression with numbers, parentheses, +, -, *, /, //, %, **,
            and functions abs, round, min, max, ceil, floor, trunc, sqrt, isqrt,
            exp, log, log10, log2, sin, cos, tan, asin, acos, atan, atan2,
            degrees, radians, sinh, cosh, tanh, hypot, gcd, lcm, and copysign.
            Constants pi, e, and tau are supported. Trigonometric arguments are radians.
    """
    if len(expression) > 500:
        return "Expression is too long."

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = float(node.value)
        elif isinstance(node, ast.Name) and node.id in constants:
            value = constants[node.id]
        elif isinstance(node, ast.UnaryOp) and isinstance(
            node.op, (ast.UAdd, ast.USub)
        ):
            value = evaluate(node.operand)
            if isinstance(node.op, ast.USub):
                value = -value
        elif isinstance(node, ast.BinOp) and type(node.op) in operations:
            value = operations[type(node.op)](evaluate(node.left), evaluate(node.right))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            base, exponent = evaluate(node.left), evaluate(node.right)
            if abs(exponent) > 1000:
                raise ValueError("Exponent is too large")
            value = math.pow(base, exponent)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in functions
            and not node.keywords
        ):
            args = [evaluate(arg) for arg in node.args]
            if node.func.id in {"isqrt", "gcd", "lcm"}:
                if any(not float(arg).is_integer() for arg in args):
                    raise ValueError("Function requires integer arguments")
                args = [int(arg) for arg in args]
            if node.func.id == "round" and len(args) == 2:
                if not float(args[1]).is_integer() or abs(args[1]) > 1000:
                    raise ValueError("Invalid precision")
                args[1] = int(args[1])
            value = functions[node.func.id](*args)
        else:
            raise ValueError("Unsupported expression")
        if not math.isfinite(value):
            raise ValueError("Result is too large")
        return value

    try:
        result = evaluate(ast.parse(expression.strip(), mode="eval").body)
        return str(result)
    except ZeroDivisionError:
        return "Cannot divide by zero."
    except (SyntaxError, ValueError, OverflowError, RecursionError, TypeError):
        return "Invalid or unsupported arithmetic expression."


@tool(parse_docstring=True)
def datetime_tool() -> str:
    """Get the current date and time in UTC (ISO 8601 format)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


@tool(parse_docstring=True)
def rag_search_tool(
    query: str | None = None,
    keywords: list[str] | None = None,
    doc_id: str | None = None,
) -> str:
    """Search internal engineering docs using semantic and keyword search.

    Args:
        query: Search question or terms. Omit to retrieve by document ID.
        keywords: Optional case-insensitive metadata labels; all must match.
        doc_id: Optional exact document ID. Required if query is omitted.
    """
    query = (query or "").strip()
    doc_id = (doc_id or "").strip()
    if not query and not doc_id:
        return "Provide a query or a document ID."
    try:
        filter_conditions = [
            FieldCondition(
                key="metadata.keywords",
                match=MatchValue(value=value.strip().lower()),
            )
            for value in keywords or []
            if value.strip()
        ]
        if doc_id:
            filter_conditions.append(
                FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id))
            )
        qdrant_filter = Filter(must=filter_conditions) if filter_conditions else None
        if query:
            documents = qdrantClient.query_points(
                collection_name=settings.qdrant_collection,
                prefetch=[
                    Prefetch(
                        query=embeddings.embed_query(query),
                        using="dense",
                        filter=qdrant_filter,
                        limit=20,
                    ),
                    Prefetch(
                        query=TextQuery(text=query),
                        using="page_content",
                        filter=qdrant_filter,
                        limit=20,
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=10,
                with_payload=True,
            ).points
        else:
            documents, _ = qdrantClient.scroll(
                collection_name=settings.qdrant_collection,
                scroll_filter=qdrant_filter,
                limit=10,
                with_payload=True,
                with_vectors=False,
            )
    except Exception:
        logger.exception("Internal documentation search failed")
        return "Internal documentation search is currently unavailable. Do not claim that no relevant documents exist."
    if not documents:
        return "No relevant internal documents found."
    return "\n\n".join(_format_document(doc) for doc in documents)


@tool(parse_docstring=True)
def web_fetch_tool(url: str) -> str:
    """Fetch readable content from a public URL, including docs and source code.

    Args:
        url: The URL to fetch.
    """
    if not url.startswith(("https://", "http://")):
        return "Invalid URL."

    try:
        with (
            httpx.Client(timeout=10, follow_redirects=True) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()

            content_type = (
                response.headers.get("content-type", "").split(";")[0].lower()
            )

            chunks = []
            total = 0

            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > 1_000_000:
                    return "Response exceeds the size limit."
                chunks.append(chunk)

            content = b"".join(chunks).decode(
                response.encoding or "utf-8",
                errors="replace",
            )
            source = str(response.url)

        if content_type in ("text/html", "application/xhtml+xml"):
            soup = BeautifulSoup(content, "html.parser")

            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            content = soup.get_text(" ", strip=True)

        elif content_type == "application/json" or content_type.endswith("+json"):
            try:
                content = json.dumps(
                    json.loads(content),
                    indent=2,
                    ensure_ascii=False,
                )
            except json.JSONDecodeError:
                pass

        return f"Source: {source}\nContent:\n{content}"

    except httpx.HTTPError:
        logger.exception("Web fetch failed: %s", url)
        return "Failed to fetch the URL."


@tool(parse_docstring=True)
def web_search_tool(query: str) -> str:
    """Search the web for current technical information, documentation,
    and references. Returns up to five results with titles, URLs, and snippets.

    Args:
        query: A focused web search query.
    """
    try:
        results = DDGS().text(query, max_results=5)

        if not results:
            return "No search results found."

        return "\n".join(
            f"Title: {result.get('title')}\n"
            f"Link: {result.get('href')}\n"
            f"Snippet: {result.get('body')}\n---"
            for result in results
        )
    except Exception as e:
        logger.exception("Web search failed")
        return f"An error occurred during the metasearch: {e!s}"
