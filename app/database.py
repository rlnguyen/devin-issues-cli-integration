"""
Database Setup

This module sets up the SQLAlchemy database connection and provides
a session factory for database operations.

Usage:
    from app.database import get_db, init_db
    
    # Initialize database (creates tables)
    init_db()
    
    # Get a database session
    db = next(get_db())
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=False,  # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Session:
    """
    Get a database session.
    
    This is a generator function that yields a database session
    and ensures it's closed after use.
    
    Usage:
        db = next(get_db())
        try:
            # Use db here
            db.add(obj)
            db.commit()
        finally:
            db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize the database.
    
    Creates all tables defined in models.py.
    Should be called once at application startup.
    """
    from app.models import Issue, DevinSession, Event
    
    logger.info("🗄️  Initializing database...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database initialized")


def drop_all_tables():
    """
    Drop all tables in the database.
    
    ⚠️  WARNING: This will delete all data!
    Only use for testing or resetting the database.
    """
    logger.warning("⚠️  Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("✅ All tables dropped")


if __name__ == "__main__":
    """Test database connection."""
    print("Testing database connection...")
    print(f"Database URL: {settings.database_url}")
    
    try:
        # Test connection
        with engine.connect() as conn:
            print("✅ Database connection successful!")
        
        # Initialize database
        init_db()
        print("✅ Database tables created!")
        
    except Exception as e:
        print(f"❌ Database error: {e}")

