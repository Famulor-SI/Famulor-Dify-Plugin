import importlib.util
import json
from pathlib import Path

import httpx
import pytest
import respx
import yaml
from dify_plugin.core.entities.plugin.setup import PluginConfiguration
from dify_plugin.entities.tool import ToolConfiguration, ToolProviderConfiguration
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from famulor_client import FamulorAPIError, FamulorClient, normalize_base_url, transcript_turns

ROOT = Path(__file__).resolve().parents[1]
API = "https://app.famulor.io/api/v1"
CREDS = {"api_key": "fam_test", "base_url": ""}


def load(rel):
    return yaml.safe_load((ROOT / rel).read_text())


def tool_class(name):
    spec = importlib.util.spec_from_file_location(f"t_{name}", ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from dify_plugin import Tool

    classes = [v for v in vars(mod).values() if isinstance(v, type) and issubclass(v, Tool) and v is not Tool]
    assert len(classes) == 1
    return classes[0]


def run(name, params, creds=CREDS):
    tool = tool_class(name).from_credentials(creds)
    msgs = list(tool._invoke(params))
    js = [m.message.json_object for m in msgs if m.type.value == "json"]
    txt = [m.message.text for m in msgs if m.type.value == "text"]
    return (js[0] if js else None), "\n".join(txt)


# ------------------------------------------------------------ schema --------


def test_manifest_and_yaml_schemas_validate():
    manifest = load("manifest.yaml")
    PluginConfiguration(**manifest)
    provider = load("provider/famulor.yaml")
    ToolProviderConfiguration(**{**provider, "tools": []})
    names = []
    for rel in provider["tools"]:
        cfg = ToolConfiguration(**load(rel))
        names.append(cfg.identity.name)
        assert (ROOT / load(rel)["extra"]["python"]["source"]).is_file()
    assert names == ["list_assistants", "start_outbound_call", "get_call", "list_calls", "create_contact", "list_campaigns", "start_campaign"]
    assert (ROOT / "_assets" / manifest["icon"]).is_file() and (ROOT / "_assets" / manifest["icon_dark"]).is_file()
    assert manifest["version"] == manifest["meta"]["version"]
    assert manifest["author"] == "famulor" and provider["identity"]["author"] == "famulor"
    assert all(load(rel)["identity"]["author"] == "famulor" for rel in provider["tools"])


# ------------------------------------------------------------ client --------


@pytest.mark.parametrize(
    "given,expected",
    [
        (None, API),
        ("", API),
        ("app.example.com", "https://app.example.com/api/v1"),
        ("https://app.example.com/", "https://app.example.com/api/v1"),
        ("https://app.example.com/api/v1", "https://app.example.com/api/v1"),
    ],
)
def test_base_url_ok(given, expected):
    assert normalize_base_url(given) == expected


@pytest.mark.parametrize("bad", ["http://app.example.com", "https://user:pw@app.example.com", "https://app.example.com/other", "ftp://x.y"])
def test_base_url_rejected(bad):
    with pytest.raises(FamulorAPIError):
        normalize_base_url(bad)


@respx.mock
def test_client_retries_reads_not_writes(monkeypatch):
    monkeypatch.setattr("famulor_client.time.sleep", lambda s: None)
    get = respx.get(f"{API}/assistants").mock(side_effect=[httpx.Response(503), httpx.Response(200, json={"data": []})])
    post = respx.post(f"{API}/calls").mock(return_value=httpx.Response(503))
    c = FamulorClient("fam_test")
    assert c.list_assistants() == []
    assert get.call_count == 2
    with pytest.raises(FamulorAPIError):
        c.create_call({"assistant_id": "a", "to_number": "+4930123456"})
    assert post.call_count == 1


@respx.mock
def test_error_does_not_leak_key():
    respx.get(f"{API}/me").mock(return_value=httpx.Response(401, json={"error": {"code": "unauthorized", "message": "Invalid API key."}}))
    with pytest.raises(FamulorAPIError) as ei:
        FamulorClient("fam_supersecret").me()
    assert "fam_supersecret" not in str(ei.value) and ei.value.status_code == 401


def test_transcript_variants():
    assert transcript_turns({"transcript_display": [{"kind": "message", "role": "assistant", "text": "Hi"}]}) == [{"role": "assistant", "text": "Hi"}]
    assert transcript_turns({"transcript": [{"role": "user", "content": "Yo"}]}) == [{"role": "user", "text": "Yo"}]
    assert transcript_turns({}) == []


# ------------------------------------------------------------ provider ------


def _provider():
    spec = importlib.util.spec_from_file_location("prov", ROOT / "provider" / "famulor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.FamulorProvider()


@respx.mock
def test_provider_validation_ok_and_white_label():
    me = respx.get("https://app.example.com/api/v1/me").mock(return_value=httpx.Response(200, json={"data": {"tenant": {"id": "t"}}}))
    _provider()._validate_credentials({"api_key": "fam_x", "base_url": "https://app.example.com"})
    assert me.calls.last.request.headers["authorization"] == "Bearer fam_x"


@respx.mock
def test_provider_validation_fails():
    respx.get(f"{API}/me").mock(return_value=httpx.Response(401, json={"error": {"code": "unauthorized", "message": "Invalid API key."}}))
    with pytest.raises(ToolProviderCredentialValidationError, match="invalid"):
        _provider()._validate_credentials({"api_key": "fam_bad"})
    with pytest.raises(ToolProviderCredentialValidationError):
        _provider()._validate_credentials({"api_key": ""})
    with pytest.raises(ToolProviderCredentialValidationError, match="https"):
        _provider()._validate_credentials({"api_key": "fam_x", "base_url": "http://insecure.example.com"})


# ------------------------------------------------------------ tools ---------


@respx.mock
def test_list_assistants():
    route = respx.get(f"{API}/assistants").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "a1", "name": "Support", "is_active": True, "system_prompt": "secret prompt"}]})
    )
    js, txt = run("list_assistants", {"limit": 500})
    assert js == {"assistants": [{"id": "a1", "name": "Support", "is_active": True}], "count": 1}
    assert "Support (a1)" in txt
    assert route.calls.last.request.url.params["limit"] == "200"


