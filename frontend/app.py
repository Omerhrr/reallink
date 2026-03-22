"""
RealLink Ecosystem - Flask Frontend
Main application with Jinja templates + HTMX + Alpine.js + TailwindCSS
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import requests
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'reallink_secret_key_change_in_production')

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Backend API URL
API_URL = os.getenv('API_URL', 'http://localhost:8000/api')


class User(UserMixin):
    """User class for Flask-Login"""
    def __init__(self, id, name, email, phone, role, token):
        self.id = id
        self.name = name
        self.email = email
        self.phone = phone
        self.role = role
        self.token = token


@login_manager.user_loader
def load_user(user_id):
    """Load user from session"""
    if 'user_token' in session:
        return User(
            id=session.get('user_id'),
            name=session.get('user_name'),
            email=session.get('user_email'),
            phone=session.get('user_phone'),
            role=session.get('user_role'),
            token=session.get('user_token')
        )
    return None


def get_auth_headers():
    """Get authorization headers for API calls"""
    token = session.get('user_token')
    if token:
        return {'Authorization': f'Bearer {token}'}
    return {}


def api_call(method, endpoint, data=None, params=None):
    """Make API call to backend"""
    url = f"{API_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}
    headers.update(get_auth_headers())

    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            return None

        return response
    except requests.RequestException as e:
        print(f"API Error: {e}")
        return None


def api_upload_file(endpoint, files, data=None):
    """Upload file to backend API"""
    url = f"{API_URL}{endpoint}"
    headers = get_auth_headers()
    # Don't set Content-Type for multipart, requests will set it automatically

    try:
        response = requests.post(url, files=files, data=data, headers=headers)
        return response
    except requests.RequestException as e:
        print(f"Upload Error: {e}")
        return None


# Context processor for templates
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Home page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')

        data = {'password': password}
        if phone:
            data['phone'] = phone
        if email:
            data['email'] = email

        response = api_call('POST', '/auth/login', data=data)

        if response and response.status_code == 200:
            result = response.json()
            user_data = result.get('user', {})

            # Store in session
            session['user_token'] = result.get('access_token')
            session['user_id'] = user_data.get('id')
            session['user_name'] = user_data.get('name')
            session['user_email'] = user_data.get('email')
            session['user_phone'] = user_data.get('phone')
            session['user_role'] = user_data.get('role')

            user = User(
                id=user_data.get('id'),
                name=user_data.get('name'),
                email=user_data.get('email'),
                phone=user_data.get('phone'),
                role=user_data.get('role'),
                token=result.get('access_token')
            )
            login_user(user)

            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register page"""
    if request.method == 'POST':
        data = {
            'name': request.form.get('name'),
            'phone': request.form.get('phone'),
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'role': request.form.get('role', 'OWNER')
        }

        response = api_call('POST', '/auth/register', data=data)

        if response and response.status_code == 200:
            result = response.json()
            user_data = result.get('user', {})

            # Store in session
            session['user_token'] = result.get('access_token')
            session['user_id'] = user_data.get('id')
            session['user_name'] = user_data.get('name')
            session['user_email'] = user_data.get('email')
            session['user_phone'] = user_data.get('phone')
            session['user_role'] = user_data.get('role')

            user = User(
                id=user_data.get('id'),
                name=user_data.get('name'),
                email=user_data.get('email'),
                phone=user_data.get('phone'),
                role=user_data.get('role'),
                token=result.get('access_token')
            )
            login_user(user)

            flash('Registration successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            error = response.json().get('detail', 'Registration failed') if response else 'Registration failed'
            flash(error, 'error')

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    """Logout"""
    session.clear()
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page"""
    # Get user's properties
    response = api_call('GET', '/properties/')
    properties = response.json() if response and response.status_code == 200 else []

    # Get user's interests
    interests_response = api_call('GET', '/interactions/interests')
    interests = interests_response.json() if interests_response and interests_response.status_code == 200 else []

    return render_template('dashboard.html', properties=properties, interests=interests)


# ==================== PROPERTY ROUTES ====================

@app.route('/properties')
def properties_list():
    """List all properties (RealScan Explorer)"""
    # Get filters from query params
    params = {
        'location': request.args.get('location'),
        'property_type': request.args.get('type'),
        'min_price': request.args.get('min_price'),
        'max_price': request.args.get('max_price'),
        'status': 'LISTED'
    }

    # Remove None values
    params = {k: v for k, v in params.items() if v}

    response = api_call('GET', '/properties/', params=params)
    properties = response.json() if response and response.status_code == 200 else []

    return render_template('properties/list.html', properties=properties)


@app.route('/properties/create', methods=['GET', 'POST'])
@login_required
def create_property():
    """Create property page"""
    if request.method == 'POST':
        data = {
            'title': request.form.get('title'),
            'location': request.form.get('location'),
            'property_type': request.form.get('property_type', 'SALE'),
            'price': float(request.form.get('price', 0)) if request.form.get('price') else None,
            'description': request.form.get('description'),
            'bedrooms': int(request.form.get('bedrooms', 0)),
            'bathrooms': int(request.form.get('bathrooms', 0)),
            'area_sqm': float(request.form.get('area_sqm', 0)) if request.form.get('area_sqm') else None
        }

        response = api_call('POST', '/properties/', data=data)

        if response and response.status_code == 200:
            result = response.json()
            flash('Property created successfully!', 'success')
            return redirect(url_for('property_detail', property_id=result.get('id')))
        else:
            flash('Failed to create property', 'error')

    return render_template('properties/create.html')


@app.route('/properties/<int:property_id>')
def property_detail(property_id):
    """Property detail page"""
    response = api_call('GET', f'/properties/{property_id}')

    if response and response.status_code == 200:
        data = response.json()
        return render_template('properties/detail.html', property=data)

    flash('Property not found', 'error')
    return redirect(url_for('properties_list'))


@app.route('/properties/<int:property_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_property(property_id):
    """Edit property page"""
    if request.method == 'POST':
        data = {}
        for field in ['title', 'location', 'price', 'description', 'bedrooms', 'bathrooms', 'area_sqm']:
            value = request.form.get(field)
            if value:
                if field in ['price', 'area_sqm']:
                    data[field] = float(value)
                elif field in ['bedrooms', 'bathrooms']:
                    data[field] = int(value)
                else:
                    data[field] = value

        response = api_call('PUT', f'/properties/{property_id}', data=data)

        if response and response.status_code == 200:
            flash('Property updated successfully!', 'success')
            return redirect(url_for('property_detail', property_id=property_id))
        else:
            flash('Failed to update property', 'error')

    # GET - fetch property data
    response = api_call('GET', f'/properties/{property_id}')
    if response and response.status_code == 200:
        data = response.json()
        return render_template('properties/edit.html', property=data.get('property', data))

    flash('Property not found', 'error')
    return redirect(url_for('properties_list'))


@app.route('/properties/<int:property_id>/list', methods=['POST'])
@login_required
def list_property(property_id):
    """List a property (move from DRAFT to LISTED)"""
    response = api_call('POST', f'/properties/{property_id}/list')

    if response and response.status_code == 200:
        flash('Property listed successfully!', 'success')
    else:
        error = response.json().get('detail', 'Failed to list property') if response else 'Failed to list property'
        flash(error, 'error')

    return redirect(url_for('property_detail', property_id=property_id))


@app.route('/properties/<int:property_id>/delete', methods=['POST'])
@login_required
def delete_property(property_id):
    """Delete a property"""
    response = api_call('DELETE', f'/properties/{property_id}')

    if response and response.status_code == 200:
        flash('Property deleted successfully!', 'success')
        return redirect(url_for('dashboard'))

    flash('Failed to delete property', 'error')
    return redirect(url_for('property_detail', property_id=property_id))


# ==================== UNIT ROUTES ====================

@app.route('/properties/<int:property_id>/units/create', methods=['POST'])
@login_required
def create_unit(property_id):
    """Create a unit for a property"""
    data = {
        'name': request.form.get('name'),
        'price': float(request.form.get('price', 0)),
        'description': request.form.get('description'),
        'area_sqm': float(request.form.get('area_sqm', 0)) if request.form.get('area_sqm') else None
    }

    response = api_call('POST', f'/properties/{property_id}/units', data=data)

    if response and response.status_code == 200:
        flash('Unit created successfully!', 'success')
    else:
        flash('Failed to create unit', 'error')

    return redirect(url_for('property_detail', property_id=property_id))


# ==================== IMAGE UPLOAD ROUTES ====================

@app.route('/properties/<int:property_id>/images/upload', methods=['POST'])
@login_required
def upload_property_image(property_id):
    """Upload image for a property"""
    if 'image' not in request.files:
        flash('No image file selected', 'error')
        return redirect(url_for('property_detail', property_id=property_id))

    file = request.files['image']
    if file.filename == '':
        flash('No image file selected', 'error')
        return redirect(url_for('property_detail', property_id=property_id))

    files = {'file': (file.filename, file.stream, file.content_type)}
    data = {
        'caption': request.form.get('caption', ''),
        'is_primary': request.form.get('is_primary', 'false').lower() == 'true'
    }

    response = api_upload_file(f'/properties/{property_id}/images', files, data)

    if response and response.status_code == 200:
        flash('Image uploaded successfully!', 'success')
    else:
        error = response.json().get('detail', 'Failed to upload image') if response else 'Failed to upload image'
        flash(error, 'error')

    return redirect(url_for('property_detail', property_id=property_id))


@app.route('/properties/<int:property_id>/images/<int:image_id>/delete', methods=['POST'])
@login_required
def delete_property_image(property_id, image_id):
    """Delete a property image"""
    response = api_call('DELETE', f'/properties/{property_id}/images/{image_id}')

    if response and response.status_code == 200:
        flash('Image deleted successfully!', 'success')
    else:
        flash('Failed to delete image', 'error')

    return redirect(url_for('property_detail', property_id=property_id))


@app.route('/properties/<int:property_id>/images/<int:image_id>/set-primary', methods=['POST'])
@login_required
def set_primary_image(property_id, image_id):
    """Set an image as primary"""
    response = api_call('POST', f'/properties/{property_id}/images/{image_id}/set-primary')

    if response and response.status_code == 200:
        flash('Primary image updated!', 'success')
    else:
        flash('Failed to set primary image', 'error')

    return redirect(url_for('property_detail', property_id=property_id))


# ==================== DOCUMENT UPLOAD ROUTES ====================

@app.route('/properties/<int:property_id>/documents/upload', methods=['POST'])
@login_required
def upload_property_document(property_id):
    """Upload document for a property with hash generation"""
    if 'document' not in request.files:
        flash('No document file selected', 'error')
        return redirect(url_for('property_detail', property_id=property_id))

    file = request.files['document']
    if file.filename == '':
        flash('No document file selected', 'error')
        return redirect(url_for('property_detail', property_id=property_id))

    doc_type = request.form.get('doc_type', 'other')

    files = {'file': (file.filename, file.stream, file.content_type)}
    data = {'doc_type': doc_type}

    response = api_upload_file(f'/properties/{property_id}/documents', files, data)

    if response and response.status_code == 200:
        result = response.json()
        flash(f'Document uploaded successfully! Hash: {result.get("doc_hash", "")[:16]}...', 'success')
    else:
        error = response.json().get('detail', 'Failed to upload document') if response else 'Failed to upload document'
        flash(error, 'error')

    return redirect(url_for('property_detail', property_id=property_id))


# ==================== VERIFICATION ROUTES ====================

@app.route('/realscan')
def realscan_explorer():
    """RealScan Explorer page - Etherscan-like interface for real estate"""
    params = {
        'location': request.args.get('location'),
        'min_price': request.args.get('min_price'),
        'max_price': request.args.get('max_price'),
        'property_type': request.args.get('type')
    }
    params = {k: v for k, v in params.items() if v}

    # Get properties
    response = api_call('GET', '/verification/explorer', params=params)
    data = response.json() if response and response.status_code == 200 else {'properties': []}
    
    # Get statistics
    stats_response = api_call('GET', '/verification/statistics')
    stats = stats_response.json() if stats_response and stats_response.status_code == 200 else None
    
    # Get recent transfers
    transfers_response = api_call('GET', '/verification/recent-transfers', params={'limit': 5})
    recent_transfers = transfers_response.json().get('transfers', []) if transfers_response and transfers_response.status_code == 200 else []

    return render_template('realscan/explorer.html', data=data, stats=stats, recent_transfers=recent_transfers)


@app.route('/realscan/search')
def realscan_search():
    """Search RealScan - Like Etherscan's global search"""
    query = request.args.get('q', '')
    
    if not query:
        return redirect(url_for('realscan_explorer'))
    
    response = api_call('GET', '/verification/search', params={'q': query})
    
    if response and response.status_code == 200:
        data = response.json()
        return render_template('realscan/search_results.html', 
                             query=query,
                             results=data.get('results', {}),
                             total_found=data.get('total_found', 0))
    
    return render_template('realscan/search_results.html', 
                         query=query, 
                         results={'properties': [], 'ownership_records': [], 'documents': []},
                         total_found=0)


@app.route('/realscan/transfer/<int:record_id>')
def transfer_detail(record_id):
    """Transfer detail page - Like Etherscan's transaction detail"""
    response = api_call('GET', f'/verification/transfer/{record_id}')
    
    if response and response.status_code == 200:
        data = response.json()
        return render_template('realscan/transfer_detail.html', data=data)
    
    flash('Transfer record not found', 'error')
    return redirect(url_for('realscan_explorer'))


@app.route('/realscan/transfers')
def all_transfers():
    """All transfers page - Like Etherscan's transactions list"""
    response = api_call('GET', '/verification/recent-transfers', params={'limit': 50})
    
    transfers = response.json().get('transfers', []) if response and response.status_code == 200 else []
    
    return render_template('realscan/all_transfers.html', transfers=transfers)


@app.route('/realscan/<int:property_id>')
def realscan_detail(property_id):
    """RealScan detail page with verification data"""
    response = api_call('GET', f'/verification/property/{property_id}')

    if response and response.status_code == 200:
        data = response.json()
        return render_template('realscan/detail.html', data=data)

    flash('Property not found', 'error')
    return redirect(url_for('realscan_explorer'))


@app.route('/realscan/<int:property_id>/fraud-analysis')
def fraud_analysis(property_id):
    """Fraud analysis page"""
    response = api_call('GET', f'/verification/property/{property_id}/fraud-analysis')

    if response and response.status_code == 200:
        data = response.json()
        return render_template('realscan/fraud_analysis.html', analysis=data, property_id=property_id)

    flash('Analysis failed', 'error')
    return redirect(url_for('realscan_detail', property_id=property_id))


# ==================== AGENT ROUTES ====================

@app.route('/agents')
def agents_list():
    """List all agents"""
    response = api_call('GET', '/agents/')
    agents = response.json() if response and response.status_code == 200 else []

    return render_template('agents/list.html', agents=agents)


@app.route('/agents/profile')
@login_required
def agent_profile():
    """Agent profile page"""
    response = api_call('GET', '/agents/profile')

    if response and response.status_code == 200:
        data = response.json()
        return render_template('agents/profile.html', agent=data)

    # No agent profile yet
    return render_template('agents/create_profile.html')


@app.route('/agents/create-profile', methods=['POST'])
@login_required
def create_agent_profile():
    """Create agent profile"""
    data = {
        'license_number': request.form.get('license_number')
    }

    response = api_call('POST', '/agents/profile', data=data)

    if response and response.status_code == 200:
        flash('Agent profile created! Awaiting verification.', 'success')
        return redirect(url_for('agent_profile'))

    flash('Failed to create agent profile', 'error')
    return redirect(url_for('agent_profile'))


@app.route('/agents/<int:agent_id>')
def agent_detail(agent_id):
    """Agent detail page"""
    response = api_call('GET', f'/agents/{agent_id}')

    if response and response.status_code == 200:
        data = response.json()
        return render_template('agents/detail.html', agent=data)

    flash('Agent not found', 'error')
    return redirect(url_for('agents_list'))


@app.route('/agents/<int:agent_id>/request-assignment', methods=['POST'])
@login_required
def request_agent_assignment(agent_id):
    """Request an agent for a property assignment (owner)"""
    property_id = request.form.get('property_id')
    notes = request.form.get('notes', '')

    if not property_id:
        flash('Please select a property', 'error')
        return redirect(url_for('agent_detail', agent_id=agent_id))

    data = {
        'property_id': int(property_id),
        'notes': notes
    }

    response = api_call('POST', f'/agents/assignments/request', data=data)

    if response and response.status_code == 200:
        flash('Assignment request sent successfully!', 'success')
    else:
        error = response.json().get('detail', 'Failed to request assignment') if response else 'Failed to request assignment'
        flash(error, 'error')

    return redirect(url_for('agent_detail', agent_id=agent_id))


@app.route('/agents/assignments/<int:assignment_id>/approve', methods=['POST'])
@login_required
def approve_agent_assignment(assignment_id):
    """Approve an agent assignment (owner)"""
    response = api_call('POST', f'/agents/assignments/{assignment_id}/approve')

    if response and response.status_code == 200:
        flash('Assignment approved!', 'success')
    else:
        flash('Failed to approve assignment', 'error')

    return redirect(url_for('dashboard'))


# ==================== INTERACTION ROUTES ====================

@app.route('/interests/<int:property_id>', methods=['POST'])
@login_required
def express_interest(property_id):
    """Express interest in a property"""
    data = {
        'property_id': property_id,
        'unit_id': request.form.get('unit_id'),
        'message': request.form.get('message')
    }

    response = api_call('POST', '/interactions/interests', data=data)

    if response and response.status_code == 200:
        flash('Interest expressed successfully!', 'success')
    else:
        flash('Failed to express interest', 'error')

    return redirect(url_for('property_detail', property_id=property_id))


@app.route('/transfer-ownership/<int:property_id>', methods=['POST'])
@login_required
def transfer_ownership(property_id):
    """Transfer property ownership"""
    data = {
        'new_owner_id': int(request.form.get('new_owner_id')),
        'amount': float(request.form.get('amount', 0)) if request.form.get('amount') else None,
        'agent_id': int(request.form.get('agent_id')) if request.form.get('agent_id') else None
    }

    response = api_call('POST', f'/properties/{property_id}/transfer-ownership', data=data)

    if response and response.status_code == 200:
        flash('Ownership transferred successfully!', 'success')
        return redirect(url_for('dashboard'))

    flash('Failed to transfer ownership', 'error')
    return redirect(url_for('property_detail', property_id=property_id))


# ==================== HTMX ENDPOINTS ====================

@app.route('/htmx/properties/search')
def htmx_property_search():
    """HTMX endpoint for property search"""
    params = {
        'location': request.args.get('q'),
        'status': 'LISTED'
    }

    response = api_call('GET', '/properties/', params=params)
    properties = response.json() if response and response.status_code == 200 else []

    return render_template('components/property_cards.html', properties=properties)


@app.route('/htmx/trust-score/<int:property_id>')
def htmx_trust_score(property_id):
    """HTMX endpoint for trust score"""
    response = api_call('GET', f'/properties/{property_id}')

    if response and response.status_code == 200:
        data = response.json()
        trust_score = data.get('trust_score', {})
        return render_template('components/trust_score.html', trust_score=trust_score)

    return '<span class="text-gray-500">N/A</span>'


# ==================== TIMELINE ROUTES ====================

@app.route('/properties/<int:property_id>/timeline')
def property_timeline(property_id):
    """Property timeline page"""
    response = api_call('GET', f'/properties/{property_id}/timeline')

    if response and response.status_code == 200:
        events = response.json()
        return render_template('properties/timeline.html', events=events, property_id=property_id)

    flash('Failed to load timeline', 'error')
    return redirect(url_for('property_detail', property_id=property_id))


@app.route('/properties/<int:property_id>/inspections', methods=['POST'])
@login_required
def schedule_inspection(property_id):
    """Schedule an inspection"""
    data = {
        'scheduled_date': request.form.get('scheduled_date'),
        'notes': request.form.get('notes'),
        'agent_id': request.form.get('agent_id')
    }

    response = api_call('POST', f'/properties/{property_id}/inspections', data=data)

    if response and response.status_code == 200:
        flash('Inspection scheduled successfully!', 'success')
    else:
        error = response.json().get('detail', 'Failed to schedule inspection') if response else 'Failed to schedule inspection'
        flash(error, 'error')

    return redirect(url_for('property_timeline', property_id=property_id))


# ==================== CHAT ROUTES ====================

@app.route('/chat')
def chat_assistant():
    """AI Chat Assistant page"""
    return render_template('chat/assistant.html')


# ==================== AGENT RATING ROUTES ====================

@app.route('/properties/<int:property_id>/rate-agent', methods=['GET', 'POST'])
@login_required
def rate_agent(property_id):
    """Rate agent for a property"""
    if request.method == 'POST':
        data = {
            'agent_id': int(request.form.get('agent_id')),
            'rating': int(request.form.get('rating')),
            'comment': request.form.get('comment'),
            'transaction_type': request.form.get('transaction_type')
        }

        response = api_call('POST', f'/properties/{property_id}/rate-agent', data=data)

        if response and response.status_code == 200:
            flash('Agent rated successfully!', 'success')
            return redirect(url_for('property_detail', property_id=property_id))
        else:
            error = response.json().get('detail', 'Failed to rate agent') if response else 'Failed to rate agent'
            flash(error, 'error')

    # GET - show rating form
    agent_id = request.args.get('agent_id')
    if not agent_id:
        flash('Please select an agent to rate', 'error')
        return redirect(url_for('property_detail', property_id=property_id))

    # Get property details
    property_response = api_call('GET', f'/properties/{property_id}')
    if not property_response or property_response.status_code != 200:
        flash('Property not found', 'error')
        return redirect(url_for('dashboard'))
    property_data = property_response.json()

    # Get agent details
    agent_response = api_call('GET', f'/agents/{agent_id}')
    if not agent_response or agent_response.status_code != 200:
        flash('Agent not found', 'error')
        return redirect(url_for('property_detail', property_id=property_id))
    agent_data = agent_response.json()

    # Get previous ratings for this agent
    ratings_response = api_call('GET', f'/properties/{property_id}/agent-ratings')
    previous_ratings = ratings_response.json() if ratings_response and ratings_response.status_code == 200 else []

    return render_template('agents/rate_agent.html', 
                          property=property_data.get('property', property_data),
                          agent=agent_data,
                          previous_ratings=previous_ratings[:5])


# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard page"""
    # Check if user is admin
    if session.get('user_role') != 'ADMIN':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))

    # Get dashboard statistics
    stats_response = api_call('GET', '/admin/dashboard')
    stats = stats_response.json().get('statistics', {}) if stats_response and stats_response.status_code == 200 else {}

    # Get users
    users_response = api_call('GET', '/admin/users')
    users = users_response.json().get('users', []) if users_response and users_response.status_code == 200 else []

    # Get pending documents
    docs_response = api_call('GET', '/admin/documents/pending')
    documents = docs_response.json().get('documents', []) if docs_response and docs_response.status_code == 200 else []

    # Get disputes
    disputes_response = api_call('GET', '/admin/disputes')
    disputes = disputes_response.json().get('disputes', []) if disputes_response and disputes_response.status_code == 200 else []

    # Get fraud alerts
    alerts_response = api_call('GET', '/admin/fraud-alerts')
    alerts = alerts_response.json().get('alerts', []) if alerts_response and alerts_response.status_code == 200 else []

    # Get subscriptions count
    subs_response = api_call('GET', '/ussd/subscriptions')
    stats['total_subscriptions'] = len(subs_response.json().get('subscriptions', [])) if subs_response and subs_response.status_code == 200 else 0

    return render_template('admin/dashboard.html',
                          stats=stats,
                          users=users[:10],
                          documents=documents[:10],
                          disputes=disputes[:10],
                          alerts=alerts[:10])


