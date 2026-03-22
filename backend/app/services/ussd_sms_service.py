"""
USSD and SMS Service for RealLink Ecosystem
Integrates with Africa's Talking API
"""

import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
import os


class USSDService:
    """
    USSD Service for Africa's Talking integration
    Handles USSD menu navigation and subscription
    """

    def __init__(self, username: Optional[str] = None, api_key: Optional[str] = None):
        self.username = username or os.getenv("AFRICAS_TALKING_USERNAME", "sandbox")
        self.api_key = api_key or os.getenv("AFRICAS_TALKING_API_KEY")
        self.base_url = "https://api.africastalking.com/version1"

    async def handle_ussd(
        self,
        session_id: str,
        service_code: str,
        phone_number: str,
        text: str,
        db: Session
    ) -> str:
        """
        Handle USSD request from Africa's Talking callback

        Flow:
        1. Dial *00123#
        2. Enter name
        3. Enter location
        4. Select intent (rent/buy)
        5. Store subscription
        """
        # Parse the text to determine current step
        steps = text.split("*") if text else []
        current_step = len(steps)

        if current_step == 0:
            # Initial request - welcome message
            return "CON Welcome to RealLink!\n\nEnter your name:"

        elif current_step == 1:
            # Name entered - ask for location
            return "CON Enter your preferred location:"

        elif current_step == 2:
            # Location entered - ask for intent
            return "CON What are you looking for?\n1. Rent\n2. Buy"

        elif current_step == 3:
            # Intent selected - confirm and save
            name = steps[0]
            location = steps[1]
            intent_choice = steps[2]

            if intent_choice == "1":
                intent = "rent"
            elif intent_choice == "2":
                intent = "buy"
            else:
                return "END Invalid selection. Please dial again."

            # Save subscription to database
            from app.models import Subscription

            subscription = Subscription(
                phone=phone_number,
                name=name,
                location=location,
                intent=intent,
                active=True
            )

            db.add(subscription)
            db.commit()

            return f"END Thank you {name}!\n\nYou will receive SMS alerts for properties in {location} for {intent}."

        else:
            return "END Session ended. Dial *00123# to start again."

    def get_menu_for_property_search(
        self,
        location: str,
        intent: str,
        db: Session
    ) -> str:
        """Generate USSD menu for property search results"""
        from app.models import Property, PropertyStatus, PropertyType

        property_type = PropertyType.RENT if intent == "rent" else PropertyType.SALE

        properties = db.query(Property).filter(
            Property.location.ilike(f"%{location}%"),
            Property.property_type == property_type,
            Property.status == PropertyStatus.LISTED
        ).limit(5).all()

        if not properties:
            return "END No properties found in your area. We will notify you when new listings are available."

        menu = "CON Properties found:\n\n"
        for i, prop in enumerate(properties, 1):
            price_str = f"₦{prop.price:,.0f}" if prop.price else "Price on request"
            menu += f"{i}. {prop.title}\n   {price_str}\n\n"

        menu += "Reply with number for details or 0 to exit"
        return menu