@respx.mock
def test_start_outbound_call():
    route = respx.post(f"{API}/calls").mock(return_value=httpx.Response(201, json={"data": {"id": "c1", "status": "queued", "to_number": "+4930123456"}}))
    js, txt = run("start_outbound_call", {"assistant_id": "a1", "to_number": "+49 30 123456", "variables": '{"customer_name": "Ada"}'})
    assert json.loads(route.calls.last.request.content) == {"assistant_id": "a1", "to_number": "+4930123456", "variables": {"customer_name": "Ada"}}
    assert js["call"]["id"] == "c1" and "queued" in txt


@pytest.mark.parametrize(
    "params,msg",
    [
        ({"assistant_id": "a1", "to_number": "030123"}, "E.164"),
        ({"assistant_id": "", "to_number": "+4930123456"}, "Assistant ID"),
        ({"assistant_id": "a1", "to_number": "+4930123456", "variables": "[1]"}, "JSON object"),
        ({"assistant_id": "a1", "to_number": "+4930123456", "variables": "{bad"}, "JSON object"),
    ],
)
@respx.mock
def test_start_outbound_call_validation_makes_no_request(params, msg):
    route = respx.post(f"{API}/calls").mock(return_value=httpx.Response(201, json={"data": {}}))
    with pytest.raises(ValueError, match=msg):
        run("start_outbound_call", params)
    assert not route.called


