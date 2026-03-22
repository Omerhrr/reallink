"""
Property Routes for RealLink Ecosystem
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models import Property, Unit, Document, User, PropertyStatus, PropertyType, UnitStatus
from app.dependencies import get_db
from app.services.property_service import PropertyService, UnitService, DocumentService, TrustScoreService
from app.services.ledger_service import LedgerService
from app.routes.auth import get_current_user
from app.utils import hash_document

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
