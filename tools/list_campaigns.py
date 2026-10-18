from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from famulor_client import (
    FamulorAPIError,
    clamp_limit,
    client_from_credentials,
    opt_str,
)

FIELDS = ("id", "name", "status", "channel", "assistant_id", "scheduled_start_at", "started_at", "completed_at", "created_at")


class ListCampaignsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            with client_from_credentials(self.runtime.credentials) as client:
                data = client.list_campaigns(status=opt_str(tool_parameters, "status"),
                                             limit=clamp_limit(tool_parameters.get("limit"), 50)) or []
        except FamulorAPIError as e:
            raise ValueError(str(e)) from e
        campaigns = [{k: c.get(k) for k in FIELDS if k in c} for c in data]
        yield self.create_json_message({"campaigns": campaigns, "count": len(campaigns)})
        if campaigns:
            yield self.create_text_message("Famulor campaigns:\n" + "\n".join(
                f"- {c.get('name')} ({c.get('id')}) – {c.get('status')}" for c in campaigns))
        else:
            yield self.create_text_message("No campaigns found.")
