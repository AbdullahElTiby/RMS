# Restaurant Management System

A comprehensive, full-featured restaurant management system built with Flask and SQLAlchemy. This system provides complete restaurant operations management including inventory tracking, order processing, staff scheduling, customer loyalty programs, and advanced analytics.

## Features

### Core Functionality
- **User Management**: Role-based access control with multiple user types (Admin, Manager, Chef, Waiter, Cashier, etc.)
- **Menu Management**: Create and manage menu items with categories, pricing, and preparation times
- **Inventory Management**: Track ingredients, suppliers, stock levels, and automatic low-stock alerts
- **Order Processing**: Handle dine-in, takeaway, and delivery orders with real-time status updates
- **Kitchen Display System**: Real-time order tracking and status updates for kitchen staff
- **Table Management**: Manage restaurant tables, reservations, and seating arrangements
- **Customer Management**: Customer profiles with loyalty points and purchase history
- **Staff Scheduling**: Create and manage staff shifts and schedules
- **Payment Processing**: Multiple payment methods with receipt generation
- **Reporting & Analytics**: Comprehensive sales reports, popular items, and business insights

### Advanced Features
- **AI-Powered Insights**: Machine learning predictions for demand forecasting and inventory optimization
- **Loyalty Program**: Automated customer loyalty points with tiered rewards
- **Real-time Notifications**: Low stock alerts and operational notifications
- **Multi-language Support**: English, Arabic, and Turkish language options
- **Public Online Ordering**: Customer-facing menu and ordering system
- **Advanced Analytics**: Revenue trends, customer insights, and operational efficiency metrics
- **CRM Integration**: Customer notes and relationship management
- **Supplier Management**: Track suppliers and manage procurement

## Installation

### Prerequisites
- Python 3.8 or higher
- SQLite (included with Python) or PostgreSQL/MySQL for production

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/AbdullahElTiby/RMS.git
   cd RMS
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   FLASK_APP=app.py
   FLASK_ENV=development
   SECRET_KEY=your-secret-key-here
   ```

5. **Initialize the database**
   ```bash
   python init_db.py
   ```

6. **Run the application**
   ```bash
   python run.py
   ```

The application will be available at `http://localhost:5000`

### Default Admin Credentials
- Username: `admin`
- Password: `admin123`

## Usage

### Web Interface
Access the web interface at `http://localhost:5000` and log in with appropriate credentials.

### API Endpoints
The system provides a comprehensive REST API for all operations:

#### Authentication
- `POST /api/login` - User authentication
- `POST /api/logout` - User logout

#### Menu Management
- `GET /api/menu` - Get all menu items
- `POST /api/menu` - Create new menu item
- `PUT /api/menu/<id>` - Update menu item
- `DELETE /api/menu/<id>` - Delete menu item

#### Order Management
- `GET /api/orders` - Get all orders
- `POST /api/orders` - Create new order
- `GET /api/orders/<id>` - Get order details
- `PATCH /api/orders/<id>` - Update order status

#### Inventory Management
- `GET /api/inventory` - Get all ingredients
- `POST /api/inventory` - Add new ingredient
- `PUT /api/inventory/<id>` - Update ingredient
- `POST /api/inventory/restock` - Restock inventory

#### Customer Management
- `GET /api/customers` - Get all customers
- `POST /api/customers` - Create new customer
- `GET /api/customers/<id>` - Get customer details

#### Analytics & Reporting
- `GET /api/reports/sales` - Sales reports
- `GET /api/reports/popular-items` - Popular items report
- `GET /api/analytics/overview` - Analytics dashboard

#### AI Features
- `GET /api/ai/inventory-insights` - AI-powered inventory insights
- `GET /api/ai/menu-suggestions` - Menu optimization suggestions
- `GET /api/ai/demand-prediction` - Demand forecasting
- `GET /api/ai/optimize-inventory` - Inventory optimization

### Kitchen Display System
Access the KDS at `/kitchen` for real-time order management.

### Public Menu
Customers can view the menu and place orders at `/our-menu`.

## Project Structure

```
RMS/
├── app.py                 # Main Flask application
├── ai_service.py          # AI/ML service integration
├── check_inventory.py     # Inventory checking utilities
├── check_transactions.py  # Transaction verification
├── config.py             # Configuration settings
├── db_migration.py        # Database migration utilities
├── init_db.py            # Database initialization
├── migrate_categories.py  # Category migration script
├── run.py                # Application runner
├── setup_ai.py           # AI service setup
├── test_api.py           # API testing utilities
├── update_costs.py       # Cost update utilities
├── requirements.txt      # Python dependencies
├── README.md             # Project documentation
├── LICENSE               # License file
├── .gitignore            # Git ignore rules
├── instance/             # Database files
├── uploads/              # File uploads
│   └── images/           # Menu item images
└── templates/            # HTML templates
    ├── base.html         # Base template
    ├── index.html        # Dashboard
    ├── login.html        # Login page
    ├── menu.html         # Menu management
    ├── orders.html       # Order management
    ├── order_details.html # Order details
    ├── inventory.html    # Inventory management
    ├── kitchen.html      # Kitchen display
    ├── cashier.html      # Cashier interface
    ├── customers.html    # Customer management
    ├── staff.html        # Staff management
    ├── staff_schedule.html # Staff scheduling
    ├── tables.html       # Table management
    ├── reservations.html # Reservation system
    ├── reports.html      # Reports and analytics
    ├── settings.html     # System settings
    ├── public_menu.html  # Public menu for customers
    ├── receipt.html      # Receipt template
    ├── ai.html           # AI insights interface
    └── access_denied.html # Access denied page
```

## Configuration

### Environment Variables
- `FLASK_APP`: Main application file (app.py)
- `FLASK_ENV`: Environment (development/production)
- `SECRET_KEY`: Flask secret key for sessions
- `DATABASE_URL`: Database connection string (optional, defaults to SQLite)

### Settings
The application includes a settings management system accessible through the web interface or API at `/api/settings`.

## API Documentation

### Authentication
All API endpoints require authentication except public endpoints. Include session cookies or use API keys for authentication.

### Response Format
All API responses are in JSON format with consistent structure:
```json
{
  "message": "Success message",
  "data": {...},
  "error": "Error message (if applicable)"
}
```

### Error Handling
- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Create a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Write comprehensive tests for new features
- Update documentation for API changes
- Ensure all tests pass before submitting PR

## License

This project is proprietary software. All rights reserved. See LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the documentation for common solutions

## Changelog

### Version 1.0.0
- Initial release with complete restaurant management functionality
- AI-powered insights and analytics
- Multi-language support
- Comprehensive API
- Real-time kitchen display system

## Future Enhancements

- Mobile application development
- Integration with POS systems
- Advanced reporting with data visualization
- Machine learning for demand prediction
- Integration with delivery services
- Multi-location support
