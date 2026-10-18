from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from famulor_client import FamulorAPIError, clamp_limit, client_from_credentials

FIELDS = ("id", "name", "is_active", "mode", "tags", "outbound_phone_number_id", "created_at")


class ListAssistantsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            with client_from_credentials(self.runtime.credentials) as client:
                data = client.list_assistants(limit=clamp_limit(tool_parameters.get("limit"), 50)) or []
        except FamulorAPIError as e:
            raise ValueError(str(e)) from e
        assistants = [{k: a.get(k) for k in FIELDS if k in a} for a in data]
        yield self.create_json_message({"assistants": assistants, "count": len(assistants)})
        if assistants:
            lines = [f"- {a.get('name')} ({a.get('id')}){'' if a.get('is_active', True) else ' [inactive]'}" for a in assistants]
            yield self.create_text_message("Famulor assistants:\n" + "\n".join(lines))
        else:
            yield self.create_text_message("No assistants found in this Famulor workspace.")
