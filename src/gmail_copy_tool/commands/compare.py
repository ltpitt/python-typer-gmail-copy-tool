import typer
import logging
from gmail_copy_tool.core.gmail_client import GmailClient

app = typer.Typer()
logger = logging.getLogger(__name__)

@app.command()


    source: str = typer.Option(..., help="Source Gmail account email address"),
    target: str = typer.Option(..., help="Target Gmail account email address"),
    credentials_source: str = typer.Option("credentials_source.json", help="Path to source account credentials file (default: credentials_source.json)"),
    credentials_target: str = typer.Option("credentials_target.json", help="Path to target account credentials file (default: credentials_target.json)")
):
    """Compare source and target Gmail accounts to verify all emails have been copied."""
    typer.echo(f"Comparing accounts: {source} -> {target}")
    try:
        source_client = GmailClient(source, credentials_path=credentials_source)
        target_client = GmailClient(target, credentials_path=credentials_target)

        # Fetch all message IDs from both accounts
        source_ids = set(_get_all_message_ids(source_client))
        target_ids = set(_get_all_message_ids(target_client))

        missing_in_target = source_ids - target_ids
        extra_in_target = target_ids - source_ids

        typer.echo(f"Total in source: {len(source_ids)}")
        typer.echo(f"Total in target: {len(target_ids)}")
        typer.echo(f"Missing in target: {len(missing_in_target)}")
        typer.echo(f"Extra in target: {len(extra_in_target)}")

        if missing_in_target:
            typer.secho("Messages missing in target:", fg=typer.colors.RED, bold=True)
            for msg_id in list(missing_in_target)[:20]:
                typer.echo(f"- {msg_id}")
            if len(missing_in_target) > 20:
                typer.echo(f"...and {len(missing_in_target) - 20} more.")
        else:
            typer.secho("All source messages found in target.", fg=typer.colors.GREEN, bold=True)

        if extra_in_target:
            typer.secho("Messages in target not found in source:", fg=typer.colors.YELLOW)
            for msg_id in list(extra_in_target)[:20]:
                typer.echo(f"- {msg_id}")
            if len(extra_in_target) > 20:
                typer.echo(f"...and {len(extra_in_target) - 20} more.")
        else:
            typer.secho("No extra messages in target.", fg=typer.colors.GREEN)

    except typer.Exit:
        pass
    except Exception as e:
        logger.exception(f"Error during compare: {e}")
        typer.secho(f"ERROR: {str(e)}", fg=typer.colors.RED, bold=True)
def _get_all_message_ids(client):
    """Fetch all message IDs from a GmailClient."""
    service = client.service
    user_id = "me"
    message_ids = []
    page_token = None
    while True:
        try:
            results = service.users().messages().list(userId=user_id, pageToken=page_token, includeSpamTrash=False).execute()
            messages = results.get("messages", [])
            message_ids.extend(msg["id"] for msg in messages)
            page_token = results.get("nextPageToken")
            if not page_token:
                break
        except Exception as e:
            logger.error(f"Failed to fetch message IDs: {e}")
            break
    return message_ids
