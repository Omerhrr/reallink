"""
Agent Service for RealLink Ecosystem
Handles agent lifecycle, assignments, and accountability
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import (
    Agent, User, PropertyAgent, Property, UserRole,
    AgentAssignmentStatus
)
from app.services.state_machine import (
    AgentAssignmentStateMachine, PermissionChecker, TransitionError
)


class AgentService:
    """Service for agent operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_agent_profile(
        self,
        user_id: int,
        license_number: Optional[str] = None
    ) -> Agent:
        """Create agent profile for a user"""
        # Check if user exists
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Check if agent profile already exists
        existing = self.db.query(Agent).filter(Agent.user_id == user_id).first()
        if existing:
            raise ValueError(f"Agent profile already exists for user {user_id}")

        agent = Agent(
            user_id=user_id,
            license_number=license_number,
            verified=False,
            rating=0.0,
            total_deals=0
        )

        self.db.add(agent)

        # Update user role
        user.role = UserRole.AGENT

        self.db.commit()
        self.db.refresh(agent)

        return agent

    def verify_agent(self, agent_id: int) -> Agent:
        """Verify an agent's profile"""
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        agent.verified = True
        self.db.commit()
        self.db.refresh(agent)

        return agent

    def update_agent_rating(self, agent_id: int) -> Agent:
        """Recalculate agent rating based on completed deals"""
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Get completed assignments
        completed = self.db.query(PropertyAgent).filter(
            PropertyAgent.agent_id == agent_id,
            PropertyAgent.status == AgentAssignmentStatus.COMPLETED
        ).all()

        agent.total_deals = len(completed)
        # Rating would be calculated from feedback in production
        self.db.commit()
        self.db.refresh(agent)

        return agent

    def get_agent(self, agent_id: int) -> Optional[Agent]:
        """Get agent by ID"""
        return self.db.query(Agent).filter(Agent.id == agent_id).first()

    def get_agent_by_user(self, user_id: int) -> Optional[Agent]:
        """Get agent by user ID"""
        return self.db.query(Agent).filter(Agent.user_id == user_id).first()

    def list_agents(
        self,
        verified_only: bool = False,
        min_rating: float = 0.0,
        skip: int = 0,
        limit: int = 20
    ) -> List[Agent]:
        """List agents with optional filters"""
        query = self.db.query(Agent)

        if verified_only:
            query = query.filter(Agent.verified == True)
        if min_rating > 0:
            query = query.filter(Agent.rating >= min_rating)

        return query.offset(skip).limit(limit).all()


