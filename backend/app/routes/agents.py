"""
Agent Routes for RealLink Ecosystem
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.models import Agent, User, PropertyAgent, AgentAssignmentStatus
from app.dependencies import get_db
from app.services.agent_service import AgentService, PropertyAgentService
from app.routes.auth import get_current_user

router = APIRouter()


# Pydantic models
class AgentCreate(BaseModel):
    license_number: Optional[str] = None


class AgentResponse(BaseModel):
    id: int
    user_id: int
    license_number: Optional[str]
    rating: float
    verified: bool
    total_deals: int
    created_at: datetime

    class Config:
        from_attributes = True


class AssignmentRequest(BaseModel):
    property_id: int
    notes: Optional[str] = None


class AssignmentResponse(BaseModel):
    id: int
    property_id: int
    agent_id: int
    status: str
    assigned_at: datetime
    completed_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


@router.post("/profile", response_model=AgentResponse)
async def create_agent_profile(
    data: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create agent profile for current user"""
    service = AgentService(db)

    try:
        agent = service.create_agent_profile(
            user_id=current_user.id,
            license_number=data.license_number
        )

        return AgentResponse(
            id=agent.id,
            user_id=agent.user_id,
            license_number=agent.license_number,
            rating=agent.rating,
            verified=agent.verified,
            total_deals=agent.total_deals,
            created_at=agent.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/profile", response_model=dict)
async def get_my_agent_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get agent profile for current user with assignments"""
    agent = db.query(Agent).filter(Agent.user_id == current_user.id).first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent profile not found")

    # Get assignments
    assignments = db.query(PropertyAgent).filter(
        PropertyAgent.agent_id == agent.id
    ).all()

    return {
        "agent": AgentResponse(
            id=agent.id,
            user_id=agent.user_id,
            license_number=agent.license_number,
            rating=agent.rating,
            verified=agent.verified,
            total_deals=agent.total_deals,
            created_at=agent.created_at
        ),
        "user": {
            "name": agent.user.name,
            "phone": agent.user.phone,
            "email": agent.user.email
        },
        "assignments": [
            AssignmentResponse(
                id=a.id,
                property_id=a.property_id,
                agent_id=a.agent_id,
                status=a.status.value,
                assigned_at=a.assigned_at,
                completed_at=a.completed_at,
                notes=a.notes
            ) for a in assignments
        ]
    }


@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    verified_only: bool = False,
    min_rating: float = 0.0,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """List all agents"""
    service = AgentService(db)
    agents = service.list_agents(
        verified_only=verified_only,
        min_rating=min_rating,
        skip=skip,
        limit=limit
    )

    return [
        AgentResponse(
            id=a.id,
            user_id=a.user_id,
            license_number=a.license_number,
            rating=a.rating,
            verified=a.verified,
            total_deals=a.total_deals,
            created_at=a.created_at
        ) for a in agents
    ]


@router.get("/{agent_id}", response_model=dict)
async def get_agent(
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Get agent details with assignments"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get assignments
    assignments = db.query(PropertyAgent).filter(
        PropertyAgent.agent_id == agent_id
    ).all()

    return {
        "agent": AgentResponse(
            id=agent.id,
            user_id=agent.user_id,
            license_number=agent.license_number,
            rating=agent.rating,
            verified=agent.verified,
            total_deals=agent.total_deals,
            created_at=agent.created_at
        ),
        "user": {
            "name": agent.user.name,
            "phone": agent.user.phone,
            "email": agent.user.email
        },
        "assignments": [
            AssignmentResponse(
                id=a.id,
                property_id=a.property_id,
                agent_id=a.agent_id,
                status=a.status.value,
                assigned_at=a.assigned_at,
                completed_at=a.completed_at,
                notes=a.notes
            ) for a in assignments
        ]
    }


# Property-Agent Assignment routes
@router.post("/assignments/request", response_model=AssignmentResponse)
async def request_assignment(
    data: AssignmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Agent requests to work on a property"""
    # Get agent profile
    agent = db.query(Agent).filter(Agent.user_id == current_user.id).first()

    if not agent:
        raise HTTPException(status_code=403, detail="User is not an agent")

    service = PropertyAgentService(db)

    try:
        assignment = service.request_assignment(
            property_id=data.property_id,
            agent_id=agent.id,
            notes=data.notes
        )

        return AssignmentResponse(
            id=assignment.id,
            property_id=assignment.property_id,
            agent_id=assignment.agent_id,
            status=assignment.status.value,
            assigned_at=assignment.assigned_at,
            completed_at=assignment.completed_at,
            notes=assignment.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/assignments/{assignment_id}/approve", response_model=AssignmentResponse)
async def approve_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Owner approves agent assignment"""
    service = PropertyAgentService(db)

    try:
        assignment = service.approve_assignment(
            assignment_id=assignment_id,
            owner_id=current_user.id
        )

        return AssignmentResponse(
            id=assignment.id,
            property_id=assignment.property_id,
            agent_id=assignment.agent_id,
            status=assignment.status.value,
            assigned_at=assignment.assigned_at,
            completed_at=assignment.completed_at,
            notes=assignment.notes
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/assignments/{assignment_id}/activate", response_model=AssignmentResponse)
async def activate_assignment(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """Activate an approved assignment"""
    service = PropertyAgentService(db)

    try:
        assignment = service.activate_assignment(assignment_id)

        return AssignmentResponse(
            id=assignment.id,
            property_id=assignment.property_id,
            agent_id=assignment.agent_id,
            status=assignment.status.value,
            assigned_at=assignment.assigned_at,
            completed_at=assignment.completed_at,
            notes=assignment.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/assignments/{assignment_id}/complete", response_model=AssignmentResponse)
async def complete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """Mark assignment as completed"""
    service = PropertyAgentService(db)

    try:
        assignment = service.complete_assignment(assignment_id)

        return AssignmentResponse(
            id=assignment.id,
            property_id=assignment.property_id,
            agent_id=assignment.agent_id,
            status=assignment.status.value,
            assigned_at=assignment.assigned_at,
            completed_at=assignment.completed_at,
            notes=assignment.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my-assignments", response_model=List[AssignmentResponse])
async def get_my_assignments(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get assignments for current agent"""
    agent = db.query(Agent).filter(Agent.user_id == current_user.id).first()

    if not agent:
        raise HTTPException(status_code=403, detail="User is not an agent")

    query = db.query(PropertyAgent).filter(PropertyAgent.agent_id == agent.id)

    if status:
        try:
            query = query.filter(PropertyAgent.status == AgentAssignmentStatus(status.upper()))
        except ValueError:
            pass

    assignments = query.all()

    return [
        AssignmentResponse(
            id=a.id,
            property_id=a.property_id,
            agent_id=a.agent_id,
            status=a.status.value,
            assigned_at=a.assigned_at,
            completed_at=a.completed_at,
            notes=a.notes
        ) for a in assignments
    ]
