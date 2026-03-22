#!/usr/bin/env python3
"""
Demo Data Seed Script for RealLink Ecosystem
Populates the database with sample data for testing and demos

Run with: python seed_demo_data.py
"""

import sys
import os
from datetime import datetime, timedelta
import random

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.models import (
    Base, get_engine, get_session_maker, init_db,
    User, Property, Unit, Document, Agent, PropertyAgent,
    OwnershipRecord, Interest, Subscription, Dispute, FraudAlert,
    PropertyImage, Inspection, AgentRating, TimelineEvent, ChatSession, ChatMessage,
    Transaction,
    PropertyStatus, PropertyType, UnitStatus, AgentAssignmentStatus,
    UserRole, InterestStatus, DisputeStatus, TransactionType
)
from app.utils import hash_user_address, hash_document, create_property_id, create_ledger_hash


# Sample data constants
SAMPLE_LOCATIONS = [
    "Victoria Island, Lagos",
    "Ikoyi, Lagos",
    "Lekki Phase 1, Lagos",
    "Ikeja GRA, Lagos",
    "Yaba, Lagos",
    "Ibadan, Oyo State",
    "Abuja Central, FCT",
    "Maitama, Abuja",
    "Asokoro, Abuja",
    "Port Harcourt, Rivers"
]

PROPERTY_TITLES = [
    "Modern 4-Bedroom Duplex",
    "Luxury 3-Bedroom Apartment",
    "Spacious Family Home",
    "Executive Office Space",
    "Commercial Plot",
    "Semi-Detached Bungalow",
    "Studio Apartment",
    "Penthouse Suite",
    "Terrace House",
    "Commercial Complex",
]

DESCRIPTIONS = [
    "Beautiful property with modern finishes and excellent location. Features include spacious rooms, modern kitchen, and secure parking.",
    "Premium property in a sought-after neighborhood. Contemporary design with quality finishes and proximity to amenities.",
    "Stunning property offering exceptional value. Well-maintained gardens, secure compound, and easy access to main roads."
]

DOC_TYPES = ["deed", "title", "survey", "c_of_o", "building_approval", "tax_clearance"]