class PropertyAgentService:
    """Service for property-agent assignments"""

    def __init__(self, db: Session):
        self.db = db

    def request_assignment(
        self,
        property_id: int,
        agent_id: int,
        notes: Optional[str] = None
    ) -> PropertyAgent:
        """
        Agent requests to work on a property
        Status: REQUESTED
        """
        # Verify property exists
        property_obj = self.db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise ValueError(f"Property {property_id} not found")

        # Verify agent exists
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Check if already assigned
        existing = self.db.query(PropertyAgent).filter(
            PropertyAgent.property_id == property_id,
            PropertyAgent.agent_id == agent_id
        ).first()

        if existing:
            raise ValueError("Agent already has assignment for this property")

        assignment = PropertyAgent(
            property_id=property_id,
            agent_id=agent_id,
            status=AgentAssignmentStatus.REQUESTED,
            notes=notes
        )

        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        return assignment

    def approve_assignment(
        self,
        assignment_id: int,
        owner_id: int
    ) -> PropertyAgent:
        """
        Owner approves agent assignment
        Status: REQUESTED -> APPROVED
        """
        assignment = self.db.query(PropertyAgent).filter(
            PropertyAgent.id == assignment_id
        ).first()

        if not assignment:
            raise ValueError(f"Assignment {assignment_id} not found")

        # Verify owner
        property_obj = self.db.query(Property).filter(
            Property.id == assignment.property_id
        ).first()

        if property_obj.owner_id != owner_id:
            raise PermissionError("Only property owner can approve assignments")

        # State transition
        new_status, success, message = AgentAssignmentStateMachine.transition(
            assignment.status.value,
            AgentAssignmentStatus.APPROVED.value
        )

        if not success:
            raise TransitionError(message)

        assignment.status = AgentAssignmentStatus(new_status)
        self.db.commit()
        self.db.refresh(assignment)

        return assignment

    def activate_assignment(self, assignment_id: int) -> PropertyAgent:
        """
        Activate approved assignment
        Status: APPROVED -> ACTIVE
        """
        assignment = self.db.query(PropertyAgent).filter(
            PropertyAgent.id == assignment_id
        ).first()

        if not assignment:
            raise ValueError(f"Assignment {assignment_id} not found")

        # Check MVP rule: only one active agent per property
        active_agents = self.db.query(PropertyAgent).filter(
            PropertyAgent.property_id == assignment.property_id,
            PropertyAgent.status == AgentAssignmentStatus.ACTIVE
        ).count()

        if active_agents > 0:
            raise ValueError("Property already has an active agent (MVP rule)")

        new_status, success, message = AgentAssignmentStateMachine.transition(
            assignment.status.value,
            AgentAssignmentStatus.ACTIVE.value
        )

        if not success:
            raise TransitionError(message)

        assignment.status = AgentAssignmentStatus(new_status)
        self.db.commit()
        self.db.refresh(assignment)

        return assignment

    def complete_assignment(self, assignment_id: int) -> PropertyAgent:
        """
        Mark assignment as completed
        Status: ACTIVE -> COMPLETED
        """
        assignment = self.db.query(PropertyAgent).filter(
            PropertyAgent.id == assignment_id
        ).first()

        if not assignment:
            raise ValueError(f"Assignment {assignment_id} not found")

        new_status, success, message = AgentAssignmentStateMachine.transition(
            assignment.status.value,
            AgentAssignmentStatus.COMPLETED.value
        )

        if not success:
            raise TransitionError(message)

        assignment.status = AgentAssignmentStatus(new_status)
        assignment.completed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(assignment)

        # Update agent stats
        from app.services.agent_service import AgentService
        agent_service = AgentService(self.db)
        agent_service.update_agent_rating(assignment.agent_id)

        return assignment

    def archive_assignment(self, assignment_id: int) -> PropertyAgent:
        """
        Archive completed or rejected assignment
        Status: COMPLETED -> ARCHIVED
        """
        assignment = self.db.query(PropertyAgent).filter(
            PropertyAgent.id == assignment_id
        ).first()

        if not assignment:
            raise ValueError(f"Assignment {assignment_id} not found")

        new_status, success, message = AgentAssignmentStateMachine.transition(
            assignment.status.value,
            AgentAssignmentStatus.ARCHIVED.value
        )

        if not success:
            raise TransitionError(message)

        assignment.status = AgentAssignmentStatus(new_status)
        self.db.commit()
        self.db.refresh(assignment)

        return assignment

    def get_property_agents(
        self,
        property_id: int,
        status: Optional[AgentAssignmentStatus] = None
    ) -> List[PropertyAgent]:
        """Get all agent assignments for a property"""
        query = self.db.query(PropertyAgent).filter(
            PropertyAgent.property_id == property_id
        )

        if status:
            query = query.filter(PropertyAgent.status == status)

        return query.all()

    def get_agent_assignments(
        self,
        agent_id: int,
        status: Optional[AgentAssignmentStatus] = None
    ) -> List[PropertyAgent]:
        """Get all assignments for an agent"""
        query = self.db.query(PropertyAgent).filter(
            PropertyAgent.agent_id == agent_id
        )

        if status:
            query = query.filter(PropertyAgent.status == status)

        return query.all()
