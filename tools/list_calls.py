from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from famulor_client import (
    FamulorAPIError,
    call_summary,
    clamp_limit,
    client_from_credentials,
    opt_str,
)


class ListCallsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        params = {
            "assistant_id": opt_str(tool_parameters, "assistant_id"),
            "campaign_id": opt_str(tool_parameters, "campaign_id"),
            "status": opt_str(tool_parameters, "status"),
            "limit": clamp_limit(tool_parameters.get("limit"), 20),
            "sort": "created_at",
        }
        try:
            with client_from_credentials(self.runtime.credentials) as client:
                data = client.list_calls(**params) or []
        except FamulorAPIError as e:
            raise ValueError(str(e)) from e
        calls = [call_summary(c) for c in data]
        yield self.create_json_message({"calls": calls, "count": len(calls)})
        if not calls:
            yield self.create_text_message("No calls found.")
            return
        lines = [f"- {c.get('id')} | {c.get('status')} | {c.get('to_number') or c.get('from_number') or ''} | {c.get('created_at')}" for c in calls]
        yield self.create_text_message("Recent Famulor calls:\n" + "\n".join(lines))
