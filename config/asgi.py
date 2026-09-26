"""ASGI entrypoint.

Present because Django generates it and some deployment targets expect it.
Skillbridge itself has no asynchronous consumers — messaging is ordinary HTTP.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
