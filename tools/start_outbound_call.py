import json
import re
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from famulor_client import (
    FamulorAPIError,
    call_summary,
    client_from_credentials,
    opt_str,
    require_str,
)

E164 = re.compile(r"^\+[1-9]\d{6,14}$")


def parse_variables(raw: Any) -> dict[str, Any] | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(str(raw))
    except json.JSONDecodeError as e:
        raise ValueError("Variables must be a JSON object, e.g. {\"customer_name\": \"Ada\"}.") from e
    if not isinstance(value, dict):
        raise ValueError("Variables must be a JSON object.")
    return value


class StartOutboundCallTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            assistant_id = require_str(tool_parameters, "assistant_id", "Assistant ID")
            to_number = re.sub(r"[\s\-()/.]", "", require_str(tool_parameters, "to_number", "Phone number"))
        except FamulorAPIError as e:
            raise ValueError(str(e)) from e
        if not E164.match(to_number):
            raise ValueError("Phone number must be in E.164 format, e.g. +4930123456.")
        body: dict[str, Any] = {"assistant_id": assistant_id, "to_number": to_number}
        phone_number_id = opt_str(tool_parameters, "phone_number_id")
        if phone_number_id:
            body["phone_number_id"] = phone_number_id
        variables = parse_variables(tool_parameters.get("variables"))
        if variables:
            body["variables"] = variables
        try:
            with client_from_credentials(self.runtime.credentials) as client:
                call = client.create_call(body) or {}
        except FamulorAPIError as e:
            raise ValueError(str(e)) from e
        yield self.create_json_message({"call": call_summary(call)})
        yield self.create_text_message(
            f"Call {call.get('id')} to {to_number} created with status '{call.get('status')}'. "
            "Use Get Call with this id to read the result once the call has ended."
        )
