from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = "Core"

    def ready(self):
        from apps.core import signals  # noqa: F401


@receiver(connection_created)
def configure_sqlite(sender, connection, **kwargs):
    """Turn on the two SQLite pragmas this project depends on.

    ``foreign_keys`` is off by default in SQLite, which would silently void
    every ``on_delete=PROTECT`` guard on the financial tables. ``journal_mode``
    lets a reader and a writer work at the same time, which matters as soon as
    two browser tabs are open.
    """
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
