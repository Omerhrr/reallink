"""
Fraud Detection Service for RealLink Ecosystem
Rule-based and AI-powered fraud detection
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FraudType(str, Enum):
    DUPLICATE_DOCUMENT = "duplicate_document"
    DUPLICATE_PROPERTY = "duplicate_property"
    MULTIPLE_LISTINGS = "multiple_listings"
    SUSPICIOUS_AGENT = "suspicious_agent"
    AI_DETECTED = "ai_detected"
    OWNERSHIP_MISMATCH = "ownership_mismatch"
    PRICE_ANOMALY = "price_anomaly"


class FraudDetector:
    """Fraud detection engine with rule-based and AI analysis"""

    def __init__(self):
        self.rules = [
            self._check_duplicate_document,
            self._check_duplicate_property,
            self._check_multiple_listings,
            self._check_suspicious_agent,
            self._check_ownership_mismatch,
            self._check_price_anomaly,
        ]

    def analyze_property(
        self,
        property_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
        ownership_records: List[Dict[str, Any]],
        agent_data: Optional[Dict[str, Any]] = None,
        similar_properties: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive fraud analysis on a property
        Returns risk assessment with score and reasons
        """
        alerts = []
        total_risk_score = 0

        # Run all rule-based checks
        for rule in self.rules:
            try:
                alert = rule(
                    property_data=property_data,
                    documents=documents,
                    ownership_records=ownership_records,
                    agent_data=agent_data,
                    similar_properties=similar_properties or []
                )
                if alert:
                    alerts.append(alert)
                    total_risk_score += alert.get("risk_points", 0)
            except Exception as e:
                alerts.append({
                    "type": "analysis_error",
                    "severity": RiskLevel.LOW.value,
                    "message": f"Analysis error: {str(e)}",
                    "risk_points": 0
                })

        # Calculate overall risk level
        if total_risk_score >= 50:
            risk_level = RiskLevel.HIGH
        elif total_risk_score >= 25:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        return {
            "risk_level": risk_level.value,
            "risk_score": min(100, total_risk_score),
            "alerts": alerts,
            "analyzed_at": datetime.utcnow().isoformat(),
            "recommendation": self._get_recommendation(risk_level, alerts)
        }

    def _check_duplicate_document(
        self,
        property_data: Dict,
        documents: List[Dict],
        **kwargs
    ) -> Optional[Dict]:
        """Check for duplicate document hashes across properties"""
        doc_hashes = [doc.get("doc_hash") for doc in documents]
        # This would check against database for duplicates
        # For now, check within property
        if len(doc_hashes) != len(set(doc_hashes)):
            return {
                "type": FraudType.DUPLICATE_DOCUMENT.value,
                "severity": RiskLevel.HIGH.value,
                "message": "Duplicate documents detected within this property",
                "risk_points": 40
            }
        return None

    def _check_duplicate_property(
        self,
        property_data: Dict,
        similar_properties: List[Dict],
        **kwargs
    ) -> Optional[Dict]:
        """Check for similar properties that might be duplicates"""
        if len(similar_properties) > 0:
            return {
                "type": FraudType.DUPLICATE_PROPERTY.value,
                "severity": RiskLevel.HIGH.value,
                "message": f"Found {len(similar_properties)} similar property listings",
                "risk_points": 50,
                "details": similar_properties[:3]
            }
        return None

    def _check_multiple_listings(
        self,
        property_data: Dict,
        **kwargs
    ) -> Optional[Dict]:
        """Check for multiple agents listing same property"""
        # This would be populated from database check
        return None

    def _check_suspicious_agent(
        self,
        property_data: Dict,
        agent_data: Optional[Dict],
        **kwargs
    ) -> Optional[Dict]:
        """Analyze agent for suspicious patterns"""
        if not agent_data:
            return None

        alerts = []
        risk_points = 0

        # Check if agent is unverified
        if not agent_data.get("verified"):
            alerts.append("Agent is not verified")
            risk_points += 10

        # Check agent rating
        if agent_data.get("rating", 0) < 2.5:
            alerts.append("Agent has low rating")
            risk_points += 15

        # Check deal volume (too many or too few could be suspicious)
        total_deals = agent_data.get("total_deals", 0)
        if total_deals > 100:
            alerts.append("Agent has unusually high deal volume")
            risk_points += 5

        if alerts:
            return {
                "type": FraudType.SUSPICIOUS_AGENT.value,
                "severity": RiskLevel.MEDIUM.value,
                "message": "; ".join(alerts),
                "risk_points": risk_points
            }
        return None

    def _check_ownership_mismatch(
        self,
        property_data: Dict,
        ownership_records: List[Dict],
        **kwargs
    ) -> Optional[Dict]:
        """Verify ownership chain integrity"""
        if not ownership_records:
            return {
                "type": FraudType.OWNERSHIP_MISMATCH.value,
                "severity": RiskLevel.MEDIUM.value,
                "message": "No ownership records found",
                "risk_points": 20
            }

        # Check chain integrity
        sorted_records = sorted(ownership_records, key=lambda r: r.get("timestamp", ""))
        for i, record in enumerate(sorted_records[1:], 1):
            if record.get("previous_hash") != sorted_records[i-1].get("current_hash"):
                return {
                    "type": FraudType.OWNERSHIP_MISMATCH.value,
                    "severity": RiskLevel.HIGH.value,
                    "message": "Ownership chain integrity violated",
                    "risk_points": 45
                }
        return None

    def _check_price_anomaly(
        self,
        property_data: Dict,
        similar_properties: List[Dict],
        **kwargs
    ) -> Optional[Dict]:
        """Check for pricing anomalies compared to similar properties"""
        if not similar_properties:
            return None

        current_price = property_data.get("price", 0)
        if current_price <= 0:
            return None

        prices = [p.get("price", 0) for p in similar_properties if p.get("price", 0) > 0]
        if not prices:
            return None

        avg_price = sum(prices) / len(prices)

        # Check if price is significantly different
        deviation = abs(current_price - avg_price) / avg_price if avg_price > 0 else 0

        if deviation > 0.5:  # More than 50% deviation
            return {
                "type": FraudType.PRICE_ANOMALY.value,
                "severity": RiskLevel.MEDIUM.value,
                "message": f"Price deviates {deviation:.0%} from market average",
                "risk_points": 15,
                "details": {
                    "current_price": current_price,
                    "market_average": avg_price
                }
            }
        return None

    def _get_recommendation(self, risk_level: RiskLevel, alerts: List[Dict]) -> str:
        """Generate recommendation based on analysis"""
        if risk_level == RiskLevel.HIGH:
            return "HIGH RISK: Recommend manual verification before proceeding. Multiple fraud indicators detected."
        elif risk_level == RiskLevel.MEDIUM:
            return "MEDIUM RISK: Additional verification recommended. Some risk factors identified."
        else:
            return "LOW RISK: Property appears safe but always verify documents independently."


# AI-powered analysis (OpenRouter integration)
async def ai_fraud_analysis(
    property_data: Dict[str, Any],
    documents: List[Dict[str, Any]],
    ownership_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Use AI to analyze property for fraud indicators
    This function integrates with OpenRouter for AI analysis
    """
    # This would call OpenRouter API
    # For now, return structured prompt
    prompt = f"""
    Analyze the following property listing for potential fraud:

    Property: {json.dumps(property_data, indent=2)}

    Documents: {len(documents)} documents uploaded

    Ownership Chain: {len(ownership_records)} records

    Provide analysis in JSON format:
    {{
        "risk_level": "LOW|MEDIUM|HIGH",
        "score": 0-100,
        "reasons": ["list of risk factors"],
        "recommendation": "text recommendation"
    }}
    """

    return {
        "prompt": prompt,
        "model": "openai/gpt-4-turbo",
        "requires_api": True
    }


# Global detector instance
fraud_detector = FraudDetector()
