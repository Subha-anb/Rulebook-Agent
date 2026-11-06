"""Runs the real Anthropic SDK against a fake API, so no key or spend is needed."""
import json
import sys
from pathlib import Path

import anthropic
import pytest

try:
    import httpx2 as httpx
except ImportError:
    import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import DATA_SOURCES, REGISTER, clean_key, create_app
from assistant import Assistant, document_blocks
from pack import load_pack


def sse_body(events: list[dict]) -> bytes:
    return "".join(
        f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events
    ).encode()


def stream_events(stop_reason="end_turn", cached=(0, 5000)) -> list[dict]:
    read, written = cached
    citation = {
        "type": "content_block_location", "cited_text": "Cap at 2x contract value",
        "document_index": 5, "document_title": "Contract library v1.1",
        "start_block_index": 3, "end_block_index": 4,
    }
    return [
        {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "content": [],
            "model": "claude-opus-5-5", "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 20, "output_tokens": 1,
                      "cache_read_input_tokens": read, "cache_creation_input_tokens": written}}},
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "text", "text": "", "citations": []}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "The fallback is 2x."}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "citations_delta", "citation": citation}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
         "usage": {"output_tokens": 12}},
        {"type": "message_stop"},
    ]


class FakeApi:
    def __init__(self, **event_args):
        self.bodies = []
        self.event_args = event_args

    def __call__(self, request):
        self.bodies.append(json.loads(request.content))
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content=sse_body(stream_events(**self.event_args)))


@pytest.fixture(scope="module")
def pack():
    return load_pack(REGISTER, DATA_SOURCES)


def make_assistant(pack, api):
    client = anthropic.Anthropic(
        api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(api)))
    return Assistant(pack, client)


def test_pack_loads_only_current_versions(pack):
    assert [d.title for d in pack.documents] == [
        "California RFP v1.0", "Past bids v1.0", "Kansas UX assets v1.1",
        "Compliance rules v1.1", "Skills and rates v1.0", "Contract library v1.1",
    ]
    assert not pack.warnings


def test_pack_text_is_the_revised_text(pack):
    text = {d.name: "\n".join(d.blocks) for d in pack.documents}
    assert "Notice within 48 hours" in text["Contract library"]
    assert "Notice within 72 hours" not in text["Contract library"]
    assert "10 eligibility notices" in text["Kansas UX assets"]
    assert "Medi-Cal threshold languages" not in text["Compliance rules"]


def test_table_rows_keep_their_headers(pack):
    contract = next(d for d in pack.documents if d.name == "Contract library")
    row = next(b for b in contract.blocks if b.startswith("Clause: Limitation of liability"))
    assert "Fallback: Cap at 2x contract value" in row


def test_requests_carry_the_refusal_and_conflict_rules(pack):
    api = FakeApi()
    list(make_assistant(pack, api).ask("a", "Q"))
    system = api.bodies[0]["system"]
    assert 'exactly "Not in the rulebook"' in system
    assert '"Conflict:"' in system
    assert '"Escalate to:"' in system


def test_only_the_last_document_carries_the_cache_marker(pack):
    blocks = document_blocks(pack)
    assert [("cache_control" in b) for b in blocks] == [False] * 5 + [True]


def test_every_question_sends_an_identical_cached_prefix(pack):
    api = FakeApi()
    assistant = make_assistant(pack, api)
    list(assistant.ask("a", "First question"))
    list(assistant.ask("b", "A different question"))
    first, second = api.bodies
    assert first["system"] == second["system"]
    assert first["messages"][0]["content"][:6] == second["messages"][0]["content"][:6]
    assert first["model"] == "claude-opus-5-5"
    assert first["fallbacks"] == "default"


def test_followups_replay_the_conversation_without_changing_the_prefix(pack):
    api = FakeApi()
    assistant = make_assistant(pack, api)
    list(assistant.ask("a", "First question"))
    list(assistant.ask("a", "Follow-up"))
    first, second = api.bodies
    assert second["messages"][0] == first["messages"][0]
    assert [m["role"] for m in second["messages"]] == ["user", "assistant", "user"]


def test_citations_name_the_document_version_and_text(pack):
    events = list(make_assistant(pack, FakeApi()).ask("a", "Fallback?"))
    citation = next(e for e in events if e["type"] == "citation")
    assert citation == {
        "type": "citation", "n": 1, "document": "Contract library v1.1",
        "file": "5 Contract library - 1.1.docx", "text": "Cap at 2x contract value",
    }


def test_usage_reports_cache_reads(pack):
    api = FakeApi(cached=(5000, 0))
    done = list(make_assistant(pack, api).ask("a", "Q"))[-1]
    assert done["cache_read_tokens"] == 5000
    assert done["cache_write_tokens"] == 0


def test_a_refused_turn_is_not_kept_in_the_conversation(pack):
    assistant = make_assistant(pack, FakeApi(stop_reason="refusal"))
    events = list(assistant.ask("a", "Q"))
    assert any(e["type"] == "notice" for e in events)
    assert "a" not in assistant.conversations


def read_events(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.get_data(as_text=True).splitlines()
            if line.startswith("data: ")]


def test_web_route_streams_events(pack):
    web = create_app(make_assistant(pack, FakeApi())).test_client()
    response = web.post("/api/ask", json={"question": "Fallback?"})
    kinds = [e["type"] for e in read_events(response)]
    assert kinds == ["conversation", "text", "citation", "done"]


def test_web_route_rejects_empty_questions(pack):
    web = create_app(make_assistant(pack, FakeApi())).test_client()
    assert web.post("/api/ask", json={"question": "  "}).status_code == 400


@pytest.mark.parametrize("pasted", [
    "sk-ant-api03-abc_1", "  sk-ant-api03-abc_1\r\n", "\x1b[200~sk-ant-api03-abc_1\x1b[201~",
    "\x16sk-ant-api03-abc_1",
])
def test_pasted_keys_are_cleaned(pasted):
    assert clean_key(pasted) == "sk-ant-api03-abc_1"


def test_web_route_reports_a_rejected_key(pack):
    def rejected(request):
        return httpx.Response(401, json={
            "type": "error", "error": {"type": "authentication_error", "message": "invalid key"}})
    web = create_app(make_assistant(pack, rejected)).test_client()
    events = read_events(web.post("/api/ask", json={"question": "Q"}))
    assert events[-1]["type"] == "error"
    assert "API key" in events[-1]["message"]