@app.route('/admin/documents/<int:doc_id>/verify', methods=['POST'])
@login_required
def admin_verify_document(doc_id):
    """Verify a document (admin only)"""
    if session.get('user_role') != 'ADMIN':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))

    response = api_call('POST', f'/admin/documents/{doc_id}/verify')

    if response and response.status_code == 200:
        flash('Document verified successfully!', 'success')
    else:
        flash('Failed to verify document', 'error')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/documents/<int:doc_id>/reject', methods=['POST'])
@login_required
def admin_reject_document(doc_id):
    """Reject a document (admin only)"""
    if session.get('user_role') != 'ADMIN':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))

    reason = request.form.get('reason', 'Document rejected')
    response = api_call('POST', f'/admin/documents/{doc_id}/reject', data={'reason': reason})

    if response and response.status_code == 200:
        flash('Document rejected', 'success')
    else:
        flash('Failed to reject document', 'error')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/disputes/<int:dispute_id>/resolve', methods=['POST'])
@login_required
def admin_resolve_dispute(dispute_id):
    """Resolve a dispute (admin only)"""
    if session.get('user_role') != 'ADMIN':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))

    resolution = request.form.get('resolution', '')
    response = api_call('POST', f'/admin/disputes/{dispute_id}/resolve', data={'resolution': resolution})

    if response and response.status_code == 200:
        flash('Dispute resolved successfully!', 'success')
    else:
        flash('Failed to resolve dispute', 'error')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/fraud-alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
