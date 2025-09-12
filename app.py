from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import time
import json
import os
import requests
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

# File upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
IMAGE_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'images')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['IMAGE_UPLOAD_FOLDER'] = IMAGE_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Ensure upload directories exist
os.makedirs(IMAGE_UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Performance optimizations
from flask_caching import Cache
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Add cache headers for static assets
@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 year
    elif request.path in ['/api/inventory/low-stock', '/api/reservations']:
        response.headers['Cache-Control'] = 'private, max-age=300'  # 5 minutes
    return response

# Loyalty configuration
LOYALTY_POINTS_PER_CURRENCY = 1.0  # points per 1.00 currency spent
LOYALTY_REDEMPTION_VALUE_PER_POINT = 0.01  # each point worth 0.01 currency
LOYALTY_TIER_THRESHOLDS = {
    'bronze': 0,
    'silver': 500,
    'gold': 1500,
    'platinum': 5000
}
LOYALTY_TIER_BONUSES = {
    'bronze': 1.0,  # 1x points
    'silver': 1.25, # 25% bonus
    'gold': 1.5,    # 50% bonus
    'platinum': 2.0 # 100% bonus
}

def get_customer_loyalty_tier(points):
    """Determine customer loyalty tier based on points"""
    points = points or 0
    if points >= LOYALTY_TIER_THRESHOLDS['platinum']:
        return 'platinum'
    elif points >= LOYALTY_TIER_THRESHOLDS['gold']:
        return 'gold'
    elif points >= LOYALTY_TIER_THRESHOLDS['silver']:
        return 'silver'
    else:
        return 'bronze'

def get_next_tier_threshold(points):
    """Get the points needed for the next tier"""
    points = points or 0
    if points < LOYALTY_TIER_THRESHOLDS['silver']:
        return LOYALTY_TIER_THRESHOLDS['silver']
    elif points < LOYALTY_TIER_THRESHOLDS['gold']:
        return LOYALTY_TIER_THRESHOLDS['gold']
    elif points < LOYALTY_TIER_THRESHOLDS['platinum']:
        return LOYALTY_TIER_THRESHOLDS['platinum']
    else:
        return None  # Already at max tier

def get_points_to_next_tier(points):
    """Get points needed to reach next tier"""
    points = points or 0
    next_threshold = get_next_tier_threshold(points)
    if next_threshold:
        return next_threshold - points
    return 0  # Already at max tier

# Notification configuration
LOW_STOCK_THRESHOLD = 20  # percentage
CRITICAL_STOCK_THRESHOLD = 10  # percentage
EXPIRING_ITEMS_DAYS = 7  # days before expiration alert

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, manager, head_chef, chef, sous_chef, bartender, waiter, cashier, host, delivery_driver, cleaner
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, required_permission):
        """Check if user has the required permission based on their role"""
        role_permissions = {
            'admin': ['manage_all', 'view_reports', 'manage_staff', 'manage_menu', 'manage_inventory'],
            'manager': ['view_reports', 'manage_staff', 'manage_menu', 'manage_inventory'],
            'head_chef': ['manage_kitchen', 'view_kitchen_reports', 'manage_inventory'],
            'chef': ['manage_kitchen', 'view_kitchen_reports'],
            'sous_chef': ['manage_kitchen'],
            'bartender': ['manage_bar', 'view_bar_reports'],
            'waiter': ['take_orders', 'view_table_status'],
            'cashier': ['process_payments', 'view_sales'],
            'host': ['manage_reservations', 'view_table_status'],
            'delivery_driver': ['manage_deliveries', 'view_delivery_orders'],
            'cleaner': ['view_cleaning_schedule']
        }
        return required_permission in role_permissions.get(self.role, [])

# Role validation function
def validate_role(role):
    valid_roles = [
        'admin', 'manager', 'head_chef', 'chef', 'sous_chef', 
        'bartender', 'waiter', 'cashier', 'host', 'delivery_driver', 'cleaner'
    ]
    return role in valid_roles

class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # appetizer, main, dessert, drink, etc.
    is_available = db.Column(db.Boolean, default=True)
    preparation_time = db.Column(db.Integer)  # in minutes
    image_url = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ingredient(db.Model):
    __tablename__ = 'ingredients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(20), nullable=False)  # kg, g, l, ml, pieces, etc.
    current_stock = db.Column(db.Float, default=0)
    min_stock = db.Column(db.Float, default=0)
    cost_per_unit = db.Column(db.Float)
    supplier = db.Column(db.String(100))
    last_restocked = db.Column(db.DateTime)

class Recipe(db.Model):
    __tablename__ = 'recipes'
    id = db.Column(db.Integer, primary_key=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    quantity_required = db.Column(db.Float, nullable=False)
    
    menu_item = db.relationship('MenuItem', backref=db.backref('recipes', lazy=True))
    ingredient = db.relationship('Ingredient', backref=db.backref('recipes', lazy=True))

class Table(db.Model):
    __tablename__ = 'tables'
    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.Integer, unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='available')  # available, occupied, reserved, cleaning
    location = db.Column(db.String(100))  # indoor, outdoor, bar, etc.

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    loyalty_points = db.Column(db.Integer, default=0)
    total_orders = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'))
    party_size = db.Column(db.Integer, nullable=False)
    reservation_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='confirmed')  # confirmed, seated, completed, cancelled
    special_requests = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    customer = db.relationship('Customer', backref=db.backref('reservations', lazy=True))
    table = db.relationship('Table', backref=db.backref('reservations', lazy=True))

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_type = db.Column(db.String(20), nullable=False)  # dine-in, takeaway, delivery
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cooking, ready, served, completed, cancelled
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'))
    total_amount = db.Column(db.Float, default=0)
    tax_amount = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    final_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    customer = db.relationship('Customer', backref=db.backref('orders', lazy=True))
    table = db.relationship('Table', backref=db.backref('orders', lazy=True))

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)
    special_instructions = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, cooking, ready, served
    
    order = db.relationship('Order', backref=db.backref('items', lazy=True))
    menu_item = db.relationship('MenuItem', backref=db.backref('order_items', lazy=True))

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)  # cash, card, mobile, online
    payment_status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    transaction_id = db.Column(db.String(100))
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    order = db.relationship('Order', backref=db.backref('payments', lazy=True))

class StaffSchedule(db.Model):
    __tablename__ = 'staff_schedules'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    shift_start = db.Column(db.DateTime, nullable=False)
    shift_end = db.Column(db.DateTime, nullable=False)
    role_for_shift = db.Column(db.String(20))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('schedules', lazy=True))

class InventoryTransaction(db.Model):
    __tablename__ = 'inventory_transactions'
    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # purchase, usage, adjustment, waste
    quantity = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    related_order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    
    ingredient = db.relationship('Ingredient', backref=db.backref('transactions', lazy=True))
    order = db.relationship('Order', backref=db.backref('inventory_transactions', lazy=True))

# Suppliers
class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    address = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Staff clock in/out
class StaffTimeLog(db.Model):
    __tablename__ = 'staff_time_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    clock_in = db.Column(db.DateTime, nullable=False)
    clock_out = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    user = db.relationship('User', backref=db.backref('time_logs', lazy=True))

# CRM Notes
class CRMNote(db.Model):
    __tablename__ = 'crm_notes'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    customer = db.relationship('Customer', backref=db.backref('crm_notes', lazy=True))
    created_by = db.relationship('User')

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/menu')
def menu_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('menu.html')

@app.route('/our-menu')
def public_menu_page():
    return render_template('public_menu.html')

@app.route('/orders')
def order_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('orders.html')

@app.route('/inventory')
def inventory_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('inventory.html')

@app.route('/staff_schedule')
def staff_schedule_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('staff_schedule.html')

@app.route('/reservations')
def reservations_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('reservations.html')

@app.route('/reports')
def reports_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('reports.html')

@app.route('/staff')
def staff_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('staff.html')

@app.route('/customers')
def customers_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('customers.html')

@app.route('/tables')
def tables_management():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('tables.html')

@app.route('/kitchen')
def kitchen_display():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('kitchen.html')

@app.route('/cashier')
def cashier_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Check if user has cashier role or higher
    user_role = session.get('role')
    if user_role not in ['admin', 'manager', 'cashier']:
        return jsonify({'message': 'Access denied. Cashier role or higher required.'}), 403

    return render_template('cashier.html')

@app.route('/settings')
def settings_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Check if user has admin or manager role
    user_role = session.get('role')
    if user_role not in ['admin', 'manager']:
        return jsonify({'message': 'Access denied. Admin or Manager role required.'}), 403

    return render_template('settings.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api')
def api_index():
    return jsonify({'message': 'Restaurant Management System API'})

# Authentication Routes
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()

    if user and user.check_password(data['password']) and user.is_active:
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        session['first_name'] = user.first_name
        session['last_name'] = user.last_name

        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        }), 200

    return jsonify({'message': 'Invalid credentials'}), 401

