"""
GitHub API Client

This client handles all interactions with the GitHub REST API.
It uses httpx for async HTTP requests and handles authentication,
rate limiting, and error handling.

Reference: https://docs.github.com/en/rest
"""

import httpx
from typing import List, Optional
from app.config import settings
from app.pyd_models.github_models import GitHubIssue, GitHubComment


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"GitHub API Error {status_code}: {message}")


class GitHubClient:
    """
    Client for interacting with GitHub's REST API.
    
    This class provides methods to:
    - List issues from a repository
    - Get details of a specific issue
    - Get comments on an issue
    - Handle authentication and rate limiting
    
    Usage:
        client = GitHubClient()
        issues = client.list_issues("python", "cpython", labels="bug")
        issue = client.get_issue("python", "cpython", 12345)
    """
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize the GitHub client.
        
        Args:
            token: GitHub Personal Access Token. If not provided,
                   uses GITHUB_TOKEN from environment variables.
        """
        self.token = token or settings.github_token
        self.base_url = "https://api.github.com"
        
        # Set up headers for all requests
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[dict] = None,
        json_data: Optional[dict] = None
    ) -> dict:
        """
        Make an HTTP request to GitHub API.
        
        This is an internal helper method that handles:
        - Authentication (adds token to headers)
        - Error handling
        - Rate limit awareness
        
        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., "/repos/owner/repo/issues")
            params: Query parameters
            json_data: JSON body for POST/PATCH requests
            
        Returns:
            dict: JSON response from GitHub
            
        Raises:
            GitHubAPIError: If the request fails
        """
        url = f"{self.base_url}{endpoint}"
        
        with httpx.Client() as client:
            response = client.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=30.0
            )
            
            # Check for errors
            if response.status_code >= 400:
                error_msg = response.json().get("message", "Unknown error")
                raise GitHubAPIError(response.status_code, error_msg)
            
            # Check rate limit (optional - for monitoring)
            rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
            if rate_limit_remaining:
                remaining = int(rate_limit_remaining)
                if remaining < 100:
                    print(f"GitHub API rate limit low: {remaining} requests remaining")
            
            return response.json()
    
    def list_issues(
        self,
        owner: str,
        repo: str,
        labels: Optional[str] = None,
        state: str = "open",
        assignee: Optional[str] = None,
        page: int = 1,
        per_page: int = 30
    ) -> List[GitHubIssue]:
        """
        List issues from a GitHub repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            labels: Comma-separated label names to filter by (e.g., "bug,help wanted")
            state: Issue state - "open", "closed", or "all"
            assignee: Filter by assignee username
            page: Page number for pagination (default: 1)
            per_page: Results per page, max 100 (default: 30)
            
        Returns:
            List of GitHubIssue objects
            
        Example:
            client = GitHubClient()
            issues = client.list_issues("python", "cpython", labels="bug", state="open")
            for issue in issues:
                print(f"#{issue.number}: {issue.title}")
        """
        endpoint = f"/repos/{owner}/{repo}/issues"
        
        # Build query parameters
        params = {
            "state": state,
            "page": page,
            "per_page": min(per_page, 100),  # GitHub max is 100
            "sort": "updated",
            "direction": "desc",
        }
        
        if labels:
            params["labels"] = labels
        
        if assignee:
            params["assignee"] = assignee
        
        # Make the request
        response_data = self._make_request("GET", endpoint, params=params)
        
        # Filter out pull requests - GitHub includes PRs in the issues endpoint
        issues_only = [item for item in response_data if "pull_request" not in item]
        
        # Parse response into Pydantic models to auto-validate data
        issues = [GitHubIssue(**issue_data) for issue_data in issues_only]
        
        return issues
    
    def get_issue(self, owner: str, repo: str, issue_number: int) -> GitHubIssue:
        """
        Get details of a specific GitHub issue.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number (e.g., 123)
            
        Returns:
            GitHubIssue object with full issue details
            
        Example:
            client = GitHubClient()
            issue = client.get_issue("python", "cpython", 12345)
            print(f"Title: {issue.title}")
            print(f"Body: {issue.body}")
        """
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}"
        
        response_data = self._make_request("GET", endpoint)
        
        # Parse into Pydantic model
        issue = GitHubIssue(**response_data)
        
        return issue
    
    def get_issue_comments(
        self, 
        owner: str, 
        repo: str, 
        issue_number: int
    ) -> List[GitHubComment]:
        """
        Get all comments on a GitHub issue.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            
        Returns:
            List of GitHubComment objects
            
        Example:
            client = GitHubClient()
            comments = client.get_issue_comments("python", "cpython", 12345)
            for comment in comments:
                print(f"{comment.user.login}: {comment.body[:100]}...")
        """
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
        
        response_data = self._make_request("GET", endpoint)
        
        # Parse into Pydantic models
        comments = [GitHubComment(**comment_data) for comment_data in response_data]
        
        return comments
    
    def create_comment(
        self, 
        owner: str, 
        repo: str, 
        issue_number: int, 
        body: str
    ) -> GitHubComment:
        """
        Create a comment on a GitHub issue.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            body: Comment text (markdown)
            
        Returns:
            GitHubComment object for the created comment
            
        Example:
            client = GitHubClient()
            comment = client.create_comment(
                "myorg", "myrepo", 123,
                "🤖 Devin has started working on this issue!"
            )
        """
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
        
        response_data = self._make_request(
            "POST", 
            endpoint, 
            json_data={"body": body}
        )
        
        comment = GitHubComment(**response_data)
        
        return comment


# Local testing
if __name__ == "__main__":
    print("Testing GitHub Client...\n")
    
    client = GitHubClient()
    
    # Test 1: List issues from a public repo
    print("Fetching issues from python/cpython (labeled 'type-bug')...")
    issues = []  # Initialize to avoid NameError
    try:
        issues = client.list_issues(
            "python", 
            "cpython", 
            labels="type-bug",
            state="open",
            per_page=5
        )
        print(f"Found {len(issues)} issues:\n")
        for issue in issues:
            labels = issue.get_display_labels()
            print(f" ❗#{issue.number}: {issue.title}")
            print(f"     Labels: {labels}")
            print(f"     Updated: {issue.updated_at.strftime('%Y-%m-%d')}\n")
    except GitHubAPIError as e:
        print(f"Error: {e}")
    
    # Test 2: Get a specific issue
    if issues:
        first_issue_num = issues[0].number
        print(f"\nFetching details for issue #{first_issue_num}...")
        try:
            issue = client.get_issue("python", "cpython", first_issue_num)
            print(f"Title: {issue.title}")
            print(f"   Body: {issue.body[:200] if issue.body else 'No description'}...")
            print(f"   Comments: {issue.comments}")
        except GitHubAPIError as e:
            print(f"Error: {e}")

