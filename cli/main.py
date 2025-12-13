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
    List GitHub issues with smart filtering.
    
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
        
        # GET all issues from repo/name
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
        
        # Time ago instead of raw date
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
    Scope an issue using Devin AI.
    
    Devin will analyze the issue and provide:
    - Implementation plan
    - Confidence score
    - Risk assessment
    - Estimated effort
    
    Examples:
        devin-issues scope python/cpython 12345
        devin-issues scope myorg/myrepo 42 --no-wait
    """
    # Parse owner/repo
    try:
        owner, repo_name = repo.split("/")
    except ValueError:
        console.print("❌ [red]Invalid repo format. Use: owner/repo[/red]")
        raise typer.Exit(1)
    
    # Show what we're doing
    console.print(f"\n🔍 Scoping issue [bold cyan]{owner}/{repo_name}#{issue_number}[/bold cyan]")
    console.print()
    
    # Make API request
    try:
        with console.status("[bold green]Running Devin session...", spinner="dots"):
            response = httpx.post(
                f"{url}/api/v1/scope/{owner}/{repo_name}/{issue_number}",
                params={"wait": wait},
                timeout=None if wait else 30.0,  # No timeout if waiting
            )
            response.raise_for_status()
            data = response.json()
        
    except httpx.HTTPError as e:
        console.print(f"❌ [red]Failed to scope issue: {e}[/red]")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                console.print(f"   [dim]{error_detail.get('detail', {}).get('message', '')}[/dim]")
            except:
                pass
        raise typer.Exit(1)
    
    # Display results
    session_id = data.get("session_id")
    session_url = data.get("url")
    issue_info = data.get("issue", {})
    
    # Show session info
    console.print(f"✅ Session created: [cyan]{session_id}[/cyan]")
    if session_url:
        console.print(f"🔗 View session: [link={session_url}]{session_url}[/link]")
    console.print()
    
    # If not waiting, show message and exit
    if not wait:
        console.print("🤖 [yellow]Devin is analyzing the issue in the background.[/yellow]")
        console.print(f"   Use [cyan]devin-issues status {session_id}[/cyan] to check progress")
        console.print()
        return
    
    # If waiting and we have scoping results
    scoping = data.get("scoping")
    if not scoping:
        console.print("⚠️  [yellow]No scoping results available yet[/yellow]")
        return
    
    # Display scoping results
    console.print("=" * 80)
    console.print()
    
    # Summary
    summary_panel = Panel(
        scoping.get("summary", "No summary available"),
        title="📝 Summary",
        border_style="cyan"
    )
    console.print(summary_panel)
    console.print()
    
    # Confidence and metrics
    confidence = scoping.get("confidence", 0.0)
    confidence_pct = int(confidence * 100)
    
    # Color code confidence
    if confidence_pct >= 80:
        confidence_color = "bold green"
        confidence_emoji = "🟢"
    elif confidence_pct >= 60:
        confidence_color = "yellow"
        confidence_emoji = "🟡"
    else:
        confidence_color = "red"
        confidence_emoji = "🔴"
    
    metrics_text = f"""[bold]Confidence Score:[/bold] [{confidence_color}]{confidence_emoji} {confidence_pct}%[/{confidence_color}]
