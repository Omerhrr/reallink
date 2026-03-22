"""
Interaction Routes for RealLink Ecosystem
User interests, disputes, and transactions
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models import Interest, Dispute, Transaction, Property, InterestStatus, DisputeStatus, User, UserRole
from app.dependencies import get_db
from app.routes.auth import get_current_user

router = APIRouter()


# Pydantic models
class InterestCreate(BaseModel):
    property_id: int
    unit_id: Optional[int] = None
    message: Optional[str] = None


class InterestResponse(BaseModel):
    id: int
    property_id: int
    user_id: int
    unit_id: Optional[int]
    status: str
    message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DisputeCreate(BaseModel):
    property_id: int
    reason: str


class DisputeResponse(BaseModel):
    id: int
    property_id: int
    user_id: int
    reason: str
    status: str
    resolution: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


# Interest endpoints
@router.post("/interests", response_model=InterestResponse)
async def create_interest(
    data: InterestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Express interest in a property"""
    # Check if property exists
    property_obj = db.query(Property).filter(Property.id == data.property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Check if interest already exists
    existing = db.query(Interest).filter(
        Interest.property_id == data.property_id,
        Interest.user_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Interest already expressed")

    interest = Interest(
        property_id=data.property_id,
        user_id=current_user.id,
        unit_id=data.unit_id,
        message=data.message,
        status=InterestStatus.PENDING
    )

    db.add(interest)
    db.commit()
    db.refresh(interest)

    return InterestResponse(
        id=interest.id,
        property_id=interest.property_id,
        user_id=interest.user_id,
        unit_id=interest.unit_id,
        status=interest.status.value,
        message=interest.message,
        created_at=interest.created_at
    )


@router.get("/interests", response_model=List[InterestResponse])
async def get_my_interests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's interests"""
    interests = db.query(Interest).filter(Interest.user_id == current_user.id).all()

    return [
        InterestResponse(
            id=i.id,
            property_id=i.property_id,
            user_id=i.user_id,
            unit_id=i.unit_id,
            status=i.status.value,
            message=i.message,
            created_at=i.created_at
        ) for i in interests
    ]


@router.get("/interests/property/{property_id}", response_model=List[InterestResponse])
async def get_property_interests(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get interests for a property (owner only)"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    if property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only property owner can view interests")

    interests = db.query(Interest).filter(Interest.property_id == property_id).all()

    return [
        InterestResponse(
            id=i.id,
            property_id=i.property_id,
            user_id=i.user_id,
            unit_id=i.unit_id,
            status=i.status.value,
            message=i.message,
            created_at=i.created_at
        ) for i in interests
    ]


@router.put("/interests/{interest_id}/status")
async def update_interest_status(
    interest_id: int,
    status: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update interest status (owner only)"""
    interest = db.query(Interest).filter(Interest.id == interest_id).first()

    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")

    property_obj = db.query(Property).filter(Property.id == interest.property_id).first()

    if property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only property owner can update interest status")

    try:
        interest.status = InterestStatus(status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    db.commit()
    db.refresh(interest)

    return {"message": "Interest status updated", "status": interest.status.value}


# Dispute endpoints
@router.post("/disputes", response_model=DisputeResponse)
async def create_dispute(
    data: DisputeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a dispute for a property"""
    property_obj = db.query(Property).filter(Property.id == data.property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    dispute = Dispute(
        property_id=data.property_id,
        user_id=current_user.id,
        reason=data.reason,
        status=DisputeStatus.OPEN
    )

    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    return DisputeResponse(
        id=dispute.id,
        property_id=dispute.property_id,
        user_id=dispute.user_id,
        reason=dispute.reason,
        status=dispute.status.value,
        resolution=dispute.resolution,
        created_at=dispute.created_at,
        resolved_at=dispute.resolved_at
    )


@router.get("/disputes", response_model=List[DisputeResponse])
async def get_my_disputes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's disputes"""
    disputes = db.query(Dispute).filter(Dispute.user_id == current_user.id).all()

    return [
        DisputeResponse(
            id=d.id,
            property_id=d.property_id,
            user_id=d.user_id,
            reason=d.reason,
            status=d.status.value,
            resolution=d.resolution,
            created_at=d.created_at,
            resolved_at=d.resolved_at
        ) for d in disputes
    ]


@router.put("/disputes/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: int,
    resolution: str,
    status: str = "RESOLVED",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resolve a dispute (admin only)"""
    # Check if user is admin
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can resolve disputes")

    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()

    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    try:
        dispute.status = DisputeStatus(status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    dispute.resolution = resolution
    dispute.resolved_at = datetime.utcnow()

    db.commit()
    db.refresh(dispute)

    return {"message": "Dispute resolved", "dispute_id": dispute.id}


# Transaction history
@router.get("/transactions")
async def get_my_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's transaction history"""
    transactions = db.query(Transaction).filter(
        (Transaction.from_user_id == current_user.id) |
        (Transaction.to_user_id == current_user.id)
    ).order_by(Transaction.timestamp.desc()).all()

    return [
        {
            "id": t.id,
            "property_id": t.property_id,
            "transaction_type": t.transaction_type.value,
            "unit_id": t.unit_id,
            "from_user_id": t.from_user_id,
            "to_user_id": t.to_user_id,
            "agent_id": t.agent_id,
            "amount": t.amount,
            "timestamp": t.timestamp.isoformat()
        } for t in transactions
    ]