class SMSService:
    """
    SMS Service for Africa's Talking integration
    Handles sending SMS notifications
    """

    def __init__(self, username: Optional[str] = None, api_key: Optional[str] = None):
        self.username = username or os.getenv("AFRICAS_TALKING_USERNAME", "sandbox")
        self.api_key = api_key or os.getenv("AFRICAS_TALKING_API_KEY")
        self.base_url = "https://api.africastalking.com/version1"

    async def send_sms(
        self,
        to: str,
        message: str,
        sender_id: Optional[str] = "RealLink"
    ) -> Dict[str, Any]:
        """
        Send SMS via Africa's Talking API
        """
        if not self.api_key:
            # Sandbox mode - just log
            return {
                "success": True,
                "message": f"[SANDBOX] SMS to {to}: {message}",
                "sandbox": True
            }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/messaging",
                    headers={
                        "apiKey": self.api_key,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json"
                    },
                    data={
                        "username": self.username,
                        "to": to,
                        "message": message,
                        "from": sender_id
                    }
                )

                response.raise_for_status()
                return response.json()

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }

    async def send_property_alert(
        self,
        phone: str,
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send new property alert to subscriber"""
        message = f"""New Property Alert!
{property_data.get('title', 'Property')}
Location: {property_data.get('location', 'N/A')}
Price: ₦{property_data.get('price', 0):,}
Type: {property_data.get('property_type', 'N/A')}

Reply YES to express interest.
View on RealScan: reallink.africa/p/{property_data.get('property_id')}"""

        return await self.send_sms(phone, message)

    async def send_fraud_alert(
        self,
        phone: str,
        property_id: str,
        risk_level: str
    ) -> Dict[str, Any]:
        """Send fraud alert notification"""
        message = f"""REALSCAN ALERT
Property {property_id} has been flagged as {risk_level} RISK.
Please verify before proceeding.
Check details on RealScan."""

        return await self.send_sms(phone, message)

    async def send_inspection_reminder(
        self,
        phone: str,
        property_title: str,
        date: str,
        time: str
    ) -> Dict[str, Any]:
        """Send inspection scheduling reminder"""
        message = f"""INSPECTION REMINDER
Property: {property_title}
Date: {date}
Time: {time}

Please confirm your attendance.
RealLink Ecosystem"""

        return await self.send_sms(phone, message)

    async def send_sale_notification(
        self,
        phone: str,
        property_title: str
    ) -> Dict[str, Any]:
        """Send property sold notification"""
        message = f"""PROPERTY SOLD
{property_title}
This property has been sold.
Thank you for your interest.
RealLink Ecosystem"""

        return await self.send_sms(phone, message)

    async def send_rental_notification(
        self,
        phone: str,
        property_title: str,
        unit_name: str
    ) -> Dict[str, Any]:
        """Send property fully rented notification"""
        message = f"""PROPERTY RENTED
{property_title}
Unit: {unit_name}
This property is now fully rented.
RealLink Ecosystem"""

        return await self.send_sms(phone, message)

    async def send_inspection_scheduled(
        self,
        phone: str,
        property_title: str,
        date: str,
        time: str
    ) -> Dict[str, Any]:
        """Send SMS notification when inspection is scheduled"""
        message = f"""INSPECTION SCHEDULED
Property: {property_title}
Date: {date}
Time: {time}

You will receive a reminder before your inspection.
RealLink Ecosystem"""

        return await self.send_sms(phone, message)

    async def send_fully_rented_notification(
        self,
        phone: str,
        property_title: str,
        property_id: str,
        total_units: int
    ) -> Dict[str, Any]:
        """Send SMS when property becomes fully rented"""
        message = f"""FULLY RENTED
{property_title}
Property ID: {property_id}

All {total_units} unit(s) have been rented.
Thank you for using RealLink.
RealLink Ecosystem"""

        return await self.send_sms(phone, message)

    async def match_and_notify_subscribers(
        self,
        db: Session,
        property_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Find matching subscribers and send notifications
        """
        from app.models import Subscription, PropertyType

        # Find matching subscriptions
        location = property_data.get("location", "")
        property_type = property_data.get("property_type")

        query = db.query(Subscription).filter(
            Subscription.active == True,
            Subscription.location.ilike(f"%{location}%")
        )

        if property_type == PropertyType.RENT:
            query = query.filter(
                (Subscription.intent == "rent") | (Subscription.intent == None)
            )
        else:
            query = query.filter(
                (Subscription.intent == "buy") | (Subscription.intent == None)
            )

        subscriptions = query.all()

        results = []
        for sub in subscriptions:
            result = await self.send_property_alert(sub.phone, property_data)
            results.append({
                "phone": sub.phone,
                "name": sub.name,
                "sent": result.get("success", False)
            })

        return results


# Create default instances
ussd_service = USSDService()
sms_service = SMSService()
