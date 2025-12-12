"""
Devin API Client

This client handles all interactions with the Devin AI API.
It manages session creation, polling, and retrieving structured outputs.

Reference: https://docs.devin.ai/api-reference
"""

import httpx
import time
import logging
from typing import Optional, Dict, Any
from app.config import settings
from app.pyd_models.devin_models import (
    SessionResponse,
    ScopingOutput,
    ExecutionOutput,
    create_scoping_schema,
    create_execution_schema,
    build_scoping_prompt,
    build_execution_prompt,
)

logger = logging.getLogger(__name__)


class DevinAPIError(Exception):
    """Custom exception for Devin API errors."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Devin API Error {status_code}: {message}")


class DevinClient:
    """
    Client for interacting with Devin AI API.
    
    This class provides methods to:
    - Create scoping sessions (analyze issues)
    - Create execution sessions (implement fixes)
    - Poll for session completion
    - Retrieve structured outputs
    
    Usage:
        client = DevinClient()
        session = client.create_scoping_session(
            repo="python/cpython",
            issue_number=12345,
            issue_title="Fix parser bug",
            issue_body="...",
            comments=[]
        )
        
        # Wait for completion
        result = client.poll_until_complete(session.session_id)
    """
    
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        """
        Initialize the Devin client.
        
        Args:
            api_key: Devin API key. If not provided, uses DEVIN_API_KEY from env.
            api_url: Devin API base URL. If not provided, uses DEVIN_API_URL from env.
        """
        self.api_key = api_key or settings.devin_api_key
        self.api_url = (api_url or settings.devin_api_url).rstrip("/")
        
        # Set up headers for all requests
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to Devin API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/sessions")
            json_data: JSON body for POST requests
            params: Query parameters
            
        Returns:
            JSON response from Devin API
            
        Raises:
            DevinAPIError: If the request fails
        """
        url = f"{self.api_url}{endpoint}"
        
        logger.debug(f"Devin API: {method} {url}")
        
        with httpx.Client() as client:
            response = client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json_data,
                params=params,
                timeout=60.0,
            )
            
            # Check for errors
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", "Unknown error")
                except Exception:
                    error_msg = response.text or "Unknown error"
                
                raise DevinAPIError(response.status_code, error_msg)
            
            response_data = response.json()
            # Log response at INFO level for debugging
            # logger.info(f"Devin API response: {response_data}")
            return response_data
    
    def create_session(
        self,
        prompt: str,
        repo_url: Optional[str] = None,
        structured_output_schema: Optional[Dict[str, Any]] = None,
    ) -> SessionResponse:
        """
        Create a new Devin session.
        
        This is the low-level method to create any type of session.
        Usually you'll use create_scoping_session() or create_execution_session() instead.
        
        Args:
            prompt: Instructions for Devin
            repo_url: GitHub repository URL (if applicable)
            structured_output_schema: JSON schema for structured output
            
        Returns:
            SessionResponse with session ID and metadata
        """
        request_data = {
            "prompt": prompt,
        }
        
        if repo_url:
            request_data["repo_url"] = repo_url
        
        if structured_output_schema:
            request_data["structured_output_schema"] = structured_output_schema
        
        logger.info(f"🤖 Creating Devin session...")
        response_data = self._make_request("POST", "/sessions", json_data=request_data)
        
        session = SessionResponse(**response_data)
        logger.info(f"✅ Session created: {session.session_id}")
        
        return session
    
    def get_session(self, session_id: str) -> SessionResponse:
        """
        Get the current status and data of a session.
        
        Args:
            session_id: The session ID to check
            
        Returns:
            SessionResponse with current status and outputs
        """
        response_data = self._make_request("GET", f"/sessions/{session_id}")
        return SessionResponse(**response_data)
    
    def poll_until_complete(
        self,
        session_id: str,
        timeout: int = 1800,  # 30 minutes
        poll_interval: int = 15  # 15 seconds
    ) -> SessionResponse:
        """
        Poll a session until it completes (or times out).
        
        Uses exponential backoff to be nice to the API.
        
        Args:
            session_id: Session to poll
            timeout: Maximum time to wait in seconds
            poll_interval: Initial polling interval in seconds
            
        Returns:
            SessionResponse when session is complete
            
        Raises:
            TimeoutError: If session doesn't complete within timeout
            DevinAPIError: If session enters error state
        """
        start_time = time.time()
        current_interval = poll_interval
        
        logger.info(f"⏳ Polling session {session_id} (timeout: {timeout}s)...")
        
        while True:
            elapsed = time.time() - start_time
            
            # Check timeout
            if elapsed > timeout:
                raise TimeoutError(
                    f"Session {session_id} did not complete within {timeout} seconds"
                )
            
            # Get current status
            session = self.get_session(session_id)
            
            # Log at INFO level so we can see it in the logs
            logger.info(f"📊 Polling: status='{session.status}', has_output={bool(session.structured_output)}")
            logger.info(f"session.status: {session.status}")
            # Check if complete (either status indicates done OR we have structured output)
            if session.status and session.status.lower() in ["finished", "completed", "done", "idle", "succeeded"]:
                logger.info(f"✅ Session {session_id} finished by status! (took {elapsed:.1f}s)")
                return session
            elif session.structured_output:  # If we have structured output, consider it done
                logger.info(f"✅ Session {session_id} finished with output! (took {elapsed:.1f}s)")
                return session
            elif session.status and session.status.lower() in ["error", "failed"]:
                raise DevinAPIError(500, f"Session {session_id} encountered an error")
            elif session.status and session.status.lower() == "blocked":
                logger.warning(f"⚠️ Session {session_id} is blocked - may need user input")
                # Continue polling in case it unblocks
            
            # Wait before next poll (with exponential backoff)
            time.sleep(current_interval)
    
    def create_scoping_session(
        self,
        repo: str,
        issue_number: int,
        issue_title: str,
        issue_body: str,
        comments: list[str] = None,
    ) -> SessionResponse:
        """
        Create a session to scope/analyze an issue.
        
        This asks Devin to analyze the issue and provide:
        - Implementation plan
        - Risk assessment
        - Effort estimate
        - Confidence score
        
        Args:
            repo: Repository name (owner/repo)
            issue_number: GitHub issue number
            issue_title: Issue title
            issue_body: Issue description
            comments: List of comment texts
            
        Returns:
            SessionResponse with session ID
            
        Example:
            client = DevinClient()
            session = client.create_scoping_session(
                repo="python/cpython",
                issue_number=12345,
                issue_title="Fix parser bug",
                issue_body="The parser crashes when...",
                comments=["I can reproduce this", "Same issue here"]
            )
            print(f"View at: {session.url}")
        """
        comments = comments or []
        
        # Build the prompt
        prompt = build_scoping_prompt(
            repo=repo,
            issue_number=issue_number,
            issue_title=issue_title,
            issue_body=issue_body,
            comments=comments,
        )
        
        # Get the structured output schema
        schema = create_scoping_schema()
        
        # Construct repo URL
        repo_url = f"https://github.com/{repo}"
        
        logger.info(f"📋 Creating scoping session for {repo}#{issue_number}")
        
        # Create session
        session = self.create_session(
            prompt=prompt,
            repo_url=repo_url,
            structured_output_schema=schema,
        )
        
        return session
    
    def parse_scoping_output(self, session: SessionResponse) -> Optional[ScopingOutput]:
        """
        Extract and parse scoping output from a completed session.
        
        Args:
            session: Completed session response
            
        Returns:
            ScopingOutput if available, None otherwise
        """
        if not session.structured_output:
            logger.warning("No structured output available in session")
            return None
        
        try:
            return ScopingOutput(**session.structured_output)
        except Exception as e:
            logger.error(f"Failed to parse scoping output: {e}")
            return None
    
    def create_execution_session(
        self,
        repo: str,
        issue_number: int,
        issue_title: str,
        issue_body: str,
        scoping_plan: Optional[list[str]] = None,
    ) -> SessionResponse:
        """
        Create a session to execute/implement an issue fix.
        
        This asks Devin to actually implement the fix and create a PR.
        
        Args:
            repo: Repository name (owner/repo)
            issue_number: GitHub issue number
            issue_title: Issue title
            issue_body: Issue description
            scoping_plan: Optional implementation plan from scoping
            
        Returns:
            SessionResponse with session ID
        """
        # Build the prompt
        repo_url = f"https://github.com/{repo}"
        prompt = build_execution_prompt(
            repo_url=repo_url,
            issue_number=issue_number,
            issue_title=issue_title,
            issue_body=issue_body,
            scoping_plan=scoping_plan,
        )
        
        # Get the structured output schema
        schema = create_execution_schema()
        
        logger.info(f"🚀 Creating execution session for {repo}#{issue_number}")
        
        # Create session
        session = self.create_session(
            prompt=prompt,
            repo_url=repo_url,
            structured_output_schema=schema,
        )
        
        return session
    
    def parse_execution_output(self, session: SessionResponse) -> Optional[ExecutionOutput]:
        """
        Extract and parse execution output from a completed session.
        
        Args:
            session: Completed session response
            
        Returns:
            ExecutionOutput if available, None otherwise
        """
        if not session.structured_output:
            logger.warning("No structured output available in session")
            return None
        
        try:
            return ExecutionOutput(**session.structured_output)
        except Exception as e:
            logger.error(f"Failed to parse execution output: {e}")
            return None


# Local Testing
if __name__ == "__main__":
    """Test the Devin client (requires valid API key)."""
    print("Testing Devin Client...\n")
    
    client = DevinClient()
    
    # Note: This is just a structure test - actual API calls require valid credentials
    print("✅ Devin client initialized")
    print(f"   API URL: {client.api_url}")
    print(f"   API Key: {'*' * 20} (hidden)")
    print("\n💡 To test with real API calls, ensure DEVIN_API_KEY is configured in .env")

