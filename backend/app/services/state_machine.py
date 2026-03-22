"""
State Machine Service for RealLink Ecosystem
Handles state transitions for properties, units, and agents
"""

from typing import Optional, Dict, Any, Tuple
from enum import Enum
from datetime import datetime


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted"""
    pass


class PropertyStateMachine:
    """
    State machine for property lifecycle management

    States: DRAFT -> LISTED -> UNDER_OFFER -> PARTIALLY_RENTED/FULLY_RENTED -> SOLD

    Valid transitions:
    - DRAFT -> LISTED
    - LISTED -> UNDER_OFFER
    - LISTED -> SOLD
    - UNDER_OFFER -> LISTED (offer rejected)
    - UNDER_OFFER -> SOLD
    - UNDER_OFFER -> PARTIALLY_RENTED
    - PARTIALLY_RENTED -> FULLY_RENTED
    - PARTIALLY_RENTED -> SOLD (rare case)
    - FULLY_RENTED -> LISTED (all rentals ended)
    """

    VALID_TRANSITIONS = {
        "DRAFT": ["LISTED"],
        "LISTED": ["UNDER_OFFER", "SOLD"],
        "UNDER_OFFER": ["LISTED", "SOLD", "PARTIALLY_RENTED", "FULLY_RENTED"],
        "PARTIALLY_RENTED": ["FULLY_RENTED", "SOLD"],
        "FULLY_RENTED": ["LISTED"],  # When all rentals end
        "SOLD": []  # Terminal state
    }

    @classmethod
    def can_transition(cls, current_state: str, target_state: str) -> bool:
        """Check if transition is valid"""
        valid_targets = cls.VALID_TRANSITIONS.get(current_state, [])
        return target_state in valid_targets

    @classmethod
    def transition(cls, current_state: str, target_state: str) -> Tuple[str, bool, str]:
        """
        Attempt state transition
        Returns: (new_state, success, message)
        """
        if cls.can_transition(current_state, target_state):
            return target_state, True, f"Transitioned from {current_state} to {target_state}"
        return current_state, False, f"Invalid transition: {current_state} -> {target_state}"

    @classmethod
    def get_valid_transitions(cls, current_state: str) -> list:
        """Get all valid next states"""
        return cls.VALID_TRANSITIONS.get(current_state, [])


class UnitStateMachine:
    """
    State machine for unit rental lifecycle

    States: AVAILABLE -> RESERVED -> RENTED

    Valid transitions:
    - AVAILABLE -> RESERVED
    - AVAILABLE -> RENTED
    - RESERVED -> AVAILABLE (reservation cancelled)
    - RESERVED -> RENTED
    - RENTED -> AVAILABLE (rental ended)
    """

    VALID_TRANSITIONS = {
        "AVAILABLE": ["RESERVED", "RENTED"],
        "RESERVED": ["AVAILABLE", "RENTED"],
        "RENTED": ["AVAILABLE"]
    }

    @classmethod
    def can_transition(cls, current_state: str, target_state: str) -> bool:
        """Check if transition is valid"""
        valid_targets = cls.VALID_TRANSITIONS.get(current_state, [])
        return target_state in valid_targets

    @classmethod
    def transition(cls, current_state: str, target_state: str) -> Tuple[str, bool, str]:
        """
        Attempt state transition
        Returns: (new_state, success, message)
        """
        if cls.can_transition(current_state, target_state):
            return target_state, True, f"Transitioned from {current_state} to {target_state}"
        return current_state, False, f"Invalid transition: {current_state} -> {target_state}"

    @classmethod
    def get_valid_transitions(cls, current_state: str) -> list:
        """Get all valid next states"""
        return cls.VALID_TRANSITIONS.get(current_state, [])


class AgentAssignmentStateMachine:
    """
    State machine for agent assignment lifecycle

    States: REQUESTED -> APPROVED -> ACTIVE -> COMPLETED -> ARCHIVED

    Valid transitions:
    - REQUESTED -> APPROVED (owner accepts)
    - REQUESTED -> ARCHIVED (owner rejects)
    - APPROVED -> ACTIVE (agent starts working)
    - ACTIVE -> COMPLETED (deal closed)
    - COMPLETED -> ARCHIVED
    """

    VALID_TRANSITIONS = {
        "REQUESTED": ["APPROVED", "ARCHIVED"],
        "APPROVED": ["ACTIVE"],
        "ACTIVE": ["COMPLETED"],
        "COMPLETED": ["ARCHIVED"],
        "ARCHIVED": []  # Terminal state
    }

    @classmethod
    def can_transition(cls, current_state: str, target_state: str) -> bool:
        """Check if transition is valid"""
        valid_targets = cls.VALID_TRANSITIONS.get(current_state, [])
        return target_state in valid_targets

    @classmethod
    def transition(cls, current_state: str, target_state: str) -> Tuple[str, bool, str]:
        """
        Attempt state transition
        Returns: (new_state, success, message)
        """
        if cls.can_transition(current_state, target_state):
            return target_state, True, f"Transitioned from {current_state} to {target_state}"
        return current_state, False, f"Invalid transition: {current_state} -> {target_state}"

    @classmethod
    def get_valid_transitions(cls, current_state: str) -> list:
        """Get all valid next states"""
        return cls.VALID_TRANSITIONS.get(current_state, [])


class PermissionChecker:
    """
    Permission checking for property operations
    Implements the permission rules from requirements
    """

    @staticmethod
    def can_modify_property(user_id: int, property_owner_id: int, agent_assignments: list) -> Tuple[bool, str]:
        """
        Check if user can modify property
        Rules:
        - Owner can always modify
        - Approved/Active agent can modify
        """
        if user_id == property_owner_id:
            return True, "User is property owner"

        # Check if user is an approved/active agent
        for assignment in agent_assignments:
            if assignment.get("agent_user_id") == user_id:
                if assignment.get("status") in ["APPROVED", "ACTIVE"]:
                    return True, "User is approved agent for this property"

        return False, "User is not authorized to modify this property"

    @staticmethod
    def can_transfer_ownership(user_id: int, property_owner_id: int) -> Tuple[bool, str]:
        """
        Check if user can transfer ownership
        Rule: Only owner can transfer ownership
        """
        if user_id == property_owner_id:
            return True, "User is property owner"
        return False, "Only the owner can transfer ownership"

    @staticmethod
    def can_rent_unit(unit_status: str) -> Tuple[bool, str]:
        """
        Check if unit can be rented
        Rule: Unit must be AVAILABLE
        """
        if unit_status == "AVAILABLE":
            return True, "Unit is available for rent"
        return False, f"Unit is {unit_status}, cannot rent"

    @staticmethod
    def check_active_agent_limit(property_agents: list) -> Tuple[bool, str]:
        """
        Check if property can have another active agent
        Rule: One ACTIVE agent per property (MVP)
        """
        active_agents = [a for a in property_agents if a.get("status") == "ACTIVE"]
        if len(active_agents) >= 1:
            return False, "Property already has an active agent"
        return True, "Property can accept an active agent"


# Export state machines
__all__ = [
    "TransitionError",
    "PropertyStateMachine",
    "UnitStateMachine",
    "AgentAssignmentStateMachine",
    "PermissionChecker"
]
