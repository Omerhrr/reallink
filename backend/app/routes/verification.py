"""
Verification Routes for RealLink Ecosystem
RealScan Explorer and Fraud Detection

RealScan is like Etherscan but for Real Estate:
- Browse verified properties (like browsing blocks)
- View ownership transfer history (like transactions)
- Search by property ID, hash, or owner
- View statistics and analytics
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.models import (
    Property, Document, OwnershipRecord, FraudAlert, 
    PropertyStatus, User, Agent, PropertyAgent, AgentAssignmentStatus, PropertyType
)
from app.dependencies import get_db
from app.services.property_service import TrustScoreService
from app.services.ai_service import AIService
from app.utils.fraud_detection import FraudDetector

router = APIRouter()


# Pydantic models
class FraudAnalysisResponse(BaseModel):
    risk_level: str
    risk_score: int
    alerts: List[Dict[str, Any]]
    recommendation: str
    analyzed_at: str


@router.get("/property/{property_id}")
async def verify_property(
    property_id: int,
    db: Session = Depends(get_db)
):
    """Get complete verification data for a property (RealScan)"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Get documents
    documents = db.query(Document).filter(Document.property_id == property_id).all()

    # Get ownership history
    ownership_records = db.query(OwnershipRecord).filter(
        OwnershipRecord.property_id == property_id
    ).order_by(OwnershipRecord.timestamp.asc()).all()

    # Calculate trust score
    trust_service = TrustScoreService(db)
    trust_score = trust_service.calculate_property_trust_score(property_id)

    # Get fraud alerts
    fraud_alerts = db.query(FraudAlert).filter(
        FraudAlert.property_id == property_id
    ).all()

    # Verify ownership chain
    is_chain_valid = True
    chain_message = "Chain verified"
    if ownership_records:
        sorted_records = sorted(ownership_records, key=lambda r: r.timestamp)
        for i, record in enumerate(sorted_records[1:], 1):
            if record.previous_hash != sorted_records[i-1].current_hash:
                is_chain_valid = False
                chain_message = f"Chain broken at record {record.id}"
                break

    return {
        "property": {
            "id": property_obj.id,
            "property_id": property_obj.property_id,
            "title": property_obj.title,
            "location": property_obj.location,
            "status": property_obj.status.value,
            "created_at": property_obj.created_at.isoformat()
        },
        "trust_score": trust_score,
        "documents": [
            {
                "id": d.id,
                "file_name": d.file_name,
                "doc_type": d.doc_type,
                "verified": d.verified,
                "doc_hash": d.doc_hash[:16] + "..." if d.doc_hash else None
            } for d in documents
        ],
        "ownership_chain": {
            "is_valid": is_chain_valid,
            "message": chain_message,
            "records": [
                {
                    "id": r.id,
                    "owner_id": r.owner_id,
                    "transaction_type": r.transaction_type,
                    "timestamp": r.timestamp.isoformat()
                } for r in ownership_records
            ]
        },
        "fraud_alerts": [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "description": a.description,
                "resolved": a.resolved,
                "created_at": a.created_at.isoformat()
            } for a in fraud_alerts
        ]
    }


