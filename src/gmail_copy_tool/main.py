import typer
from functools import wraps

from gmail_copy_tool.commands.compare import compare
from gmail_copy_tool.commands.setup import setup
from gmail_copy_tool.commands.list_accounts import list_accounts

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

# Suppress googleapiclient.discovery_cache INFO logs
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.WARNING)

app = typer.Typer()

# Wrapper to auto-enable sync mode when using 'sync' command
def sync_wrapper(
    source: str,
    target: str,
    label: str = None,
    after: str = None,
    before: str = None,
    year: int = None,
    limit: int = 20,
    show_duplicates: bool = False,
    yes: bool = False
):
    """Sync source to target: copy missing emails and delete extras."""
    compare(source, target, label, after, before, year, limit, show_duplicates, sync=True, yes=yes)

app.command(name="sync")(sync_wrapper)
app.command(name="setup")(setup)
app.command(name="list")(list_accounts)


if __name__ == "__main__":
    app()
