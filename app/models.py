"""
Database Models

SQLAlchemy models for storing GitHub issues, Devin sessions, and events.

Tables:
- issues: GitHub issues with scoping metadata
- devin_sessions: Devin scoping and execution sessions
- events: Audit log of all operations
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class Issue(Base):
    """
    GitHub issue with scoping metadata.
    
    Stores issues that have been scoped or executed,
    along with confidence scores and status.
    """
    __tablename__ = "issues"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # GitHub identifiers
    owner = Column(String, nullable=False, index=True)
    repo = Column(String, nullable=False, index=True)
    issue_number = Column(Integer, nullable=False, index=True)
    
    # Issue details
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    state = Column(String, nullable=False)  # open, closed
    labels = Column(JSON, nullable=True)  # List of label names
    
    # Scoping results
    confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    risk_level = Column(String, nullable=True)  # low, medium, high
    estimated_effort = Column(Float, nullable=True)  # hours
    implementation_plan = Column(JSON, nullable=True)  # List of steps
    
    # Execution results
    pr_url = Column(String, nullable=True)
    branch_name = Column(String, nullable=True)
    tests_passed = Column(Integer, nullable=True)
    tests_failed = Column(Integer, nullable=True)
    
    # Status tracking
    is_scoped = Column(Boolean, default=False)
    is_executed = Column(Boolean, default=False)
    last_scoped_at = Column(DateTime, nullable=True)
    last_executed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    sessions = relationship("DevinSession", back_populates="issue")
    
    def __repr__(self):
        return f"<Issue {self.owner}/{self.repo}#{self.issue_number}: {self.title}>"


class DevinSession(Base):
    """
    Devin AI session (scoping or execution).
    
    Tracks Devin sessions, their status, and results.
    """
    __tablename__ = "devin_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Session identifiers
    session_id = Column(String, unique=True, nullable=False, index=True)
    session_url = Column(String, nullable=True)
    
    # Link to issue
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=True)
    owner = Column(String, nullable=False, index=True)
    repo = Column(String, nullable=False, index=True)
    issue_number = Column(Integer, nullable=False, index=True)
    
    # Session type
    phase = Column(String, nullable=False, index=True)  # scope, exec
    
    # Status
    status = Column(String, nullable=True)  # new, claimed, running, finished, error, etc.
    
    # Results
    structured_output = Column(JSON, nullable=True)
    
    # Scoping specific
    confidence = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)
    estimated_effort = Column(Float, nullable=True)
    
    # Execution specific
    pr_url = Column(String, nullable=True)
    branch_name = Column(String, nullable=True)
    tests_passed = Column(Integer, nullable=True)
    tests_failed = Column(Integer, nullable=True)
    
    # Timing
    duration_seconds = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    issue = relationship("Issue", back_populates="sessions")
    
    def __repr__(self):
        return f"<DevinSession {self.session_id} ({self.phase}): {self.owner}/{self.repo}#{self.issue_number}>"


class Event(Base):
    """
    Audit log of system events.
    
    Records all important operations for debugging and analytics.
    """
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Event type
    event_type = Column(String, nullable=False, index=True)  # list, scope, execute, error
    
    # Context
    owner = Column(String, nullable=True, index=True)
    repo = Column(String, nullable=True, index=True)
    issue_number = Column(Integer, nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)
    
    # Event details
    message = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)  # Additional data (renamed from metadata)
    
    # Error tracking
    is_error = Column(Boolean, default=False, index=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<Event {self.event_type}: {self.message}>"


# Helper functions for common database operations

def get_or_create_issue(db, owner: str, repo: str, issue_number: int, **kwargs):
    """
    Get an existing issue or create a new one.
    
    Args:
        db: Database session
        owner: Repository owner
        repo: Repository name
        issue_number: Issue number
        **kwargs: Additional fields to set if creating
        
    Returns:
        Tuple of (issue, created) where created is True if new
    """
    issue = db.query(Issue).filter(
        Issue.owner == owner,
        Issue.repo == repo,
        Issue.issue_number == issue_number
    ).first()
    
    if issue:
        return issue, False
    
    issue = Issue(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        **kwargs
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    
    return issue, True


def create_session_record(db, session_id: str, phase: str, owner: str, repo: str, issue_number: int, **kwargs):
    """
    Create a new Devin session record.
    
    Args:
        db: Database session
        session_id: Devin session ID
        phase: Session phase (scope or exec)
        owner: Repository owner
        repo: Repository name
        issue_number: Issue number
        **kwargs: Additional fields
        
    Returns:
        Created DevinSession object
    """
    session = DevinSession(
        session_id=session_id,
        phase=phase,
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        **kwargs
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return session


def log_event(db, event_type: str, message: str, **kwargs):
    """
    Log an event to the audit log.
    
    Args:
        db: Database session
        event_type: Type of event
        message: Event message
        **kwargs: Additional context (owner, repo, session_id, etc.)
    """
    event = Event(
        event_type=event_type,
        message=message,
        **kwargs
    )
    db.add(event)
    db.commit()
    
    return event

