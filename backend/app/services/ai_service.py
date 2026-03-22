"""
AI Service for RealLink Ecosystem
Integrates with OpenRouter for AI-powered features
"""

import json
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
import os


class AIService:
    """Service for AI-powered features via OpenRouter"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        self.model = "openai/gpt-4-turbo"  # Can be configured

    async def analyze_fraud_risk(
        self,
        property_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
        ownership_records: List[Dict[str, Any]],
        agent_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze property for fraud risk using AI
        Returns structured risk assessment
        """
        prompt = self._build_fraud_analysis_prompt(
            property_data, documents, ownership_records, agent_data
        )

        try:
            response = await self._call_openrouter(prompt)
            return self._parse_fraud_response(response)
        except Exception as e:
            return {
                "error": str(e),
                "risk_level": "UNKNOWN",
                "score": 0,
                "reasons": ["AI analysis failed"],
                "recommendation": "Manual verification recommended"
            }

    def _build_fraud_analysis_prompt(
        self,
        property_data: Dict[str, Any],
        documents: List[Dict[str, Any]],
        ownership_records: List[Dict[str, Any]],
        agent_data: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for fraud analysis"""
        return f"""
You are a real estate fraud detection expert for the African market.
Analyze the following property listing for potential fraud indicators.

PROPERTY DATA:
{json.dumps(property_data, indent=2, default=str)}

DOCUMENTS ({len(documents)} uploaded):
{json.dumps([{"name": d.get("file_name"), "type": d.get("doc_type"), "verified": d.get("verified")} for d in documents], indent=2)}

OWNERSHIP CHAIN ({len(ownership_records)} records):
{json.dumps([{"owner_id": r.get("owner_id"), "type": r.get("transaction_type"), "date": str(r.get("timestamp"))} for r in ownership_records], indent=2)}

AGENT DATA:
{json.dumps(agent_data, indent=2, default=str) if agent_data else "No agent assigned"}

Analyze for these fraud types:
1. Duplicate listings
2. Fake documents
3. Ownership disputes
4. Suspicious pricing
5. Agent red flags

Respond ONLY with valid JSON:
{{
    "risk_level": "LOW" | "MEDIUM" | "HIGH",
    "score": <0-100>,
    "reasons": ["list of specific risk factors found"],
    "recommendation": "<detailed recommendation>"
}}
"""

    def _parse_fraud_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response into structured format"""
        try:
            # Try to extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        return {
            "risk_level": "MEDIUM",
            "score": 50,
            "reasons": ["Could not parse AI response"],
            "recommendation": "Manual verification recommended",
            "raw_response": response
        }

    async def analyze_document(
        self,
        document_content: str,
        document_type: str
    ) -> Dict[str, Any]:
        """
        Analyze document for inconsistencies
        """
        prompt = f"""
You are a document verification expert.
Analyze this {document_type} document for potential issues:

DOCUMENT CONTENT:
{document_content[:2000]}  # Limit content size

Check for:
1. Inconsistencies in dates
2. Missing required fields
3. Suspicious formatting
4. Red flags for forgery

Respond ONLY with valid JSON:
{{
    "is_valid": true|false,
    "confidence": <0-100>,
    "issues": ["list of issues found"],
    "recommendation": "<text>"
}}
"""

        try:
            response = await self._call_openrouter(prompt)
            return self._parse_document_response(response)
        except Exception as e:
            return {
                "is_valid": None,
                "confidence": 0,
                "issues": [str(e)],
                "recommendation": "Manual review required"
            }

    def _parse_document_response(self, response: str) -> Dict[str, Any]:
        """Parse document analysis response"""
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(response[json_start:json_end])
        except json.JSONDecodeError:
            pass

        return {
            "is_valid": None,
            "confidence": 0,
            "issues": ["Parse error"],
            "recommendation": "Manual review required"
        }

    async def suggest_price(
        self,
        property_data: Dict[str, Any],
        similar_properties: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Suggest optimal price for a property
        """
        prompt = f"""
You are a real estate valuation expert for the African market.
Suggest optimal pricing for this property:

PROPERTY:
Location: {property_data.get("location")}
Type: {property_data.get("property_type")}
Bedrooms: {property_data.get("bedrooms")}
Bathrooms: {property_data.get("bathrooms")}
Area: {property_data.get("area_sqm")} sqm

SIMILAR PROPERTIES:
{json.dumps([{"location": p.get("location"), "price": p.get("price"), "area": p.get("area_sqm")} for p in similar_properties[:10]], indent=2)}

Respond ONLY with valid JSON:
{{
    "suggested_price": <number>,
    "price_range": {{"min": <number>, "max": <number>}},
    "factors": ["list of pricing factors"],
    "market_trend": "rising" | "stable" | "falling"
}}
"""

        try:
            response = await self._call_openrouter(prompt)
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            return json.loads(response[json_start:json_end])
        except Exception as e:
            return {
                "suggested_price": property_data.get("price"),
                "error": str(e)
            }

    async def explain_trust_score(
        self,
        trust_score_data: Dict[str, Any]
    ) -> str:
        """
        Generate human-readable explanation of trust score
        """
        prompt = f"""
Explain this property trust score in simple terms:

TRUST SCORE DATA:
{json.dumps(trust_score_data, indent=2)}

Provide a 2-3 sentence explanation suitable for a property buyer.
Focus on the most important factors and actionable advice.
"""

        try:
            response = await self._call_openrouter(prompt)
            return response.strip()
        except Exception:
            return f"This property has a trust score of {trust_score_data.get('score', 0)}/100. Please review the documents and ownership history carefully."

    async def _call_openrouter(self, prompt: str) -> str:
        """Make API call to OpenRouter"""
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://reallink.africa",
                    "X-Title": "RealLink Ecosystem"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a real estate fraud detection and analysis expert for the African market. Always respond with valid JSON when requested."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000
                },
                timeout=30.0
            )

            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _call_openrouter_with_system(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]]
    ) -> str:
        """Make API call to OpenRouter with custom system prompt and conversation history"""
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        # Build messages array with system prompt
        full_messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ] + messages

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://reallink.africa",
                    "X-Title": "RealLink Ecosystem"
                },
                json={
                    "model": self.model,
                    "messages": full_messages,
                    "temperature": 0.7,
                    "max_tokens": 1500
                },
                timeout=30.0
            )

            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


# Create default instance
ai_service = AIService()
