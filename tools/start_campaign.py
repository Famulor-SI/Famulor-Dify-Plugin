from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from famulor_client import FamulorAPIError, client_from_credentials, require_str


class StartCampaignTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            campaign_id = require_str(tool_parameters, "campaign_id", "Campaign ID")
            with client_from_credentials(self.runtime.credentials) as client:
                result = client.start_campaign(campaign_id) or {}
        except FamulorAPIError as e:
            raise ValueError(str(e)) from e
        yield self.create_json_message({"campaign": result})
        yield self.create_text_message(f"Campaign {result.get('campaign_id', campaign_id)} status: {result.get('status')}.")
