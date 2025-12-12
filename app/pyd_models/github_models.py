"""
Pydantic models for GitHub API responses. These models:
1. Define the structure of data we receive from GitHub
2. Automatically validate and parse JSON responses
3. Provide type hints for better IDE support

Reference: https://docs.github.com/en/rest/issues/issues
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class GitHubUser(BaseModel):
    """
    Represents a GitHub user.
    
    Attributes:
        login: GitHub username
        id: User ID
        avatar_url: URL to user's avatar image
        html_url: URL to user's GitHub profile
    """
    login: str
    id: int
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    
    class Config:
        # Allow extra fields from API response (ignore them)
        extra = "ignore"


class GitHubLabel(BaseModel):
    """
    Represents a GitHub issue label.
    
    Attributes:
        id: Label ID
        name: Label name (e.g., "bug", "enhancement")
        color: Hex color code (e.g., "d73a4a")
        description: Optional label description
    """
    id: int
    name: str
    color: str
    description: Optional[str] = None
    
    class Config:
        extra = "ignore"


class GitHubIssue(BaseModel):
    """
    Represents a GitHub issue.
    
    This is the main model for issue data. Contains all relevant
    information needed for scoping and execution.
    
    Attributes:
        number: Issue number (e.g., 123)
        title: Issue title
        body: Issue description/body (markdown)
        state: Issue state ("open", "closed")
        labels: List of labels attached to the issue
        user: User who created the issue
        assignee: User assigned to the issue (if any)
        html_url: URL to the issue on GitHub
        created_at: When the issue was created
        updated_at: When the issue was last updated
        comments: Number of comments (not the actual comments)
    """
    number: int
    title: str
    body: Optional[str] = None  # Can be empty
    state: str  # "open" or "closed"
    labels: List[GitHubLabel] = []
    user: GitHubUser
    assignee: Optional[GitHubUser] = None
    html_url: str
    created_at: datetime
    updated_at: datetime
    comments: int = 0  # Number of comments
    
    class Config:
        extra = "ignore"
    
    def get_label_names(self) -> List[str]:
        """Helper method to get just the label names."""
        return [label.name for label in self.labels]
    
    def get_display_labels(self) -> str:
        """Get labels as a comma-separated string for display."""
        return ", ".join(self.get_label_names())


class GitHubComment(BaseModel):
    """
    Represents a comment on a GitHub issue.
    
    Attributes:
        id: Comment ID
        body: Comment text (markdown)
        user: Who wrote the comment
        created_at: When the comment was created
        updated_at: When the comment was last updated
    """
    id: int
    body: str
    user: GitHubUser
    created_at: datetime
    updated_at: datetime
    html_url: Optional[str] = None
    
    class Config:
        extra = "ignore"


class IssueListRequest(BaseModel):
    """
    Request parameters for listing issues.
    
    Used to validate and document API request parameters.
    """
    owner: str
    repo: str
    labels: Optional[str] = None  # Comma-separated label names
    state: str = "open"  # "open", "closed", or "all"
    assignee: Optional[str] = None
    sort: str = "created"  # "created", "updated", "comments"
    direction: str = "desc"  # "asc" or "desc"
    page: int = 1
    per_page: int = 30  # Max 100
    
    class Config:
        extra = "ignore"

