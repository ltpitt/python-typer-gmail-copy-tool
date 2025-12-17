"""Setup wizard for configuring Gmail accounts."""
import typer
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from gmail_copy_tool.utils.config import ConfigManager
from gmail_copy_tool.utils.gmail_api_helpers import ensure_token

app = typer.Typer()
console = Console()

SCOPES = "https://mail.google.com/"


@app.command()
def setup(
    config_dir: str = typer.Option(None, help="Custom config directory (for testing)")
):
    """Interactive setup wizard to configure Gmail accounts.
    
    This will guide you through:
    1. Creating OAuth credentials via Google Cloud Console
    2. Adding accounts with simple nicknames
    3. Authenticating via browser
    """
    console.print("\n[bold cyan]Welcome to Gmail Copy Tool Setup![/bold cyan]\n")
    
    # Initialize config manager
    config_manager = ConfigManager(Path(config_dir) if config_dir else None)
    
    # Show existing accounts if any
    existing = config_manager.list_accounts()
    if existing:
        console.print("[yellow]Existing accounts:[/yellow]")
        config_manager.display_accounts()
        console.print()
    
    # Ask if user has OAuth credentials
    console.print("[cyan]Before we begin, you need OAuth 2.0 credentials from Google Cloud Console.[/cyan]")
    console.print("\nIf you don't have them yet:")
    console.print("1. Go to: [link]https://console.cloud.google.com/[/link]")
    console.print("2. Create a project (or use existing)")
    console.print("3. Enable Gmail API")
    console.print("4. Create OAuth 2.0 Client ID (Desktop app)")
    console.print("5. Download the credentials JSON file\n")
    
    has_credentials = Confirm.ask("Do you have the credentials JSON file ready?", default=True)
    
    if not has_credentials:
        console.print("\n[yellow]Please get your credentials first, then run this setup again.[/yellow]")
        console.print("[cyan]Run: gmail-copy-tool setup[/cyan]")
        raise typer.Exit(0)
    
    # Add accounts loop
    while True:
        console.print("\n[bold]Add a new account[/bold]")
        
        # Get account details
        email = Prompt.ask("Gmail address", default="")
        if not email or "@" not in email:
            console.print("[red]Invalid email address.[/red]")
            continue
        
        nickname = Prompt.ask(
            "Nickname for this account (e.g., 'work', 'archive1')",
            default=email.split("@")[0]
        )
        
        credentials_path = Prompt.ask(
            "Path to credentials JSON file",
            default="credentials.json"
        )
        
        # Validate credentials file exists
        if not Path(credentials_path).exists():
            console.print(f"[red]Error: File not found: {credentials_path}[/red]")
            continue
        
        # Generate token path
        token_filename = f"token_{nickname}.json"
        token_path = str(config_manager.config_dir / token_filename)
        
        console.print(f"\n[cyan]Authenticating {email}...[/cyan]")
        console.print("[yellow]A browser window will open for OAuth authorization.[/yellow]")
        
        try:
            # Ensure token (will open browser for OAuth)
            ensure_token(token_path, credentials_path, SCOPES)
            
            # Save to config
            config_manager.add_account(nickname, email, credentials_path, token_path)
            
            console.print(f"[green]✓ Account '{nickname}' ({email}) configured successfully![/green]")
        
        except Exception as e:
            console.print(f"[red]Error during authentication: {e}[/red]")
            continue
        
        # Ask to add another
        add_another = Confirm.ask("\nAdd another account?", default=False)
        if not add_another:
            break
    
    # Show final summary
    console.print("\n[bold green]Setup complete![/bold green]\n")
    console.print("Your configured accounts:")
    config_manager.display_accounts()
    
    console.print("\n[cyan]You can now use simple commands like:[/cyan]")
    console.print(f"  gmail-copy-tool copy {nickname} <target-nickname>")
    console.print(f"  gmail-copy-tool analyze {nickname}")
    console.print("  gmail-copy-tool list")
