"""
Database Models for RealLink Ecosystem
SQLAlchemy ORM models for all entities
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import enum

Base = declarative_base()


# ==================== ENUMS ====================

class PropertyStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    LISTED = "LISTED"
    UNDER_OFFER = "UNDER_OFFER"
    PARTIALLY_RENTED = "PARTIALLY_RENTED"
    FULLY_RENTED = "FULLY_RENTED"
    SOLD = "SOLD"


class UnitStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    RENTED = "RENTED"


class AgentAssignmentStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class PropertyType(str, enum.Enum):
    RENT = "RENT"
    SALE = "SALE"


class TransactionType(str, enum.Enum):
    SALE = "SALE"
    RENT = "RENT"


class InterestStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONTACTED = "CONTACTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DisputeStatus(str, enum.Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    AGENT = "AGENT"
    TENANT = "TENANT"
    BUYER = "BUYER"
    ADMIN = "ADMIN"


class OfferStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    COUNTERED = "COUNTERED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentType(str, enum.Enum):
    PURCHASE = "PURCHASE"
    RENT = "RENT"
    DEPOSIT = "DEPOSIT"
    COMMISSION = "COMMISSION"


# ==================== MODELS ====================

class User(Base):
    """User model - represented as hashed address for privacy"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String(128), unique=True, nullable=False, index=True)  # Hashed identifier
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=True)  # Bcrypt hashed password
    role = Column(SQLEnum(UserRole), default=UserRole.OWNER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    properties = relationship("Property", back_populates="owner")
    agent_profile = relationship("Agent", back_populates="user", uselist=False)
    interests = relationship("Interest", back_populates="user")
    disputes = relationship("Dispute", back_populates="user")


class Property(Base):
    """Property model - building-level entity"""
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(String(64), unique=True, nullable=False, index=True)  # Unique property identifier
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    location = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    property_type = Column(SQLEnum(PropertyType), default=PropertyType.SALE)
    status = Column(SQLEnum(PropertyStatus), default=PropertyStatus.DRAFT)
    price = Column(Float, nullable=True)
    bedrooms = Column(Integer, default=0)
    bathrooms = Column(Integer, default=0)
    area_sqm = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="properties")
    units = relationship("Unit", back_populates="property", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="property", cascade="all, delete-orphan")
    ownership_records = relationship("OwnershipRecord", back_populates="property")
    property_agents = relationship("PropertyAgent", back_populates="property")
    interests = relationship("Interest", back_populates="property")
    transactions = relationship("Transaction", back_populates="property")
    disputes = relationship("Dispute", back_populates="property")


class Unit(Base):
    """Unit model - sub-entity (room/flat/shop) within a property"""
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    status = Column(SQLEnum(UnitStatus), default=UnitStatus.AVAILABLE)
    tenant_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    area_sqm = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="units")
    tenant = relationship("User", foreign_keys=[tenant_id])


