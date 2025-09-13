#!/usr/bin/env python3
"""
Database Migration Script for Restaurant Management System
This script handles database schema updates and data migrations.
"""

import sqlite3
import json
from datetime import datetime

def migrate_roles_table():
    """Add roles table to existing database"""
    try:
        # Connect to database
        conn = sqlite3.connect('instance/restaurant.db')
        cursor = conn.cursor()

        # Check if roles table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='roles'")
        if cursor.fetchone():
            print("Roles table already exists. Skipping migration.")
            conn.close()
            return

        # Create roles table
        cursor.execute('''
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(50) UNIQUE NOT NULL,
                description TEXT,
                permissions TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create some default roles
        default_roles = [
            {
                'name': 'supervisor',
                'description': 'Supervises daily operations and manages staff',
                'permissions': json.dumps([
                    'view_menu', 'edit_menu', 'manage_categories',
                    'take_orders', 'view_orders', 'manage_orders',
                    'view_inventory', 'manage_inventory',
                    'view_staff', 'manage_staff',
                    'view_reports', 'export_reports'
                ])
            },
            {
                'name': 'bartender',
                'description': 'Handles bar operations and beverage orders',
                'permissions': json.dumps([
                    'view_menu', 'take_orders', 'view_orders',
                    'view_inventory', 'manage_inventory'
                ])
            },
            {
                'name': 'host',
                'description': 'Manages reservations and customer seating',
                'permissions': json.dumps([
                    'manage_reservations', 'view_table_status'
                ])
            },
            {
                'name': 'delivery_driver',
                'description': 'Handles delivery orders and customer deliveries',
                'permissions': json.dumps([
                    'manage_deliveries', 'view_delivery_orders'
                ])
            },
            {
                'name': 'cleaner',
                'description': 'Handles cleaning schedules and maintenance',
                'permissions': json.dumps([
                    'view_cleaning_schedule'
                ])
            }
        ]

        # Insert default roles
        for role in default_roles:
            cursor.execute('''
                INSERT INTO roles (name, description, permissions, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                role['name'],
                role['description'],
                role['permissions'],
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ))

        conn.commit()
        print("Roles table created successfully with default roles!")
        print("Default roles added:")
        for role in default_roles:
            print(f"  - {role['name']}: {role['description']}")

    except Exception as e:
        print(f"Error during migration: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def migrate_settings_table():
    """Ensure settings table exists and has proper structure"""
    try:
        conn = sqlite3.connect('instance/restaurant.db')
        cursor = conn.cursor()

        # Check if settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if not cursor.fetchone():
            # Create settings table
            cursor.execute('''
                CREATE TABLE settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key VARCHAR(100) UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("Settings table created successfully!")
        else:
            print("Settings table already exists.")

        conn.commit()

    except Exception as e:
        print(f"Error during settings migration: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def run_migrations():
    """Run all database migrations"""
    print("Starting database migrations...")

    # Ensure instance directory exists
    import os
    os.makedirs('instance', exist_ok=True)

    # Run migrations
    migrate_settings_table()
    migrate_roles_table()

    print("All migrations completed successfully!")

if __name__ == '__main__':
    run_migrations()
