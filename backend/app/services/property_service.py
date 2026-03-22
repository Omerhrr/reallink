"""
Property Service for RealLink Ecosystem
Handles property CRUD operations and business logic
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import (
    Property, Unit, Document, OwnershipRecord, User, Agent,
    PropertyStatus, PropertyType, UnitStatus, AgentAssignmentStatus
)
from app.utils import (
    create_property_id, create_ledger_hash, generate_hash,
    hash_document, calculate_trust_score
)
from app.services.state_machine import (
    PropertyStateMachine, UnitStateMachine, PermissionChecker, TransitionError
)


class PropertyService:
    """Service for property operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_property(
        self,
        owner_id: int,
        title: str,
        location: str,
        property_type: PropertyType = PropertyType.SALE,
        price: Optional[float] = None,
        description: Optional[str] = None,
        bedrooms: int = 0,
        bathrooms: int = 0,
        area_sqm: Optional[float] = None
    ) -> Property:
        """Create a new property in DRAFT state"""
        timestamp = datetime.utcnow()
        property_id = create_property_id(location, timestamp, owner_id)

        property_obj = Property(
            property_id=property_id,
            owner_id=owner_id,
            title=title,
            location=location,
            description=description,
            property_type=property_type,
            price=price,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            area_sqm=area_sqm,
            status=PropertyStatus.DRAFT
        )

        self.db.add(property_obj)
        self.db.commit()
        self.db.refresh(property_obj)

        return property_obj

    def list_property(self, property_id: int) -> Property:
        """Move property from DRAFT to LISTED"""
        property_obj = self.db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise ValueError(f"Property {property_id} not found")

        new_status, success, message = PropertyStateMachine.transition(
            property_obj.status.value, PropertyStatus.LISTED.value
        )

        if not success:
            raise TransitionError(message)

        property_obj.status = PropertyStatus(new_status)
        self.db.commit()
        self.db.refresh(property_obj)

        return property_obj

    def get_property(self, property_id: int) -> Optional[Property]:
        """Get property by internal ID"""
        return self.db.query(Property).filter(Property.id == property_id).first()

    def get_property_by_code(self, property_id_code: str) -> Optional[Property]:
        """Get property by property_id code (PROP-XXXXXXXX)"""
        return self.db.query(Property).filter(Property.property_id == property_id_code).first()

    def get_properties(
        self,
        owner_id: Optional[int] = None,
        status: Optional[PropertyStatus] = None,
        location: Optional[str] = None,
        property_type: Optional[PropertyType] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[Property]:
        """Get properties with optional filters"""
        query = self.db.query(Property)

        if owner_id:
            query = query.filter(Property.owner_id == owner_id)
        if status:
            query = query.filter(Property.status == status)
        if location:
            query = query.filter(Property.location.ilike(f"%{location}%"))
        if property_type:
            query = query.filter(Property.property_type == property_type)
        if min_price is not None:
            query = query.filter(Property.price >= min_price)
        if max_price is not None:
            query = query.filter(Property.price <= max_price)

        return query.offset(skip).limit(limit).all()

    def update_property(
        self,
        property_id: int,
        user_id: int,
        **updates
    ) -> Property:
        """Update property if user has permission"""
        property_obj = self.get_property(property_id)
        if not property_obj:
            raise ValueError(f"Property {property_id} not found")

        # Check permission
        can_modify, reason = PermissionChecker.can_modify_property(
            user_id, property_obj.owner_id,
            []  # Would fetch agent assignments in production
        )

        if not can_modify:
            raise PermissionError(reason)

        # Update allowed fields
        allowed_fields = [
            "title", "description", "price", "bedrooms",
            "bathrooms", "area_sqm", "location"
        ]

        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                setattr(property_obj, field, value)

        property_obj.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(property_obj)

        return property_obj

    def delete_property(self, property_id: int, user_id: int) -> bool:
        """Delete property if user is owner"""
        property_obj = self.get_property(property_id)
        if not property_obj:
            raise ValueError(f"Property {property_id} not found")

        if property_obj.owner_id != user_id:
            raise PermissionError("Only owner can delete property")

        self.db.delete(property_obj)
        self.db.commit()
        return True


class UnitService:
    """Service for unit operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_unit(
        self,
        property_id: int,
        name: str,
        price: float,
        description: Optional[str] = None,
        area_sqm: Optional[float] = None
    ) -> Unit:
        """Create a new unit for a property"""
        unit = Unit(
            property_id=property_id,
            name=name,
            description=description,
            price=price,
            area_sqm=area_sqm,
            status=UnitStatus.AVAILABLE
        )

        self.db.add(unit)
        self.db.commit()
        self.db.refresh(unit)

        return unit

    def get_units_for_property(self, property_id: int) -> List[Unit]:
        """Get all units for a property"""
        return self.db.query(Unit).filter(Unit.property_id == property_id).all()

    def rent_unit(self, unit_id: int, tenant_id: int) -> Unit:
        """Rent a unit to a tenant"""
        unit = self.db.query(Unit).filter(Unit.id == unit_id).first()
        if not unit:
            raise ValueError(f"Unit {unit_id} not found")

        can_rent, reason = PermissionChecker.can_rent_unit(unit.status.value)
        if not can_rent:
            raise TransitionError(reason)

        unit.status = UnitStatus.RENTED
        unit.tenant_id = tenant_id
        self.db.commit()
        self.db.refresh(unit)

        # Update property status based on unit status
        self._update_property_rental_status(unit.property_id)

        return unit

    def _update_property_rental_status(self, property_id: int):
        """Update property status based on unit rental status"""
        units = self.get_units_for_property(property_id)
        total_units = len(units)
        rented_units = sum(1 for u in units if u.status == UnitStatus.RENTED)

        property_obj = self.db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            return

        if rented_units == 0:
            # All units available
            pass  # Keep current status
        elif rented_units == total_units:
            property_obj.status = PropertyStatus.FULLY_RENTED
        else:
            property_obj.status = PropertyStatus.PARTIALLY_RENTED

        self.db.commit()


class DocumentService:
    """Service for document operations"""

    def __init__(self, db: Session):
        self.db = db

    def upload_document(
        self,
        property_id: int,
        file_content: bytes,
        file_name: str,
        file_url: str,
        doc_type: Optional[str] = None
    ) -> Document:
        """Upload and hash a document"""
        doc_hash = hash_document(file_content)

        # Check for duplicate hash
        existing = self.db.query(Document).filter(Document.doc_hash == doc_hash).first()
        if existing:
            raise ValueError(f"Document already exists on property {existing.property_id}")

        document = Document(
            property_id=property_id,
            file_url=file_url,
            file_name=file_name,
            doc_hash=doc_hash,
            doc_type=doc_type,
            verified=False
        )

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        return document

    def get_documents_for_property(self, property_id: int) -> List[Document]:
        """Get all documents for a property"""
        return self.db.query(Document).filter(Document.property_id == property_id).all()

    def verify_document(self, document_id: int) -> Document:
        """Mark a document as verified"""
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        document.verified = True
        self.db.commit()
        self.db.refresh(document)

        return document


class TrustScoreService:
    """Service for calculating property trust scores"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_property_trust_score(self, property_id: int) -> Dict[str, Any]:
        """Calculate comprehensive trust score for a property"""
        property_obj = self.db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise ValueError(f"Property {property_id} not found")

        # Get documents
        documents = self.db.query(Document).filter(Document.property_id == property_id).all()
        verified_docs = sum(1 for d in documents if d.verified)
        total_docs = len(documents)

        # Get ownership records
        ownership_records = self.db.query(OwnershipRecord).filter(
            OwnershipRecord.property_id == property_id
        ).all()

        # Calculate ownership clarity (based on chain length and verification)
        ownership_clarity = 0.8 if len(ownership_records) > 0 else 0.2
        if len(ownership_records) > 1:
            # Verify chain
            ownership_clarity = 1.0  # Assume verified for now

        # Get agent rating if exists
        from app.models import PropertyAgent, AgentAssignmentStatus
        agent_assignment = self.db.query(PropertyAgent).filter(
            PropertyAgent.property_id == property_id,
            PropertyAgent.status == AgentAssignmentStatus.ACTIVE
        ).first()

        agent_rating = 0.0
        if agent_assignment and agent_assignment.agent:
            agent_rating = agent_assignment.agent.rating or 0.0

        # Count fraud alerts
        from app.models import FraudAlert
        fraud_flags = self.db.query(FraudAlert).filter(
            FraudAlert.property_id == property_id,
            FraudAlert.resolved == False
        ).count()

        return calculate_trust_score(
            verified_docs=verified_docs,
            total_docs=total_docs,
            ownership_clarity=ownership_clarity,
            agent_rating=agent_rating,
            fraud_flags=fraud_flags
        )
