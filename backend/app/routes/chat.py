"""
Chat Routes for RealLink Ecosystem
AI-powered chat assistant endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json
import uuid

from app.models import User, Property, ChatSession, ChatMessage
from app.dependencies import get_db
from app.routes.auth import get_current_user
from app.services.ai_service import AIService

router = APIRouter()


# Pydantic models
class ChatMessageCreate(BaseModel):
    message: str
    session_id: Optional[str] = None
    context_type: Optional[str] = None  # property, general, search
    context_id: Optional[int] = None  # property_id if context is property


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: int
    session_id: str
    context_type: Optional[str]
    context_id: Optional[int]
    created_at: datetime
    messages: List[ChatMessageResponse]

    class Config:
        from_attributes = True


@router.post("/message", response_model=dict)
async def send_chat_message(
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message to the AI assistant and get a response"""
    ai_service = AIService()

    # Get or create session
    session = None
    if message_data.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == message_data.session_id,
            ChatSession.user_id == current_user.id
        ).first()

    if not session:
        session_id = str(uuid.uuid4())
        session = ChatSession(
            user_id=current_user.id,
            session_id=session_id,
            context_type=message_data.context_type,
            context_id=message_data.context_id
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # Save user message
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=message_data.message
    )
    db.add(user_message)
    db.commit()

    # Build context for AI
    context = await _build_chat_context(db, session, message_data.message)

    # Get previous messages for conversation history
    previous_messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.created_at).all()

    # Generate AI response
    try:
        ai_response = await _generate_ai_response(
            ai_service=ai_service,
            message=message_data.message,
            context=context,
            previous_messages=previous_messages
        )
    except Exception as e:
        ai_response = f"I apologize, but I'm having trouble processing your request right now. Please try again later. Error: {str(e)}"

    # Save assistant message
    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=ai_response
    )
    db.add(assistant_message)
    
    # Update session timestamp
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(assistant_message)

    return {
        "session_id": session.session_id,
        "message": ChatMessageResponse(
            id=assistant_message.id,
            role=assistant_message.role,
            content=assistant_message.content,
            created_at=assistant_message.created_at
        )
    }


@router.get("/sessions", response_model=List[dict])
async def list_chat_sessions(
    limit: int = 10,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's chat sessions"""
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).offset(offset).limit(limit).all()

    return [
        {
            "id": s.id,
            "session_id": s.session_id,
            "context_type": s.context_type,
            "context_id": s.context_id,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "message_count": db.query(ChatMessage).filter(ChatMessage.session_id == s.id).count()
        } for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific chat session with messages"""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.created_at).all()

    return ChatSessionResponse(
        id=session.id,
        session_id=session.session_id,
        context_type=session.context_type,
        context_id=session.context_id,
        created_at=session.created_at,
        messages=[
            ChatMessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at
            ) for m in messages
        ]
    )


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chat session"""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    db.delete(session)
    db.commit()

    return {"message": "Chat session deleted successfully"}


@router.post("/property/{property_id}/ask", response_model=dict)
async def ask_about_property(
    property_id: int,
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ask a question about a specific property"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")

    # Override context with property
    message_data.context_type = "property"
    message_data.context_id = property_id

    return await send_chat_message(message_data, current_user, db)


# Helper functions
async def _build_chat_context(db: Session, session: ChatSession, message: str) -> dict:
    """Build context for AI response"""
    context = {
        "user_id": session.user_id,
        "session_type": session.context_type,
    }

    # Add property context if relevant
    if session.context_type == "property" and session.context_id:
        property_obj = db.query(Property).filter(Property.id == session.context_id).first()
        if property_obj:
            context["property"] = {
                "id": property_obj.id,
                "property_id": property_obj.property_id,
                "title": property_obj.title,
                "location": property_obj.location,
                "price": property_obj.price,
                "status": property_obj.status.value,
                "property_type": property_obj.property_type.value,
                "bedrooms": property_obj.bedrooms,
                "bathrooms": property_obj.bathrooms,
                "area_sqm": property_obj.area_sqm,
                "description": property_obj.description
            }

    return context


async def _generate_ai_response(
    ai_service: AIService,
    message: str,
    context: dict,
    previous_messages: List[ChatMessage]
) -> str:
    """Generate AI response using the AI service"""
    # Build system prompt based on context
    system_prompt = """You are a helpful AI assistant for RealLink, a real estate platform for Africa. 
You help users with:
- Property searches and recommendations
- Questions about properties (location, price, features)
- Information about the buying/renting process
- Fraud prevention tips
- General real estate advice for the African market

Be helpful, concise, and professional. If you don't know something specific about a property, 
suggest the user contact an agent or view the property details on RealScan.

Always prioritize user safety and warn about potential fraud indicators."""

    # Add property context to prompt if available
    if "property" in context:
        prop = context["property"]
        system_prompt += f"""

The user is asking about this specific property:
- Title: {prop['title']}
- Location: {prop['location']}
- Price: ₦{prop['price']:,.0f}" if prop['price'] else "Price on request"
- Type: {prop['property_type']}
- Status: {prop['status']}
- Bedrooms: {prop['bedrooms']}, Bathrooms: {prop['bathrooms']}
- Area: {prop['area_sqm']} sqm" if prop['area_sqm'] else ""
- Description: {prop['description'][:500]}..." if prop['description'] else "No description available"

Provide specific information about this property when answering questions."""

    # Build conversation history
    conversation = []
    for msg in previous_messages[-10:]:  # Last 10 messages for context
        conversation.append({
            "role": msg.role,
            "content": msg.content
        })

    # Use AI service to generate response
    try:
        response = await ai_service._call_openrouter_with_system(
            system_prompt=system_prompt,
            messages=conversation + [{"role": "user", "content": message}]
        )
        return response
    except Exception as e:
        # Fallback response
        return _get_fallback_response(message, context)


def _get_fallback_response(message: str, context: dict) -> str:
    """Generate a fallback response when AI is unavailable"""
    message_lower = message.lower()

    if "price" in message_lower or "cost" in message_lower:
        if "property" in context:
            prop = context["property"]
            price = prop.get("price")
            if price:
                return f"The price for this property is ₦{price:,.0f}. For negotiation and payment details, please contact the property owner or agent."
            return "The price for this property is available on request. Please contact the owner or agent for details."
        return "I can help you with pricing information. Please specify which property you're interested in."

    if "location" in message_lower or "where" in message_lower:
        if "property" in context:
            return f"This property is located at: {context['property']['location']}"
        return "I can help with location information. Which property are you asking about?"

    if "contact" in message_lower or "agent" in message_lower:
        return "You can contact agents through their profile page on RealLink. Look for verified agents with good ratings for the best experience."

    if "safe" in message_lower or "fraud" in message_lower or "scam" in message_lower:
        return """Here are some tips to stay safe:
• Always verify property documents before payment
• Check the trust score on RealScan
• Meet sellers/agents in safe, public locations
• Don't pay full amount upfront
• Use verified agents with good ratings

If you suspect fraud, please report it through our platform."""

    return "I'm here to help you with your real estate needs. You can ask me about property details, pricing, locations, or general advice about buying or renting in Africa. How can I assist you today?"
