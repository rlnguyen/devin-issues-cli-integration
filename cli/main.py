"""
Devin GitHub Issues CLI

Command-line interface for managing GitHub issues with Devin AI.

Usage:
    python -m cli.main list python/cpython --label bug
    python -m cli.main scope owner/repo 123
    python -m cli.main execute owner/repo 123
"""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.text import Text
import httpx
from datetime import datetime

from app.config import settings

# Create Typer app
app = typer.Typer(
    name="devin-issues",
    help="🤖 Devin GitHub Issues Automation CLI",
    add_completion=False,
)

console = Console()

# Default orchestrator URL
DEFAULT_ORCHESTRATOR_URL = f"http://{settings.orchestrator_host}:{settings.orchestrator_port}"


def get_label_color(label_name: str) -> str:
    """
    Return a color for a label based on its type.
    
    Red: Bugs and Errors
    Blue: Features and improvements
    Cyan: Documentation
    Green: Simple (Junior-dev) issues
    Bold-red: Critical Issues
    Yellow: Unassigned
    """
    label_lower = label_name.lower()
    
    # Bugs and errors
    if any(word in label_lower for word in ["bug", "error", "crash", "fail"]):
        return "red"
    # Features and enhancements
    elif any(word in label_lower for word in ["feature", "enhancement", "improve"]):
        return "blue"
    # Documentation
    elif any(word in label_lower for word in ["doc", "documentation"]):
        return "cyan"
    # Good first issues
    elif any(word in label_lower for word in ["good first", "beginner", "easy"]):
        return "green"
    # High priority
    elif any(word in label_lower for word in ["critical", "urgent", "high"]):
        return "bold red"
    else:
        return "yellow"


def format_time_ago(dt: datetime) -> str:
    """
    Format a datetime as 'X days ago' or 'X hours ago'.
    
    Unique feature: Human-readable time display!
    """
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds >= 3600:
        hours = diff.seconds // 3600
        return f"{hours}h ago"
    else:
        minutes = diff.seconds // 60
        return f"{minutes}m ago"