def create_demo_users(db: Session) -> dict:
    """Create demo users with different roles"""
    users = {}

    # Admin user
    admin = User(
        address=hash_user_address("admin@reallink.africa"),
        name="Admin User",
        phone="+2348012345678",
        email="admin@reallink.africa",
        password_hash="$2b$12$I0Xb/rJgsf4G.oaVLU9kH.9bVr9lsHrV7wMdTxyNLqvI4scoAKTvW",  # "admin123"
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(admin)
    users['admin'] = admin

    # Owner users
    owner_names = [
        ("Chinedu Okafor", "+2348023456789", "chinedu.okafor@email.com"),
        ("Amina Ibrahim", "+2348034567890", "amina.ibrahim@email.com"),
        ("Obi Nnamdi", "+2348045678901", "obi.nnamdi@email.com"),
        ("Fatima Mohammed", "+2348056789012", "fatima.mohammed@email.com"),
        ("Emeka Eze", "+2348067890123", "emeka.eze@email.com"),
    ]

    users['owners'] = []
    for name, phone, email in owner_names:
        owner = User(
            address=hash_user_address(phone),
            name=name,
            phone=phone,
            email=email,
            password_hash="$2b$12$/cDkrune67z5LxnuQlc6hOuiqpSq8n8XX1m0Pr6Qenj0Qd0cQDHiq",  # "password123"
            role=UserRole.OWNER,
            is_active=True
        )
        db.add(owner)
        users['owners'].append(owner)

    # Agent users
    agent_data = [
        ("Kemi Adeyemi", "+2348078901234", "kemi.adeyemi@email.com", "LAG-2024-001"),
        ("Tunde Bakare", "+2348089012345", "tunde.bakare@email.com", "ABJ-2024-002"),
        ("Ngozi Ezeani", "+2348090123456", "ngozi.ezeani@email.com", "IBD-2024-003"),
    ]

    users['agents'] = []
    for name, phone, email, license_num in agent_data:
        agent_user = User(
            address=hash_user_address(phone),
            name=name,
            phone=phone,
            email=email,
            password_hash="$2b$12$/cDkrune67z5LxnuQlc6hOuiqpSq8n8XX1m0Pr6Qenj0Qd0cQDHiq",  # "password123"
            role=UserRole.AGENT,
            is_active=True
        )
        db.add(agent_user)
        users['agents'].append((agent_user, license_num))

    # Buyer/Tenant users
    buyer_data = [
        ("John Peters", "+2348101234567", "john.peters@email.com"),
        ("Sarah Johnson", "+2348112345678", "sarah.johnson@email.com"),
        ("Michael Okon", "+2348123456789", "michael.okon@email.com"),
    ]

    users['buyers'] = []
    for name, phone, email in buyer_data:
        buyer = User(
            address=hash_user_address(phone),
            name=name,
            phone=phone,
            email=email,
            password_hash="$2b$12$/cDkrune67z5LxnuQlc6hOuiqpSq8n8XX1m0Pr6Qenj0Qd0cQDHiq",  # "password123"
            role=UserRole.BUYER,
            is_active=True
        )
        db.add(buyer)
        users['buyers'].append(buyer)

    db.commit()

    # Refresh all users to get IDs
    db.refresh(admin)
    for owner in users['owners']:
        db.refresh(owner)
    for agent_user, _ in users['agents']:
        db.refresh(agent_user)
    for buyer in users['buyers']:
        db.refresh(buyer)

    return users


def create_demo_agents(db: Session, users: dict) -> list:
    """Create agent profiles"""
    agents = []

    for agent_user, license_num in users['agents']:
        agent = Agent(
            user_id=agent_user.id,
            license_number=license_num,
            rating=random.uniform(3.5, 4.9),
            verified=True,
            total_deals=random.randint(5, 50)
        )
        db.add(agent)
        agents.append(agent)

    db.commit()

    for agent in agents:
        db.refresh(agent)

    return agents


def create_demo_properties(db: Session, users: dict) -> list:
    """Create demo properties with ownership records"""
    properties = []

    for i in range(15):
        owner = random.choice(users['owners'])
        location = random.choice(SAMPLE_LOCATIONS)
        timestamp = datetime.utcnow() - timedelta(days=random.randint(1, 365))

        # Determine property type and status
        property_type = random.choice([PropertyType.SALE, PropertyType.RENT])
        status = random.choice([
            PropertyStatus.LISTED, PropertyStatus.LISTED,
            PropertyStatus.UNDER_OFFER, PropertyStatus.SOLD
        ])

        # Generate price based on location
        base_price = random.randint(15, 150) * 1_000_000
        if property_type == PropertyType.RENT:
            base_price = random.randint(500, 5000) * 1000  # Monthly rent

        property_id = create_property_id(location, timestamp, owner.id)

        prop = Property(
            property_id=property_id,
            owner_id=owner.id,
            title=random.choice(PROPERTY_TITLES),
            location=location,
            description=random.choice(DESCRIPTIONS),
            property_type=property_type,
            status=status,
            price=float(base_price),
            bedrooms=random.randint(1, 6),
            bathrooms=random.randint(1, 4),
            area_sqm=float(random.randint(100, 500)),
            created_at=timestamp
        )
        db.add(prop)
        properties.append(prop)

    db.commit()

    for prop in properties:
        db.refresh(prop)

        # Create ownership record
        record = OwnershipRecord(
            property_id=prop.id,
            owner_id=prop.owner_id,
            previous_hash=None,
            current_hash=create_ledger_hash(
                prop.id, prop.owner_id, None, prop.created_at, "initial"
            ),
            transaction_type="initial",
            timestamp=prop.created_at
        )
        db.add(record)

        # Create timeline event
        event = TimelineEvent(
            property_id=prop.id,
            event_type="PROPERTY_CREATED",
            description=f"Property '{prop.title}' was created",
            user_id=prop.owner_id,
            created_at=prop.created_at
        )
        db.add(event)

        # Add LISTED event if status is not DRAFT
        if prop.status in [PropertyStatus.LISTED, PropertyStatus.UNDER_OFFER, PropertyStatus.SOLD]:
            listed_event = TimelineEvent(
                property_id=prop.id,
                event_type="PROPERTY_LISTED",
                description=f"Property '{prop.title}' was listed for {prop.property_type.value}",
                user_id=prop.owner_id,
                created_at=prop.created_at + timedelta(hours=1)
            )
            db.add(listed_event)

    db.commit()

    return properties


def create_demo_units(db: Session, properties: list) -> list:
    """Create units for rental properties"""
    units = []

    for prop in properties:
        if prop.property_type == PropertyType.RENT:
            # Create 1-4 units for rental properties
            num_units = random.randint(1, 4)
            for j in range(num_units):
                unit = Unit(
                    property_id=prop.id,
                    name=f"Unit {j + 1}{'A' if num_units > 1 else ''}",
                    description=f"{'Self-contained' if random.random() > 0.5 else '2-bedroom'} unit",
                    price=float(random.randint(300, 3000) * 1000),
                    status=random.choice([UnitStatus.AVAILABLE, UnitStatus.AVAILABLE, UnitStatus.RENTED]),
                    area_sqm=float(random.randint(30, 100))
                )
                db.add(unit)
                units.append(unit)

    db.commit()

    for unit in units:
        db.refresh(unit)

    return units


def create_demo_documents(db: Session, properties: list) -> list:
    """Create demo documents"""
    documents = []

    for prop in properties[:10]:  # Documents for first 10 properties
        # Create 1-3 documents per property
        num_docs = random.randint(1, 3)
        for j in range(num_docs):
            doc_type = random.choice(DOC_TYPES)
            content = f"Demo document content for {prop.title} - {doc_type}"

            doc = Document(
                property_id=prop.id,
                file_url=f"/uploads/properties/{prop.id}/{doc_type}_{j + 1}.pdf",
                file_name=f"{doc_type}_{j + 1}.pdf",
                doc_hash=hash_document(content.encode()),
                doc_type=doc_type,
                verified=random.random() > 0.3  # 70% verified
            )
            db.add(doc)
            documents.append(doc)

    db.commit()

    for doc in documents:
        db.refresh(doc)

    return documents


def create_demo_agent_assignments(db: Session, properties: list, agents: list) -> list:
    """Create agent assignments"""
    assignments = []

    for prop in properties[:8]:  # Assign agents to first 8 properties
        if random.random() > 0.5 and agents:  # 50% chance of having an agent
            agent = random.choice(agents)
            assignment = PropertyAgent(
                property_id=prop.id,
                agent_id=agent.id,
                status=random.choice([
                    AgentAssignmentStatus.ACTIVE,
                    AgentAssignmentStatus.COMPLETED
                ]),
                notes="Demo assignment for testing"
            )
            db.add(assignment)
            assignments.append(assignment)

    db.commit()

    for assignment in assignments:
        db.refresh(assignment)

    return assignments


def create_demo_interests(db: Session, properties: list, users: dict) -> list:
    """Create demo interests"""
    interests = []

    for buyer in users['buyers']:
        # Each buyer expresses interest in 1-3 properties
        sample_size = min(random.randint(1, 3), len(properties))
        for prop in random.sample(properties, sample_size):
            interest = Interest(
                property_id=prop.id,
                user_id=buyer.id,
                status=random.choice([InterestStatus.PENDING, InterestStatus.CONTACTED]),
                message="I am interested in this property. Please contact me for viewing."
            )
            db.add(interest)
            interests.append(interest)

    db.commit()

    for interest in interests:
        db.refresh(interest)

    return interests


def create_demo_subscriptions(db: Session) -> list:
    """Create demo USSD subscriptions"""
    subscriptions = []

    sub_data = [
        ("+2348134567890", "Blessing Okoro", "Lekki", "rent"),
        ("+2348145678901", "Yusuf Adamu", "Victoria Island", "buy"),
        ("+2348156789012", "Chioma Nwosu", "Ikeja", "rent"),
        ("+2348167890123", "Adekunle James", "Abuja", "buy"),
        ("+2348178901234", "Grace Emmanuel", "Ibadan", "rent"),
    ]

    for phone, name, location, intent in sub_data:
        subscription = Subscription(
            phone=phone,
            name=name,
            location=location,
            intent=intent,
            active=True
        )
        db.add(subscription)
        subscriptions.append(subscription)

    db.commit()

    for sub in subscriptions:
        db.refresh(sub)

    return subscriptions


def create_demo_disputes(db: Session, properties: list, users: dict) -> list:
    """Create demo disputes"""
    disputes = []

    # Create 2-3 disputes
    num_disputes = min(3, len(properties), len(users['buyers']))
    for i in range(num_disputes):
        dispute = Dispute(
            property_id=properties[i].id,
            user_id=users['buyers'][i % len(users['buyers'])].id,
            reason="Dispute regarding property boundaries and documentation clarity.",
            status=random.choice([DisputeStatus.OPEN, DisputeStatus.INVESTIGATING]),
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))
        )
        db.add(dispute)
        disputes.append(dispute)

    db.commit()

    for dispute in disputes:
        db.refresh(dispute)

    return disputes


