# RealLink Ecosystem

Fraud-resistant real estate platform for Africa with property verification, lifecycle tracking, agent accountability, and AI-powered intelligence.

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM with SQLite database
- **Pydantic** - Data validation
- **OpenRouter** - AI integration for fraud detection
- **Africa's Talking** - USSD/SMS communication

### Frontend
- **Flask** - Python web framework
- **Jinja2** - Template engine
- **HTMX** - Dynamic HTML interactions
- **Alpine.js** - Lightweight JavaScript framework
- **TailwindCSS** - Utility-first CSS

## Project Structure

```
reallink-ecosystem/
├── run.py                        # Main runner (starts both servers)
├── run.sh                        # Shell script runner
├── README.md
│
├── backend/
│   ├── run.py                    # Backend runner
│   ├── requirements.txt
│   └── app/
│       ├── main.py               # FastAPI application
│       ├── models/
│       │   └── __init__.py       # SQLAlchemy database models
│       ├── services/             # Business logic
│       │   ├── property_service.py
│       │   ├── ledger_service.py
│       │   ├── agent_service.py
│       │   ├── state_machine.py
│       │   ├── ai_service.py
│       │   └── ussd_sms_service.py
│       ├── routes/               # API endpoints
│       │   ├── auth.py
│       │   ├── properties.py
│       │   ├── agents.py
│       │   ├── verification.py
│       │   ├── interactions.py
│       │   ├── ussd.py
│       │   └── admin.py
│       └── utils/
│           ├── __init__.py       # Hashing, trust score
│           └── fraud_detection.py
│
└── frontend/
    ├── run.py                    # Frontend runner
    ├── requirements.txt
    ├── app.py                    # Flask application
    └── templates/
        ├── base.html
        ├── index.html
        ├── login.html
        ├── register.html
        ├── dashboard.html
        ├── properties/
        │   ├── list.html
        │   ├── create.html
        │   ├── detail.html
        │   └── edit.html
        ├── realscan/
        │   ├── explorer.html
        │   ├── detail.html
        │   └── fraud_analysis.html
        ├── agents/
        │   ├── list.html
        │   ├── detail.html
        │   ├── profile.html
        │   └── create_profile.html
        └── components/
            ├── property_cards.html
            └── trust_score.html
```

## Features

### Core Models
- **Property** - Building-level entity with state machine
- **Unit** - Sub-entity (room/flat/shop) for rentals
- **User** - Represented as hashed address for privacy
- **Agent** - Permission-based participant with lifecycle
- **Ledger** - Hash-linked ownership records

### State Machines
- **Property States**: DRAFT → LISTED → UNDER_OFFER → PARTIALLY_RENTED/FULLY_RENTED → SOLD
- **Unit States**: AVAILABLE → RESERVED → RENTED
- **Agent States**: REQUESTED → APPROVED → ACTIVE → COMPLETED → ARCHIVED

### AI Features
- Fraud risk analysis
- Document validation
- Price suggestions
- Trust score explanations

