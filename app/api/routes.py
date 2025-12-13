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

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from typing import List, Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.clients.github_client import GitHubClient, GitHubAPIError
from app.clients.devin_client import DevinClient, DevinAPIError
from app.pyd_models.github_models import GitHubIssue
from app.pyd_models.devin_models import ScopingOutput, SessionResponse
from app.database import get_db
from app.models import get_or_create_issue, create_session_record, log_event, DevinSession, Issue

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


# Devin Integration Endpoints

@router.post("/scope/{owner}/{repo}/{issue_number}")
async def scope_issue(
    owner: str,
    repo: str,
    issue_number: int,
    wait: bool = Query(
        True,
        description="Wait for scoping to complete (True) or return session ID immediately (False)"
    ),
    db: Session = Depends(get_db),
):
    """
    🔍 Scope an issue using Devin AI.
    
    This endpoint:
    1. Fetches the issue and comments from GitHub
    2. Creates a Devin session to analyze the issue
    3. Optionally waits for Devin to complete the analysis
    4. Returns implementation plan, confidence score, and session details
    
    **Parameters:**
    - **owner**: Repository owner
    - **repo**: Repository name
    - **issue_number**: Issue number to scope
    - **wait**: If True, waits for Devin to complete (default). If False, returns session ID immediately.
    
    **Returns:**
    - Session metadata
    - Scoping output (if wait=True and session completes)
    
    **Example:**
    ```
    POST /api/v1/scope/python/cpython/12345?wait=true
    ```
    """
    logger.info(f"🔍 Scoping {owner}/{repo}#{issue_number} (wait={wait})")
    
    try:
        # Step 1: Fetch issue from GitHub
        github_client = GitHubClient()
        
        try:
            issue = github_client.get_issue(owner, repo, issue_number)
            logger.info(f"📋 Fetched issue: {issue.title}")
        except GitHubAPIError as e:
            logger.error(f"❌ GitHub error: {e}")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": "Failed to fetch issue from GitHub",
                    "message": e.message,
                    "owner": owner,
                    "repo": repo,
                    "issue_number": issue_number
                }
            )
        
        # Step 2: Get comments for additional context
        try:
            comments_obj = github_client.get_issue_comments(owner, repo, issue_number)
            comment_texts = [comment.body for comment in comments_obj[:10]]  # Max 10 comments for now
            logger.info(f"💬 Fetched {len(comment_texts)} comments")
        except Exception as e:
            logger.warning(f"⚠️  Failed to fetch comments: {e}")
            comment_texts = []
        
        # Step 3: Create Devin scoping session
        devin_client = DevinClient()
        
        try:
            session = devin_client.create_scoping_session(
                repo=f"{owner}/{repo}",
                issue_number=issue_number,
                issue_title=issue.title,
                issue_body=issue.body or "",
                comments=comment_texts,
            )
            logger.info(f"🤖 Devin session created: {session.session_id}")
            
            # Save to database
            try:
                # Get or create issue record
                issue_record, created = get_or_create_issue(
                    db,
                    owner=owner,
                    repo=repo,
                    issue_number=issue_number,
                    title=issue.title,
                    body=issue.body or "",
                    state=issue.state,
                    labels=[label.name for label in issue.labels],
                )
                
                # Create session record
                session_record = create_session_record(
                    db,
                    session_id=session.session_id,
                    phase="scope",
                    owner=owner,
                    repo=repo,
                    issue_number=issue_number,
                    session_url=session.url,
                    status=session.status,
                    issue_id=issue_record.id,
                )
                
                # Log event
                log_event(
                    db,
                    event_type="scope_started",
                    message=f"Started scoping {owner}/{repo}#{issue_number}",
                    owner=owner,
                    repo=repo,
                    issue_number=issue_number,
                    session_id=session.session_id,
                )
                
                logger.info(f"💾 Saved to database: session_id={session_record.id}")
            except Exception as e:
                logger.error(f"⚠️  Failed to save to database: {e}")
                # Continue even if database save fails
            
        except DevinAPIError as e:
            logger.error(f"❌ Devin API error: {e}")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": "Failed to create Devin session",
                    "message": e.message
                }
            )
        
        # Step 4: If wait=False, return session info immediately
        if not wait:
            return {
                "session_id": session.session_id,
                "status": session.status,
                "url": session.url,
                "message": "Session created. Use GET /api/v1/sessions/{session_id} to check progress.",
                "issue": {
                    "owner": owner,
                    "repo": repo,
                    "number": issue_number,
                    "title": issue.title
                }
            }
        
        # Step 5: If wait=True, poll until complete
        logger.info(f"⏳ Waiting for Devin to complete scoping...")
        
        try:
            completed_session = devin_client.poll_until_complete(
                session.session_id,
                timeout=1800,  # 30 minutes
            )
        except TimeoutError:
            logger.warning(f"⏱️ Session timed out")
            raise HTTPException(
                status_code=408,
                detail={
                    "error": "Session timeout",
                    "message": "Devin session did not complete within 30 minutes",
                    "session_id": session.session_id,
                    "session_url": session.url
                }
            )
        except DevinAPIError as e:
            logger.error(f"❌ Devin error during polling: {e}")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": "Error while waiting for Devin",
                    "message": e.message,
                    "session_id": session.session_id
                }
            )
        
        # Step 6: Parse scoping output
        scoping_output = devin_client.parse_scoping_output(completed_session)
        
        if not scoping_output:
            logger.warning("⚠️  No structured output available")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "No scoping output available",
                    "message": "Devin session completed but did not return structured output",
                    "session_id": session.session_id,
                    "session_url": completed_session.url
                }
            )
        
        # Step 7: Return results
        logger.info(f"✅ Scoping complete! Confidence: {scoping_output.confidence}")
        
        # Update database with results
        try:
            # Update issue record
            issue_record = db.query(Issue).filter(
                Issue.owner == owner,
                Issue.repo == repo,
                Issue.issue_number == issue_number
            ).first()
            
            if issue_record:
                issue_record.confidence = scoping_output.confidence
                issue_record.risk_level = scoping_output.risk_level
                issue_record.estimated_effort = scoping_output.estimated_effort
                issue_record.implementation_plan = scoping_output.plan
                issue_record.is_scoped = True
                issue_record.last_scoped_at = func.now()
            
            # Update session record
            session_record = db.query(DevinSession).filter(
                DevinSession.session_id == session.session_id
            ).first()
            
            if session_record:
                session_record.status = completed_session.status
                session_record.structured_output = completed_session.structured_output
                session_record.confidence = scoping_output.confidence
                session_record.risk_level = scoping_output.risk_level
                session_record.estimated_effort = scoping_output.estimated_effort
                session_record.completed_at = func.now()
            
            db.commit()
            
            # Log event
            log_event(
                db,
                event_type="scope_completed",
                message=f"Scoping completed for {owner}/{repo}#{issue_number} (confidence: {scoping_output.confidence})",
                owner=owner,
                repo=repo,
                issue_number=issue_number,
                session_id=session.session_id,
            )
            
            logger.info("💾 Updated database with scoping results")
        except Exception as e:
            logger.error(f"⚠️  Failed to update database: {e}")
        
        return {
            "session_id": completed_session.session_id,
            "status": completed_session.status,
            "url": completed_session.url,
            "issue": {
                "owner": owner,
                "repo": repo,
                "number": issue_number,
                "title": issue.title
            },
            "scoping": {
                "summary": scoping_output.summary,
                "plan": scoping_output.plan,
                "risk_level": scoping_output.risk_level,
                "estimated_effort": scoping_output.estimated_effort,
                "confidence": scoping_output.confidence,
            }
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"❌ Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "message": str(e)
            }
        )