def create_demo_fraud_alerts(db: Session, properties: list) -> list:
    """Create demo fraud alerts"""
    alerts = []

    alert_types = ["duplicate_doc", "suspicious_agent", "price_anomaly"]
    severities = ["LOW", "MEDIUM", "HIGH"]

    # Create 1-2 fraud alerts
    num_alerts = min(2, len(properties))
    for i in range(num_alerts):
        alert = FraudAlert(
            property_id=properties[-(i + 1)].id,  # Use last properties
            alert_type=random.choice(alert_types),
            severity=random.choice(severities),
            description="Potential fraud indicator detected during automated screening.",
            resolved=random.random() > 0.7  # 30% unresolved
        )
        db.add(alert)
        alerts.append(alert)

    db.commit()

    for alert in alerts:
        db.refresh(alert)

    return alerts


def create_demo_inspections(db: Session, properties: list, users: dict, agents: list) -> list:
    """Create demo inspections"""
    inspections = []

    for buyer in users['buyers'][:2]:  # Create inspections for first 2 buyers
        prop = random.choice(properties)
        inspection = Inspection(
            property_id=prop.id,
            user_id=buyer.id,
            scheduled_date=datetime.utcnow() + timedelta(days=random.randint(1, 14)),
            status="SCHEDULED",
            notes="Demo inspection scheduled",
            agent_id=random.choice(agents).id if agents else None
        )
        db.add(inspection)
        inspections.append(inspection)

    db.commit()

    for inspection in inspections:
        db.refresh(inspection)

    return inspections


