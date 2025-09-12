from app import app, db, User
from werkzeug.security import generate_password_hash

def init_database():
    with app.app_context():
        # Drop and create all tables
        db.drop_all()
        db.create_all()
        
        # Create only the admin user (no sample data)
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
        
        print("Database initialized successfully!")
        print("Admin login: username='admin', password='admin123'")
        print("No sample data added - ready for your custom data!")

if __name__ == '__main__':
    init_database()