### USSD/SMS
- Subscription via USSD (*00123#)
- Property alerts via SMS
- Fraud notifications
- Inspection reminders

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Option 1: Run Both Servers Together

```bash
cd /home/z/my-project/reallink-ecosystem

# Install dependencies
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt

# Run both servers
python run.py
```

### Option 2: Run Servers Separately

```bash
# Terminal 1 - Backend
cd /home/z/my-project/reallink-ecosystem/backend
pip install -r requirements.txt
python run.py

# Terminal 2 - Frontend
cd /home/z/my-project/reallink-ecosystem/frontend
pip install -r requirements.txt
python run.py
```

### Access the Application
| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:5000 |
| **Backend API** | http://localhost:8000 |
| **API Documentation** | http://localhost:8000/docs |
| **Health Check** | http://localhost:8000/health |

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login user |
| GET | `/api/auth/me` | Get current user |
| PUT | `/api/auth/me` | Update profile |

### Properties
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/properties` | List properties |
| POST | `/api/properties` | Create property |
| GET | `/api/properties/{id}` | Get property details |
| PUT | `/api/properties/{id}` | Update property |
| DELETE | `/api/properties/{id}` | Delete property |
| POST | `/api/properties/{id}/list` | List property (DRAFT → LISTED) |
| POST | `/api/properties/{id}/units` | Create unit |
| POST | `/api/properties/{id}/units/{unit_id}/rent` | Rent unit |
| POST | `/api/properties/{id}/documents` | Upload document |
| POST | `/api/properties/{id}/transfer-ownership` | Transfer ownership |

### Verification (RealScan)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/verification/explorer` | Browse verified properties |
| GET | `/api/verification/property/{id}` | Get verification data |
| GET | `/api/verification/property/{id}/fraud-analysis` | Fraud analysis |
| POST | `/api/verification/property/{id}/ai-analysis` | AI fraud analysis |
| GET | `/api/verification/property/{id}/price-suggestion` | AI price suggestion |

### Agents
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/agents` | List agents |
| POST | `/api/agents/profile` | Create agent profile |
| GET | `/api/agents/profile` | Get my agent profile |
| GET | `/api/agents/{id}` | Get agent details |
| POST | `/api/agents/assignments/request` | Request assignment |
| POST | `/api/agents/assignments/{id}/approve` | Approve assignment |
| POST | `/api/agents/assignments/{id}/activate` | Activate assignment |
| POST | `/api/agents/assignments/{id}/complete` | Complete assignment |

### Interactions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/interactions/interests` | Express interest |
| GET | `/api/interactions/interests` | Get my interests |
| POST | `/api/interactions/disputes` | Create dispute |
| GET | `/api/interactions/transactions` | Get my transactions |

### USSD/SMS
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ussd/callback` | USSD callback (Africa's Talking) |
| GET | `/api/ussd/subscriptions` | List subscriptions |
| POST | `/api/ussd/subscriptions` | Create subscription |
| POST | `/api/ussd/sms/send` | Send SMS |
| POST | `/api/ussd/sms/property-alert/{id}` | Send property alerts |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/dashboard` | Admin statistics |
| GET | `/api/admin/users` | List users |
| PUT | `/api/admin/users/{id}/role` | Update user role |
| GET | `/api/admin/documents/pending` | List pending documents |
| POST | `/api/admin/documents/{id}/verify` | Verify document |
| POST | `/api/admin/agents/{id}/verify` | Verify agent |
| GET | `/api/admin/fraud-alerts` | List fraud alerts |
| GET | `/api/admin/disputes` | List disputes |

## Environment Variables

Create a `.env` file in the backend directory:

```env
# Database
DATABASE_URL=sqlite:///./reallink.db

# Security
SECRET_KEY=your-secret-key-change-in-production

# Backend Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
DEBUG=true

# Frontend Server
FRONTEND_HOST=0.0.0.0
FRONTEND_PORT=5000
API_URL=http://localhost:8000/api

# OpenRouter (AI)
OPENROUTER_API_KEY=your-api-key

# Africa's Talking
AFRICAS_TALKING_USERNAME=sandbox
AFRICAS_TALKING_API_KEY=your-api-key
```

## Demo Flow

1. User subscribes via USSD (*00123#)
2. Owner lists property
3. System hashes documents + verifies
4. User receives SMS alert
5. User checks RealScan
6. AI shows risk analysis
7. User expresses interest
8. Agent handles interaction
9. Property is sold or rented
10. Ledger updates
11. Fraud attempt is demonstrated and blocked

## Trust Score Calculation

The trust score (0-100) is calculated from:

| Component | Max Points | Description |
|-----------|------------|-------------|
| Documents | 30 | Verified docs / total docs × 30 |
| Ownership | 25 | Ownership chain clarity |
| Agent Rating | 20 | Agent rating / 5 × 20 |
| Fraud Flags | -15 each | Deduction for unresolved flags |
| Bonus | +10 | For 3+ verified documents |

## License

MIT License
