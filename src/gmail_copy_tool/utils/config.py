"""Configuration manager for Gmail Copy Tool accounts."""
import json
import os
from pathlib import Path
from typing import Dict, Optional
import typer
from rich.console import Console
from rich.table import Table

console = Console()


class ConfigManager:
    """Manage account configurations for Gmail Copy Tool."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize config manager.
        
        Args:
            config_dir: Custom config directory (mainly for testing).
                       Defaults to ~/.gmail-copy-tool/
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / ".gmail-copy-tool"
        
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_dir()
    
    def _ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self) -> Dict:
        """Load configuration from file.
        
        Returns:
            Dictionary with accounts configuration.
        """
        if not self.config_file.exists():
            return {"accounts": {}}
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            console.print(f"[red]Error: Config file is corrupted: {self.config_file}[/red]")
            raise typer.Exit(1)
    
    def save_config(self, config: Dict):
        """Save configuration to file.
        
        Args:
            config: Configuration dictionary to save.
        """
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def add_account(self, nickname: str, email: str, credentials_path: str, token_path: str):
        """Add or update an account in the configuration.
        
        Args:
            nickname: Short name for the account (e.g., 'archive3')
            email: Gmail email address
            credentials_path: Path to OAuth credentials file
            token_path: Path to token file
        """
        config = self.load_config()
        
        # Store paths relative to config_dir if they're in config_dir
        credentials_path = str(Path(credentials_path).resolve())
        token_path = str(Path(token_path).resolve())
        
        config["accounts"][nickname] = {
            "email": email,
            "credentials": credentials_path,
            "token": token_path
        }
        
        self.save_config(config)
        console.print(f"[green]✓ Account '{nickname}' saved![/green]")
    
    def get_account(self, nickname: str) -> Optional[Dict]:
        """Get account configuration by nickname.
        
        Args:
            nickname: Account nickname
            
        Returns:
            Account configuration dict or None if not found.
        """
        config = self.load_config()
        return config["accounts"].get(nickname)
    
    def list_accounts(self) -> Dict:
        """Get all configured accounts.
        
        Returns:
            Dictionary of all accounts.
        """
        config = self.load_config()
        return config.get("accounts", {})
    
    def remove_account(self, nickname: str):
        """Remove an account from configuration.
        
        Args:
            nickname: Account nickname to remove
        """
        config = self.load_config()
        if nickname in config["accounts"]:
            del config["accounts"][nickname]
            self.save_config(config)
            console.print(f"[green]✓ Account '{nickname}' removed![/green]")
        else:
            console.print(f"[yellow]Account '{nickname}' not found.[/yellow]")
    
    def resolve_account(self, nickname_or_email: str) -> Dict:
        """Resolve account by nickname or email.
        
        This method provides flexibility for both new (nickname) and
        old (direct email) usage patterns.
        
        Args:
            nickname_or_email: Account nickname or email address
            
        Returns:
            Account configuration with 'email', 'credentials', 'token'
            
        Raises:
            typer.Exit: If account not found
        """
        # Try as nickname first
        account = self.get_account(nickname_or_email)
        if account:
            return account
        
        # Check if it looks like an email
        if "@" in nickname_or_email:
            console.print(f"[yellow]Warning: '{nickname_or_email}' is not configured.[/yellow]")
            console.print("[yellow]Run 'gmail-copy-tool setup' to configure accounts.[/yellow]")
            console.print(f"[yellow]Or use 'gmail-copy-tool list' to see configured accounts.[/yellow]")
            raise typer.Exit(1)
        
        # Not found
        console.print(f"[red]Error: Account '{nickname_or_email}' not found.[/red]")
        console.print("[yellow]Run 'gmail-copy-tool list' to see configured accounts.[/yellow]")
        raise typer.Exit(1)
    
    def display_accounts(self):
        """Display all configured accounts in a nice table."""
        accounts = self.list_accounts()
        
        if not accounts:
            console.print("[yellow]No accounts configured yet.[/yellow]")
            console.print("[cyan]Run 'gmail-copy-tool setup' to add accounts.[/cyan]")
            return
        
        table = Table(title="Configured Gmail Accounts", show_header=True, header_style="bold cyan")
        table.add_column("Nickname", style="cyan")
        table.add_column("Email", style="green")
        table.add_column("Status", style="yellow")
        
        for nickname, account in accounts.items():
            # Check if token file exists
            token_exists = Path(account["token"]).exists()
            status = "✓ Ready" if token_exists else "✗ Need OAuth"
            
            table.add_row(nickname, account["email"], status)
        
        console.print(table)
    
    def add_account_directly(self, nickname: str, email: str, credentials: str, token: str):
        """Add an account directly without validation (useful for testing).
        
        Args:
            nickname: Account nickname
            email: Gmail email address
            credentials: Path to credentials file
            token: Path to token file
        """
        config = self.load_config()
        
        if "accounts" not in config:
            config["accounts"] = {}
        
        config["accounts"][nickname] = {
            "email": email,
            "credentials": credentials,
            "token": token
        }
        
        self.save_config(config)
