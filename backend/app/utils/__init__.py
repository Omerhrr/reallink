"""
Utility functions for RealLink Ecosystem
Document hashing, ledger chain logic, and helper functions
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any


def generate_hash(data: str) -> str:
    """Generate SHA256 hash of a string"""
    return hashlib.sha256(data.encode()).hexdigest()


def hash_document(file_content: bytes) -> str:
    """Generate SHA256 hash of document content for fingerprinting"""
    return hashlib.sha256(file_content).hexdigest()


def hash_user_address(identifier: str) -> str:
    """Hash user identifier for privacy-preserving address"""
    salt = os.getenv("HASH_SALT", "reallink_default_salt_change_in_production")
    return generate_hash(f"{salt}:{identifier}")


def create_property_id(location: str, timestamp: datetime, owner_id: int) -> str:
    """Generate unique property ID"""
    data = f"{location}:{timestamp.isoformat()}:{owner_id}"
    return f"PROP-{generate_hash(data)[:12].upper()}"


def create_ledger_hash(
    property_id: int,
    owner_id: int,
    previous_hash: Optional[str],
    timestamp: datetime,
    transaction_type: str = "initial"
) -> str:
    """
    Create hash-linked ledger record hash
    This creates a chain where each record references the previous one
    """
    record_data = {
        "property_id": property_id,
        "owner_id": owner_id,
        "previous_hash": previous_hash or "GENESIS",
        "timestamp": timestamp.isoformat(),
        "transaction_type": transaction_type
    }
    return generate_hash(json.dumps(record_data, sort_keys=True))


def verify_ledger_chain(records: list) -> tuple[bool, str]:
    """
    Verify integrity of ownership ledger chain
    Returns (is_valid, message)
    """
    if not records:
        return False, "No records to verify"

    # Sort by timestamp
    sorted_records = sorted(records, key=lambda r: r.timestamp)

    for i, record in enumerate(sorted_records):
        # Recalculate the hash
        expected_hash = create_ledger_hash(
            property_id=record.property_id,
            owner_id=record.owner_id,
            previous_hash=record.previous_hash,
            timestamp=record.timestamp,
            transaction_type=record.transaction_type or "initial"
        )

        if record.current_hash != expected_hash:
            return False, f"Hash mismatch at record {record.id}"

        # Verify chain linkage (except for first record)
        if i > 0:
            if record.previous_hash != sorted_records[i - 1].current_hash:
                return False, f"Chain broken at record {record.id}"

    return True, "Ledger chain is valid"


def calculate_trust_score(
    verified_docs: int,
    total_docs: int,
    ownership_clarity: float,
    agent_rating: float,
    fraud_flags: int
) -> Dict[str, Any]:
    """
    Calculate property trust score (0-100)
    Returns score and breakdown
    """
    score = 0
    breakdown = {}

    # Document verification (up to 30 points)
    if total_docs > 0:
        doc_score = (verified_docs / total_docs) * 30
        score += doc_score
        breakdown["documents"] = {
            "score": doc_score,
            "verified": verified_docs,
            "total": total_docs
        }
    else:
        breakdown["documents"] = {"score": 0, "verified": 0, "total": 0}

    # Ownership clarity (up to 25 points)
    score += ownership_clarity * 25
    breakdown["ownership"] = {"score": ownership_clarity * 25}

    # Agent rating (up to 20 points)
    agent_score = min(agent_rating / 5.0, 1.0) * 20
    score += agent_score
    breakdown["agent"] = {"score": agent_score, "rating": agent_rating}

    # Fraud penalty (each flag reduces score by 15 points)
    fraud_penalty = min(fraud_flags * 15, 50)
    score = max(0, score - fraud_penalty)
    breakdown["fraud_flags"] = {"count": fraud_flags, "penalty": fraud_penalty}

    # Bonus for multiple verifications
    if verified_docs >= 3:
        score += 10
        breakdown["bonus"] = {"multi_doc_verification": 10}

    final_score = min(100, max(0, round(score)))
    breakdown["final_score"] = final_score

    return {
        "score": final_score,
        "breakdown": breakdown
    }


def detect_duplicate_hash(doc_hash: str, existing_hashes: list) -> bool:
    """Check if document hash already exists (potential fraud)"""
    return doc_hash in existing_hashes


def format_currency(amount: float, currency: str = "NGN") -> str:
    """Format currency with proper notation"""
    if currency == "NGN":
        if amount >= 1_000_000:
            return f"₦{amount/1_000_000:.1f}M"
        elif amount >= 1_000:
            return f"₦{amount/1_000:.0f}K"
        return f"₦{amount:.0f}"
    return f"{amount:.2f} {currency}"


def format_phone_international(phone: str, country_code: str = "+234") -> str:
    """Format Nigerian phone number for international use"""
    phone = phone.strip()
    if phone.startswith("0"):
        return country_code + phone[1:]
    if phone.startswith("+"):
        return phone
    return country_code + phone
