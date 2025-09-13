#!/usr/bin/env python3
"""
Migration script to convert string categories to Category model.
This script should be run once after deploying the new Category model.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize Flask app with same config as main app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

db = SQLAlchemy(app)

# Define models (same as in app.py)
class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    category = db.relationship('Category', backref=db.backref('menu_items', lazy=True))
    is_available = db.Column(db.Boolean, default=True)
    preparation_time = db.Column(db.Integer)  # in minutes
    image_url = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def migrate_categories():
    """Migrate existing string categories to Category model"""
    with app.app_context():
        print("Starting category migration...")

        # Get all unique categories from existing menu items
        # Note: This assumes the old category field still exists as a string
        # We'll need to temporarily add it back if it was removed

        # For now, let's create default categories that match the hardcoded ones
        default_categories = [
            {'name': 'appetizer', 'description': 'Appetizers and starters', 'display_order': 1},
            {'name': 'main', 'description': 'Main courses', 'display_order': 2},
            {'name': 'dessert', 'description': 'Desserts and sweets', 'display_order': 3},
            {'name': 'drink', 'description': 'Beverages and drinks', 'display_order': 4},
            {'name': 'side', 'description': 'Side dishes', 'display_order': 5},
        ]

        created_count = 0
        for cat_data in default_categories:
            # Check if category already exists
            existing = Category.query.filter_by(name=cat_data['name']).first()
            if not existing:
                category = Category(
                    name=cat_data['name'],
                    description=cat_data['description'],
                    display_order=cat_data['display_order'],
                    is_active=True
                )
                db.session.add(category)
                created_count += 1
                print(f"Created category: {cat_data['name']}")

        db.session.commit()
        print(f"Created {created_count} categories")

        # Now update all menu items to use category_id instead of string category
        # This assumes we temporarily have both fields during migration
        menu_items = MenuItem.query.all()
        updated_count = 0

        for item in menu_items:
            # If item doesn't have category_id set but has a category string
            if not item.category_id:
                # Find the category by name
                category = Category.query.filter_by(name=item.category).first()
                if category:
                    item.category_id = category.id
                    updated_count += 1
                    print(f"Updated menu item '{item.name}' to use category_id {category.id}")
                else:
                    # If no matching category found, assign to first available category
                    default_cat = Category.query.first()
                    if default_cat:
                        item.category_id = default_cat.id
                        updated_count += 1
                        print(f"Assigned menu item '{item.name}' to default category {default_cat.name}")

        db.session.commit()
        print(f"Updated {updated_count} menu items")

        print("Category migration completed successfully!")

if __name__ == '__main__':
    migrate_categories()
