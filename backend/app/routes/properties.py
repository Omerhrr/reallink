"""
Property Routes for RealLink Ecosystem
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models import (
    Property, Unit, Document, User, PropertyStatus, PropertyType, UnitStatus,
    PropertyImage, Inspection, AgentRating, TimelineEvent, Agent
)
from app.dependencies import get_db
from app.services.property_service import PropertyService, UnitService, DocumentService, TrustScoreService
from app.services.ledger_service import LedgerService
from app.routes.auth import get_current_user
from app.utils import hash_document
import json
import uuid
import os

router = APIRouter()

# Pydantic models
class PropertyCreate(BaseModel):
    title: str
    location: str
    property_type: str = "SALE"
    price: Optional[float] = None
    description: Optional[str] = None
    bedrooms: int = 0
    bathrooms: int = 0
    area_sqm: Optional[float] = None


class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    location: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area_sqm: Optional[float] = None


class UnitCreate(BaseModel):
    name: str
    price: float
    description: Optional[str] = None
    area_sqm: Optional[float] = None


class PropertyResponse(BaseModel):
    id: int
    property_id: str
    title: str
    location: str
    description: Optional[str]
    property_type: str
    status: str
    price: Optional[float]
    bedrooms: int
    bathrooms: int
    area_sqm: Optional[float]
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UnitResponse(BaseModel):
    id: int
    property_id: int
    name: str
    description: Optional[str]
    price: float
    status: str
    tenant_id: Optional[int]
    area_sqm: Optional[float]

    class Config:
        from_attributes = True


@router.post("/", response_model=PropertyResponse)
async def create_property(
    property_data: PropertyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new property"""
    service = PropertyService(db)

    try:
        prop_type = PropertyType(property_data.property_type.upper())
    except ValueError:
        prop_type = PropertyType.SALE

    property_obj = service.create_property(
        owner_id=current_user.id,
        title=property_data.title,
        location=property_data.location,
        property_type=prop_type,
        price=property_data.price,
        description=property_data.description,
        bedrooms=property_data.bedrooms,
        bathrooms=property_data.bathrooms,
        area_sqm=property_data.area_sqm
    )

    return PropertyResponse(
        id=property_obj.id,
        property_id=property_obj.property_id,
        title=property_obj.title,
        location=property_obj.location,
        description=property_obj.description,
        property_type=property_obj.property_type.value,
        status=property_obj.status.value,
        price=property_obj.price,
        bedrooms=property_obj.bedrooms,
        bathrooms=property_obj.bathrooms,
        area_sqm=property_obj.area_sqm,
        owner_id=property_obj.owner_id,
        created_at=property_obj.created_at
    )