# Menu Management
@app.route('/api/menu', methods=['GET'])
def get_menu():
    category = request.args.get('category')
    if category:
        items = MenuItem.query.filter_by(category=category).all()
    else:
        items = MenuItem.query.all()

    # Check inventory availability for each item based on recipe requirements
    menu_data = []
    for item in items:
        # Get all recipes for this menu item
        recipes = Recipe.query.filter_by(menu_item_id=item.id).all()

        # Check if we have enough inventory for all recipe ingredients
        can_make = True
        if recipes:  # Only check if item has recipes defined
            for recipe in recipes:
                ingredient = Ingredient.query.get(recipe.ingredient_id)
                if ingredient:
                    required_quantity = recipe.quantity_required
                    available_quantity = ingredient.current_stock or 0
                    if available_quantity < required_quantity:
                        can_make = False
                        break

        # Item is available if it's marked as available AND we have enough inventory
        effective_availability = item.is_available and can_make

        menu_data.append({
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'price': item.price,
            'category': item.category,
            'preparation_time': item.preparation_time,
            'image_url': item.image_url,
            'is_available': effective_availability,  # Modified to consider inventory
            'inventory_available': can_make  # Additional field to distinguish inventory vs manual availability
        })

    return jsonify(menu_data)

# Image Upload
@app.route('/api/upload/image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = str(uuid.uuid4()) + '.' + file_extension
        
        # Save the file
        filepath = os.path.join(IMAGE_UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        
        # Return the relative path for storing in database
        image_url = f'/uploads/images/{unique_filename}'
        
        return jsonify({
            'message': 'File uploaded successfully',
            'image_url': image_url,
            'filename': unique_filename
        }), 201
    
    return jsonify({'error': 'Invalid file type. Allowed types: png, jpg, jpeg, gif, webp'}), 400

# Serve uploaded files
@app.route('/uploads/images/<filename>')
def uploaded_file(filename):
    return send_from_directory(IMAGE_UPLOAD_FOLDER, filename)

# Table Management
@app.route('/api/tables', methods=['GET', 'POST'])
def handle_tables():
    if request.method == 'POST':
        data = request.get_json()
        table = Table(
            table_number=data['table_number'],
            capacity=data['capacity'],
            location=data.get('location', 'indoor'),
            status=data.get('status', 'available')
        )
        db.session.add(table)
        db.session.commit()
        return jsonify({
            'message': 'Table created',
            'id': table.id,
            'table': {
                'id': table.id,
                'table_number': table.table_number,
                'capacity': table.capacity,
                'status': table.status,
                'location': table.location
            }
        }), 201

    elif request.method == 'GET':
        tables = Table.query.all()
        return jsonify([{
            'id': table.id,
            'table_number': table.table_number,
            'capacity': table.capacity,
            'status': table.status,
            'location': table.location
        } for table in tables])

@app.route('/api/tables/<int:table_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_table(table_id):
    table = Table.query.get_or_404(table_id)

    if request.method == 'GET':
        return jsonify({
            'id': table.id,
            'table_number': table.table_number,
            'capacity': table.capacity,
            'status': table.status,
            'location': table.location
        })

    elif request.method == 'PUT':
        data = request.get_json()
        table.table_number = data.get('table_number', table.table_number)
        table.capacity = data.get('capacity', table.capacity)
        table.location = data.get('location', table.location)
        table.status = data.get('status', table.status)
        db.session.commit()
        return jsonify({
            'message': 'Table updated',
            'table': {
                'id': table.id,
                'table_number': table.table_number,
                'capacity': table.capacity,
                'status': table.status,
                'location': table.location
            }
        })

    elif request.method == 'DELETE':
        db.session.delete(table)
        db.session.commit()
        return jsonify({'message': 'Table deleted'})

@app.route('/api/menu', methods=['POST'])
def add_menu_item():
    # Handle both JSON and form data
    if request.content_type and 'application/json' in request.content_type:
        # JSON data (backwards compatibility)
        data = request.get_json()
        image_url = data.get('image_url')
    else:
        # Form data with potential file upload
        data = request.form.to_dict()
        image_url = None
        
        # Handle file upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                # Generate unique filename
                file_extension = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = str(uuid.uuid4()) + '.' + file_extension
                
                # Save the file
                filepath = os.path.join(IMAGE_UPLOAD_FOLDER, unique_filename)
                file.save(filepath)
                
                # Set the image URL
                image_url = f'/uploads/images/{unique_filename}'
    
    # Convert form values to appropriate types
    price = float(data['price']) if 'price' in data else 0
    preparation_time = int(data['preparation_time']) if data.get('preparation_time') else None
    is_available = data.get('is_available', 'true').lower() == 'true'
    
    item = MenuItem(
        name=data['name'],
        description=data.get('description', ''),
        price=price,
        category=data['category'],
        preparation_time=preparation_time,
        image_url=image_url,
        is_available=is_available
    )
    db.session.add(item)
    db.session.flush()  # Get the item ID without committing
    
    # Add recipe ingredients if provided (JSON format)
    if request.content_type and 'application/json' in request.content_type and 'recipe_ingredients' in data:
        for ingredient_data in data['recipe_ingredients']:
            recipe = Recipe(
                menu_item_id=item.id,
                ingredient_id=ingredient_data['ingredient_id'],
                quantity_required=ingredient_data['quantity_required']
            )
            db.session.add(recipe)
    
    # Handle recipe ingredients from form data
    elif not (request.content_type and 'application/json' in request.content_type):
        recipe_ingredient_ids = request.form.getlist('recipe_ingredient_id')
        recipe_quantities = request.form.getlist('recipe_quantity')
        
        for ingredient_id, quantity in zip(recipe_ingredient_ids, recipe_quantities):
            if ingredient_id and quantity:
                recipe = Recipe(
                    menu_item_id=item.id,
                    ingredient_id=int(ingredient_id),
                    quantity_required=float(quantity)
                )
                db.session.add(recipe)
    
    db.session.commit()
    return jsonify({
        'message': 'Menu item added',
        'id': item.id,
        'item': {
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'price': item.price,
            'category': item.category,
            'preparation_time': item.preparation_time,
            'image_url': item.image_url,
            'is_available': item.is_available
        }
    }), 201

@app.route('/api/menu/<int:item_id>', methods=['GET'])
def get_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    return jsonify({
        'id': item.id,
        'name': item.name,
        'description': item.description,
        'price': item.price,
        'category': item.category,
        'preparation_time': item.preparation_time,
        'image_url': item.image_url,
        'is_available': item.is_available,
        'created_at': item.created_at.isoformat()
    })

@app.route('/api/menu/<int:item_id>', methods=['PUT'])
def update_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    
    # Handle both JSON and form data
    if request.content_type and 'application/json' in request.content_type:
        # JSON data (backwards compatibility)
        data = request.get_json()
        
        item.name = data.get('name', item.name)
        item.description = data.get('description', item.description)
        item.price = data.get('price', item.price)
        item.category = data.get('category', item.category)
        item.preparation_time = data.get('preparation_time', item.preparation_time)
        item.image_url = data.get('image_url', item.image_url)
        item.is_available = data.get('is_available', item.is_available)
        
        # Update recipe ingredients if provided
        if 'recipe_ingredients' in data:
            # Delete existing recipes
            Recipe.query.filter_by(menu_item_id=item_id).delete()
            
            # Add new recipes
            for ingredient_data in data['recipe_ingredients']:
                recipe = Recipe(
                    menu_item_id=item_id,
                    ingredient_id=ingredient_data['ingredient_id'],
                    quantity_required=ingredient_data['quantity_required']
                )
                db.session.add(recipe)
    else:
        # Form data with potential file upload
        data = request.form.to_dict()
        
        item.name = data.get('name', item.name)
        item.description = data.get('description', item.description)
        item.price = float(data['price']) if 'price' in data else item.price
        item.category = data.get('category', item.category)
        item.preparation_time = int(data['preparation_time']) if data.get('preparation_time') else item.preparation_time
        item.is_available = data.get('is_available', 'true').lower() == 'true'
        
        # Handle file upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                # Generate unique filename
                file_extension = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = str(uuid.uuid4()) + '.' + file_extension
                
                # Save the file
                filepath = os.path.join(IMAGE_UPLOAD_FOLDER, unique_filename)
                file.save(filepath)
                
                # Update the image URL
                item.image_url = f'/uploads/images/{unique_filename}'
        
        # Handle recipe ingredients from form data
        recipe_ingredient_ids = request.form.getlist('recipe_ingredient_id')
        recipe_quantities = request.form.getlist('recipe_quantity')
        
        if recipe_ingredient_ids:
            # Delete existing recipes
            Recipe.query.filter_by(menu_item_id=item_id).delete()
            
            # Add new recipes
            for ingredient_id, quantity in zip(recipe_ingredient_ids, recipe_quantities):
                if ingredient_id and quantity:
                    recipe = Recipe(
                        menu_item_id=item_id,
                        ingredient_id=int(ingredient_id),
                        quantity_required=float(quantity)
                    )
                    db.session.add(recipe)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Menu item updated',
        'item': {
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'price': item.price,
            'category': item.category,
            'preparation_time': item.preparation_time,
            'image_url': item.image_url,
            'is_available': item.is_available
        }
    })

@app.route('/api/menu/<int:item_id>', methods=['PATCH'])
def patch_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    data = request.get_json()
    
    if 'is_available' in data:
        item.is_available = data['is_available']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Menu item updated',
        'item': {
            'id': item.id,
            'name': item.name,
            'is_available': item.is_available
        }
    })

