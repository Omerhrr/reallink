"""
Ledger Service for RealLink Ecosystem
Handles ownership records and hash-linked ledger operations
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import OwnershipRecord, Property, User, Transaction, TransactionType, PropertyStatus
from app.utils import create_ledger_hash, verify_ledger_chain
from app.services.state_machine import PropertyStateMachine, PermissionChecker, TransitionError


class LedgerService:
    """Service for ownership ledger operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_initial_record(
        self,
        property_id: int,
        owner_id: int
    ) -> OwnershipRecord:
        """Create initial ownership record for a new property"""
        timestamp = datetime.utcnow()

        # Create genesis hash
        current_hash = create_ledger_hash(
            property_id=property_id,
            owner_id=owner_id,
            previous_hash=None,
            timestamp=timestamp,
            transaction_type="initial"
        )

        record = OwnershipRecord(
            property_id=property_id,
            owner_id=owner_id,
            previous_hash=None,
            current_hash=current_hash,
            transaction_type="initial",
            timestamp=timestamp
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        return record

    def transfer_ownership(
        self,
        property_id: int,
        from_user_id: int,
        to_user_id: int,
        agent_id: Optional[int] = None,
        amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Transfer property ownership
        Creates new ledger record and updates property
        """
        # Get property
        property_obj = self.db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise ValueError(f"Property {property_id} not found")

        # Check permission
        can_transfer, reason = PermissionChecker.can_transfer_ownership(
            from_user_id, property_obj.owner_id
        )
        if not can_transfer:
            raise PermissionError(reason)

        # Check state transition
        new_status, success, message = PropertyStateMachine.transition(
            property_obj.status.value, PropertyStatus.SOLD.value
        )
        if not success:
            # Allow from more states
            if property_obj.status == PropertyStatus.LISTED:
                pass  # Can sell from LISTED
            else:
                raise TransitionError(message)

        # Get last ownership record
        last_record = self.db.query(OwnershipRecord).filter(
            OwnershipRecord.property_id == property_id
        ).order_by(OwnershipRecord.timestamp.desc()).first()

        timestamp = datetime.utcnow()
        previous_hash = last_record.current_hash if last_record else None

        # Create new ledger record
        current_hash = create_ledger_hash(
            property_id=property_id,
            owner_id=to_user_id,
            previous_hash=previous_hash,
            timestamp=timestamp,
            transaction_type="transfer"
        )

        record = OwnershipRecord(
            property_id=property_id,
            owner_id=to_user_id,
            previous_hash=previous_hash,
            current_hash=current_hash,
            transaction_type="transfer",
            timestamp=timestamp
        )

        self.db.add(record)

        # Update property
        property_obj.owner_id = to_user_id
        property_obj.status = PropertyStatus.SOLD

        # Create transaction record
        transaction = Transaction(
            property_id=property_id,
            transaction_type=TransactionType.SALE,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            agent_id=agent_id,
            amount=amount,
            timestamp=timestamp
        )

        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(record)

        return {
            "record": record,
            "transaction": transaction,
            "property": property_obj
        }

    def get_ownership_history(self, property_id: int) -> List[OwnershipRecord]:
        """Get complete ownership history for a property"""
        return self.db.query(OwnershipRecord).filter(
            OwnershipRecord.property_id == property_id
        ).order_by(OwnershipRecord.timestamp.asc()).all()

    def verify_ownership_chain(self, property_id: int) -> Dict[str, Any]:
        """Verify integrity of ownership chain"""
        records = self.get_ownership_history(property_id)
        is_valid, message = verify_ledger_chain([
            {
                "id": r.id,
                "property_id": r.property_id,
                "owner_id": r.owner_id,
                "previous_hash": r.previous_hash,
                "current_hash": r.current_hash,
                "timestamp": r.timestamp,
                "transaction_type": r.transaction_type
            }
            for r in records
        ])

        return {
            "property_id": property_id,
            "is_valid": is_valid,
            "message": message,
            "records_count": len(records)
        }

    def get_current_owner(self, property_id: int) -> Optional[User]:
        """Get current owner of a property"""
        property_obj = self.db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            return None

        return self.db.query(User).filter(User.id == property_obj.owner_id).first()


class TransactionService:
    """Service for transaction records"""

    def __init__(self, db: Session):
        self.db = db

    def record_rental(
        self,
        property_id: int,
        unit_id: int,
        tenant_id: int,
        landlord_id: int,
        agent_id: Optional[int] = None,
        amount: Optional[float] = None
    ) -> Transaction:
        """Record a rental transaction"""
        transaction = Transaction(
            property_id=property_id,
            transaction_type=TransactionType.RENT,
            unit_id=unit_id,
            from_user_id=landlord_id,
            to_user_id=tenant_id,
            agent_id=agent_id,
            amount=amount
        )

        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)

        return transaction

    def record_sale(
        self,
        property_id: int,
        buyer_id: int,
        seller_id: int,
        agent_id: Optional[int] = None,
        amount: Optional[float] = None
    ) -> Transaction:
        """Record a sale transaction"""
        transaction = Transaction(
            property_id=property_id,
            transaction_type=TransactionType.SALE,
            from_user_id=seller_id,
            to_user_id=buyer_id,
            agent_id=agent_id,
            amount=amount
        )

        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)

        return transaction

    def get_transactions_for_property(self, property_id: int) -> List[Transaction]:
        """Get all transactions for a property"""
        return self.db.query(Transaction).filter(
            Transaction.property_id == property_id
        ).order_by(Transaction.timestamp.desc()).all()

    def get_user_transactions(self, user_id: int) -> List[Transaction]:
        """Get all transactions involving a user"""
        return self.db.query(Transaction).filter(
            (Transaction.from_user_id == user_id) | (Transaction.to_user_id == user_id)
        ).order_by(Transaction.timestamp.desc()).all()