def create_demo_ratings(db: Session, properties: list, agents: list, users: dict) -> list:
    """Create demo agent ratings"""
    ratings = []

    # Create ratings for sold properties
    sold_properties = [p for p in properties if p.status == PropertyStatus.SOLD]

    for prop in sold_properties[:3]:  # Rate first 3 sold properties
        if prop.owner_id and agents:
            rating = AgentRating(
                agent_id=random.choice(agents).id,
                property_id=prop.id,
                user_id=prop.owner_id,
                rating=random.randint(4, 5),
                comment="Excellent service and professional handling of the transaction.",
                transaction_type="SALE"
            )
            db.add(rating)
            ratings.append(rating)

    db.commit()

    for rating in ratings:
        db.refresh(rating)

    return ratings


def main():
    """Main function to seed demo data"""
    print("=" * 60)
    print("RealLink Ecosystem - Demo Data Seed Script")
    print("=" * 60)

    # Initialize database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./reallink.db")
    print(f"\nUsing database: {DATABASE_URL}")

    engine = get_engine(DATABASE_URL)
    init_db(engine)
    SessionLocal = get_session_maker(engine)
    db = SessionLocal()

    try:
        print("\nSeeding demo data...")

        # Check if data already exists
        existing_users = db.query(User).count()
        if existing_users > 0:
            print(f"\nDatabase already contains {existing_users} users.")
            response = input("Do you want to clear and re-seed? (y/N): ")
            if response.lower() != 'y':
                print("Aborting seed operation.")
                return

            # Clear existing data
            print("Clearing existing data...")
            db.query(ChatMessage).delete()
            db.query(ChatSession).delete()
            db.query(AgentRating).delete()
            db.query(Inspection).delete()
            db.query(TimelineEvent).delete()
            db.query(FraudAlert).delete()
            db.query(Dispute).delete()
            db.query(Subscription).delete()
            db.query(Interest).delete()
            db.query(PropertyAgent).delete()
            db.query(Document).delete()
            db.query(Unit).delete()
            db.query(OwnershipRecord).delete()
            db.query(PropertyImage).delete()
            db.query(Transaction).delete()
            db.query(Agent).delete()
            db.query(Property).delete()
            db.query(User).delete()
            db.commit()
            print("Data cleared.")

        # Create demo data
        print("\n1. Creating users...")
        users = create_demo_users(db)
        print(f"   Created: 1 admin, {len(users['owners'])} owners, "
              f"{len(users['agents'])} agents, {len(users['buyers'])} buyers")

        print("\n2. Creating agent profiles...")
        agents = create_demo_agents(db, users)
        print(f"   Created: {len(agents)} agent profiles")

        print("\n3. Creating properties...")
        properties = create_demo_properties(db, users)
        print(f"   Created: {len(properties)} properties")

        print("\n4. Creating units...")
        units = create_demo_units(db, properties)
        print(f"   Created: {len(units)} units")

        print("\n5. Creating documents...")
        documents = create_demo_documents(db, properties)
        print(f"   Created: {len(documents)} documents")

        print("\n6. Creating agent assignments...")
        assignments = create_demo_agent_assignments(db, properties, agents)
        print(f"   Created: {len(assignments)} assignments")

        print("\n7. Creating interests...")
        interests = create_demo_interests(db, properties, users)
        print(f"   Created: {len(interests)} interests")

        print("\n8. Creating subscriptions...")
        subscriptions = create_demo_subscriptions(db)
        print(f"   Created: {len(subscriptions)} subscriptions")

        print("\n9. Creating disputes...")
        disputes = create_demo_disputes(db, properties, users)
        print(f"   Created: {len(disputes)} disputes")

        print("\n10. Creating fraud alerts...")
        alerts = create_demo_fraud_alerts(db, properties)
        print(f"   Created: {len(alerts)} alerts")

        print("\n11. Creating inspections...")
        inspections = create_demo_inspections(db, properties, users, agents)
        print(f"   Created: {len(inspections)} inspections")

        print("\n12. Creating agent ratings...")
        ratings = create_demo_ratings(db, properties, agents, users)
        print(f"   Created: {len(ratings)} ratings")

        print("\n" + "=" * 60)
        print("Demo data seeding completed successfully!")
        print("=" * 60)

        # Print login credentials
        print("\nDemo Login Credentials:")
        print("-" * 40)
        print("Admin:")
        print("  Email: admin@reallink.africa")
        print("  Password: admin123")
        print()
        print("Owner:")
        print("  Email: chinedu.okafor@email.com")
        print("  Password: password123")
        print()
        print("Agent:")
        print("  Email: kemi.adeyemi@email.com")
        print("  Password: password123")
        print()
        print("Buyer:")
        print("  Email: john.peters@email.com")
        print("  Password: password123")
        print("-" * 40)

    except Exception as e:
        print(f"\nError seeding data: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
