"""Discuss/Ask pipeline: tool hints, intent gate, thread continuation, prompt."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models.schemas import GenerateSQLRequest
from app.services.discuss_prompts import (
    build_discuss_persona,
    build_query_and_error_context,
    build_selected_objects_context,
    extract_json_object,
    is_thread_continuation,
    looks_like_sql_statement,
    parse_recent_conversation,
)
from app.services.discuss_service import (
    DiscussToolResult,
    build_discuss_system_prompt,
    classify_discuss_intent,
    discuss_conversation,
    try_resolve_tool_lookup,
)
from app.services.markdown_tool_registry import MarkdownToolRegistryService, parse_tool_markdown
from app.services.tool_function_invoker import ToolFunctionInvoker


def test_parse_tool_markdown_front_matter():
    tool = parse_tool_markdown(
        "---\nname: icd10_lookup\ndescription: Look up ICD-10 codes\nprotocol: mcp\nhints: icd, code\nserver_url: http://localhost/mcp\n---\nUse for diagnosis codes.\n",
        "icd10_lookup",
    )
    assert tool["name"] == "icd10_lookup"
    assert tool["protocol"] == "mcp"
    assert "icd" in tool["hints"]
    assert "Use for diagnosis codes." in tool["instructions"]


def test_registry_reads_tools_folder(tmp_path: Path):
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "lookup.md").write_text(
        "---\nname: lookup\ndescription: codes\nprotocol: sub_agent\nhints: icd\n---\n",
        encoding="utf-8",
    )
    tools = MarkdownToolRegistryService().get_all_tools(tmp_path)
    assert len(tools) == 1
    assert tools[0]["name"] == "lookup"


def test_matches_tool_hint_aliases():
    tools = [{"name": "icd10_lookup", "description": "ICD-10 codes", "hints": ["icd"], "instructions": ""}]
    assert ToolFunctionInvoker.matches_tool_hint("what is the icd-10 code for diabetes?", tools)
    assert not ToolFunctionInvoker.matches_tool_hint("hello there", tools)


def test_thread_continuation_guard():
    recent = ["user: analyze sales", "assistant: I can break that down by region."]
    assert is_thread_continuation(recent, "yes")
    assert is_thread_continuation(recent, "please.")
    assert not is_thread_continuation(recent, "Can you instead tell me the capital city of France today?")
    assert not is_thread_continuation([], "yes")


def test_parse_recent_conversation_excludes_current_user():
    history = "user: first\nassistant: reply\nuser: follow up"
    turns = parse_recent_conversation(history, exclude_current=True, current_query="follow up")
    assert turns[-1][0] == "assistant"
    assert turns[0] == ("user", "first")


def test_parse_recent_conversation_keeps_multiline_assistant_as_one_turn():
    history = (
        "user: What data is available for a staff dashboard?\n"
        "assistant: The database has employees, orders, and territories.\n"
        "\n"
        "If you want, I can next give you:\n"
        "1. a Power BI-ready star schema version of this dataset, or\n"
        "2. a single detailed row-level SQL dataset.\n"
    )
    turns = parse_recent_conversation(history, exclude_current=False)
    assert len(turns) == 2
    assert turns[0] == ("user", "What data is available for a staff dashboard?")
    assert "Power BI-ready star schema" in turns[1][1]
    assert all(role in {"user", "assistant"} for role, _ in turns)


def test_parse_recent_conversation_accepts_json_turns():
    history = json.dumps([
        {"role": "user", "content": "What data is available?"},
        {"role": "assistant", "content": "Employees, orders, territories.\n1. star schema\n2. row-level SQL"},
    ])
    turns = parse_recent_conversation(history, exclude_current=False)
    assert len(turns) == 2
    assert "star schema" in turns[1][1]


def test_looks_like_sql_and_json_extract():
    assert looks_like_sql_statement("SELECT * FROM dbo.Orders")
    parsed = extract_json_object('```json\n{"intent":"off_topic","reply":"stay on data"}\n```')
    assert parsed["intent"] == "off_topic"


def test_system_prompt_includes_persona_and_selected_objects():
    request = GenerateSQLRequest(
        query="what do these tables mean?",
        queryMode="ask",
        user_selected_tables=["dbo.Orders"],
        previousSQL="SELECT 1",
        error_message="timeout",
    )
    prompt = build_discuss_system_prompt(request, DiscussToolResult(block="### TOOL RESULT (lookup)\nok"))
    assert "data-analysis assistant" in prompt
    assert "SELECTED DATABASE OBJECTS" in prompt
    assert "CURRENT QUERY / ERROR CONTEXT" in prompt
    assert "TOOL RESULT" in prompt
    assert build_discuss_persona().split()[0] in prompt


def test_selected_objects_and_query_context_helpers():
    selected = build_selected_objects_context(None, ["dbo.Customers"])
    assert "dbo" in selected and "Customers" in selected
    context = build_query_and_error_context("SELECT 1", "divide by zero")
    assert "SELECT 1" in context
    assert "divide by zero" in context


@patch("app.services.llm_client.LlmClient")
def test_classifier_short_circuits_off_topic(mock_client_cls):
    mock_client_cls.return_value.complete.return_value = '{"intent":"off_topic","reply":"Ask about this database."}'
    intent, reply = classify_discuss_intent("what is the weather?", [], "src")
    assert intent == "off_topic"
    assert "database" in reply.lower()


@patch("app.services.llm_client.LlmClient")
def test_classifier_fail_open_to_db_query(mock_client_cls):
    mock_client_cls.return_value.complete.side_effect = RuntimeError("down")
    intent, reply = classify_discuss_intent("show sales", [], "src")
    assert intent == "db_query"
    assert reply == ""


@patch("app.services.discuss_service.try_resolve_tool_lookup", return_value=None)
@patch("app.services.discuss_service.classify_discuss_intent", return_value=("off_topic", "Let's stay on the data."))
def test_discuss_short_circuit_skips_completion(mock_classify, mock_tool):
    with patch("app.services.llm_service.get_llm_service") as mock_llm:
        result = discuss_conversation(GenerateSQLRequest(query="tell me a joke", queryMode="ask"))
        mock_llm.assert_not_called()
    assert result.query_type == "ask"
    assert result.sql == ""
    assert "data" in (result.explanation or "").lower()


@patch("app.services.discuss_service.try_resolve_tool_lookup", return_value=None)
@patch("app.services.discuss_service.classify_discuss_intent", return_value=("off_topic", "ignored"))
def test_discuss_continuation_overrides_short_circuit(mock_classify, mock_tool):
    llm = MagicMock()
    llm.chat_completion.return_value = "Here is the regional breakdown."
    request = GenerateSQLRequest(
        query="yes",
        queryMode="ask",
        queryHistory="user: analyze sales\nassistant: I can break that down by region.",
    )
    with patch("app.services.llm_service.get_llm_service", return_value=llm):
        result = discuss_conversation(request)
    llm.chat_completion.assert_called_once()
    assert "regional" in (result.explanation or "")


@patch("app.services.discuss_service.try_resolve_tool_lookup", return_value=None)
@patch("app.services.discuss_service.classify_discuss_intent", return_value=("off_topic", "ignored"))
def test_discuss_keeps_multiline_thread_for_short_follow_up(mock_classify, mock_tool):
    llm = MagicMock()
    llm.chat_completion.return_value = "Here is the Power BI-ready star schema."
    history = json.dumps([
        {"role": "user", "content": "What data is available for a staff dashboard?"},
        {
            "role": "assistant",
            "content": (
                "Employees, orders, and territories are available.\n\n"
                "If you want, I can next give you:\n"
                "1. a Power BI-ready star schema version of this dataset, or\n"
                "2. a single detailed row-level SQL dataset."
            ),
        },
    ])
    request = GenerateSQLRequest(query="1 please", queryMode="ask", queryHistory=history)
    with patch("app.services.llm_service.get_llm_service", return_value=llm):
        result = discuss_conversation(request)
    sent = llm.chat_completion.call_args[0][0]
    roles = [message["role"] for message in sent]
    assert roles == ["system", "user", "assistant", "user"]
    assert "Employees, orders, and territories" in sent[2]["content"]
    assert sent[3]["content"] == "1 please"
    assert "star schema" in (result.explanation or "")


@patch("app.services.discuss_service.classify_discuss_intent")
@patch(
    "app.services.discuss_service.try_resolve_tool_lookup",
    return_value=DiscussToolResult(block="### TOOL RESULT (icd10)\nE11", tool_event_name="icd10"),
)
def test_tool_result_skips_classifier(mock_tool, mock_classify):
    llm = MagicMock()
    llm.chat_completion.return_value = "The ICD-10 code is E11."
    with patch("app.services.llm_service.get_llm_service", return_value=llm):
        result = discuss_conversation(GenerateSQLRequest(query="icd-10 for type 2 diabetes", queryMode="ask"))
    mock_classify.assert_not_called()
    assert result.tool_event == "icd10"


def test_tool_lookup_requires_hint_match(tmp_path: Path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "lookup.md").write_text(
        "---\nname: lookup\ndescription: ICD codes\nprotocol: mcp\nhints: icd\n---\n",
        encoding="utf-8",
    )
    with patch("app.services.discuss_service.resolve_discuss_tool_folder", return_value=tmp_path):
        assert try_resolve_tool_lookup("hello world", "src") is None
