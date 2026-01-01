import typer

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
app.command(name="sync")(compare)
app.command(name="setup")(setup)
app.command(name="list")(list_accounts)


if __name__ == "__main__":
    app()
