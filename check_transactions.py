from app import db, InventoryTransaction, app

def check_transactions():
    with app.app_context():
        print("Recent Inventory Transactions:")
        transactions = InventoryTransaction.query.order_by(InventoryTransaction.transaction_date.desc()).limit(10).all()

        if not transactions:
            print("No transactions found. Let's create some sample transactions to demonstrate cost tracking.")

            # Import Ingredient to get sample data
            from app import Ingredient
            ingredients = Ingredient.query.all()

            if ingredients:
                # Create sample transactions
                sample_transactions = []
                for ingredient in ingredients[:3]:  # Use first 3 ingredients
                    if ingredient.cost_per_unit:
                        transaction = InventoryTransaction(
                            ingredient_id=ingredient.id,
                            transaction_type='usage',
                            quantity=0.5,  # Sample quantity
                            notes=f'Sample usage for {ingredient.name}',
                            related_order_id=1
                        )
                        sample_transactions.append(transaction)

                for transaction in sample_transactions:
                    db.session.add(transaction)

                db.session.commit()
                print("✓ Created sample transactions!")

                # Re-fetch transactions
                transactions = InventoryTransaction.query.order_by(InventoryTransaction.transaction_date.desc()).limit(10).all()

        for transaction in transactions:
            from app import Ingredient
            ingredient = Ingredient.query.get(transaction.ingredient_id)
            cost_per_unit = ingredient.cost_per_unit if ingredient else 0
            total_cost = transaction.quantity * cost_per_unit if cost_per_unit else 0

            print(f"• {ingredient.name if ingredient else 'Unknown'} - {transaction.transaction_type}")
            print(f"  Quantity: {transaction.quantity} {ingredient.unit if ingredient else ''}")
            print(f"  Cost per unit: ${cost_per_unit}")
            print(f"  Total cost: ${total_cost:.2f}")
            print(f"  Date: {transaction.transaction_date}")
            print(f"  Notes: {transaction.notes}")
            print()

if __name__ == "__main__":
    check_transactions()