@router.get("/property/{property_id}/fraud-analysis")
async def analyze_fraud(
    property_id: int,
    db: Session = Depends(get_db)
):
    """Perform fraud analysis on a property"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Get related data
    documents = db.query(Document).filter(Document.property_id == property_id).all()
    ownership_records = db.query(OwnershipRecord).filter(
        OwnershipRecord.property_id == property_id
    ).all()

    # Get agent data
    agent_assignment = db.query(PropertyAgent).filter(
        PropertyAgent.property_id == property_id,
        PropertyAgent.status == AgentAssignmentStatus.ACTIVE
    ).first()

    agent_data = None
    if agent_assignment and agent_assignment.agent:
        agent_data = {
            "id": agent_assignment.agent.id,
            "verified": agent_assignment.agent.verified,
            "rating": agent_assignment.agent.rating,
            "total_deals": agent_assignment.agent.total_deals
        }

    # Run fraud detection
    detector = FraudDetector()
    property_data = {
        "id": property_obj.id,
        "title": property_obj.title,
        "location": property_obj.location,
        "price": property_obj.price,
        "status": property_obj.status.value
    }

    docs_data = [
        {
            "id": d.id,
            "doc_hash": d.doc_hash,
            "doc_type": d.doc_type,
            "verified": d.verified
        } for d in documents
    ]

    records_data = [
        {
            "id": r.id,
            "owner_id": r.owner_id,
            "previous_hash": r.previous_hash,
            "current_hash": r.current_hash,
            "transaction_type": r.transaction_type,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None
        } for r in ownership_records
    ]

    analysis = detector.analyze_property(
        property_data=property_data,
        documents=docs_data,
        ownership_records=records_data,
        agent_data=agent_data
    )

    return analysis


@router.post("/property/{property_id}/ai-analysis")
async def ai_analyze_property(
    property_id: int,
    db: Session = Depends(get_db)
):
    """AI-powered fraud analysis via OpenRouter"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Get related data
    documents = db.query(Document).filter(Document.property_id == property_id).all()
    ownership_records = db.query(OwnershipRecord).filter(
        OwnershipRecord.property_id == property_id
    ).all()

    # Get agent data
    agent_assignment = db.query(PropertyAgent).filter(
        PropertyAgent.property_id == property_id,
        PropertyAgent.status == AgentAssignmentStatus.ACTIVE
    ).first()

    agent_data = None
    if agent_assignment and agent_assignment.agent:
        agent_data = {
            "id": agent_assignment.agent.id,
            "verified": agent_assignment.agent.verified,
            "rating": agent_assignment.agent.rating
        }

    # Call AI service
    ai_service = AIService()
    analysis = await ai_service.analyze_fraud_risk(
        property_data={
            "id": property_obj.id,
            "title": property_obj.title,
            "location": property_obj.location,
            "price": property_obj.price,
            "property_type": property_obj.property_type.value,
            "status": property_obj.status.value
        },
        documents=[
            {
                "file_name": d.file_name,
                "doc_type": d.doc_type,
                "verified": d.verified
            } for d in documents
        ],
        ownership_records=[
            {
                "owner_id": r.owner_id,
                "transaction_type": r.transaction_type,
                "timestamp": str(r.timestamp)
            } for r in ownership_records
        ],
        agent_data=agent_data
    )

    return analysis


