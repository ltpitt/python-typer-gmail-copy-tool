"""List configured Gmail accounts."""
import typer
from pathlib import Path
from gmail_copy_tool.utils.config import ConfigManager

app = typer.Typer()


@app.command()
def list_accounts(
    config_dir: str = typer.Option(None, help="Custom config directory (for testing)")
):
    """List all configured Gmail accounts.
    
    Shows account nicknames, email addresses, and authentication status.
    """
    config_manager = ConfigManager(Path(config_dir) if config_dir else None)
    config_manager.display_accounts()