@app.route('/api/menu/<int:item_id>', methods=['DELETE'])
def delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    
    return jsonify({'message': 'Menu item deleted'})

# Recipe Management
@app.route('/api/menu/<int:item_id>/recipe', methods=['GET'])
def get_menu_item_recipe(item_id):
    recipes = Recipe.query.filter_by(menu_item_id=item_id).all()
    return jsonify([{
        'id': recipe.id,
        'menu_item_id': recipe.menu_item_id,
        'ingredient_id': recipe.ingredient_id,
        'quantity_required': recipe.quantity_required,
        'ingredient_name': recipe.ingredient.name if recipe.ingredient else None,
        'ingredient_unit': recipe.ingredient.unit if recipe.ingredient else None
    } for recipe in recipes])

@app.route('/api/menu/<int:item_id>/recipe', methods=['POST'])
def update_menu_item_recipe(item_id):
    data = request.get_json()
    
    # Delete existing recipes
    Recipe.query.filter_by(menu_item_id=item_id).delete()
    
    # Add new recipes
    for ingredient_data in data.get('ingredients', []):
        recipe = Recipe(
            menu_item_id=item_id,
            ingredient_id=ingredient_data['ingredient_id'],
            quantity_required=ingredient_data['quantity_required']
        )
        db.session.add(recipe)
    
    db.session.commit()
    return jsonify({'message': 'Recipe updated successfully'})

# Inventory deduction when orders are placed
def deduct_inventory_for_order(order_id):
    order = Order.query.get(order_id)
    if not order:
        return
    
    for order_item in order.items:
        # Get all recipes for this menu item
        recipes = Recipe.query.filter_by(menu_item_id=order_item.menu_item_id).all()
        
        for recipe in recipes:
            ingredient = Ingredient.query.get(recipe.ingredient_id)
            if ingredient:
                # Calculate total quantity needed
                total_quantity = recipe.quantity_required * order_item.quantity
                
                # Deduct from inventory
                ingredient.current_stock = max(0, ingredient.current_stock - total_quantity)
                
                # Get language for transaction note translation
                # Try to get language from request context, default to 'en'
                try:
                    from flask import request
                    language = request.args.get('lang', 'en') if request else 'en'
                except:
                    language = 'en'
                
                # Transaction note translations
                transaction_note_translations = {
                    'en': 'Used for {quantity} x {item_name}',
                    'ar': 'مستخدم لـ {quantity} x {item_name}',
                    'tr': '{quantity} x {item_name} için kullanıldı'
                }
                
                note_template = transaction_note_translations.get(language, transaction_note_translations['en'])
                note = note_template.format(quantity=order_item.quantity, item_name=order_item.menu_item.name)
                
                # Record inventory transaction
                transaction = InventoryTransaction(
                    ingredient_id=ingredient.id,
                    transaction_type='usage',
                    quantity=total_quantity,
                    related_order_id=order_id,
                    notes=note
                )
                db.session.add(transaction)
    
    db.session.commit()

# Order Management
@app.route('/api/orders', methods=['GET', 'POST'])
def handle_orders():
    if request.method == 'POST':
        data = request.get_json()
        
        order = Order(
            order_type=data['order_type'],
            customer_id=data.get('customer_id'),
            table_id=data.get('table_id'),
            notes=data.get('notes')
        )
        
        db.session.add(order)
        db.session.flush()  # Get the order ID
        
        total_amount = 0
        for item_data in data['items']:
            menu_item = MenuItem.query.get(item_data['menu_item_id'])
            if not menu_item or not menu_item.is_available:
                return jsonify({'message': f'Menu item {item_data["menu_item_id"]} not available'}), 400
            
            order_item = OrderItem(
                order_id=order.id,
                menu_item_id=item_data['menu_item_id'],
                quantity=item_data['quantity'],
                price=menu_item.price,
                special_instructions=item_data.get('special_instructions')
            )
            db.session.add(order_item)
            total_amount += menu_item.price * item_data['quantity']
        
        order.total_amount = total_amount
        order.tax_amount = total_amount * 0.1  # 10% tax
        order.final_amount = total_amount + order.tax_amount
        
        # Update table status if it's a dine-in order
        if order.order_type == 'dine-in' and order.table_id:
            table = Table.query.get(order.table_id)
            table.status = 'occupied'
        
        db.session.commit()
        
        # Deduct inventory for the order
        deduct_inventory_for_order(order.id)
        
        return jsonify({'message': 'Order created', 'order_id': order.id}), 201
    
    elif request.method == 'GET':
        orders = Order.query.order_by(Order.created_at.desc()).all()
        return jsonify([{
            'id': order.id,
            'order_type': order.order_type,
            'status': order.status,
            'final_amount': order.final_amount,
            'created_at': order.created_at.isoformat(),
            'table_number': order.table.table_number if order.table else None,
            'customer_name': f"{order.customer.first_name} {order.customer.last_name}" if order.customer else 'Guest'
        } for order in orders])

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = Order.query.get_or_404(order_id)
    return jsonify({
        'id': order.id,
        'order_type': order.order_type,
        'status': order.status,
        'total_amount': order.total_amount,
        'final_amount': order.final_amount,
        'created_at': order.created_at.isoformat(),
        'items': [{
            'id': item.id,
            'menu_item_name': item.menu_item.name,
            'quantity': item.quantity,
            'price': item.price,
            'status': item.status
        } for item in order.items]
    })

@app.route('/receipt/<int:order_id>', methods=['GET'])
def render_receipt(order_id):
    order = Order.query.get_or_404(order_id)
    payments = Payment.query.filter_by(order_id=order.id, payment_status='completed').all()
    total_paid = sum(p.amount for p in payments)
    balance = (order.final_amount or 0) - total_paid
    return render_template('receipt.html', order=order, payments=payments, total_paid=total_paid, balance=balance)

@app.route('/api/orders/<int:order_id>/payments', methods=['GET', 'POST'])
def handle_order_payments(order_id):
    order = Order.query.get_or_404(order_id)
    if request.method == 'POST':
        data = request.get_json()
        amount = float(data['amount'])
        payment_method = data['method']  # cash, card, mobile, online
        transaction_id = data.get('transaction_id')

        payment = Payment(
            order_id=order.id,
            amount=amount,
            payment_method=payment_method,
            payment_status='completed',
            transaction_id=transaction_id
        )
        db.session.add(payment)
        db.session.flush()

        # Update order status if fully paid - send to kitchen
        total_paid = db.session.query(db.func.sum(Payment.amount)).filter_by(order_id=order.id, payment_status='completed').scalar() or 0
        if total_paid >= (order.final_amount or 0):
            # Send order to kitchen if it's not already completed or cancelled
            if order.status not in ['completed', 'cancelled']:
                order.status = 'confirmed'  # This will send order to kitchen
        # Accrue loyalty on completion with tier bonuses
        if order.customer_id and (order.final_amount or 0) > 0:
            customer = Customer.query.get(order.customer_id)
            if customer:
                # Calculate base points
                base_points = int(round((order.final_amount or 0) * LOYALTY_POINTS_PER_CURRENCY))

                # Apply tier bonus
                current_tier = get_customer_loyalty_tier(customer.loyalty_points or 0)
                tier_multiplier = LOYALTY_TIER_BONUSES.get(current_tier, 1.0)
                earned = int(round(base_points * tier_multiplier))

                customer.loyalty_points = (customer.loyalty_points or 0) + earned
        db.session.commit()

        return jsonify({'message': 'Payment recorded', 'payment_id': payment.id, 'total_paid': float(total_paid)}), 201

    # GET
    payments = Payment.query.filter_by(order_id=order.id).order_by(Payment.payment_date.asc()).all()
    return jsonify([{
        'id': p.id,
        'amount': p.amount,
        'method': p.payment_method,
        'status': p.payment_status,
        'transaction_id': p.transaction_id,
        'payment_date': p.payment_date.isoformat()
    } for p in payments])

# Inventory Management
@app.route('/api/inventory', methods=['GET', 'POST'])
def handle_inventory():
    if request.method == 'POST':
        data = request.get_json()
        new_ingredient = Ingredient(
            name=data['name'],
            unit=data['unit'],
            min_stock=data['min_stock'],
            current_stock=0  # Ingredients start with 0 stock
        )
        db.session.add(new_ingredient)
        db.session.commit()
        return jsonify({'message': 'Ingredient added', 'id': new_ingredient.id}), 201
    
    elif request.method == 'GET':
        ingredients = Ingredient.query.all()
        return jsonify([{
            'id': ing.id,
            'name': ing.name,
            'unit': ing.unit,
            'current_stock': ing.current_stock,
            'min_stock': ing.min_stock,
            'cost_per_unit': ing.cost_per_unit,
            'supplier': ing.supplier,
            'status': 'low' if ing.current_stock <= ing.min_stock else 'adequate'
        } for ing in ingredients])

