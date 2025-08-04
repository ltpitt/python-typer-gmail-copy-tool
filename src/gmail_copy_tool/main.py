import typer
from gmail_copy_tool.commands import analyze

app = typer.Typer()
app.add_typer(analyze.app, name="analyze")

@app.command()
def hello():
    """Say hello!"""
    print("Hello from gmail-copy-tool!")

if __name__ == "__main__":
    app()