@router.get("/", response_model=List[PropertyResponse])
async def list_properties(
    status: Optional[str] = None,
    location: Optional[str] = None,
    property_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """List properties with optional filters"""
    query = db.query(Property)

    if status:
        try:
            query = query.filter(Property.status == PropertyStatus(status.upper()))
        except ValueError:
            pass

    if location:
        query = query.filter(Property.location.ilike(f"%{location}%"))

    if property_type:
        try:
            query = query.filter(Property.property_type == PropertyType(property_type.upper()))
        except ValueError:
            pass

    if min_price is not None:
        query = query.filter(Property.price >= min_price)

    if max_price is not None:
        query = query.filter(Property.price <= max_price)

    properties = query.offset(skip).limit(limit).all()

    return [
        PropertyResponse(
            id=p.id,
            property_id=p.property_id,
            title=p.title,
            location=p.location,
            description=p.description,
            property_type=p.property_type.value,
            status=p.status.value,
            price=p.price,
            bedrooms=p.bedrooms,
            bathrooms=p.bathrooms,
            area_sqm=p.area_sqm,
            owner_id=p.owner_id,
            created_at=p.created_at
        ) for p in properties
    ]


@router.get("/{property_id}", response_model=dict)
async def get_property(
    property_id: int,
    db: Session = Depends(get_db)
):
    """Get property details with trust score"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Get units
    units = db.query(Unit).filter(Unit.property_id == property_id).all()

    # Get documents
    documents = db.query(Document).filter(Document.property_id == property_id).all()

    # Calculate trust score
    trust_service = TrustScoreService(db)
    trust_score = trust_service.calculate_property_trust_score(property_id)

    return {
        "property": PropertyResponse(
            id=property_obj.id,
            property_id=property_obj.property_id,
            title=property_obj.title,
            location=property_obj.location,
            description=property_obj.description,
            property_type=property_obj.property_type.value,
            status=property_obj.status.value,
            price=property_obj.price,
            bedrooms=property_obj.bedrooms,
            bathrooms=property_obj.bathrooms,
            area_sqm=property_obj.area_sqm,
            owner_id=property_obj.owner_id,
            created_at=property_obj.created_at
        ),
        "units": [
            UnitResponse(
                id=u.id,
                property_id=u.property_id,
                name=u.name,
                description=u.description,
                price=u.price,
                status=u.status.value,
                tenant_id=u.tenant_id,
                area_sqm=u.area_sqm
            ) for u in units
        ],
        "documents": [
            {
                "id": d.id,
                "file_name": d.file_name,
                "doc_type": d.doc_type,
                "verified": d.verified,
                "created_at": d.created_at.isoformat()
            } for d in documents
        ],
        "trust_score": trust_score
    }


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: int,
    property_data: PropertyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update property"""
    service = PropertyService(db)

    try:
        property_obj = service.update_property(
            property_id=property_id,
            user_id=current_user.id,
            title=property_data.title,
            location=property_data.location,
            price=property_data.price,
            description=property_data.description,
            bedrooms=property_data.bedrooms,
            bathrooms=property_data.bathrooms,
            area_sqm=property_data.area_sqm
        )

        return PropertyResponse(
            id=property_obj.id,
            property_id=property_obj.property_id,
            title=property_obj.title,
            location=property_obj.location,
            description=property_obj.description,
            property_type=property_obj.property_type.value,
            status=property_obj.status.value,
            price=property_obj.price,
            bedrooms=property_obj.bedrooms,
            bathrooms=property_obj.bathrooms,
            area_sqm=property_obj.area_sqm,
            owner_id=property_obj.owner_id,
            created_at=property_obj.created_at
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{property_id}/list", response_model=PropertyResponse)
async def list_property(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Move property from DRAFT to LISTED"""
    service = PropertyService(db)

    property_obj = service.get_property(property_id)
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    if property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can list property")

    try:
        property_obj = service.list_property(property_id)
        return PropertyResponse(
            id=property_obj.id,
            property_id=property_obj.property_id,
            title=property_obj.title,
            location=property_obj.location,
            description=property_obj.description,
            property_type=property_obj.property_type.value,
            status=property_obj.status.value,
            price=property_obj.price,
            bedrooms=property_obj.bedrooms,
            bathrooms=property_obj.bathrooms,
            area_sqm=property_obj.area_sqm,
            owner_id=property_obj.owner_id,
            created_at=property_obj.created_at
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{property_id}/under-offer", response_model=PropertyResponse)
async def mark_under_offer(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark property as UNDER_OFFER (offer received)"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Check permission - owner or active agent
    from app.models import PropertyAgent, AgentAssignmentStatus
    is_owner = property_obj.owner_id == current_user.id
    is_active_agent = db.query(PropertyAgent).filter(
        PropertyAgent.property_id == property_id,
        PropertyAgent.agent_id == current_user.id if hasattr(current_user, 'agent_id') else 0,
        PropertyAgent.status == AgentAssignmentStatus.ACTIVE
    ).first() is not None

    if not (is_owner or is_active_agent):
        raise HTTPException(status_code=403, detail="Only owner or active agent can mark property as under offer")

    # Check if transition is valid
    from app.services.state_machine import PropertyStateMachine
    if not PropertyStateMachine.can_transition(property_obj.status.value, "UNDER_OFFER"):
        raise HTTPException(status_code=400, detail=f"Cannot transition from {property_obj.status.value} to UNDER_OFFER")

    property_obj.status = PropertyStatus.UNDER_OFFER
    db.commit()
    db.refresh(property_obj)

    return PropertyResponse(
        id=property_obj.id,
        property_id=property_obj.property_id,
        title=property_obj.title,
        location=property_obj.location,
        description=property_obj.description,
        property_type=property_obj.property_type.value,
        status=property_obj.status.value,
        price=property_obj.price,
        bedrooms=property_obj.bedrooms,
        bathrooms=property_obj.bathrooms,
        area_sqm=property_obj.area_sqm,
        owner_id=property_obj.owner_id,
        created_at=property_obj.created_at
    )


@router.post("/{property_id}/reject-offer", response_model=PropertyResponse)
async def reject_offer(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject offer and return property to LISTED status"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    if property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can reject offers")

    # Check if transition is valid
    from app.services.state_machine import PropertyStateMachine
    if not PropertyStateMachine.can_transition(property_obj.status.value, "LISTED"):
        raise HTTPException(status_code=400, detail=f"Cannot transition from {property_obj.status.value} to LISTED")

    property_obj.status = PropertyStatus.LISTED
    db.commit()
    db.refresh(property_obj)

    return PropertyResponse(
        id=property_obj.id,
        property_id=property_obj.property_id,
        title=property_obj.title,
        location=property_obj.location,
        description=property_obj.description,
        property_type=property_obj.property_type.value,
        status=property_obj.status.value,
        price=property_obj.price,
        bedrooms=property_obj.bedrooms,
        bathrooms=property_obj.bathrooms,
        area_sqm=property_obj.area_sqm,
        owner_id=property_obj.owner_id,
        created_at=property_obj.created_at
    )


@router.post("/{property_id}/sell")
async def sell_property(
    property_id: int,
    new_owner_id: int,
    amount: Optional[float] = None,
    agent_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Complete property sale - transitions to SOLD status"""
    from app.services.ledger_service import LedgerService
    from app.services.state_machine import PropertyStateMachine
    from app.services.ussd_sms_service import SMSService

    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Only owner can sell
    if property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can sell property")

    # Check valid transition
    if not PropertyStateMachine.can_transition(property_obj.status.value, "SOLD"):
        raise HTTPException(status_code=400, detail=f"Cannot sell from {property_obj.status.value} status")

    # Transfer ownership
    ledger_service = LedgerService(db)
    result = ledger_service.transfer_ownership(
        property_id=property_id,
        from_user_id=current_user.id,
        to_user_id=new_owner_id,
        agent_id=agent_id,
        amount=amount
    )

    # Update property status
    property_obj.status = PropertyStatus.SOLD
    db.commit()

    # Complete agent assignment if exists
    if agent_id:
        from app.models import PropertyAgent, AgentAssignmentStatus
        agent_assignment = db.query(PropertyAgent).filter(
            PropertyAgent.property_id == property_id,
            PropertyAgent.agent_id == agent_id,
            PropertyAgent.status == AgentAssignmentStatus.ACTIVE
        ).first()
        if agent_assignment:
            agent_assignment.status = AgentAssignmentStatus.COMPLETED
            agent_assignment.completed_at = datetime.utcnow()
            db.commit()

    # Send SMS notification to new owner
    new_owner = db.query(User).filter(User.id == new_owner_id).first()
    if new_owner and new_owner.phone:
        sms_service = SMSService()
        await sms_service.send_sms(
            to=new_owner.phone,
            message=f"Congratulations! You are now the verified owner of property {property_obj.property_id} at {property_obj.location}. View on RealScan: realscan.io/p/{property_obj.property_id}"
        )

    return {
        "message": "Property sold successfully",
        "property_id": property_id,
        "new_owner_id": new_owner_id,
        "status": "SOLD",
        "ledger_record_id": result["record"].id
    }


@router.delete("/{property_id}")
async def delete_property(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete property"""
    service = PropertyService(db)

    try:
        service.delete_property(property_id, current_user.id)
        return {"message": "Property deleted successfully"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Unit endpoints
@router.post("/{property_id}/units", response_model=UnitResponse)
async def create_unit(
    property_id: int,
    unit_data: UnitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a unit for a property"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    if property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can add units")

    service = UnitService(db)
    unit = service.create_unit(
        property_id=property_id,
        name=unit_data.name,
        price=unit_data.price,
        description=unit_data.description,
        area_sqm=unit_data.area_sqm
    )

    return UnitResponse(
        id=unit.id,
        property_id=unit.property_id,
        name=unit.name,
        description=unit.description,
        price=unit.price,
        status=unit.status.value,
        tenant_id=unit.tenant_id,
        area_sqm=unit.area_sqm
    )


@router.get("/{property_id}/units", response_model=List[UnitResponse])
async def list_units(
    property_id: int,
    db: Session = Depends(get_db)
):
    """List all units for a property"""
    units = db.query(Unit).filter(Unit.property_id == property_id).all()

    return [
        UnitResponse(
            id=u.id,
            property_id=u.property_id,
            name=u.name,
            description=u.description,
            price=u.price,
            status=u.status.value,
            tenant_id=u.tenant_id,
            area_sqm=u.area_sqm
        ) for u in units
    ]


@router.post("/{property_id}/units/{unit_id}/rent")
async def rent_unit(
    property_id: int,
    unit_id: int,
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Rent a unit to a tenant"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Check if user can rent (owner or active agent)
    if property_obj.owner_id != current_user.id:
        # Check if user is active agent
        from app.models import PropertyAgent, AgentAssignmentStatus
        agent_assignment = db.query(PropertyAgent).filter(
            PropertyAgent.property_id == property_id,
            PropertyAgent.status == AgentAssignmentStatus.ACTIVE
        ).first()

        if not agent_assignment:
            raise HTTPException(status_code=403, detail="Not authorized to rent units")

    service = UnitService(db)
    try:
        unit = service.rent_unit(unit_id, tenant_id)
        return {"message": "Unit rented successfully", "unit_id": unit.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Document endpoints
@router.post("/{property_id}/documents")
async def upload_document(
    property_id: int,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a document for a property"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    if property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can upload documents")

    # Read file content
    content = await file.read()
    doc_hash = hash_document(content)

    # Check for duplicate
    service = DocumentService(db)

    # Save file (in production, save to cloud storage)
    file_url = f"/uploads/{property_id}/{file.filename}"

    try:
        document = service.upload_document(
            property_id=property_id,
            file_content=content,
            file_name=file.filename,
            file_url=file_url,
            doc_type=doc_type
        )

        return {
            "id": document.id,
            "file_name": document.file_name,
            "doc_hash": document.doc_hash,
            "doc_type": document.doc_type,
            "message": "Document uploaded successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{property_id}/ownership-history")
async def get_ownership_history(
    property_id: int,
    db: Session = Depends(get_db)
):
    """Get ownership history for a property"""
    from app.services.ledger_service import LedgerService

    service = LedgerService(db)
    records = service.get_ownership_history(property_id)

    return {
        "property_id": property_id,
        "records": [
            {
                "id": r.id,
                "owner_id": r.owner_id,
                "transaction_type": r.transaction_type,
                "previous_hash": r.previous_hash,
                "current_hash": r.current_hash,
                "timestamp": r.timestamp.isoformat()
            } for r in records
        ]
    }


@router.post("/{property_id}/transfer-ownership")
async def transfer_ownership(
    property_id: int,
    new_owner_id: int,
    amount: Optional[float] = None,
    agent_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Transfer property ownership"""
    from app.services.ledger_service import LedgerService

    service = LedgerService(db)

    try:
        result = service.transfer_ownership(
            property_id=property_id,
            from_user_id=current_user.id,
            to_user_id=new_owner_id,
            agent_id=agent_id,
            amount=amount
        )

        return {
            "message": "Ownership transferred successfully",
            "property_id": property_id,
            "new_owner_id": new_owner_id,
            "ledger_record_id": result["record"].id
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== IMAGE UPLOAD ENDPOINTS ====================

class ImageResponse(BaseModel):
    id: int
    property_id: int
    image_url: str
    caption: Optional[str]
    is_primary: bool
    order: int
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/{property_id}/images", response_model=ImageResponse)
async def upload_property_image(
    property_id: int,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    is_primary: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload an image for a property"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Check permission - owner can upload
    if property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can upload images")

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPEG, PNG, GIF, WebP")

    # Read file content
    content = await file.read()
    
    # Generate unique filename
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
    
    # In production, save to cloud storage (S3, Cloudinary, etc.)
    # For now, we'll use a URL pattern
    upload_dir = f"uploads/properties/{property_id}"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_filename)
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    image_url = f"/static/uploads/properties/{property_id}/{unique_filename}"

    # Get current max order
    max_order = db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id
    ).count()

    # If this is primary, unset other primary images
    if is_primary:
        db.query(PropertyImage).filter(
            PropertyImage.property_id == property_id,
            PropertyImage.is_primary == True
        ).update({"is_primary": False})

    # Create image record
    image = PropertyImage(
        property_id=property_id,
        image_url=image_url,
        image_path=file_path,
        caption=caption,
        is_primary=is_primary or max_order == 0,  # First image is primary by default
        order=max_order,
        uploaded_by=current_user.id
    )

    db.add(image)
    db.commit()
    db.refresh(image)

    return ImageResponse(
        id=image.id,
        property_id=image.property_id,
        image_url=image.image_url,
        caption=image.caption,
        is_primary=image.is_primary,
        order=image.order,
        created_at=image.created_at
    )


@router.get("/{property_id}/images", response_model=List[ImageResponse])
async def list_property_images(
    property_id: int,
    db: Session = Depends(get_db)
):
    """List all images for a property"""
    images = db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id
    ).order_by(PropertyImage.order).all()

    return [
        ImageResponse(
            id=img.id,
            property_id=img.property_id,
            image_url=img.image_url,
            caption=img.caption,
            is_primary=img.is_primary,
            order=img.order,
            created_at=img.created_at
        ) for img in images
    ]


@router.delete("/{property_id}/images/{image_id}")
async def delete_property_image(
    property_id: int,
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a property image"""
    image = db.query(PropertyImage).filter(
        PropertyImage.id == image_id,
        PropertyImage.property_id == property_id
    ).first()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can delete images")

    # Delete file from disk
    if image.image_path and os.path.exists(image.image_path):
        os.remove(image.image_path)

    db.delete(image)
    db.commit()

    return {"message": "Image deleted successfully"}


@router.post("/{property_id}/images/{image_id}/set-primary")
async def set_primary_image(
    property_id: int,
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set an image as the primary image for a property"""
    image = db.query(PropertyImage).filter(
        PropertyImage.id == image_id,
        PropertyImage.property_id == property_id
    ).first()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can set primary image")

    # Unset other primary images
    db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id,
        PropertyImage.is_primary == True
    ).update({"is_primary": False})

    # Set this image as primary
    image.is_primary = True
    db.commit()

    return {"message": "Primary image set successfully"}


# ==================== TIMELINE ENDPOINTS ====================

class TimelineEventResponse(BaseModel):
    id: int
    property_id: int
    event_type: str
    description: str
    user_id: Optional[int]
    metadata: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{property_id}/timeline", response_model=List[TimelineEventResponse])
async def get_property_timeline(
    property_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get timeline events for a property"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    events = db.query(TimelineEvent).filter(
        TimelineEvent.property_id == property_id
    ).order_by(TimelineEvent.created_at.desc()).offset(offset).limit(limit).all()

    return [
        TimelineEventResponse(
            id=e.id,
            property_id=e.property_id,
            event_type=e.event_type,
            description=e.description,
            user_id=e.user_id,
            metadata=json.loads(e.metadata_json) if e.metadata_json else None,
            created_at=e.created_at
        ) for e in events
    ]


# ==================== INSPECTION ENDPOINTS ====================

class InspectionCreate(BaseModel):
    scheduled_date: datetime
    notes: Optional[str] = None
    agent_id: Optional[int] = None


class InspectionResponse(BaseModel):
    id: int
    property_id: int
    user_id: int
    scheduled_date: datetime
    status: str
    notes: Optional[str]
    agent_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/{property_id}/inspections", response_model=InspectionResponse)
async def schedule_inspection(
    property_id: int,
    inspection_data: InspectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Schedule a property inspection"""
    from app.services.ussd_sms_service import SMSService

    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    inspection = Inspection(
        property_id=property_id,
        user_id=current_user.id,
        scheduled_date=inspection_data.scheduled_date,
        notes=inspection_data.notes,
        agent_id=inspection_data.agent_id,
        status="SCHEDULED"
    )

    db.add(inspection)

    # Create timeline event
    event = TimelineEvent(
        property_id=property_id,
        event_type="INSPECTION_SCHEDULED",
        description=f"Inspection scheduled for {inspection_data.scheduled_date.strftime('%Y-%m-%d %H:%M')}",
        user_id=current_user.id,
        metadata_json=json.dumps({
            "inspection_id": None,  # Will be updated after commit
            "scheduled_date": inspection_data.scheduled_date.isoformat()
        })
    )
    db.add(event)
    db.commit()
    db.refresh(inspection)

    # Update timeline event with inspection ID
    event.metadata_json = json.dumps({
        "inspection_id": inspection.id,
        "scheduled_date": inspection_data.scheduled_date.isoformat()
    })
    db.commit()

    # Send SMS notification
    if current_user.phone:
        sms_service = SMSService()
        await sms_service.send_inspection_scheduled(
            phone=current_user.phone,
            property_title=property_obj.title,
            date=inspection_data.scheduled_date.strftime('%Y-%m-%d'),
            time=inspection_data.scheduled_date.strftime('%H:%M')
        )

    return InspectionResponse(
        id=inspection.id,
        property_id=inspection.property_id,
        user_id=inspection.user_id,
        scheduled_date=inspection.scheduled_date,
        status=inspection.status,
        notes=inspection.notes,
        agent_id=inspection.agent_id,
        created_at=inspection.created_at
    )


@router.get("/{property_id}/inspections", response_model=List[InspectionResponse])
async def list_inspections(
    property_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List inspections for a property"""
    query = db.query(Inspection).filter(Inspection.property_id == property_id)

    if status:
        query = query.filter(Inspection.status == status.upper())

    inspections = query.order_by(Inspection.scheduled_date.desc()).all()

    return [
        InspectionResponse(
            id=i.id,
            property_id=i.property_id,
            user_id=i.user_id,
            scheduled_date=i.scheduled_date,
            status=i.status,
            notes=i.notes,
            agent_id=i.agent_id,
            created_at=i.created_at
        ) for i in inspections
    ]


@router.post("/{property_id}/inspections/{inspection_id}/complete")
async def complete_inspection(
    property_id: int,
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark an inspection as completed"""
    inspection = db.query(Inspection).filter(
        Inspection.id == inspection_id,
        Inspection.property_id == property_id
    ).first()

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    inspection.status = "COMPLETED"
    
    # Create timeline event
    event = TimelineEvent(
        property_id=property_id,
        event_type="INSPECTION_COMPLETED",
        description=f"Inspection completed",
        user_id=current_user.id,
        metadata_json=json.dumps({"inspection_id": inspection_id})
    )
    db.add(event)
    db.commit()

    return {"message": "Inspection completed successfully"}


# ==================== AGENT RATING ENDPOINTS ====================

class AgentRatingCreate(BaseModel):
    agent_id: int
    rating: int  # 1-5
    comment: Optional[str] = None
    transaction_type: Optional[str] = None


class AgentRatingResponse(BaseModel):
    id: int
    agent_id: int
    property_id: int
    user_id: int
    rating: int
    comment: Optional[str]
    transaction_type: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/{property_id}/rate-agent", response_model=AgentRatingResponse)
async def rate_agent(
    property_id: int,
    rating_data: AgentRatingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Rate an agent after a deal is completed"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Check if property is sold or fully rented (deal completed)
    if property_obj.status not in [PropertyStatus.SOLD, PropertyStatus.FULLY_RENTED]:
        raise HTTPException(
            status_code=400, 
            detail="Can only rate agents after a deal is completed (property sold or fully rented)"
        )

    # Validate rating
    if rating_data.rating < 1 or rating_data.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    # Check if agent exists
    agent = db.query(Agent).filter(Agent.id == rating_data.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check if user already rated this agent for this property
    existing_rating = db.query(AgentRating).filter(
        AgentRating.agent_id == rating_data.agent_id,
        AgentRating.property_id == property_id,
        AgentRating.user_id == current_user.id
    ).first()

    if existing_rating:
        raise HTTPException(status_code=400, detail="You have already rated this agent for this property")

    # Create rating
    rating = AgentRating(
        agent_id=rating_data.agent_id,
        property_id=property_id,
        user_id=current_user.id,
        rating=rating_data.rating,
        comment=rating_data.comment,
        transaction_type=rating_data.transaction_type
    )

    db.add(rating)

    # Update agent's average rating
    all_ratings = db.query(AgentRating).filter(
        AgentRating.agent_id == rating_data.agent_id
    ).all()

    total_ratings = len(all_ratings) + 1  # +1 for the new rating
    sum_ratings = sum(r.rating for r in all_ratings) + rating_data.rating
    new_average = sum_ratings / total_ratings

    agent.rating = round(new_average, 2)
    agent.total_deals = total_ratings

    # Create timeline event
    event = TimelineEvent(
        property_id=property_id,
        event_type="AGENT_RATED",
        description=f"Agent rated {rating_data.rating}/5 stars",
        user_id=current_user.id,
        metadata_json=json.dumps({
            "agent_id": rating_data.agent_id,
            "rating": rating_data.rating
        })
    )
    db.add(event)

    db.commit()
    db.refresh(rating)

    return AgentRatingResponse(
        id=rating.id,
        agent_id=rating.agent_id,
        property_id=rating.property_id,
        user_id=rating.user_id,
        rating=rating.rating,
        comment=rating.comment,
        transaction_type=rating.transaction_type,
        created_at=rating.created_at
    )


@router.get("/{property_id}/agent-ratings", response_model=List[AgentRatingResponse])
async def get_property_agent_ratings(
    property_id: int,
    db: Session = Depends(get_db)
):
    """Get agent ratings for a property"""
    ratings = db.query(AgentRating).filter(
        AgentRating.property_id == property_id
    ).order_by(AgentRating.created_at.desc()).all()

    return [
        AgentRatingResponse(
            id=r.id,
            agent_id=r.agent_id,
            property_id=r.property_id,
            user_id=r.user_id,
            rating=r.rating,
            comment=r.comment,
            transaction_type=r.transaction_type,
            created_at=r.created_at
        ) for r in ratings
    ]