@app.route('/api/inventory/<int:ingredient_id>', methods=['DELETE'])
def delete_ingredient(ingredient_id):
    ingredient = Ingredient.query.get_or_404(ingredient_id)
    # Optional: also delete related transactions and recipes referencing this ingredient
    InventoryTransaction.query.filter_by(ingredient_id=ingredient_id).delete()
    Recipe.query.filter_by(ingredient_id=ingredient_id).delete()
    db.session.delete(ingredient)
    db.session.commit()
    return jsonify({'message': 'Ingredient deleted'})

@app.route('/api/inventory/low-stock', methods=['GET'])
def get_low_stock():
    low_stock = Ingredient.query.filter(Ingredient.current_stock <= Ingredient.min_stock).all()
    return jsonify([{
        'id': ing.id,
        'name': ing.name,
        'current_stock': ing.current_stock,
        'min_stock': ing.min_stock,
        'unit': ing.unit
    } for ing in low_stock])

@app.route('/api/notifications/alerts', methods=['GET'])
def get_inventory_alerts():
    """Get automated inventory alerts based on thresholds"""
    # Get language from query parameter
    language = request.args.get('lang', 'en')

    # Alert translations
    alert_translations = {
        'en': {
            'low_stock_title': 'Low Stock Alert: {item}',
            'low_stock_message': '{item} is running low. Current: {current} {unit}, Minimum: {minimum} {unit}',
            'critical_stock_title': 'Critical Stock Alert: {item}',
            'critical_stock_message': '{item} is critically low! Current: {current} {unit}, Minimum: {minimum} {unit}'
        },
        'ar': {
            'low_stock_title': 'تنبيه انخفاض المخزون: {item}',
            'low_stock_message': '{item} ينخفض المخزون. الحالي: {current} {unit}، الحد الأدنى: {minimum} {unit}',
            'critical_stock_title': 'تنبيه نقص حاد في المخزون: {item}',
            'critical_stock_message': '{item} منخفض جداً! الحالي: {current} {unit}، الحد الأدنى: {minimum} {unit}'
        },
        'tr': {
            'low_stock_title': 'Düşük Stok Uyarısı: {item}',
            'low_stock_message': '{item} stoğu azalıyor. Mevcut: {current} {unit}, Minimum: {minimum} {unit}',
            'critical_stock_title': 'Kritik Stok Uyarısı: {item}',
            'critical_stock_message': '{item} kritik düzeyde düşük! Mevcut: {current} {unit}, Minimum: {minimum} {unit}'
        }
    }

    translations = alert_translations.get(language, alert_translations['en'])
    alerts = []

    # Low stock alerts
    low_stock_items = Ingredient.query.filter(
        Ingredient.current_stock <= Ingredient.min_stock
    ).all()

    for item in low_stock_items:
        alerts.append({
            'type': 'low_stock',
            'severity': 'warning',
            'title': translations['low_stock_title'].format(item=item.name),
            'message': translations['low_stock_message'].format(
                item=item.name,
                current=item.current_stock,
                unit=item.unit,
                minimum=item.min_stock
            ),
            'item_id': item.id,
            'item_name': item.name,
            'current_stock': item.current_stock,
            'min_stock': item.min_stock,
            'unit': item.unit,
            'timestamp': datetime.utcnow().isoformat()
        })

    # Critical stock alerts
    critical_items = Ingredient.query.filter(
        Ingredient.current_stock <= (Ingredient.min_stock * CRITICAL_STOCK_THRESHOLD / 100)
    ).all()

    for item in critical_items:
        alerts.append({
            'type': 'critical_stock',
            'severity': 'error',
            'title': translations['critical_stock_title'].format(item=item.name),
            'message': translations['critical_stock_message'].format(
                item=item.name,
                current=item.current_stock,
                unit=item.unit,
                minimum=item.min_stock
            ),
            'item_id': item.id,
            'item_name': item.name,
            'current_stock': item.current_stock,
            'min_stock': item.min_stock,
            'unit': item.unit,
            'timestamp': datetime.utcnow().isoformat()
        })

    # Expiring items alert (placeholder for future implementation)
    # This would require adding expiration dates to ingredients

    return jsonify({
        'alerts': alerts,
        'total_count': len(alerts),
        'critical_count': len([a for a in alerts if a['severity'] == 'error']),
        'warning_count': len([a for a in alerts if a['severity'] == 'warning'])
    })

@app.route('/api/inventory/restock', methods=['POST'])
def restock_inventory():
    data = request.get_json()
    ingredient = Ingredient.query.get_or_404(data['ingredient_id'])
    ingredient.current_stock += float(data['quantity'])
    
    # Log the transaction
    transaction = InventoryTransaction(
        ingredient_id=ingredient.id,
        transaction_type='purchase',
        quantity=float(data['quantity'])
    )
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({'message': 'Stock updated', 'new_stock': ingredient.current_stock})

@app.route('/api/inventory/wastage', methods=['POST', 'GET'])
def inventory_wastage():
    if request.method == 'POST':
        data = request.get_json()
        ingredient = Ingredient.query.get_or_404(data['ingredient_id'])
        quantity = float(data['quantity'])
        
        # Get language for wastage reason translation
        language = request.args.get('lang', 'en')
        
        # Wastage reason translations
        wastage_reason_translations = {
            'en': 'waste',
            'ar': 'نفايات',
            'tr': 'israf'
        }
        
        default_reason = wastage_reason_translations.get(language, wastage_reason_translations['en'])
        reason = data.get('reason', default_reason)
        
        ingredient.current_stock = max(0, (ingredient.current_stock or 0) - quantity)
        t = InventoryTransaction(
            ingredient_id=ingredient.id,
            transaction_type='waste',
            quantity=quantity,
            notes=reason
        )
        db.session.add(t)
        db.session.commit()
        return jsonify({'message': 'Wastage recorded', 'ingredient_id': ingredient.id, 'new_stock': ingredient.current_stock}), 201
    transactions = InventoryTransaction.query.filter_by(transaction_type='waste').order_by(InventoryTransaction.transaction_date.desc()).all()
    return jsonify([{
        'id': t.id,
        'ingredient_id': t.ingredient_id,
        'ingredient_name': t.ingredient.name if t.ingredient else None,
        'quantity': t.quantity,
        'transaction_date': t.transaction_date.isoformat(),
        'notes': t.notes
    } for t in transactions])

@app.route('/api/inventory/<int:ingredient_id>/spoil', methods=['POST'])
def spoil_ingredient(ingredient_id):
    """Spoil a portion of an ingredient, creating a waste transaction"""
    data = request.get_json()
    ingredient = Ingredient.query.get_or_404(ingredient_id)
    quantity = float(data['quantity'])
    reason = data.get('reason', '').strip()
    
    # Validate quantity
    if quantity <= 0:
        return jsonify({'message': 'Quantity must be greater than zero'}), 400
    
    if quantity > (ingredient.current_stock or 0):
        return jsonify({'message': 'Cannot spoil more than current stock'}), 400
    
    # Get language for spoil reason translation
    language = request.args.get('lang', 'en')
    
    # Default spoil reason translations
    spoil_reason_translations = {
        'en': 'Spoiled',
        'ar': 'مُفسَد',
        'tr': 'Bozuldu'
    }
    
    default_reason = spoil_reason_translations.get(language, spoil_reason_translations['en'])
    spoil_reason = reason if reason else default_reason
    
    # Update ingredient stock
    ingredient.current_stock = max(0, (ingredient.current_stock or 0) - quantity)
    
    # Create waste transaction
    transaction = InventoryTransaction(
        ingredient_id=ingredient.id,
        transaction_type='waste',
        quantity=quantity,
        notes=spoil_reason
    )
    db.session.add(transaction)
    db.session.commit()
    
    return jsonify({
        'message': 'Ingredient spoiled successfully', 
        'ingredient_id': ingredient.id, 
        'quantity_spoiled': quantity,
        'new_stock': ingredient.current_stock
    }), 200

@app.route('/api/inventory/transactions', methods=['GET'])
def get_inventory_transactions():
    transactions = InventoryTransaction.query.order_by(InventoryTransaction.transaction_date.desc()).all()
    return jsonify([{
        'id': t.id,
        'ingredient_id': t.ingredient_id,
        'ingredient_name': t.ingredient.name if t.ingredient else None,
        'transaction_type': t.transaction_type,
        'quantity': t.quantity,
        'cost_per_unit': t.ingredient.cost_per_unit if t.ingredient else None,
        'total_cost': (t.quantity * (t.ingredient.cost_per_unit or 0)) if t.ingredient else 0,
        'transaction_date': t.transaction_date.isoformat(),
        'notes': t.notes,
        'related_order_id': t.related_order_id
    } for t in transactions])

# Supplier CRUD
@app.route('/api/suppliers', methods=['GET', 'POST'])
def suppliers_collection():
    if request.method == 'POST':
        data = request.get_json()
        supplier = Supplier(
            name=data['name'],
            contact_name=data.get('contact_name'),
            email=data.get('email'),
            phone=data.get('phone'),
            address=data.get('address')
        )
        db.session.add(supplier)
        db.session.commit()
        return jsonify({'message': 'Supplier created', 'id': supplier.id}), 201
    suppliers = Supplier.query.order_by(Supplier.created_at.desc()).all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'contact_name': s.contact_name,
        'email': s.email,
        'phone': s.phone,
        'address': s.address
    } for s in suppliers])