@app.command()
def list(
    repo: str = typer.Argument(..., help="Repository in 'owner/repo' format"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Filter by label"),
    state: str = typer.Option("open", "--state", "-s", help="Issue state: open, closed, or all"),
    per_page: int = typer.Option(30, "--per-page", "-n", help="Number of issues to show (max 100)"),
    url: str = typer.Option(DEFAULT_ORCHESTRATOR_URL, "--url", "-u", help="Orchestrator URL"),
):
    """
    📋 List GitHub issues with smart filtering.
    
    Examples:
        devin-issues list python/cpython --label type-bug
        devin-issues list facebook/react --state all -n 50
    """
    # Parse owner/repo
    try:
        owner, repo_name = repo.split("/")
    except ValueError:
        console.print("❌ [red]Invalid repo format. Use: owner/repo[/red]")
        raise typer.Exit(1)
    
    # Show what we're fetching
    console.print(f"\n🔍 Fetching issues from [bold cyan]{owner}/{repo_name}[/bold cyan]")
    if label:
        console.print(f"   Filtered by label: [yellow]{label}[/yellow]")
    console.print(f"   State: [magenta]{state}[/magenta]\n")
    
    # Make API request
    try:
        params = {
            "state": state,
            "per_page": per_page,
        }
        if label:
            params["labels"] = label
        
        response = httpx.get(
            f"{url}/api/v1/issues/{owner}/{repo_name}",
            params=params,
            timeout=30.0
        )
        response.raise_for_status()
        issues = response.json()
        
    except httpx.HTTPError as e:
        console.print(f"❌ [red]Failed to fetch issues: {e}[/red]")
        raise typer.Exit(1)
    
    # Show results
    if not issues:
        console.print("📭 [yellow]No issues found matching your criteria.[/yellow]")
        return
    
    # Show summary statistics
    summary_panel = Panel(
        f"[bold green]{len(issues)}[/bold green] issues found\n"
        f"Repository: [cyan]{owner}/{repo_name}[/cyan]\n"
        f"Filter: [yellow]{label or 'none'}[/yellow]",
        title="📊 Summary",
        border_style="green"
    )
    console.print(summary_panel)
    console.print()
    
    # Create table
    table = Table(
        title=f"Issues for {owner}/{repo_name}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    
    table.add_column("#", style="cyan", width=8)
    table.add_column("Title", style="white", no_wrap=False)
    table.add_column("Labels", style="yellow", width=25)
    table.add_column("Comments", justify="right", style="blue", width=10)
    table.add_column("Updated", justify="right", style="dim", width=12)
    
    # Add rows
    for issue in issues:
        # Format issue number
        issue_num = f"#{issue['number']}"
        
        # Format title based on state
        emoji = "✅" if issue['state'] == "closed" else "🔴"
        title = f"{emoji} {issue['title']}"
        
        # Color-coded labels
        labels = issue.get('labels', [])
        if labels:
            label_texts = []
            for lbl in labels[:3]:  # Show max 3 labels
                color = get_label_color(lbl['name'])
                label_texts.append(f"[{color}]{lbl['name']}[/{color}]")
            labels_str = " ".join(label_texts)
            if len(labels) > 3:
                labels_str += f" [dim]+{len(labels)-3}[/dim]"
        else:
            labels_str = "[dim]none[/dim]"
        
        # Comment count
        comments_str = str(issue.get('comments', 0))
        
        # ime ago instead of raw date
        updated_at = datetime.fromisoformat(issue['updated_at'].replace('Z', '+00:00'))
        time_ago = format_time_ago(updated_at)
        
        table.add_row(
            issue_num,
            title,
            labels_str,
            comments_str,
            time_ago
        )
    
    console.print(table)
    console.print(f"\n💡 [dim]Tip: Use 'devin-issues scope {owner}/{repo_name} <issue_number>' to analyze an issue[/dim]\n")


@app.command()
def scope(
    repo: str = typer.Argument(..., help="Repository in 'owner/repo' format"),
    issue_number: int = typer.Argument(..., help="Issue number to scope"),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Wait for scoping to complete"),
    url: str = typer.Option(DEFAULT_ORCHESTRATOR_URL, "--url", "-u", help="Orchestrator URL"),
):
    """
    🔍 Scope an issue using Devin AI (To-Do).
    
    Devin will analyze the issue and provide:
    - Implementation plan
    - Confidence score
    - Risk assessment
    - Estimated effort
    """
    console.print(f"\n🔍 [yellow]To-do![/yellow]")
    console.print(f"   Will scope: [cyan]{repo}#{issue_number}[/cyan]\n")


@app.command()
def execute(
    repo: str = typer.Argument(..., help="Repository in 'owner/repo' format"),
    issue_number: int = typer.Argument(..., help="Issue number to execute"),
    wait: bool = typer.Option(False, "--wait/--no-wait", help="Wait for execution to complete"),
    url: str = typer.Option(DEFAULT_ORCHESTRATOR_URL, "--url", "-u", help="Orchestrator URL"),
):
    """
    🚀 Execute an issue using Devin AI (To-do).
    
    Devin will:
    - Create a feature branch
    - Implement the fix
    - Run tests
    - Open a Pull Request
    """
    console.print(f"\n🚀 [yellow]To-do![/yellow]")
    console.print(f"   Will execute: [cyan]{repo}#{issue_number}[/cyan]\n")


@app.command()
def status(
    session_id: Optional[str] = typer.Argument(None, help="Session ID to check"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Filter by repository"),
    issue: Optional[int] = typer.Option(None, "--issue", "-i", help="Filter by issue number"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum sessions to show"),
    url: str = typer.Option(DEFAULT_ORCHESTRATOR_URL, "--url", "-u", help="Orchestrator URL"),
):
    """
    📊 Check status of Devin sessions (To-do).
    
    View all sessions or get details of a specific session.
    """
    console.print(f"\n📊 [yellow]Status command coming in Phase 4![/yellow]")
    if session_id:
        console.print(f"   Will check session: [cyan]{session_id}[/cyan]\n")
    else:
        console.print(f"   Will list recent sessions\n")


@app.command()
def version():
    """Show version information."""
    console.print("\n[bold cyan]Devin GitHub Issues CLI[/bold cyan]")
    console.print(f"Version: [green]0.1.0[/green]")
    console.print(f"Orchestrator: [yellow]{DEFAULT_ORCHESTRATOR_URL}[/yellow]")
    console.print()


if __name__ == "__main__":
    app()

