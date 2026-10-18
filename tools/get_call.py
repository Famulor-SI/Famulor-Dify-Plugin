from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from famulor_client import (
    FamulorAPIError,
    call_summary,
    client_from_credentials,
    require_str,
    transcript_turns,
)


class GetCallTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        include = tool_parameters.get("include_transcript", True)
        include = include if isinstance(include, bool) else str(include).lower() not in ("false", "0", "no")
        try:
            call_id = require_str(tool_parameters, "call_id", "Call ID")
            with client_from_credentials(self.runtime.credentials) as client:
                call = client.get_call(call_id) or {}
        except FamulorAPIError as e:
            raise ValueError(str(e)) from e
        result: dict[str, Any] = {"call": call_summary(call)}
        analysis = call.get("analysis")
        if analysis:
            result["analysis"] = analysis
        if call.get("recording_url"):
            result["recording_url"] = call["recording_url"]
        turns = transcript_turns(call) if include else []
        if include:
            result["transcript"] = turns
        yield self.create_json_message(result)
        text = [f"Call {call.get('id')}: status {call.get('status')}, duration {call.get('duration_sec') or 0}s."]
        if call.get("summary"):
            text.append(f"Summary: {call['summary']}")
        if turns:
            text.append("Transcript:\n" + "\n".join(f"{t['role']}: {t['text']}" for t in turns))
        yield self.create_text_message("\n".join(text))