@app.route('/api/suppliers/<int:supplier_id>', methods=['GET', 'PUT', 'DELETE'])
def supplier_detail(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == 'GET':
        return jsonify({
            'id': supplier.id,
            'name': supplier.name,
            'contact_name': supplier.contact_name,
            'email': supplier.email,
            'phone': supplier.phone,
            'address': supplier.address
        })
    if request.method == 'PUT':
        data = request.get_json()
        supplier.name = data.get('name', supplier.name)
        supplier.contact_name = data.get('contact_name', supplier.contact_name)
        supplier.email = data.get('email', supplier.email)
        supplier.phone = data.get('phone', supplier.phone)
        supplier.address = data.get('address', supplier.address)
        db.session.commit()
        return jsonify({'message': 'Supplier updated'})
    db.session.delete(supplier)
    db.session.commit()
    return jsonify({'message': 'Supplier deleted'})

@app.route('/api/inventory/<int:ingredient_id>', methods=['PUT'])
def update_ingredient(ingredient_id):
    ingredient = Ingredient.query.get_or_404(ingredient_id)
    data = request.get_json()
    ingredient.name = data.get('name', ingredient.name)
    ingredient.unit = data.get('unit', ingredient.unit)
    if 'min_stock' in data:
        ingredient.min_stock = float(data['min_stock'])
    if 'current_stock' in data:
        ingredient.current_stock = float(data['current_stock'])
    if 'cost_per_unit' in data:
        ingredient.cost_per_unit = float(data['cost_per_unit']) if data['cost_per_unit'] is not None else None
    if 'supplier' in data:
        ingredient.supplier = data['supplier']
    db.session.commit()
    return jsonify({'message': 'Ingredient updated', 'id': ingredient.id})

# Reservation Management
@app.route('/api/reservations', methods=['GET', 'POST'])
def handle_reservations():
    if request.method == 'POST':
        data = request.get_json()
        
        # Check if table is available
        table = Table.query.get(data['table_id'])
        if table.status != 'available':
            return jsonify({'message': 'Table is not available'}), 400
        
        reservation = Reservation(
            customer_id=data.get('customer_id'),
            table_id=data['table_id'],
            party_size=data['party_size'],
            reservation_time=datetime.fromisoformat(data['reservation_time']),
            special_requests=data.get('special_requests')
        )
        
        table.status = 'reserved'
        
        db.session.add(reservation)
        db.session.commit()
        
        return jsonify({'message': 'Reservation created', 'id': reservation.id}), 201
    
    elif request.method == 'GET':
        reservations = Reservation.query.join(Table).outerjoin(Customer).order_by(Reservation.reservation_time.asc()).all()
        
        return jsonify([{
            'id': res.id,
            'customer_id': res.customer_id,
            'customer_name': f"{res.customer.first_name} {res.customer.last_name}" if res.customer else None,
            'table_id': res.table_id,
            'table_number': res.table.table_number if res.table else None,
            'party_size': res.party_size,
            'reservation_time': res.reservation_time.isoformat(),
            'status': res.status,
            'special_requests': res.special_requests
        } for res in reservations])

@app.route('/api/reservations/<int:reservation_id>', methods=['GET'])
def get_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    return jsonify({
        'id': reservation.id,
        'customer_id': reservation.customer_id,
        'customer_name': f"{reservation.customer.first_name} {reservation.customer.last_name}" if reservation.customer else None,
        'table_id': reservation.table_id,
        'table_number': reservation.table.table_number if reservation.table else None,
        'party_size': reservation.party_size,
        'reservation_time': reservation.reservation_time.isoformat(),
        'status': reservation.status,
        'special_requests': reservation.special_requests,
        'created_at': reservation.created_at.isoformat()
    })

@app.route('/api/reservations/<int:reservation_id>', methods=['PUT'])
def update_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    data = request.get_json()
    
    reservation.customer_id = data.get('customer_id', reservation.customer_id)
    reservation.table_id = data.get('table_id', reservation.table_id)
    reservation.party_size = data.get('party_size', reservation.party_size)
    
    if data.get('reservation_time'):
        reservation.reservation_time = datetime.fromisoformat(data['reservation_time'])
        
    reservation.status = data.get('status', reservation.status)
    reservation.special_requests = data.get('special_requests', reservation.special_requests)
    
    db.session.commit()
    
    return jsonify({'message': 'Reservation updated', 'id': reservation.id})

@app.route('/api/reservations/<int:reservation_id>', methods=['DELETE'])
def delete_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    db.session.delete(reservation)
    db.session.commit()
    
    return jsonify({'message': 'Reservation deleted'})

@app.route('/api/customers', methods=['GET', 'POST'])
def get_or_create_customers():
    if request.method == 'POST':
        data = request.get_json()
        customer = Customer(
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            email=data.get('email'),
            phone=data.get('phone'),
        )
        # Optional initial loyalty
        if 'loyalty_points' in data and isinstance(data['loyalty_points'], (int, float)):
            customer.loyalty_points = int(data['loyalty_points'])
        db.session.add(customer)
        db.session.commit()
        return jsonify({'message': 'Customer created', 'id': customer.id}), 201
    customers = Customer.query.order_by(Customer.created_at.desc()).all()
    return jsonify([{
        'id': c.id,
        'first_name': c.first_name,
        'last_name': c.last_name,
        'email': c.email,
        'phone': c.phone,
        'loyalty_points': c.loyalty_points,
        'loyalty_tier': get_customer_loyalty_tier(c.loyalty_points),
        'next_tier_points': get_next_tier_threshold(c.loyalty_points),
        'points_to_next_tier': get_points_to_next_tier(c.loyalty_points)
    } for c in customers])

@app.route('/api/customers/<int:customer_id>/loyalty', methods=['POST'])
def adjust_loyalty(customer_id):
    data = request.get_json()
    customer = Customer.query.get_or_404(customer_id)
    delta = int(data.get('points', 0))
    action = data.get('action', 'accrue')
    if action == 'redeem' and customer.loyalty_points < abs(delta):
        return jsonify({'message': 'Insufficient points'}), 400
    customer.loyalty_points = (customer.loyalty_points or 0) + (delta if action == 'accrue' else -abs(delta))
    db.session.commit()
    return jsonify({'message': 'Loyalty updated', 'loyalty_points': customer.loyalty_points})

@app.route('/api/customers/<int:customer_id>/crm-notes', methods=['GET', 'POST'])
def crm_notes(customer_id):
    if request.method == 'POST':
        data = request.get_json()
        note = CRMNote(
            customer_id=customer_id,
            note=data['note'],
            created_by_user_id=session.get('user_id')
        )
        db.session.add(note)
        db.session.commit()
        return jsonify({'message': 'Note added', 'id': note.id}), 201
    notes = CRMNote.query.filter_by(customer_id=customer_id).order_by(CRMNote.created_at.desc()).all()
    return jsonify([{
        'id': n.id,
        'note': n.note,
        'created_at': n.created_at.isoformat(),
        'created_by_user_id': n.created_by_user_id
    } for n in notes])

# Staff Management
@app.route('/api/staff', methods=['GET', 'POST'])
def handle_staff():
    if request.method == 'POST':
        data = request.get_json()
        
        # Validate role
        if not validate_role(data['role']):
            return jsonify({'message': 'Invalid role'}), 400
        
        # Check if username or email already exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'message': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'message': 'Email already exists'}), 400
        
        user = User(
            username=data['username'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data['email'],
            phone=data.get('phone'),
            role=data['role'],
            is_active=data.get('is_active', True)
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'message': 'Staff member created',
            'id': user.id,
            'user': {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': user.phone,
                'role': user.role,
                'is_active': user.is_active
            }
        }), 201
    
    elif request.method == 'GET':
        users = User.query.filter(User.role != 'customer').all() # Exclude customers
        return jsonify([{
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'email': user.email,
            'phone': user.phone,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat()
        } for user in users])

@app.route('/api/staff/<int:staff_id>', methods=['GET'])
def get_staff_member(staff_id):
    user = User.query.get_or_404(staff_id)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'email': user.email,
        'phone': user.phone,
        'is_active': user.is_active,
        'created_at': user.created_at.isoformat()
    })

@app.route('/api/staff/<int:staff_id>', methods=['PUT'])
def update_staff_member(staff_id):
    user = User.query.get_or_404(staff_id)
    data = request.get_json()
    
    # Validate role if provided
    if 'role' in data and not validate_role(data['role']):
        return jsonify({'message': 'Invalid role'}), 400
    
    # Check if username or email already exists (excluding current user)
    if 'username' in data and User.query.filter(User.username == data['username'], User.id != staff_id).first():
        return jsonify({'message': 'Username already exists'}), 400
    
    if 'email' in data and User.query.filter(User.email == data['email'], User.id != staff_id).first():
        return jsonify({'message': 'Email already exists'}), 400
    
    user.first_name = data.get('first_name', user.first_name)
    user.last_name = data.get('last_name', user.last_name)
    user.username = data.get('username', user.username)
    user.email = data.get('email', user.email)
    user.phone = data.get('phone', user.phone)
    user.role = data.get('role', user.role)
    user.is_active = data.get('is_active', user.is_active)
    
    if 'password' in data and data['password']:
        user.set_password(data['password'])
    
    db.session.commit()
    
    return jsonify({
        'message': 'Staff member updated',
        'user': {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'role': user.role,
            'is_active': user.is_active
        }
    })

