from app import db, Ingredient, app

def update_ingredient_costs():
    with app.app_context():
        print("Current Ingredients and their costs:")
        ingredients = Ingredient.query.all()

        for i, ingredient in enumerate(ingredients, 1):
            cost_display = f"${ingredient.cost_per_unit}" if ingredient.cost_per_unit else "Not set"
            print(f"{i}. {ingredient.name} - Current cost: {cost_display}")

        print("\nEnter the ingredient number and new cost per unit (e.g., '1 8.50' for Flour):")
        print("Type 'done' when finished.")

        while True:
            try:
                user_input = input("> ").strip()

                if user_input.lower() == 'done':
                    break

                parts = user_input.split()
                if len(parts) != 2:
                    print("Please enter: <number> <cost>")
                    continue

                ingredient_num = int(parts[0]) - 1
                new_cost = float(parts[1])

                if 0 <= ingredient_num < len(ingredients):
                    ingredient = ingredients[ingredient_num]
                    old_cost = ingredient.cost_per_unit
                    ingredient.cost_per_unit = new_cost
                    db.session.commit()
                    print(f"✓ Updated {ingredient.name}: ${old_cost} → ${new_cost}")
                else:
                    print("Invalid ingredient number.")

            except ValueError:
                print("Invalid input. Please enter a number and a cost.")
            except Exception as e:
                print(f"Error: {e}")

        print("\nFinal ingredient costs:")
        ingredients = Ingredient.query.all()
        for ingredient in ingredients:
            cost_display = f"${ingredient.cost_per_unit}" if ingredient.cost_per_unit else "Not set"
            print(f"• {ingredient.name}: {cost_display}")

if __name__ == "__main__":
    update_ingredient_costs()
