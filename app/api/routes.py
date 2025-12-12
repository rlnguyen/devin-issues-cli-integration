"""
API Routes

This module contains all API endpoints for the Devin GitHub Issues CLI.

Endpoints:
- GET /api/v1/issues/{owner}/{repo} - List issues from a repository
- POST /api/v1/scope/{owner}/{repo}/{issue_number} - Scope an issue (To-do)
- POST /api/v1/execute/{owner}/{repo}/{issue_number} - Execute an issue (To-d0)
- GET /api/v1/sessions - List all sessions (To-do)
- GET /api/v1/sessions/{session_id} - Get session details (To-do)
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from app.clients.github_client import GitHubClient, GitHubAPIError
from app.pyd_models.github_models import GitHubIssue

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get("/issues/{owner}/{repo}", response_model=List[GitHubIssue])
async def list_issues(
    owner: str,
    repo: str,
    labels: Optional[str] = Query(None, description="Comma-separated label names (e.g., 'bug,help wanted')"),
    state: str = Query("open", description="Issue state: 'open', 'closed', or 'all'"),
    assignee: Optional[str] = Query(None, description="Filter by assignee username"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    per_page: int = Query(30, ge=1, le=100, description="Results per page (max 100)")
):
    """
    List issues from a GitHub repository.
    
    This endpoint fetches issues from GitHub with optional filtering.
    
    **Parameters:**
    - **owner**: Repository owner (user or organization)
    - **repo**: Repository name
    - **labels**: Filter by labels (comma-separated)
    - **state**: Filter by state (open/closed/all)
    - **assignee**: Filter by assignee username
    - **page**: Page number for pagination
    - **per_page**: Number of results per page (max 100)
    
    **Returns:**
    - List of GitHub issues with all metadata
    
    **Example:**
    ```
    GET /api/v1/issues/python/cpython?labels=type-bug&state=open&per_page=10
    ```
    """
    logger.info(f"📋 Fetching issues: {owner}/{repo} (labels={labels}, state={state})")
    
    try:
        # Create GitHub client
        github_client = GitHubClient()
        
        # Fetch issues
        issues = github_client.list_issues(
            owner=owner,
            repo=repo,
            labels=labels,
            state=state,
            assignee=assignee,
            page=page,
            per_page=per_page
        )
        
        logger.info(f"✅ Found {len(issues)} issues for {owner}/{repo}")
        
        return issues
        
    except GitHubAPIError as e:
        logger.error(f"❌ GitHub API error: {e}")
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": "GitHub API Error",
                "message": e.message,
                "owner": owner,
                "repo": repo
            }
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": str(e)
            }
        )


@router.get("/issues/{owner}/{repo}/{issue_number}", response_model=GitHubIssue)
async def get_issue(
    owner: str,
    repo: str,
    issue_number: int
):
    """
    Get details of a specific GitHub issue.
    
    **Parameters:**
    - **owner**: Repository owner
    - **repo**: Repository name
    - **issue_number**: Issue number
    
    **Returns:**
    - Full issue details including title, body, labels, comments count, etc.
    
    **Example:**
    ```
    GET /api/v1/issues/python/cpython/12345
    ```
    """
    logger.info(f"🔍 Fetching issue: {owner}/{repo}#{issue_number}")
    
    try:
        github_client = GitHubClient()
        issue = github_client.get_issue(owner, repo, issue_number)
        
        logger.info(f"✅ Found issue #{issue_number}: {issue.title}")
        
        return issue
        
    except GitHubAPIError as e:
        logger.error(f"❌ GitHub API error: {e}")
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": "GitHub API Error",
                "message": e.message,
                "owner": owner,
                "repo": repo,
                "issue_number": issue_number
            }
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Server Error",
                "message": str(e)
            }
        )


# Placeholder endpoints for Devin integration functions

@router.post("/scope/{owner}/{repo}/{issue_number}")
async def scope_issue(owner: str, repo: str, issue_number: int):
    """
    Scope an issue using Devin.
    
    This endpoint will:
    1. Fetch the issue from GitHub
    2. Create a Devin session to analyze the issue
    3. Return implementation plan and confidence score
    
    """
    raise HTTPException(
        status_code=501,
        detail="To-do"
    )


@router.post("/execute/{owner}/{repo}/{issue_number}")
async def execute_issue(owner: str, repo: str, issue_number: int):
    """
    Execute an issue using Devin.
    
    This endpoint will:
    1. Fetch the issue from GitHub
    2. Create a Devin session to implement the fix
    3. Return session ID and PR URL when complete

    """
    raise HTTPException(
        status_code=501,
        detail="To-do"
    )


@router.get("/sessions")
async def list_sessions():
    """
    List all Devin sessions.
    """
    raise HTTPException(
        status_code=501,
        detail="To-do"
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Get details of a specific Devin session (Phase 4).
    """
    raise HTTPException(
        status_code=501,
        detail="To-do"
    )

