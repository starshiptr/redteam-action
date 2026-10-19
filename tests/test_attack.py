import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from anthropic.types.beta import BetaMessage

from redteam.attack import attack

# ponytail: hand-written in the SDK's response shape; swap for a recorded real response once the API key exists
FIXTURE = Path(__file__).parent / "fixtures" / "attack_response.json"
BUNDLE = {"diff": "-    return 0\n+    return 1", "files": {"redteam/cli.py": "def main(): ..."}, "tests": {}}


def fake_client(message):
    calls = []
    create = lambda **kw: calls.append(kw) or message
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create))), calls


def recorded():
    return BetaMessage.model_validate(json.loads(FIXTURE.read_text()))


def test_attack_parses_findings_and_sends_the_bundle():
    client, calls = fake_client(recorded())

    findings, usage = attack(BUNDLE, client=client)

    assert findings[0]["severity"] == "high"
    assert "assert main() == 0" in findings[0]["proof_test"]
    assert usage.output_tokens == 300
    sent = calls[0]
    assert sent["model"] == "claude-opus-5-5"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert "+    return 1" in sent["messages"][0]["content"]


def test_attack_raises_when_the_model_stops_early():
    message = recorded().model_copy(update={"stop_reason": "refusal"})
    client, _ = fake_client(message)

    with pytest.raises(RuntimeError, match="refusal"):
        attack(BUNDLE, client=client)
