from app import db, Ingredient, app

with app.app_context():
    ingredients = Ingredient.query.all()
    print("Current Ingredients:")
    for i in ingredients:
        print(f"ID: {i.id}, Name: {i.name}, Cost per Unit: {i.cost_per_unit}")

    if not ingredients:
        print("No ingredients found. Let's add some sample data.")

        # Add sample ingredients with costs
        sample_ingredients = [
            Ingredient(name="Flour", unit="kg", min_stock=10.0, cost_per_unit=2.50),
            Ingredient(name="Sugar", unit="kg", min_stock=5.0, cost_per_unit=1.80),
            Ingredient(name="Milk", unit="L", min_stock=20.0, cost_per_unit=1.20),
            Ingredient(name="Eggs", unit="pieces", min_stock=50, cost_per_unit=0.25),
            Ingredient(name="Butter", unit="kg", min_stock=3.0, cost_per_unit=4.50),
        ]

        for ingredient in sample_ingredients:
            db.session.add(ingredient)

        db.session.commit()
        print("Added sample ingredients with costs!")