@app.route('/api/staff/<int:staff_id>', methods=['PATCH'])
def patch_staff_member(staff_id):
    user = User.query.get_or_404(staff_id)
    data = request.get_json()
    
    if 'is_active' in data:
        user.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Staff member updated',
        'user': {
            'id': user.id,
            'is_active': user.is_active
        }
    })

# Staff clock-in/out
@app.route('/api/staff/clock-in', methods=['POST'])
def staff_clock_in():
    data = request.get_json()
    user_id = data.get('user_id') or session.get('user_id')
    if not user_id:
        return jsonify({'message': 'User not specified'}), 400
    open_log = StaffTimeLog.query.filter_by(user_id=user_id, clock_out=None).first()
    if open_log:
        return jsonify({'message': 'Already clocked in', 'clock_in': open_log.clock_in.isoformat()}), 400
    log = StaffTimeLog(user_id=user_id, clock_in=datetime.utcnow(), notes=data.get('notes'))
    db.session.add(log)
    db.session.commit()
    return jsonify({'message': 'Clocked in', 'id': log.id, 'clock_in': log.clock_in.isoformat()}), 201

@app.route('/api/staff/clock-out', methods=['POST'])
def staff_clock_out():
    data = request.get_json()
    user_id = data.get('user_id') or session.get('user_id')
    if not user_id:
        return jsonify({'message': 'User not specified'}), 400
    log = StaffTimeLog.query.filter_by(user_id=user_id, clock_out=None).order_by(StaffTimeLog.clock_in.desc()).first()
    if not log:
        return jsonify({'message': 'No active shift'}), 400
    log.clock_out = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Clocked out', 'id': log.id, 'clock_out': log.clock_out.isoformat()})

@app.route('/api/staff/time-logs', methods=['GET'])
def staff_time_logs():
    user_id = request.args.get('user_id') or session.get('user_id')
    query = StaffTimeLog.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    logs = query.order_by(StaffTimeLog.clock_in.desc()).all()
    return jsonify([{
        'id': l.id,
        'user_id': l.user_id,
        'clock_in': l.clock_in.isoformat(),
        'clock_out': l.clock_out.isoformat() if l.clock_out else None,
        'notes': l.notes
    } for l in logs])

# Kitchen Display System APIs
@app.route('/api/kitchen/orders', methods=['GET'])
def get_kitchen_orders():
    # Get orders that are in progress (not completed or cancelled)
    orders = Order.query.filter(
        Order.status.in_(['pending', 'confirmed', 'cooking', 'ready'])
    ).order_by(Order.created_at.asc()).all()
    
    return jsonify([{
        'id': order.id,
        'order_type': order.order_type,
        'status': order.status,
        'created_at': order.created_at.isoformat(),
        'table_number': order.table.table_number if order.table else None,
        'notes': order.notes,
        'items': [{
            'id': item.id,
            'menu_item_name': item.menu_item.name,
            'quantity': item.quantity,
            'special_instructions': item.special_instructions,
            'status': item.status
        } for item in order.items]
    } for order in orders])

@app.route('/api/kitchen/items/<int:item_id>', methods=['PATCH'])
def update_order_item_status(item_id):
    item = OrderItem.query.get_or_404(item_id)
    data = request.get_json()
    
    item.status = data.get('status', item.status)
    db.session.commit()
    _push_kds_change('item_status', {'item_id': item.id, 'order_id': item.order_id, 'status': item.status})
    
    # Check if all items in the order are served/completed
    order = Order.query.get(item.order_id)
    if order and all(item.status in ['served', 'completed'] for item in order.items):
        order.status = 'completed'
        db.session.commit()
    
    return jsonify({
        'message': 'Order item status updated',
        'item': {
            'id': item.id,
            'status': item.status
        }
    })

@app.route('/api/orders/<int:order_id>', methods=['PATCH'])
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.get_json()
    
    old_status = order.status
    order.status = data.get('status', order.status)
    
    # Update table status if order is completed or cancelled
    if order.status in ['completed', 'cancelled'] and order.table_id:
        table = Table.query.get(order.table_id)
        if table and table.status == 'occupied':
            table.status = 'available'
    
    db.session.commit()
    # Accrue loyalty when explicitly marked completed
    if order.status == 'completed' and order.customer_id and (order.final_amount or 0) > 0:
        customer = Customer.query.get(order.customer_id)
        if customer:
            earned = int(round((order.final_amount or 0) * LOYALTY_POINTS_PER_CURRENCY))
            customer.loyalty_points = (customer.loyalty_points or 0) + earned
            db.session.commit()
    _push_kds_change('order_status', {'order_id': order.id, 'status': order.status})
    
    return jsonify({
        'message': 'Order status updated',
        'order': {
            'id': order.id,
            'status': order.status
        }
    })

@app.route('/api/staff/schedule', methods=['POST'])
def create_schedule():
    data = request.get_json()
    
    schedule = StaffSchedule(
        user_id=data['user_id'],
        shift_start=datetime.fromisoformat(data['shift_start']),
        shift_end=datetime.fromisoformat(data['shift_end']),
        role_for_shift=data.get('role_for_shift'),
        notes=data.get('notes')
    )
    
    db.session.add(schedule)
    db.session.commit()
    
    return jsonify({'message': 'Schedule created', 'id': schedule.id}), 201

@app.route('/api/staff/schedule', methods=['GET'])
def get_schedules():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    query = StaffSchedule.query.join(User)
    
    if start_date_str:
        start_date = datetime.fromisoformat(start_date_str)
        query = query.filter(StaffSchedule.shift_start >= start_date)
    if end_date_str:
        end_date = datetime.fromisoformat(end_date_str)
        query = query.filter(StaffSchedule.shift_end <= end_date)
    
    schedules = query.order_by(StaffSchedule.shift_start.asc()).all()
    
    return jsonify([{
        'id': s.id,
        'user_id': s.user.id,
        'user_name': f"{s.user.first_name} {s.user.last_name}",
        'user_role': s.user.role, # Actual role from user table
        'shift_start': s.shift_start.isoformat(),
        'shift_end': s.shift_end.isoformat(),
        'role_for_shift': s.role_for_shift, # Specific role for this shift
        'notes': s.notes
    } for s in schedules])

@app.route('/api/staff/schedule/<int:schedule_id>', methods=['GET'])
def get_schedule_detail(schedule_id):
    schedule = StaffSchedule.query.get_or_404(schedule_id)
    return jsonify({
        'id': schedule.id,
        'user_id': schedule.user.id,
        'user_name': f"{schedule.user.first_name} {schedule.user.last_name}",
        'user_role': schedule.user.role,
        'shift_start': schedule.shift_start.isoformat(),
        'shift_end': schedule.shift_end.isoformat(),
        'role_for_shift': schedule.role_for_shift,
        'notes': schedule.notes,
        'created_at': schedule.created_at.isoformat()
    })

@app.route('/api/staff/schedule/<int:schedule_id>', methods=['PUT'])
def update_schedule(schedule_id):
    schedule = StaffSchedule.query.get_or_404(schedule_id)
    data = request.get_json()
    
    schedule.user_id = data.get('user_id', schedule.user_id)
    schedule.shift_start = datetime.fromisoformat(data.get('shift_start')) if data.get('shift_start') else schedule.shift_start
    schedule.shift_end = datetime.fromisoformat(data.get('shift_end')) if data.get('shift_end') else schedule.shift_end
    schedule.role_for_shift = data.get('role_for_shift', schedule.role_for_shift)
    schedule.notes = data.get('notes', schedule.notes)
    
    db.session.commit()
    
    return jsonify({'message': 'Schedule updated', 'id': schedule.id})

