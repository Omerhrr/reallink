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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