@router.get("/property/{property_id}/price-suggestion")
async def get_price_suggestion(
    property_id: int,
    db: Session = Depends(get_db)
):
    """Get AI-powered price suggestion"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Find similar properties
    similar_properties = db.query(Property).filter(
        Property.id != property_id,
        Property.location.ilike(f"%{property_obj.location.split(',')[0]}%"),
        Property.property_type == property_obj.property_type,
        Property.status == PropertyStatus.LISTED
    ).limit(10).all()

    # Call AI service
    ai_service = AIService()
    suggestion = await ai_service.suggest_price(
        property_data={
            "location": property_obj.location,
            "property_type": property_obj.property_type.value,
            "bedrooms": property_obj.bedrooms,
            "bathrooms": property_obj.bathrooms,
            "area_sqm": property_obj.area_sqm,
            "price": property_obj.price
        },
        similar_properties=[
            {
                "location": p.location,
                "price": p.price,
                "area_sqm": p.area_sqm
            } for p in similar_properties
        ]
    )

    return suggestion


@router.get("/property/{property_id}/trust-explanation")
async def explain_trust_score(
    property_id: int,
    db: Session = Depends(get_db)
):
    """Get AI explanation of trust score"""
    trust_service = TrustScoreService(db)
    trust_score = trust_service.calculate_property_trust_score(property_id)

    ai_service = AIService()
    explanation = await ai_service.explain_trust_score(trust_score)

    return {
        "property_id": property_id,
        "trust_score": trust_score,
        "explanation": explanation
    }


@router.get("/explorer")
async def realscan_explorer(
    location: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    property_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """RealScan Explorer - browse verified properties"""
    query = db.query(Property).filter(Property.status == PropertyStatus.LISTED)

    if location:
        query = query.filter(Property.location.ilike(f"%{location}%"))

    if min_price is not None:
        query = query.filter(Property.price >= min_price)

    if max_price is not None:
        query = query.filter(Property.price <= max_price)

    if property_type:
        try:
            query = query.filter(Property.property_type == PropertyType(property_type.upper()))
        except ValueError:
            pass

    properties = query.offset(skip).limit(limit).all()

    # Add trust scores
    trust_service = TrustScoreService(db)
    results = []
    for p in properties:
        trust = trust_service.calculate_property_trust_score(p.id)
        results.append({
            "id": p.id,
            "property_id": p.property_id,
            "title": p.title,
            "location": p.location,
            "price": p.price,
            "property_type": p.property_type.value,
            "bedrooms": p.bedrooms,
            "bathrooms": p.bathrooms,
            "trust_score": trust.get("score", 0)
        })

    return {
        "properties": results,
        "total": len(results),
        "skip": skip,
        "limit": limit
    }


# ==================== ETHERSCAN-LIKE FEATURES ====================

@router.get("/search")
async def global_search(
    q: str = Query(..., description="Search query (property ID, hash, owner name)"),
    db: Session = Depends(get_db)
):
    """
    Global search across properties, ownership records, and documents.
    Like Etherscan's search - can find by property ID, transaction hash, or owner.
    """
    results = {
        "properties": [],
        "ownership_records": [],
        "documents": []
    }
    
    search_term = f"%{q}%"

    # Search properties by ID, title, or property_id
    try:
        property_id = int(q)
        properties = db.query(Property).filter(
            (Property.id == property_id) | (Property.property_id.ilike(search_term))
        ).all()
    except ValueError:
        properties = db.query(Property).filter(
            (Property.title.ilike(search_term)) |
            (Property.location.ilike(search_term)) |
            (Property.property_id.ilike(search_term))
        ).limit(10).all()

    trust_service = TrustScoreService(db)
    for p in properties:
        trust = trust_service.calculate_property_trust_score(p.id)
        results["properties"].append({
            "id": p.id,
            "property_id": p.property_id,
            "title": p.title,
            "location": p.location,
            "price": p.price,
            "status": p.status.value,
            "trust_score": trust.get("score", 0)
        })

    # Search ownership records by hash
    ownership_records = db.query(OwnershipRecord).filter(
        (OwnershipRecord.current_hash.ilike(search_term)) |
        (OwnershipRecord.previous_hash.ilike(search_term))
    ).limit(10).all()

    for r in ownership_records:
        prop = db.query(Property).filter(Property.id == r.property_id).first()
        results["ownership_records"].append({
            "id": r.id,
            "property_id": r.property_id,
            "property_title": prop.title if prop else "Unknown",
            "transaction_type": r.transaction_type,
            "current_hash": r.current_hash[:20] + "..." if r.current_hash else None,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None
        })

    # Search documents by hash
    documents = db.query(Document).filter(
        Document.doc_hash.ilike(search_term)
    ).limit(10).all()

    for d in documents:
        prop = db.query(Property).filter(Property.id == d.property_id).first()
        results["documents"].append({
            "id": d.id,
            "property_id": d.property_id,
            "property_title": prop.title if prop else "Unknown",
            "file_name": d.file_name,
            "doc_type": d.doc_type,
            "verified": d.verified,
            "doc_hash": d.doc_hash[:20] + "..." if d.doc_hash else None
        })

    return {
        "query": q,
        "results": results,
        "total_found": (
            len(results["properties"]) + 
            len(results["ownership_records"]) + 
            len(results["documents"])
        )
    }


@router.get("/recent-transfers")
async def get_recent_transfers(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get recent ownership transfers.
    Like Etherscan's recent transactions list.
    """
    recent_records = db.query(OwnershipRecord).order_by(
        desc(OwnershipRecord.timestamp)
    ).limit(limit).all()

    transfers = []
    for record in recent_records:
        property_obj = db.query(Property).filter(
            Property.id == record.property_id
        ).first()

        # Get owner info
        owner = db.query(User).filter(User.id == record.owner_id).first()

        transfers.append({
            "record_id": record.id,
            "transaction_hash": record.current_hash,
            "property_id": record.property_id,
            "property_title": property_obj.title if property_obj else "Unknown",
            "property_location": property_obj.location if property_obj else "Unknown",
            "transaction_type": record.transaction_type,
            "owner_id": record.owner_id,
            "owner_name": owner.name if owner else "Unknown",
            "amount": record.amount,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
            "block_number": record.id  # Like Etherscan block number
        })

    return {
        "transfers": transfers,
        "total": len(transfers)
    }


