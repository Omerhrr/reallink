"""
USSD and SMS Routes for RealLink Ecosystem
Africa's Talking Integration
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.models import Subscription, Property, PropertyStatus, PropertyType
from app.dependencies import get_db
from app.services.ussd_sms_service import USSDService, SMSService

router = APIRouter()


# USSD Callback endpoint (for Africa's Talking)
@router.post("/callback")
async def ussd_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle USSD callback from Africa's Talking

    Expected parameters:
    - sessionId: Unique session ID
    - serviceCode: USSD code dialed
    - phoneNumber: User's phone number
    - text: User input (concatenated with *)
    """
    form_data = await request.form()

    session_id = form_data.get("sessionId", "")
    service_code = form_data.get("serviceCode", "")
    phone_number = form_data.get("phoneNumber", "")
    text = form_data.get("text", "")

    service = USSDService()
    response = await service.handle_ussd(
        session_id=session_id,
        service_code=service_code,
        phone_number=phone_number,
        text=text,
        db=db
    )

    return response


# SMS Callback endpoint
@router.post("/sms/callback")
async def sms_callback(request: Request):
    """
    Handle SMS delivery reports from Africa's Talking
    """
    form_data = await request.form()

    # Process delivery report
    # id = form_data.get("id")
    # status = form_data.get("status")
    # phone_number = form_data.get("phoneNumber")

    return "OK"


# Subscription management
@router.get("/subscriptions")
async def list_subscriptions(
    active_only: bool = True,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List all USSD subscriptions"""
    query = db.query(Subscription)

    if active_only:
        query = query.filter(Subscription.active == True)

    subscriptions = query.offset(skip).limit(limit).all()

    return {
        "subscriptions": [
            {
                "id": s.id,
                "phone": s.phone,
                "name": s.name,
                "location": s.location,
                "intent": s.intent,
                "active": s.active,
                "created_at": s.created_at.isoformat()
            } for s in subscriptions
        ],
        "total": len(subscriptions)
    }


@router.post("/subscriptions")
async def create_subscription(
    phone: str,
    name: str,
    location: str,
    intent: str,
    db: Session = Depends(get_db)
):
    """Create a new subscription (web interface)"""
    subscription = Subscription(
        phone=phone,
        name=name,
        location=location,
        intent=intent,
        active=True
    )

    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return {
        "id": subscription.id,
        "message": "Subscription created successfully"
    }


@router.delete("/subscriptions/{subscription_id}")
async def deactivate_subscription(
    subscription_id: int,
    db: Session = Depends(get_db)
):
    """Deactivate a subscription"""
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    subscription.active = False
    db.commit()

    return {"message": "Subscription deactivated"}


# SMS sending endpoints
@router.post("/sms/send")
async def send_sms(
    to: str,
    message: str,
    sender_id: Optional[str] = "RealLink",
    db: Session = Depends(get_db)
):
    """Send SMS via Africa's Talking"""
    service = SMSService()
    result = await service.send_sms(to=to, message=message, sender_id=sender_id)

    return result


@router.post("/sms/property-alert/{property_id}")
async def send_property_alert(
    property_id: int,
    db: Session = Depends(get_db)
):
    """Send property alert to matching subscribers"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()

    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    service = SMSService()
    results = await service.match_and_notify_subscribers(
        db=db,
        property_data={
            "property_id": property_obj.property_id,
            "title": property_obj.title,
            "location": property_obj.location,
            "price": property_obj.price,
            "property_type": property_obj.property_type.value
        }
    )

    return {
        "property_id": property_id,
        "notifications_sent": len([r for r in results if r.get("sent")]),
        "results": results
    }


@router.post("/sms/fraud-alert")
async def send_fraud_alert(
    phone: str,
    property_id: str,
    risk_level: str
):
    """Send fraud alert SMS"""
    service = SMSService()
    result = await service.send_fraud_alert(
        phone=phone,
        property_id=property_id,
        risk_level=risk_level
    )

    return result


# USSD property search
@router.get("/search")
async def ussd_property_search(
    location: str,
    intent: str,
    db: Session = Depends(get_db)
):
    """Search properties for USSD display"""
    property_type = PropertyType.RENT if intent == "rent" else PropertyType.SALE

    properties = db.query(Property).filter(
        Property.location.ilike(f"%{location}%"),
        Property.property_type == property_type,
        Property.status == PropertyStatus.LISTED
    ).limit(5).all()

    if not properties:
        return {
            "found": False,
            "message": "No properties found in your area. We will notify you when new listings are available."
        }

    return {
        "found": True,
        "properties": [
            {
                "id": p.id,
                "property_id": p.property_id,
                "title": p.title,
                "price": p.price,
                "location": p.location
            } for p in properties
        ]
    }