@respx.mock
def test_get_call_with_transcript():
    respx.get(f"{API}/calls/c1").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"id": "c1", "status": "completed", "duration_sec": 42, "summary": "Booked.", "analysis": {"success": True},
                            "transcript_display": [{"kind": "message", "role": "assistant", "text": "Hallo"}, {"kind": "message", "role": "user", "text": "Hi"}],
                            "recording_url": "https://rec.example/x"}},
        )
    )
    js, txt = run("get_call", {"call_id": "c1", "include_transcript": True})
    assert js["transcript"] == [{"role": "assistant", "text": "Hallo"}, {"role": "user", "text": "Hi"}]
    assert js["analysis"] == {"success": True} and js["recording_url"]
    assert "Summary: Booked." in txt and "assistant: Hallo" in txt
    js2, _ = run("get_call", {"call_id": "c1", "include_transcript": False})
    assert "transcript" not in js2


@respx.mock
def test_get_call_not_found():
    respx.get(f"{API}/calls/nope").mock(return_value=httpx.Response(404, json={"error": {"code": "not_found", "message": "Call not found"}}))
    with pytest.raises(ValueError, match="Call not found"):
        run("get_call", {"call_id": "nope"})


@respx.mock
def test_list_calls_filters():
    route = respx.get(f"{API}/calls").mock(return_value=httpx.Response(200, json={"data": [{"id": "c1", "status": "completed", "transcript": [1]}]}))
    js, _ = run("list_calls", {"status": "completed", "assistant_id": "a1", "campaign_id": "", "limit": 5})
    q = route.calls.last.request.url.params
    assert q["status"] == "completed" and q["assistant_id"] == "a1" and "campaign_id" not in q and q["limit"] == "5"
    assert js["calls"] == [{"id": "c1", "status": "completed"}]


@respx.mock
def test_create_contact():
    route = respx.post(f"{API}/leads").mock(return_value=httpx.Response(200, json={"data": {"id": "l1", "created": True}}))
    js, txt = run("create_contact", {"phone": "+49 170 1234567", "name": "Ada", "tags": "vip, renewal,"})
    assert json.loads(route.calls.last.request.content) == {"phone": "+491701234567", "name": "Ada", "tags": ["vip", "renewal"]}
    assert "created" in txt
    with pytest.raises(ValueError):
        run("create_contact", {"name": "no channel"})
    with pytest.raises(ValueError):
        run("create_contact", {"email": "not-an-email"})


@respx.mock
def test_campaigns():
    respx.get(f"{API}/campaigns").mock(return_value=httpx.Response(200, json={"data": [{"id": "k1", "name": "Renewals", "status": "draft"}]}))
    js, txt = run("list_campaigns", {"status": "draft"})
    assert js["campaigns"][0]["id"] == "k1" and "Renewals" in txt
    start = respx.post(f"{API}/campaigns/k1/start").mock(return_value=httpx.Response(200, json={"data": {"campaign_id": "k1", "status": "running"}}))
    js, txt = run("start_campaign", {"campaign_id": "k1"})
    assert js["campaign"]["status"] == "running" and start.call_count == 1


@respx.mock
def test_rate_limited_write_reports_error():
    respx.post(f"{API}/campaigns/k1/start").mock(return_value=httpx.Response(429, json={"error": {"code": "rate_limited", "message": "Too many requests"}}))
    with pytest.raises(ValueError, match="Too many"):
        run("start_campaign", {"campaign_id": "k1"})


# Allowed filter values as returned by the live API's 400 validation messages (checked 2026-10-19).
API_CALL_STATUSES = ["queued", "ringing", "in_progress", "completed", "failed", "no_answer", "busy"]
API_CAMPAIGN_STATUSES = ["draft", "scheduled", "running", "paused", "completed", "archived"]


@pytest.mark.parametrize("tool,param,expected", [("list_calls", "status", API_CALL_STATUSES), ("list_campaigns", "status", API_CAMPAIGN_STATUSES)])
def test_select_options_match_api_enums(tool, param, expected):
    opts = next(p for p in load(f"tools/{tool}.yaml")["parameters"] if p["name"] == param)["options"]
    assert [o["value"] for o in opts] == expected


def test_versions_consistent():
    import tomllib

    import famulor_client

    v = load("manifest.yaml")["version"]
    assert famulor_client.USER_AGENT.endswith("/" + v)
    assert tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"] == v
    assert f"**Version:** {v}" in (ROOT / "README.md").read_text()