@router.get("/transfer/{record_id}")
async def get_transfer_detail(
    record_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about an ownership transfer.
    Like Etherscan's transaction detail page.
    """
    record = db.query(OwnershipRecord).filter(OwnershipRecord.id == record_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Transfer record not found")

    property_obj = db.query(Property).filter(Property.id == record.property_id).first()
    owner = db.query(User).filter(User.id == record.owner_id).first()

    # Get previous record for chain verification
    prev_record = db.query(OwnershipRecord).filter(
        OwnershipRecord.property_id == record.property_id,
        OwnershipRecord.timestamp < record.timestamp
    ).order_by(desc(OwnershipRecord.timestamp)).first() if record.previous_hash else None

    # Get next record
    next_record = db.query(OwnershipRecord).filter(
        OwnershipRecord.property_id == record.property_id,
        OwnershipRecord.timestamp > record.timestamp
    ).order_by(OwnershipRecord.timestamp).first()

    return {
        "transfer": {
            "record_id": record.id,
            "transaction_hash": record.current_hash,
            "previous_hash": record.previous_hash,
            "transaction_type": record.transaction_type,
            "amount": record.amount,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
            "notes": record.notes
        },
        "property": {
            "id": property_obj.id,
            "property_id": property_obj.property_id,
            "title": property_obj.title,
            "location": property_obj.location
        } if property_obj else None,
        "owner": {
            "id": owner.id,
            "name": owner.name,
            "phone": owner.phone[:6] + "****" if owner.phone else None
        } if owner else None,
        "chain_info": {
            "previous_transfer_id": prev_record.id if prev_record else None,
            "next_transfer_id": next_record.id if next_record else None,
            "chain_position": db.query(OwnershipRecord).filter(
                OwnershipRecord.property_id == record.property_id,
                OwnershipRecord.timestamp <= record.timestamp
            ).count()
        }
    }


@router.get("/statistics")
async def get_realscan_statistics(
    db: Session = Depends(get_db)
):
    """
    Get RealScan statistics dashboard data.
    Like Etherscan's homepage statistics.
    """
    trust_service = TrustScoreService(db)

    # Total properties by status
    total_properties = db.query(Property).count()
    listed_properties = db.query(Property).filter(
        Property.status == PropertyStatus.LISTED
    ).count()
    draft_properties = db.query(Property).filter(
        Property.status == PropertyStatus.DRAFT
    ).count()
    sold_properties = db.query(Property).filter(
        Property.status == PropertyStatus.SOLD
    ).count()

    # Total ownership transfers
    total_transfers = db.query(OwnershipRecord).count()
    transfers_today = db.query(OwnershipRecord).filter(
        OwnershipRecord.timestamp >= datetime.utcnow() - timedelta(days=1)
    ).count()
    transfers_this_week = db.query(OwnershipRecord).filter(
        OwnershipRecord.timestamp >= datetime.utcnow() - timedelta(weeks=1)
    ).count()

    # Trust score distribution
    all_properties = db.query(Property).filter(
        Property.status.in_([PropertyStatus.LISTED, PropertyStatus.SOLD])
    ).all()
    
    trust_distribution = {"high": 0, "medium": 0, "low": 0}
    avg_trust_score = 0
    total_trust = 0
    
    for prop in all_properties:
        trust = trust_service.calculate_property_trust_score(prop.id)
        score = trust.get("score", 0)
        total_trust += score
        
        if score >= 70:
            trust_distribution["high"] += 1
        elif score >= 40:
            trust_distribution["medium"] += 1
        else:
            trust_distribution["low"] += 1
    
    if all_properties:
        avg_trust_score = round(total_trust / len(all_properties), 1)

    # Documents verification
    total_documents = db.query(Document).count()
    verified_documents = db.query(Document).filter(Document.verified == True).count()

    # Fraud alerts
    total_alerts = db.query(FraudAlert).count()
    unresolved_alerts = db.query(FraudAlert).filter(FraudAlert.resolved == False).count()
    high_severity_alerts = db.query(FraudAlert).filter(
        FraudAlert.severity == "HIGH",
        FraudAlert.resolved == False
    ).count()

    # Registered users and agents
    total_users = db.query(User).count()
    total_agents = db.query(Agent).count()
    verified_agents = db.query(Agent).filter(Agent.verified == True).count()

    # Total market value (sum of listed properties)
    total_market_value = db.query(func.sum(Property.price)).filter(
        Property.status == PropertyStatus.LISTED,
        Property.price.isnot(None)
    ).scalar() or 0

    return {
        "properties": {
            "total": total_properties,
            "listed": listed_properties,
            "draft": draft_properties,
            "sold": sold_properties
        },
        "transfers": {
            "total": total_transfers,
            "today": transfers_today,
            "this_week": transfers_this_week
        },
        "trust_scores": {
            "average": avg_trust_score,
            "distribution": trust_distribution
        },
        "documents": {
            "total": total_documents,
            "verified": verified_documents,
            "verification_rate": round(verified_documents / total_documents * 100, 1) if total_documents > 0 else 0
        },
        "fraud": {
            "total_alerts": total_alerts,
            "unresolved": unresolved_alerts,
            "high_severity": high_severity_alerts
        },
        "users": {
            "total": total_users,
            "agents": total_agents,
            "verified_agents": verified_agents
        },
        "market": {
            "total_value": total_market_value,
            "formatted_value": f"₦{total_market_value:,.0f}" if total_market_value else "N/A"
        }
    }


@router.get("/ownership-chain/{property_id}")
async def get_full_ownership_chain(
    property_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the complete ownership chain for a property with verification status.
    Like viewing all transactions for an address on Etherscan.
    """
    property_obj = db.query(Property).filter(Property.id == property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    ownership_records = db.query(OwnershipRecord).filter(
        OwnershipRecord.property_id == property_id
    ).order_by(OwnershipRecord.timestamp.asc()).all()

    # Verify chain integrity
    chain_valid = True
    chain_break_at = None

    if ownership_records:
        sorted_records = sorted(ownership_records, key=lambda r: r.timestamp)
        for i in range(1, len(sorted_records)):
            if sorted_records[i].previous_hash != sorted_records[i-1].current_hash:
                chain_valid = False
                chain_break_at = i
                break

    chain = []
    for i, record in enumerate(ownership_records):
        owner = db.query(User).filter(User.id == record.owner_id).first()

        # Calculate transfer amount if available
        chain.append({
            "position": i + 1,
            "record_id": record.id,
            "transaction_hash": record.current_hash,
            "transaction_type": record.transaction_type,
            "owner": {
                "id": owner.id,
                "name": owner.name if owner else "Unknown"
            } if owner else {"id": record.owner_id, "name": "Unknown"},
            "amount": record.amount,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
            "notes": record.notes,
            "is_valid": chain_valid or (chain_break_at is None or i < chain_break_at)
        })

    return {
        "property": {
            "id": property_obj.id,
            "property_id": property_obj.property_id,
            "title": property_obj.title,
            "location": property_obj.location
        },
        "chain_valid": chain_valid,
        "chain_break_at": chain_break_at,
        "total_owners": len(chain),
        "chain": chain
    }


@router.get("/hash/{hash_value}")
async def search_by_hash(
    hash_value: str,
    db: Session = Depends(get_db)
):
    """
    Search by any hash value (document hash, ownership hash).
    Like Etherscan's hash search.
    """
    # Search in ownership records
    ownership = db.query(OwnershipRecord).filter(
        (OwnershipRecord.current_hash == hash_value) |
        (OwnershipRecord.previous_hash == hash_value)
    ).first()

    if ownership:
        return {
            "type": "ownership_record",
            "data": {
                "record_id": ownership.id,
                "property_id": ownership.property_id,
                "transaction_type": ownership.transaction_type,
                "current_hash": ownership.current_hash,
                "previous_hash": ownership.previous_hash,
                "timestamp": ownership.timestamp.isoformat() if ownership.timestamp else None
            }
        }

    # Search in documents
    document = db.query(Document).filter(Document.doc_hash == hash_value).first()

    if document:
        return {
            "type": "document",
            "data": {
                "id": document.id,
                "property_id": document.property_id,
                "file_name": document.file_name,
                "doc_type": document.doc_type,
                "verified": document.verified,
                "doc_hash": document.doc_hash
            }
        }

    raise HTTPException(status_code=404, detail="Hash not found in any records")