@app.route('/api/staff/schedule/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    schedule = StaffSchedule.query.get_or_404(schedule_id)
    db.session.delete(schedule)
    db.session.commit()
    return jsonify({'message': 'Schedule deleted'})

# Reporting
@app.route('/api/reports/sales', methods=['GET'])
def sales_report():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    query = Order.query.filter(Order.status == 'completed')
    
    if start_date_str:
        start_date = datetime.fromisoformat(start_date_str)
        query = query.filter(Order.created_at >= start_date)
    if end_date_str:
        end_date = datetime.fromisoformat(end_date_str)
        query = query.filter(Order.created_at <= end_date)
    
    orders = query.all()
    
    total_sales = sum(order.final_amount for order in orders)
    total_orders = len(orders)
    average_order_value = total_sales / total_orders if total_orders > 0 else 0
    
    # Find best selling day
    daily_sales = {}
    for order in orders:
        day = order.created_at.date()
        daily_sales[day] = daily_sales.get(day, 0) + order.final_amount
    
    best_day = max(daily_sales.items(), key=lambda x: x[1], default=(None, 0))
    best_day_formatted = best_day[0].strftime('%Y-%m-%d') if best_day[0] else 'N/A'
    
    return jsonify({
        'total_sales': total_sales,
        'total_orders': total_orders,
        'average_order_value': average_order_value,
        'best_day': best_day_formatted,
        'period_start': start_date_str,
        'period_end': end_date_str
    })

@app.route('/api/reports/popular-items', methods=['GET'])
def popular_items_report():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    query = db.session.query(
        MenuItem.name.label('item_name'),
        db.func.sum(OrderItem.quantity).label('total_quantity'),
        db.func.sum(OrderItem.quantity * OrderItem.price).label('total_revenue')
    ).join(OrderItem, OrderItem.menu_item_id == MenuItem.id
    ).join(Order, Order.id == OrderItem.order_id
    ).filter(Order.status == 'completed')

    if start_date_str:
        start_date = datetime.fromisoformat(start_date_str)
        query = query.filter(Order.created_at >= start_date)
    if end_date_str:
        end_date = datetime.fromisoformat(end_date_str)
        query = query.filter(Order.created_at <= end_date)

    results = query.group_by(MenuItem.id).order_by(db.desc('total_quantity')).limit(20).all()

    return jsonify([{
        'item_name': result[0],
        'total_quantity': result[1],
        'total_revenue': float(result[2]) if result[2] else 0.0
    } for result in results])

# Advanced Analytics Dashboard
@app.route('/api/analytics/overview', methods=['GET'])
def analytics_overview():
    """Get comprehensive analytics overview"""
    # Date range (default to last 30 days)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    # Revenue analytics
    orders = Order.query.filter(
        Order.status == 'completed',
        Order.created_at >= start_date,
        Order.created_at <= end_date
    ).all()

    total_revenue = sum(order.final_amount or 0 for order in orders)
    total_orders = len(orders)
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

    # Customer analytics
    customers = Customer.query.all()
    total_customers = len(customers)
    active_customers = len([c for c in customers if c.total_orders and c.total_orders > 0])

    # Loyalty program stats
    total_loyalty_points = sum(c.loyalty_points or 0 for c in customers)
    avg_loyalty_points = total_loyalty_points / total_customers if total_customers > 0 else 0

    # Inventory analytics
    ingredients = Ingredient.query.all()
    low_stock_items = len([i for i in ingredients if i.current_stock <= i.min_stock])
    total_inventory_value = sum((i.current_stock or 0) * (i.cost_per_unit or 0) for i in ingredients)

    # Staff analytics
    staff_count = User.query.filter(User.role != 'customer').count()
    active_staff = User.query.filter(User.role != 'customer', User.is_active == True).count()

    return jsonify({
        'revenue': {
            'total': total_revenue,
            'orders': total_orders,
            'average_order': avg_order_value
        },
        'customers': {
            'total': total_customers,
            'active': active_customers,
            'loyalty_points': total_loyalty_points,
            'avg_loyalty_points': avg_loyalty_points
        },
        'inventory': {
            'total_items': len(ingredients),
            'low_stock': low_stock_items,
            'total_value': total_inventory_value
        },
        'staff': {
            'total': staff_count,
            'active': active_staff
        },
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        }
    })

@app.route('/api/analytics/revenue-trends', methods=['GET'])
def revenue_trends():
    """Get revenue trends over time"""
    days = int(request.args.get('days', 30))
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Daily revenue
    daily_revenue = {}
    orders = Order.query.filter(
        Order.status == 'completed',
        Order.created_at >= start_date,
        Order.created_at <= end_date
    ).all()

    for order in orders:
        day = order.created_at.date().isoformat()
        daily_revenue[day] = daily_revenue.get(day, 0) + (order.final_amount or 0)

    # Fill missing days with 0
    current_date = start_date.date()
    while current_date <= end_date.date():
        day_str = current_date.isoformat()
        if day_str not in daily_revenue:
            daily_revenue[day_str] = 0
        current_date += timedelta(days=1)

    return jsonify({
        'daily_revenue': [{'date': k, 'revenue': v} for k, v in sorted(daily_revenue.items())],
        'total_revenue': sum(daily_revenue.values()),
        'avg_daily_revenue': sum(daily_revenue.values()) / len(daily_revenue) if daily_revenue else 0
    })

@app.route('/api/analytics/customer-insights', methods=['GET'])
def customer_insights():
    """Get customer behavior insights"""
    customers = Customer.query.all()

    # Customer segments
    segments = {
        'new': len([c for c in customers if c.total_orders and c.total_orders <= 1]),
        'regular': len([c for c in customers if c.total_orders and 2 <= c.total_orders <= 10]),
        'loyal': len([c for c in customers if c.total_orders and c.total_orders > 10])
    }

    # Loyalty tier distribution
    tiers = {}
    for customer in customers:
        tier = get_customer_loyalty_tier(customer.loyalty_points)
        tiers[tier] = tiers.get(tier, 0) + 1

    # Top customers by spending
    top_customers = sorted(
        [c for c in customers if c.total_spent and c.total_spent > 0],
        key=lambda x: x.total_spent,
        reverse=True
    )[:10]

    return jsonify({
        'segments': segments,
        'tiers': tiers,
        'top_customers': [{
            'id': c.id,
            'name': f"{c.first_name} {c.last_name}",
            'total_spent': c.total_spent,
            'total_orders': c.total_orders,
            'loyalty_points': c.loyalty_points
        } for c in top_customers]
    })

@app.route('/api/analytics/operational-efficiency', methods=['GET'])
def operational_efficiency():
    """Get operational efficiency metrics"""
    # Order processing times (placeholder - would need actual timestamps)
    orders = Order.query.filter(Order.status == 'completed').all()

    # Table utilization
    tables = Table.query.all()
    occupied_tables = len([t for t in tables if t.status == 'occupied'])
    utilization_rate = (occupied_tables / len(tables)) * 100 if tables else 0

    # Staff performance (placeholder)
    staff = User.query.filter(User.role != 'customer').all()

    # Inventory turnover (placeholder calculation)
    ingredients = Ingredient.query.all()
    avg_inventory_value = sum((i.current_stock or 0) * (i.cost_per_unit or 0) for i in ingredients) / len(ingredients) if ingredients else 0

    return jsonify({
        'table_utilization': utilization_rate,
        'total_tables': len(tables),
        'occupied_tables': occupied_tables,
        'avg_inventory_value': avg_inventory_value,
        'total_ingredients': len(ingredients),
        'staff_count': len(staff),
        'completed_orders': len(orders)
    })

@app.route('/api/analytics/profitability', methods=['GET'])
def profitability_analysis():
    """Get profitability analysis"""
    # Revenue
    orders = Order.query.filter(Order.status == 'completed').all()
    total_revenue = sum(order.final_amount or 0 for order in orders)

    # Cost of goods sold (COGS) - estimated from inventory costs
    inventory_transactions = InventoryTransaction.query.filter_by(transaction_type='usage').all()
    cogs = sum(t.quantity * t.ingredient.cost_per_unit for t in inventory_transactions if t.ingredient and t.ingredient.cost_per_unit)

    # Operating expenses (placeholder - would need actual expense tracking)
    estimated_expenses = total_revenue * 0.3  # Assume 30% operating expenses

    # Profit calculations
    gross_profit = total_revenue - cogs
    net_profit = gross_profit - estimated_expenses
    profit_margin = (net_profit / total_revenue) * 100 if total_revenue > 0 else 0

    return jsonify({
        'revenue': total_revenue,
        'cogs': cogs,
        'gross_profit': gross_profit,
        'operating_expenses': estimated_expenses,
        'net_profit': net_profit,
        'profit_margin': profit_margin,
        'profitability_score': 'Excellent' if profit_margin > 20 else 'Good' if profit_margin > 10 else 'Needs Improvement'
    })

