"""Publishing_Adapter subsystem — the WordPress REST client.

The only subsystem with write access to the live site, and only after approval.
Authenticates with an Application_Password over HTTP Basic and never leaks
credentials. Depends only on Core_Package.
"""

from publishing_adapter.client import WordPressClient

__all__: list[str] = ["WordPressClient"]