@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    """
    Get details of a specific Devin session.
    
    This endpoint retrieves session status and results.
    """
    logger.info(f"📊 Fetching session {session_id}")
    
    try:
        devin_client = DevinClient()
        session = devin_client.get_session(session_id)
        
        # Try to parse scoping output if available
        scoping_output = None
        if session.structured_output:
            scoping_output = devin_client.parse_scoping_output(session)
        
        response = {
            "session_id": session.session_id,
            "status": session.status,
            "url": session.url,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }
        
        if scoping_output:
            response["scoping"] = {
                "summary": scoping_output.summary,
                "plan": scoping_output.plan,
                "risk_level": scoping_output.risk_level,
                "estimated_effort": scoping_output.estimated_effort,
                "confidence": scoping_output.confidence,
            }
        
        return response
        
    except DevinAPIError as e:
        logger.error(f"❌ Devin API error: {e}")
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": "Failed to fetch session",
                "message": e.message,
                "session_id": session_id
            }
        )


# Execution endpoint

@router.post("/execute/{owner}/{repo}/{issue_number}")
async def execute_issue(
    owner: str,
    repo: str,
    issue_number: int,
    wait: bool = Query(
        False,
        description="Wait for execution to complete (False recommended)"
    ),
):
    """
    🚀 Execute an issue using Devin AI.
    
    This endpoint:
    1. Fetches the issue from GitHub
    2. Optionally fetches the scoping plan if available
    3. Creates a Devin session to implement the fix
    4. Returns session ID (or waits for PR creation if wait=True)
    
    **Parameters:**
    - **owner**: Repository owner
    - **repo**: Repository name
    - **issue_number**: Issue number to execute
    - **wait**: If True, waits for execution (NOT recommended - can take 10-30 minutes, resulting in terminal hang)
    
    **Returns:**
    - Session metadata
    - Execution output (PR URL, branch, test results) if wait=True and session completes
    
    **Example:**
    ```
    POST /api/v1/execute/python/cpython/12345?wait=false
    ```
    """
    logger.info(f"🚀 Executing {owner}/{repo}#{issue_number} (wait={wait})")
    
    try:
        # Step 1: Fetch issue from GitHub
        github_client = GitHubClient()
        
        try:
            issue = github_client.get_issue(owner, repo, issue_number)
            logger.info(f"📋 Fetched issue: {issue.title}")
        except GitHubAPIError as e:
            logger.error(f"❌ GitHub error: {e}")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": "Failed to fetch issue from GitHub",
                    "message": e.message,
                    "owner": owner,
                    "repo": repo,
                    "issue_number": issue_number
                }
            )
        
        # Step 2: Create Devin execution session
        devin_client = DevinClient()
        
        try:
            session = devin_client.create_execution_session(
                repo=f"{owner}/{repo}",
                issue_number=issue_number,
                issue_title=issue.title,
                issue_body=issue.body or "",
                scoping_plan=None,  # Could optionally fetch from database
            )
            logger.info(f"🤖 Devin execution session created: {session.session_id}")
        except DevinAPIError as e:
            logger.error(f"❌ Devin API error: {e}")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": "Failed to create Devin execution session",
                    "message": e.message
                }
            )
        
        # Step 3: If wait=False, return session info immediately (RECOMMENDED - Devin executes in background)
        if not wait:
            return {
                "session_id": session.session_id,
                "status": session.status,
                "url": session.url,
                "message": "Execution session created. Check Devin dashboard for progress.",
                "issue": {
                    "owner": owner,
                    "repo": repo,
                    "number": issue_number,
                    "title": issue.title
                },
                "note": "Use GET /api/v1/sessions/{session_id} to check status."
            }
        
        # Step 4: If wait=True, poll until complete (can take a LONG time)
        logger.info(f"⏳ Waiting for Devin to complete execution (this may take 10-30 minutes)...")

        try:
            completed_session = devin_client.poll_until_complete(
                session.session_id,
                timeout=6000,  # Max 60 minutes for execution
            )
        except TimeoutError:
            logger.warning(f"⏱️ Execution session timed out")
            raise HTTPException(
                status_code=408,
                detail={
                    "error": "Session timeout",
                    "message": "Devin execution did not complete within 60 minutes",
                    "session_id": session.session_id,
                    "session_url": session.url,
                    "note": "Check the session URL to see Devin's progress"
                }
            )
        except DevinAPIError as e:
            logger.error(f"❌ Devin error during polling: {e}")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": "Error while waiting for Devin",
                    "message": e.message,
                    "session_id": session.session_id
                }
            )
        
        # Step 5: Parse execution output
        execution_output = devin_client.parse_execution_output(completed_session)
        
        if not execution_output:
            logger.warning("⚠️  No execution output available")
            return {
                "session_id": session.session_id,
                "status": completed_session.status,
                "url": completed_session.url,
                "message": "Session completed but no structured output available. Check session URL.",
                "issue": {
                    "owner": owner,
                    "repo": repo,
                    "number": issue_number,
                    "title": issue.title
                }
            }
        
        # Step 6: Return results
        logger.info(f"✅ Execution complete! PR: {execution_output.pr_url}")
        
        return {
            "session_id": completed_session.session_id,
            "status": completed_session.status,
            "url": completed_session.url,
            "issue": {
                "owner": owner,
                "repo": repo,
                "number": issue_number,
                "title": issue.title
            },
            "execution": {
                "status": execution_output.status,
                "branch": execution_output.branch,
                "pr_url": execution_output.pr_url,
                "tests_passed": execution_output.tests_passed,
                "tests_failed": execution_output.tests_failed,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "message": str(e)
            }
        )


@router.get("/sessions")
async def list_sessions():
    """
    List all Devin sessions (Phase 4).
    """
    raise HTTPException(
        status_code=501,
        detail="Sessions list endpoint coming in Phase 4"
    )