class Document(Base):
    """Document model - property documents with hash fingerprinting"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    doc_hash = Column(String(128), nullable=False, index=True)  # SHA256 hash for fingerprinting
    doc_type = Column(String(50), nullable=True)  # deed, title, survey, etc.
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="documents")


class OwnershipRecord(Base):
    """Ownership Record model - hash-linked ledger for ownership tracking"""
    __tablename__ = "ownership_records"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    previous_hash = Column(String(128), nullable=True)  # Hash of previous record
    current_hash = Column(String(128), nullable=False, unique=True)  # Hash of this record
    transaction_type = Column(String(20), nullable=True)  # initial, transfer, sale, inheritance, etc.
    amount = Column(Float, nullable=True)  # Transaction amount if applicable
    notes = Column(Text, nullable=True)  # Additional notes about the transfer
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="ownership_records")
    owner = relationship("User")


class Agent(Base):
    """Agent model - permission-based participant profile"""
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    license_number = Column(String(100), nullable=True)
    rating = Column(Float, default=0.0)
    verified = Column(Boolean, default=False)
    total_deals = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="agent_profile")
    property_assignments = relationship("PropertyAgent", back_populates="agent")


class PropertyAgent(Base):
    """Property-Agent assignment with lifecycle tracking"""
    __tablename__ = "property_agents"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    status = Column(SQLEnum(AgentAssignmentStatus), default=AgentAssignmentStatus.REQUESTED)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    property = relationship("Property", back_populates="property_agents")
    agent = relationship("Agent", back_populates="property_assignments")


class Interest(Base):
    """Interest model - user interest in a property"""
    __tablename__ = "interests"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    status = Column(SQLEnum(InterestStatus), default=InterestStatus.PENDING)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="interests")
    user = relationship("User", back_populates="interests")
    unit = relationship("Unit")


class Transaction(Base):
    """Transaction model - record of sales and rentals"""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    amount = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="transactions")
    unit = relationship("Unit")
    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])
    agent = relationship("Agent")


class Subscription(Base):
    """Subscription model - USSD/SMS subscriptions for property alerts"""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    location = Column(String(500), nullable=True)
    intent = Column(String(20), nullable=True)  # rent, buy
    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Dispute(Base):
    """Dispute model - fraud and conflict reports"""
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(SQLEnum(DisputeStatus), default=DisputeStatus.OPEN)
    resolution = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    property = relationship("Property", back_populates="disputes")
    user = relationship("User", back_populates="disputes")


class FraudAlert(Base):
    """Fraud Alert model - detected fraud attempts"""
    __tablename__ = "fraud_alerts"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)
    alert_type = Column(String(50), nullable=False)  # duplicate_doc, duplicate_property, suspicious_agent, ai_detected
    severity = Column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH
    description = Column(Text, nullable=False)
    ai_analysis = Column(Text, nullable=True)  # JSON from AI analysis
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PropertyImage(Base):
    """Property Image model - images associated with properties"""
    __tablename__ = "property_images"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    image_url = Column(String(500), nullable=False)
    image_path = Column(String(500), nullable=True)  # Local file path if stored locally
    caption = Column(String(255), nullable=True)
    is_primary = Column(Boolean, default=False)  # Main image for the property
    order = Column(Integer, default=0)  # Display order
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    property = relationship("Property", backref="images")
    uploader = relationship("User")


class Inspection(Base):
    """Inspection model - property inspection scheduling"""
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Who scheduled
    scheduled_date = Column(DateTime, nullable=False)
    status = Column(String(20), default="SCHEDULED")  # SCHEDULED, COMPLETED, CANCELLED
    notes = Column(Text, nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)  # Optional agent
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    property = relationship("Property")
    user = relationship("User")
    agent = relationship("Agent")


class AgentRating(Base):
    """Agent Rating model - ratings given to agents after deals"""
    __tablename__ = "agent_ratings"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Who rated
    rating = Column(Integer, nullable=False)  # 1-5 stars
    comment = Column(Text, nullable=True)
    transaction_type = Column(String(20), nullable=True)  # SALE or RENT
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    agent = relationship("Agent", backref="ratings")
    property = relationship("Property")
    user = relationship("User")


class TimelineEvent(Base):
    """Timeline Event model - property lifecycle events"""
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    event_type = Column(String(50), nullable=False)  # LISTED, OFFER, INSPECTION, SOLD, RENTED, etc.
    description = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Who triggered the event
    metadata_json = Column(Text, nullable=True)  # JSON for additional data
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    property = relationship("Property")
    user = relationship("User")


class ChatSession(Base):
    """Chat Session model - AI assistant chat sessions"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String(64), unique=True, nullable=False)
    context_type = Column(String(20), nullable=True)  # property, general, search
    context_id = Column(Integer, nullable=True)  # property_id if context is property
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """Chat Message model - individual messages in chat sessions"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")


# ==================== DATABASE SETUP ====================

def get_engine(database_url: str = "sqlite:///./reallink.db"):
    """Create database engine"""
    return create_engine(database_url, connect_args={"check_same_thread": False} if "sqlite" in database_url else {})


def get_session_maker(engine):
    """Create session maker"""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(engine):
    """Initialize database with all tables"""
    Base.metadata.create_all(bind=engine)


# Export all models
__all__ = [
    "Base", "get_engine", "get_session_maker", "init_db",
    "PropertyStatus", "UnitStatus", "AgentAssignmentStatus", "PropertyType",
    "TransactionType", "InterestStatus", "DisputeStatus", "UserRole",
    "User", "Property", "Unit", "Document", "OwnershipRecord",
    "Agent", "PropertyAgent", "Interest", "Transaction",
    "Subscription", "Dispute", "FraudAlert", "PropertyImage",
    "Inspection", "AgentRating", "TimelineEvent", "ChatSession", "ChatMessage"
]
