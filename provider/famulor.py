from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from famulor_client import FamulorAPIError, client_from_credentials


class FamulorProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        """Validate by calling GET /me, a read-only self-inspection that needs no scope."""
        try:
            with client_from_credentials(credentials) as client:
                client.me()
        except FamulorAPIError as e:
            raise ToolProviderCredentialValidationError(str(e)) from e
        except Exception as e:  # noqa: BLE001 - surface any unexpected failure as a validation error
            raise ToolProviderCredentialValidationError(f"Could not validate Famulor credentials: {type(e).__name__}") from e