def admin_resolve_fraud_alert(alert_id):
    """Resolve a fraud alert (admin only)"""
    if session.get('user_role') != 'ADMIN':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))

    response = api_call('POST', f'/admin/fraud-alerts/{alert_id}/resolve')

    if response and response.status_code == 200:
        flash('Fraud alert resolved!', 'success')
    else:
        flash('Failed to resolve fraud alert', 'error')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/users/<int:user_id>/role', methods=['POST'])
@login_required
def admin_update_user_role(user_id):
    """Update user role (admin only)"""
    if session.get('user_role') != 'ADMIN':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))

    new_role = request.form.get('role')
    response = api_call('PUT', f'/admin/users/{user_id}/role', data={'role': new_role})

    if response and response.status_code == 200:
        flash('User role updated!', 'success')
    else:
        flash('Failed to update user role', 'error')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/agents/<int:agent_id>/verify', methods=['POST'])
@login_required
def admin_verify_agent(agent_id):
    """Verify an agent (admin only)"""
    if session.get('user_role') != 'ADMIN':
        flash('Admin access required', 'error')
        return redirect(url_for('dashboard'))

    response = api_call('POST', f'/admin/agents/{agent_id}/verify')

    if response and response.status_code == 200:
        flash('Agent verified successfully!', 'success')
    else:
        flash('Failed to verify agent', 'error')

    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