# Apply loyalty points to an order (discount and deduct points)
@app.route('/api/orders/<int:order_id>/apply-loyalty', methods=['POST'])
def apply_loyalty(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status in ['completed', 'cancelled']:
        return jsonify({'message': 'Cannot apply loyalty to a completed or cancelled order'}), 400
    if not order.customer_id:
        return jsonify({'message': 'Order has no customer to apply loyalty'}), 400
    data = request.get_json()
    points_to_redeem = int(data.get('points', 0))
    if points_to_redeem <= 0:
        return jsonify({'message': 'Points must be positive'}), 400
    customer = Customer.query.get_or_404(order.customer_id)
    if (customer.loyalty_points or 0) < points_to_redeem:
        return jsonify({'message': 'Insufficient points'}), 400
    # Compute discount value
    discount_value = points_to_redeem * LOYALTY_REDEMPTION_VALUE_PER_POINT
    # Update order totals
    order.discount_amount = (order.discount_amount or 0) + discount_value
    base_total = (order.total_amount or 0) + (order.tax_amount or 0)
    order.final_amount = max(0.0, base_total - (order.discount_amount or 0))
    # Deduct points
    customer.loyalty_points = (customer.loyalty_points or 0) - points_to_redeem
    db.session.commit()
    return jsonify({'message': 'Loyalty applied', 'final_amount': order.final_amount, 'discount_amount': order.discount_amount, 'remaining_points': customer.loyalty_points})

# Public online ordering minimal endpoints
@app.route('/api/public/menu', methods=['GET'])
def public_menu():
    items = MenuItem.query.filter_by(is_available=True).all()

    # Check inventory availability for each item based on recipe requirements
    menu_data = []
    for item in items:
        # Get all recipes for this menu item
        recipes = Recipe.query.filter_by(menu_item_id=item.id).all()

        # Check if we have enough inventory for all recipe ingredients
        can_make = True
        if recipes:  # Only check if item has recipes defined
            for recipe in recipes:
                ingredient = Ingredient.query.get(recipe.ingredient_id)
                if ingredient:
                    required_quantity = recipe.quantity_required
                    available_quantity = ingredient.current_stock or 0
                    if available_quantity < required_quantity:
                        can_make = False
                        break

        # Item is available if it's marked as available AND we have enough inventory
        effective_availability = item.is_available and can_make

        menu_data.append({
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'price': item.price,
            'category': item.category,
            'preparation_time': item.preparation_time,
            'image_url': item.image_url,
            'is_available': effective_availability,  # Modified to consider inventory
            'inventory_available': can_make  # Additional field to distinguish inventory vs manual availability
        })

    return jsonify(menu_data)

@app.route('/api/public/orders', methods=['POST'])
def public_create_order():
    data = request.get_json()
    order = Order(
        order_type=data.get('order_type', 'delivery'),
        notes=data.get('notes'),
        status='pending'
    )
    db.session.add(order)
    db.session.flush()
    total = 0
    for item in data.get('items', []):
        menu_item = MenuItem.query.get_or_404(item['menu_item_id'])
        qty = int(item.get('quantity', 1))
        db.session.add(OrderItem(order_id=order.id, menu_item_id=menu_item.id, quantity=qty, price=menu_item.price))
        total += (menu_item.price or 0) * qty
    order.total_amount = total
    order.tax_amount = total * 0.1
    order.final_amount = order.total_amount + order.tax_amount
    db.session.commit()
    return jsonify({'message': 'Order created', 'order_id': order.id, 'final_amount': order.final_amount}), 201

@app.route('/api/public/pay', methods=['POST'])
def public_pay():
    data = request.get_json()
    order = Order.query.get_or_404(data['order_id'])
    amount = float(data.get('amount', order.final_amount or 0))
    method = data.get('method', 'online')
    payment = Payment(order_id=order.id, amount=amount, payment_method=method, payment_status='completed', transaction_id='MOCK-' + datetime.utcnow().strftime('%Y%m%d%H%M%S'))
    db.session.add(payment)
    db.session.commit()
    return jsonify({'message': 'Payment successful'})

# KDS realtime updates via SSE
_kds_changes = []

def _push_kds_change(event_type, payload):
    _kds_changes.append({'event': event_type, 'payload': payload, 'time': datetime.utcnow().isoformat()})

@app.route('/api/kitchen/stream')
def kds_stream():
    def event_stream():
        last_index = 0
        while True:
            if last_index < len(_kds_changes):
                for i in range(last_index, len(_kds_changes)):
                    evt = _kds_changes[i]
                    yield f"event: {evt['event']}\n"
                    yield f"data: {json.dumps(evt)}\n\n"
                last_index = len(_kds_changes)
            else:
                yield f"event: heartbeat\n"
                yield f"data: {json.dumps({'time': datetime.utcnow().isoformat()})}\n\n"
            time.sleep(3)
    return Response(event_stream(), mimetype='text/event-stream')

# AI Routes
@app.route('/api/ai/inventory-insights', methods=['GET'])
def get_inventory_insights():
    try:
        from ai_service import restaurant_ai
        # Get language from query parameter or default to 'en'
        language = request.args.get('lang', 'en')
        insights = restaurant_ai.get_inventory_insights(language)
        return jsonify({'insights': insights})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/menu-suggestions', methods=['GET'])
def get_menu_suggestions():
    try:
        from ai_service import restaurant_ai
        # Get language from query parameter or default to 'en'
        language = request.args.get('lang', 'en')
        suggestions = restaurant_ai.suggest_menu_items(language=language)
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/demand-prediction', methods=['GET'])
def get_demand_prediction():
    try:
        from ai_service import restaurant_ai
        days_ahead = int(request.args.get('days', 7))
        # Get language from query parameter or default to 'en'
        language = request.args.get('lang', 'en')
        prediction = restaurant_ai.predict_demand(days_ahead, language)
        return jsonify({'prediction': prediction})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/optimize-inventory', methods=['GET'])
def get_inventory_optimization():
    try:
        from ai_service import restaurant_ai
        # Get language from query parameter or default to 'en'
        language = request.args.get('lang', 'en')
        optimization = restaurant_ai.optimize_inventory(language)
        return jsonify({'optimization': optimization})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ai')
def ai_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('ai.html')

@app.route('/api/ai/context-chat', methods=['POST'])
def context_chat():
    try:
        from ai_service import restaurant_ai
        data = request.get_json()
        message = data.get('message', '')
        context = data.get('context', {})

        # Get user's language preference
        user_language = context.get('language', 'en')

        # Language-specific instructions
        language_instructions = {
            'en': "Please respond in English.",
            'ar': "يرجى الرد باللغة العربية.",
            'tr': "Lütfen Türkçe yanıtlayın."
        }

        # Create a context-aware prompt
        context_prompt = f"""
        You are an AI assistant for a restaurant management system. The user is currently on: {context.get('title', 'Unknown Page')}

        Current page context:
        - URL: {context.get('url', '')}
        - Page Content: {context.get('content', '')[:1000]}...
        - User Language: {user_language}

        User question: {message}

        {language_instructions.get(user_language, "Please respond in English.")}

        Please provide a helpful, contextual response based on the current page and restaurant data.
        If the question is about specific data on the page, analyze the content provided.
        Keep responses concise but informative.
        """

        # Use the existing AI service but with context
        completion = restaurant_ai.client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "Restaurant Management System",
            },
            model=restaurant_ai.model,
            messages=[{"role": "user", "content": context_prompt}],
            max_tokens=300,
            temperature=0.7
        )
        ai_response = completion.choices[0].message.content

        return jsonify({'response': ai_response})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Settings Management
@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.get_json()

        # Save each setting
        for key, value in data.items():
            # Convert value to string for storage
            value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)

            # Check if setting exists
            setting = Settings.query.filter_by(key=key).first()
            if setting:
                setting.value = value_str
            else:
                setting = Settings(key=key, value=value_str)
                db.session.add(setting)

        db.session.commit()
        return jsonify({'message': 'Settings saved successfully'}), 200

    elif request.method == 'GET':
        settings = Settings.query.all()
        result = {}

        for setting in settings:
            try:
                # Try to parse as JSON first
                result[setting.key] = json.loads(setting.value)
            except (json.JSONDecodeError, TypeError):
                # If not JSON, return as string
                result[setting.key] = setting.value

        return jsonify(result)

@app.route('/api/settings/<key>', methods=['GET', 'PUT', 'DELETE'])
def handle_setting(key):
    if request.method == 'GET':
        setting = Settings.query.filter_by(key=key).first()
        if not setting:
            return jsonify({'message': 'Setting not found'}), 404

        try:
            value = json.loads(setting.value)
        except (json.JSONDecodeError, TypeError):
            value = setting.value

        return jsonify({'key': key, 'value': value})

    elif request.method == 'PUT':
        data = request.get_json()
        value = data.get('value')

        if value is None:
            return jsonify({'message': 'Value is required'}), 400

        # Convert value to string for storage
        value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)

        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = value_str
        else:
            setting = Settings(key=key, value=value_str)
            db.session.add(setting)

        db.session.commit()
        return jsonify({'message': 'Setting updated successfully'}), 200

    elif request.method == 'DELETE':
        setting = Settings.query.filter_by(key=key).first()
        if not setting:
            return jsonify({'message': 'Setting not found'}), 404

        db.session.delete(setting)
        db.session.commit()
        return jsonify({'message': 'Setting deleted successfully'}), 200

# Database initialization function
def initialize_database():
    """Check if database exists and create it if necessary"""
    import os

    db_path = 'restaurant.db'  # Relative to instance directory
    full_db_path = os.path.join(app.instance_path, db_path)

    # Check if database file exists
    db_exists = os.path.exists(full_db_path)

    if not db_exists:
        print(f"Database not found at {full_db_path}. Creating new database...")
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")

        # Create default admin user
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                first_name='Admin',
                last_name='User',
                email='admin@restaurant.com',
                role='admin',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created!")
            print("Admin login: username='admin', password='admin123'")
    else:
        print(f"Database found at {full_db_path}. Initializing existing database...")
        # Ensure all tables exist (for schema updates)
        db.create_all()
        print("Database initialized successfully!")

# Initialize Database
with app.app_context():
    initialize_database()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
