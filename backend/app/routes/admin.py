"""
Admin Routes for RealLink Ecosystem
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.models import User, Property, Agent, Document, FraudAlert, Dispute, DisputeStatus, UserRole
from app.dependencies import get_db
from app.routes.auth import get_current_user

router = APIRouter()


# Verify admin access
async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/dashboard")
async def admin_dashboard(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get admin dashboard statistics"""
    total_users = db.query(User).count()
    total_properties = db.query(Property).count()
    total_agents = db.query(Agent).count()
    pending_disputes = db.query(Dispute).filter(Dispute.status == DisputeStatus.OPEN).count()
    fraud_alerts = db.query(FraudAlert).filter(FraudAlert.resolved == False).count()
    unverified_docs = db.query(Document).filter(Document.verified == False).count()

    return {
        "statistics": {
            "total_users": total_users,
            "total_properties": total_properties,
            "total_agents": total_agents,
            "pending_disputes": pending_disputes,
            "active_fraud_alerts": fraud_alerts,
            "unverified_documents": unverified_docs
        }
    }


@router.get("/users")
async def list_users(
    role: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """List all users"""
    query = db.query(User)

    if role:
        try:
            query = query.filter(User.role == UserRole(role.upper()))
        except ValueError:
            pass

    users = query.offset(skip).limit(limit).all()

    return {
        "users": [
            {
                "id": u.id,
                "name": u.name,
                "phone": u.phone,
                "email": u.email,
                "role": u.role.value,
                "created_at": u.created_at.isoformat()
            } for u in users
        ]
    }


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Update user role"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        user.role = UserRole(role.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")

    db.commit()
    db.refresh(user)

    return {"message": "User role updated", "new_role": user.role.value}


@router.get("/documents/pending")
async def list_pending_documents(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """List unverified documents"""
    documents = db.query(Document).filter(Document.verified == False).all()

    return {
        "documents": [
            {
                "id": d.id,
                "property_id": d.property_id,
                "file_name": d.file_name,
                "doc_type": d.doc_type,
                "created_at": d.created_at.isoformat()
            } for d in documents
        ]
    }


@router.post("/documents/{document_id}/verify")
async def verify_document(
    document_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Verify a document"""
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    document.verified = True
    db.commit()
    db.refresh(document)

    return {"message": "Document verified", "document_id": document.id}


@router.post("/agents/{agent_id}/verify")
async def verify_agent(
    agent_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Verify an agent"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.verified = True
    db.commit()
    db.refresh(agent)

    return {"message": "Agent verified", "agent_id": agent.id}


@router.get("/fraud-alerts")
async def list_fraud_alerts(
    resolved: bool = False,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """List fraud alerts"""
    query = db.query(FraudAlert).filter(FraudAlert.resolved == resolved)
    alerts = query.all()

    return {
        "alerts": [
            {
                "id": a.id,
                "property_id": a.property_id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "description": a.description,
                "resolved": a.resolved,
                "created_at": a.created_at.isoformat()
            } for a in alerts
        ]
    }


@router.post("/fraud-alerts/{alert_id}/resolve")
async def resolve_fraud_alert(
    alert_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Resolve a fraud alert"""
    alert = db.query(FraudAlert).filter(FraudAlert.id == alert_id).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.resolved = True
    db.commit()
    db.refresh(alert)

    return {"message": "Alert resolved", "alert_id": alert.id}


@router.get("/disputes")
async def list_disputes(
    status: Optional[str] = None,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """List disputes"""
    query = db.query(Dispute)

    if status:
        try:
            query = query.filter(Dispute.status == DisputeStatus(status.upper()))
        except ValueError:
            pass

    disputes = query.all()

    return {
        "disputes": [
            {
                "id": d.id,
                "property_id": d.property_id,
                "user_id": d.user_id,
                "reason": d.reason,
                "status": d.status.value,
                "resolution": d.resolution,
                "created_at": d.created_at.isoformat(),
                "resolved_at": d.resolved_at.isoformat() if d.resolved_at else None
            } for d in disputes
        ]
    }


@router.post("/disputes/{dispute_id}/resolve")
async def admin_resolve_dispute(
    dispute_id: int,
    resolution: str,
    status: str = "RESOLVED",
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin resolve a dispute"""
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

    return {
        "message": "Dispute resolved",
        "dispute_id": dispute.id,
        "status": dispute.status.value
    }
