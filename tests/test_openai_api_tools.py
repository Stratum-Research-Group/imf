"""
tests/test_openai_api_tools.py

Unit tests for Hermes Native Tool-Calling & JSON-Schema Engine in scripts/serve_openai_compatible_api.py
"""

import json
import pytest
from scripts.serve_openai_compatible_api import (
    ChatMessage,
    detect_hermes_tool_call,
)


def test_detect_hermes_tool_call_none():
    messages = [ChatMessage(role="user", content="Hello world")]
    # No tools passed
    assert detect_hermes_tool_call(messages, None, None) is None
    # tool_choice = 'none'
    tools = [{"type": "function", "function": {"name": "test_fn"}}]
    assert detect_hermes_tool_call(messages, tools, "none") is None


def test_detect_hermes_tool_call_tool_choice_function():
    messages = [ChatMessage(role="user", content="Execute function")]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculate_roots",
                "parameters": {
                    "type": "object",
                    "properties": {"dimension": {"type": "integer"}},
                },
            },
        }
    ]
    tc = detect_hermes_tool_call(
        messages, tools, {"type": "function", "function": {"name": "calculate_roots"}}
    )
    assert tc is not None
    assert len(tc) == 1
    assert tc[0]["function"]["name"] == "calculate_roots"
    args = json.loads(tc[0]["function"]["arguments"])
    assert "dimension" in args


def test_detect_hermes_tool_call_intent_matching():
    messages = [
        ChatMessage(
            role="user",
            content="Please execute_bash to check disk status with timeout 10",
        )
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_bash",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "timeout": {"type": "integer"},
                    },
                },
            },
        }
    ]
    tc = detect_hermes_tool_call(messages, tools, "auto")
    assert tc is not None
    assert len(tc) == 1
    assert tc[0]["function"]["name"] == "execute_bash"
    args = json.loads(tc[0]["function"]["arguments"])
    assert "command" in args


def test_detect_hermes_tool_call_after_tool_response():
    messages = [
        ChatMessage(role="user", content="Check directory"),
        ChatMessage(
            role="assistant",
            tool_calls=[{"id": "call_1", "type": "function", "function": {"name": "ls"}}],
        ),
        ChatMessage(role="tool", tool_call_id="call_1", content="file1.txt file2.txt"),
    ]
    tools = [{"type": "function", "function": {"name": "ls"}}]
    # After tool output, assistant synthesizes final answer without loop
    assert detect_hermes_tool_call(messages, tools, "auto") is None


def test_enforce_grammar_constrained_json():
    from scripts.serve_openai_compatible_api import enforce_grammar_constrained_json
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "verification_output",
            "schema": {
                "type": "object",
                "properties": {
                    "verified": {"type": "boolean"},
                    "axioms_count": {"type": "integer"}
                },
                "required": ["verified", "axioms_count"]
            }
        }
    }

    # Test with markdown code block
    raw_text = "Here is the result:\n```json\n{\"verified\": true, \"axioms_count\": 0}\n```\nExplanation follows."
    cleaned = enforce_grammar_constrained_json(raw_text, response_format)
    parsed = json.loads(cleaned)
    assert parsed["verified"] is True
    assert parsed["axioms_count"] == 0

    # Test fallback filling required fields if input is plain prose
    plain_text = "Verification passed with zero unproven assumptions."
    fallback = enforce_grammar_constrained_json(plain_text, response_format)
    parsed_fallback = json.loads(fallback)
    assert "verified" in parsed_fallback
    assert "axioms_count" in parsed_fallback

