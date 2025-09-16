import requests
import json

BASE_URL = "http://localhost:5000/api"

def test_api():
    print("Testing Restaurant Management System API...")
    
    # Test login
    print("\n1. Testing login...")
    try:
        response = requests.post(f"{BASE_URL}/login", json={
            "username": "admin",
            "password": "admin123"
        })
        print(f"Login Status: {response.status_code}")
        if response.status_code == 200:
            print("✓ Login successful")
        else:
            print("✗ Login failed")
    except Exception as e:
        print(f"Login error: {e}")
    
    # Test menu endpoint
    print("\n2. Testing menu endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/menu")
        print(f"Menu Status: {response.status_code}")
        if response.status_code == 200:
            menu_items = response.json()
            print(f"✓ Found {len(menu_items)} menu items")
        else:
            print("✗ Menu endpoint failed")
    except Exception as e:
        print(f"Menu error: {e}")
    
    # Test inventory endpoint
    print("\n3. Testing inventory endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/inventory")
        print(f"Inventory Status: {response.status_code}")
        if response.status_code == 200:
            inventory = response.json()
            print(f"✓ Found {len(inventory)} inventory items")
        else:
            print("✗ Inventory endpoint failed")
    except Exception as e:
        print(f"Inventory error: {e}")
    
    # Test low stock endpoint
    print("\n4. Testing low stock endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/inventory/low-stock")
        print(f"Low Stock Status: {response.status_code}")
        if response.status_code == 200:
            low_stock = response.json()
            print(f"✓ Found {len(low_stock)} low stock items")
        else:
            print("✗ Low stock endpoint failed")
    except Exception as e:
        print(f"Low stock error: {e}")
    
    # Test creating an order
    print("\n5. Testing order creation...")
    try:
        response = requests.post(f"{BASE_URL}/orders", json={
            "order_type": "dine-in",
            "table_id": 1,
            "items": [
                {"menu_item_id": 1, "quantity": 2},
                {"menu_item_id": 2, "quantity": 1}
            ]
        })
        print(f"Order Status: {response.status_code}")
        if response.status_code == 201:
            order_data = response.json()
            print(f"✓ Order created successfully (ID: {order_data['order_id']})")
        else:
            print("✗ Order creation failed")
    except Exception as e:
        print(f"Order error: {e}")
    
    # Test sales report
    print("\n6. Testing sales report...")
    try:
        response = requests.get(f"{BASE_URL}/reports/sales")
        print(f"Sales Report Status: {response.status_code}")
        if response.status_code == 200:
            sales_data = response.json()
            print(f"✓ Sales report generated")
            print(f"   Total Sales: ${sales_data.get('total_sales', 0)}")
            print(f"   Total Orders: {sales_data.get('total_orders', 0)}")
        else:
            print("✗ Sales report failed")
    except Exception as e:
        print(f"Sales report error: {e}")
    
    print("\nAPI testing completed!")

if __name__ == "__main__":
    test_api()
