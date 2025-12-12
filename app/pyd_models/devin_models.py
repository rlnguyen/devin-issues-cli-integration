"""
Pydantic models for Devin API requests and responses.

Reference: https://docs.devin.ai/api-reference
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    """Devin session status values."""
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"
    PAUSED = "paused"
    BLOCKED = "blocked"


class SessionPhase(str, Enum):
    """Phase of the session (what we're asking Devin to do)."""
    SCOPE = "scope"  # Analyzing and planning
    EXECUTE = "exec"  # Implementing the fix


class ScopingOutput(BaseModel):
    """
    Structured output from a scoping session.
    
    This is what Devin returns after analyzing an issue.
    Using a simplified flat structure for better reliability.
    """
    summary: str = Field(..., description="Brief summary of the issue and approach")
    plan: List[str] = Field(..., description="Step-by-step implementation plan")
    risk_level: str = Field(..., description="Risk level: low, medium, or high")
    est_effort_hours: float = Field(..., description="Estimated effort in hours")
    confidence: float = Field(..., description="Confidence score (0.0 to 1.0)")
    
    class Config:
        extra = "ignore"


class ExecutionOutput(BaseModel):
    """
    Structured output from an execution session.
    
    This is what Devin returns after implementing a fix.
    """
    status: str = Field(..., description="Status: done, failed, or blocked")
    branch: Optional[str] = Field(None, description="Git feature branch name created")
    pr_url: Optional[str] = Field(None, description="Pull request URL")
    tests_passed: Optional[int] = Field(None, description="Number of tests that passed")
    tests_failed: Optional[int] = Field(None, description="Number of tests that failed")
    
    class Config:
        extra = "ignore"



class CreateSessionRequest(BaseModel):
    """
    Request body for creating a Devin session.
    
    This is what we send to Devin when starting a new session.
    """
    prompt: str = Field(..., description="The prompt/instructions for Devin")
    repo_url: Optional[str] = Field(None, description="GitHub repository URL")
    structured_output_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON schema for structured output"
    )
    timeout: Optional[int] = Field(None, description="Timeout in seconds")
    
    class Config:
        extra = "ignore"


class SessionResponse(BaseModel):
    """
    Response from Devin API when creating or checking a session.
    
    This contains session metadata and status.
    """
    session_id: str = Field(..., description="Unique session ID")
    status: SessionStatus = Field(..., description="Current session status")
    created_at: Optional[datetime] = Field(None, description="When session was created")
    updated_at: Optional[datetime] = Field(None, description="When session was last updated")
    url: Optional[str] = Field(None, description="URL to view session in browser")
    
    # Output data (may be null until session completes)
    structured_output: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured output data if available"
    )
    messages: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Chat messages from the session"
    )
    
    class Config:
        extra = "ignore"


class SessionListResponse(BaseModel):
    """
    Response from listing sessions.
    
    Contains a list of sessions with pagination.
    """
    sessions: List[SessionResponse]
    total: int = Field(..., description="Total number of sessions")
    page: int = Field(1, description="Current page number")
    per_page: int = Field(20, description="Results per page")
    
    class Config:
        extra = "ignore"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_scoping_schema() -> Dict[str, Any]:
    """
    Generate JSON schema for scoping output.
    
    This tells Devin what structured format we expect back.
    Devin will try to populate this schema with data.
    """
    return {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Brief summary of issue and recommended approach"
            },
            "plan": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Step-by-step implementation plan (3-7 steps)"
            },
            "risk_level": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Risk level for implementing this fix"
            },
            "est_effort_hours": {
                "type": "number",
                "description": "Estimated effort in hours"
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence score (0.0 = no confidence, 1.0 = very confident)"
            }
        },
        "required": ["summary", "plan", "risk_level", "est_effort_hours", "confidence"]
    }


def create_execution_schema() -> Dict[str, Any]:
    """
    Generate JSON schema for execution output.
    
    This tells Devin what to return after implementing a fix.
    """
    return {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["done", "failed", "blocked"],
                "description": "Implementation status"
            },
            "branch": {
                "type": "string",
                "description": "Git branch name where changes were made"
            },
            "pr_url": {
                "type": "string",
                "description": "URL of the pull request created"
            },
            "tests_passed": {
                "type": "integer",
                "description": "Number of tests that passed"
            },
            "tests_failed": {
                "type": "integer",
                "description": "Number of tests that failed"
            }
        },
        "required": ["status"]
    }


def build_scoping_prompt(
    repo: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    comments: List[str]
) -> str:
    """
    Build a prompt for Devin to scope an issue.
    
    This creates clear instructions for what we want Devin to do.
    """
    prompt = f"""You are analyzing GitHub issue #{issue_number} from repository {repo}.

**Issue Title:** {issue_title}

**Issue Description:**
{issue_body or "No description provided"}

"""
    
    if comments:
        prompt += f"""**Discussion ({len(comments)} comments):**
"""
        for i, comment in enumerate(comments[:5], 1):  # Show max 5 comments
            prompt += f"{i}. {comment}\n\n"
    
    prompt += """**Your Task:**
Analyze this issue and provide a structured implementation plan.

Please respond with:
1. **Summary**: Brief overview of the issue and your recommended approach
2. **Plan**: Step-by-step implementation plan (3-7 concrete steps)
3. **Risk Level**: Assess risk as "low", "medium", or "high"
4. **Estimated Effort**: Hours needed to implement
5. **Confidence**: Your confidence in this plan (0.0 to 1.0)

Consider:
- Code complexity
- Testing requirements
- Potential edge cases
- Dependencies and breaking changes
- Documentation needs

Provide your response in the structured format specified.
"""
    
    return prompt


def build_execution_prompt(
    repo_url: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    scoping_plan: Optional[List[str]] = None
) -> str:
    """
    Build a prompt for Devin to execute/implement an issue.
    
    This tells Devin to actually write code and create a PR.
    """
    prompt = f"""You are implementing a fix for GitHub issue #{issue_number}.

**Repository:** {repo_url}

**Issue Title:** {issue_title}

**Issue Description:**
{issue_body or "No description provided"}

"""
    
    if scoping_plan:
        prompt += f"""**Implementation Plan:**
"""
        for i, step in enumerate(scoping_plan, 1):
            prompt += f"{i}. {step}\n"
        prompt += "\n"
    
    prompt += """**Your Task:**
1. Clone the repository (if needed)
2. Create a feature branch (name: `fix-issue-{issue_number}-<descriptive-name>`)
3. Implement the fix following best practices.
4. Write/update tests as needed
5. Ensure all tests pass
6. Create a Pull Request with:
   - Clear title referencing the issue
   - Description explaining your changes
   - Link back to the original issue

**Requirements:**
- Follow the repository's coding style
- Add appropriate comments
- Update documentation if needed
- Ensure backward compatibility
- Run linters and formatters

Please respond with structured output containing:
- Status (done/failed/blocked)
- Branch name
- PR URL
- Test results (passed/failed counts)
"""
    
    return prompt.format(issue_number=issue_number)

