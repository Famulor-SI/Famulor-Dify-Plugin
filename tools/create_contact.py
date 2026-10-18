import re
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from famulor_client import FamulorAPIError, client_from_credentials, opt_str

E164 = re.compile(r"^\+[1-9]\d{6,14}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CreateContactTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        phone = opt_str(tool_parameters, "phone")
        email = opt_str(tool_parameters, "email")
        if phone:
            phone = re.sub(r"[\s\-()/.]", "", phone)
            if not E164.match(phone):
                raise ValueError("Phone must be in E.164 format, e.g. +491701234567.")
        if email and not EMAIL.match(email):
            raise ValueError("Email address is not valid.")
        if not phone and not email:
            raise ValueError("A contact needs a phone number or an email.")
        body: dict[str, Any] = {}
        if phone:
            body["phone"] = phone
        if email:
            body["email"] = email
        name = opt_str(tool_parameters, "name")
        if name:
            body["name"] = name
        tags = [t.strip()[:40] for t in (opt_str(tool_parameters, "tags") or "").split(",") if t.strip()][:32]
        if tags:
            body["tags"] = tags
        try:
            with client_from_credentials(self.runtime.credentials) as client:
                contact = client.create_contact(body) or {}
        except FamulorAPIError as e:
            raise ValueError(str(e)) from e
        yield self.create_json_message({"contact": contact})
        verb = "created" if contact.get("created") else "updated (merged into the existing contact)"
        yield self.create_text_message(f"Contact {contact.get('id')} {verb}.")