[bold]Risk Level:[/bold] {scoping.get('risk_level', 'unknown').upper()}
[bold]Estimated Effort:[/bold] {scoping.get('estimated_effort', 0)} hours"""
    
    metrics_panel = Panel(
        metrics_text,
        title="📊 Metrics",
        border_style="green"
    )
    console.print(metrics_panel)
    console.print()
    
    # Implementation plan
    plan = scoping.get("plan", [])
    if plan:
        console.print("[bold magenta]📋 Implementation Plan:[/bold magenta]")
        console.print()
        for i, step in enumerate(plan, 1):
            console.print(f"  [cyan]{i}.[/cyan] {step}")
        console.print()
    
    console.print("=" * 80)
    console.print()
    
    # Suggest next steps
    if confidence_pct >= 70:
        console.print(f"💡 [green]High confidence! Consider executing:[/green]")
        console.print(f"   [cyan]devin-issues execute {owner}/{repo_name} {issue_number}[/cyan]")
    else:
        console.print(f"💡 [yellow]Low confidence. Review the plan carefully before executing.[/yellow]")
    
    console.print()


@app.command()
def execute(
    repo: str = typer.Argument(..., help="Repository in 'owner/repo' format"),
    issue_number: int = typer.Argument(..., help="Issue number to execute"),
    wait: bool = typer.Option(False, "--wait/--no-wait", help="Wait for execution to complete (NOT recommended)"),
    url: str = typer.Option(DEFAULT_ORCHESTRATOR_URL, "--url", "-u", help="Orchestrator URL"),
):
    """
    Execute an issue using Devin AI.
    
    Devin will:
    - Create a feature branch
    - Implement the fix
    - Run tests
    - Open a Pull Request
    
    NOTE: Execution takes 10-30 minutes or longer. Using --no-wait is recommended.
    
    Examples:
        devin-issues execute python/cpython 12345
        devin-issues execute myorg/myrepo 42 --wait
    """
    # Parse owner/repo
    try:
        owner, repo_name = repo.split("/")
    except ValueError:
        console.print("❌ [red]Invalid repo format. Use: owner/repo[/red]")
        raise typer.Exit(1)
    
    # Show what we're doing
    console.print(f"\n🚀 Executing issue [bold cyan]{owner}/{repo_name}#{issue_number}[/bold cyan]")
    console.print()
    
    if wait:
        console.print("⚠️  [yellow]Warning: Execution can take 10-30 minutes or longer, terminal will hang until it completes![/yellow]")
        console.print()
    
    # Make API request
    try:
        with console.status("[bold green]Creating execution session...", spinner="dots"):
            response = httpx.post(
                f"{url}/api/v1/execute/{owner}/{repo_name}/{issue_number}",
                params={"wait": wait},
                timeout=None if wait else 30.0,
            )
            response.raise_for_status()
            data = response.json()
        
    except httpx.HTTPError as e:
        console.print(f"❌ [red]Failed to execute issue: {e}[/red]")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                console.print(f"   [dim]{error_detail.get('detail', {}).get('message', '')}[/dim]")
            except:
                pass
        raise typer.Exit(1)
    
    # Display results
    session_id = data.get("session_id")
    session_url = data.get("url")
    issue_info = data.get("issue", {})
    
    # Show session info
    console.print(f"✅ Execution session created: [cyan]{session_id}[/cyan]")
    if session_url:
        console.print(f"🔗 View session: [link={session_url}]{session_url}[/link]")
    console.print()
    
    # If not waiting, show message and exit
    if not wait:
        console.print("🤖 [yellow]Devin is implementing the fix in the background.[/yellow]")
        console.print()
        console.print("📝 [bold]What Devin will do:[/bold]")
        console.print("   1. Clone the repository (if not already cloned)")
        console.print("   2. Create a feature branch")
        console.print("   3. Implement the fix")
        console.print("   4. Run tests")
        console.print("   5. Open a Pull Request")
        console.print()
        console.print(f"🔍 Track progress at: {session_url}")
        console.print()
        console.print(f"💡 Check status: [cyan]devin-issues status {session_id}[/cyan]")
        console.print()
        return
    
    # If waiting and we have execution results
    execution = data.get("execution")
    if not execution:
        console.print("⚠️  [yellow]Execution session completed but no results available yet[/yellow]")
        console.print(f"   Check: {session_url}")
        return
    
    # Display execution results
    console.print("=" * 80)
    console.print()
    
    # Status
    exec_status = execution.get("status", "unknown")
    if exec_status.lower() in ["done", "completed", "finished"]:
        status_emoji = "✅"
        status_color = "green"
    elif exec_status.lower() in ["failed", "error"]:
        status_emoji = "❌"
        status_color = "red"
    else:
        status_emoji = "⏸️"
        status_color = "yellow"
    
    console.print(f"{status_emoji} [bold {status_color}]Status: {exec_status.upper()}[/bold {status_color}]")
    console.print()
    
    # Branch and PR
    branch = execution.get("branch")
    pr_url = execution.get("pr_url")
    
    if branch:
        console.print(f"🌿 [bold]Branch:[/bold] [cyan]{branch}[/cyan]")
    
    if pr_url:
        console.print(f"🔗 [bold]Pull Request:[/bold] [link={pr_url}]{pr_url}[/link]")
        console.print()
    
    # Test results
    tests_passed = execution.get("tests_passed", 0)
    tests_failed = execution.get("tests_failed", 0)
    
    if tests_passed or tests_failed:
        total_tests = tests_passed + tests_failed
        pass_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0
        
        console.print(f"🧪 [bold]Test Results:[/bold]")
        console.print(f"   ✅ Passed: [green]{tests_passed}[/green]")
        console.print(f"   ❌ Failed: [red]{tests_failed}[/red]")
        console.print(f"   📊 Pass Rate: {pass_rate:.1f}%")
        console.print()
    
    console.print("=" * 80)
    console.print()
    
    # Next steps
    if pr_url:
        console.print(f"💡 [green]Review and merge the PR:[/green] {pr_url}")
    else:
        console.print(f"💡 [yellow]Check the session for details:[/yellow] {session_url}")
    
    console.print()


@app.command()
def status(
    session_id: Optional[str] = typer.Argument(None, help="Session ID to check (optional)"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Filter by repository (owner/repo)"),
    issue: Optional[int] = typer.Option(None, "--issue", "-i", help="Filter by issue number (requires --repo)"),
    phase: Optional[str] = typer.Option(None, "--phase", "-p", help="Filter by phase (scope or exec)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum sessions to show"),
    url: str = typer.Option(DEFAULT_ORCHESTRATOR_URL, "--url", "-u", help="Orchestrator URL"),
):
    """
    Check status of Devin sessions.
    
    View all sessions or get details of a specific session.
    
    Examples:
        devin-issues status                               # List all recent sessions
        devin-issues status SESSION_ID                    # Check specific session
        devin-issues status --repo python/cpython         # Filter by repo
        devin-issues status --repo myorg/myrepo -i 42     # Filter by issue
        devin-issues status --phase scope                 # Only scoping sessions
    """
    if session_id:
        # Get details of specific session
        console.print(f"\n🔍 Fetching session [cyan]{session_id}[/cyan]...\n")
        
        try:
            response = httpx.get(
                f"{url}/api/v1/sessions/{session_id}",
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            console.print(f"❌ [red]Failed to fetch session: {e}[/red]")
            raise typer.Exit(1)
        
        # Display session details
        console.print(f"[bold]Session ID:[/bold] {data.get('session_id')}")
        console.print(f"[bold]Status:[/bold] {data.get('status', 'unknown')}")
        
        if data.get('phase'):
            console.print(f"[bold]Phase:[/bold] {data.get('phase')}")
        
        if data.get('repo'):
            console.print(f"[bold]Repository:[/bold] {data.get('repo')}")
        
        if data.get('issue_number'):
            console.print(f"[bold]Issue:[/bold] #{data.get('issue_number')}")
        
        if data.get('url'):
            console.print(f"[bold]URL:[/bold] [link={data.get('url')}]{data.get('url')}[/link]")
        
        if data.get('created_at'):
            console.print(f"[bold]Created:[/bold] {data.get('created_at')}")
        
        if data.get('completed_at'):
            console.print(f"[bold]Completed:[/bold] {data.get('completed_at')}")
        
        # Show scoping results if available
        scoping = data.get('scoping')
        if scoping:
            console.print()
            console.print("[bold cyan]📋 Scoping Results:[/bold cyan]")
            console.print(f"  Confidence: {scoping.get('confidence', 0) * 100:.0f}%")
            console.print(f"  Risk Level: {scoping.get('risk_level', 'unknown').upper()}")
            console.print(f"  Estimated Effort: {scoping.get('estimated_effort', 0)} hours")
        
        # Show execution results if available
        execution = data.get('execution')
        if execution:
            console.print()
            console.print("[bold green]🚀 Execution Results:[/bold green]")
            if execution.get('pr_url'):
                console.print(f"  PR: {execution.get('pr_url')}")
            if execution.get('branch'):
                console.print(f"  Branch: {execution.get('branch')}")
            if execution.get('tests_passed') is not None:
                console.print(f"  Tests Passed: {execution.get('tests_passed')}")
                console.print(f"  Tests Failed: {execution.get('tests_failed')}")
        
        console.print()
        
    else:
        # List all sessions with filters
        console.print("\n📊 Fetching sessions...\n")
        
        try:
            params = {"limit": limit}
            if repo:
                params["repo"] = repo
            if issue:
                params["issue_number"] = issue
            if phase:
                params["phase"] = phase
            
            response = httpx.get(
                f"{url}/api/v1/sessions",
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            console.print(f"❌ [red]Failed to fetch sessions: {e}[/red]")
            raise typer.Exit(1)
        
        sessions = data.get("sessions", [])
        
        if not sessions:
            console.print("📭 [yellow]No sessions found matching your criteria.[/yellow]\n")
            return
        
        # Create table
        table = Table(
            title=f"Recent Sessions ({data.get('total')} found)",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        
        table.add_column("Session ID", style="cyan", width=20)
        table.add_column("Repo", style="white", width=25)
        table.add_column("Issue", justify="right", style="yellow", width=8)
        table.add_column("Phase", style="blue", width=8)
        table.add_column("Status", style="green", width=10)
        table.add_column("Confidence", justify="right", style="cyan", width=12)
        table.add_column("Created", style="dim", width=12)
        
        for session in sessions:
            session_id_short = session['session_id'][:20] + "..."
            repo_name = session.get('repo', 'unknown')
            issue_num = f"#{session.get('issue_number', '?')}"
            phase_display = session.get('phase', '?')
            status_display = session.get('status', 'unknown')
            
            # Confidence (for scope sessions)
            confidence = session.get('confidence')
            if confidence:
                conf_pct = int(confidence * 100)
                if conf_pct >= 80:
                    confidence_display = f"[green]{conf_pct}%[/green]"
                elif conf_pct >= 60:
                    confidence_display = f"[yellow]{conf_pct}%[/yellow]"
                else:
                    confidence_display = f"[red]{conf_pct}%[/red]"
            else:
                confidence_display = "[dim]-[/dim]"
            
            # Format created date
            created = session.get('created_at', '')
            if created:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    created_display = dt.strftime('%m/%d %H:%M')
                except:
                    created_display = created[:10]
            else:
                created_display = "unknown"
            
            table.add_row(
                session_id_short,
                repo_name,
                issue_num,
                phase_display,
                status_display,
                confidence_display,
                created_display
            )
        
        console.print(table)
        console.print(f"\n💡 [dim]Use 'devin-issues status SESSION_ID' for details[/dim]\n")


@app.command()
def version():
    """Show version information."""
    console.print("\n[bold cyan]Devin GitHub Issues CLI[/bold cyan]")
    console.print(f"Version: [green]0.1.0[/green]")
    console.print(f"Orchestrator: [yellow]{DEFAULT_ORCHESTRATOR_URL}[/yellow]")
    console.print()


if __name__ == "__main__":
    app()

