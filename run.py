#!/usr/bin/env python3
"""
Run script for the Restaurant Management System.
This script initializes the database and starts the Flask application.
"""

import os
import sys
from app import app, db

def main():
    print("Starting Restaurant Management System...")
    print("Initializing database...")
    
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
    
    print("Database initialized successfully!")
    print("Starting Flask server...")
    print("Web interface: http://localhost:5000")
    print("API base URL: http://localhost:5000/api")
    print("Press Ctrl+C to stop the server")
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)
