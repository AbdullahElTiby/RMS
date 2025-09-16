from app import app, db, User
from werkzeug.security import generate_password_hash
import os

def init_database():
    with app.app_context():
        db_path = 'restaurant.db'  # Relative to instance directory
        full_db_path = os.path.join(app.instance_path, db_path)

        # Check if database file exists
        db_exists = os.path.exists(full_db_path)

        if not db_exists:
            print(f"Database not found at {full_db_path}. Creating new database...")
            # Create all tables
            db.create_all()
            print("Database tables created successfully!")

            # Create the admin user
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

if __name__ == '__main__':
    init_database()
