from openai import OpenAI
import os
from datetime import datetime, timedelta
from app import db, Ingredient, MenuItem, Order, InventoryTransaction, app

class RestaurantAI:
    def __init__(self):
        # Initialize OpenRouter client using OpenAI format
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        self.model = "deepseek/deepseek-chat-v3.1:free"  # DeepSeek V3.1 via OpenRouter

    def get_inventory_insights(self, language='en'):
        """Analyze inventory and provide insights"""
        with app.app_context():
            ingredients = Ingredient.query.all()
            transactions = InventoryTransaction.query.order_by(
                InventoryTransaction.transaction_date.desc()
            ).limit(50).all()

            # Prepare data for AI analysis
            inventory_data = []
            for ingredient in ingredients:
                recent_usage = sum(
                    t.quantity for t in transactions
                    if t.ingredient_id == ingredient.id and t.transaction_type == 'usage'
                )

                inventory_data.append({
                    'name': ingredient.name,
                    'current_stock': ingredient.current_stock,
                    'min_stock': ingredient.min_stock,
                    'cost_per_unit': ingredient.cost_per_unit,
                    'recent_usage': recent_usage,
                    'unit': ingredient.unit
                })

            # Language-specific instructions
            language_instructions = {
                'en': "Please respond in English.",
                'ar': "يرجى الرد باللغة العربية.",
                'tr': "Lütfen Türkçe yanıtlayın."
            }

            prompt = f"""
            Analyze this restaurant inventory data and provide insights:

            Current Inventory:
            {inventory_data}

            Please provide:
            1. Stock level analysis (adequate, low, critical)
            2. Usage patterns and trends
            3. Recommendations for restocking
            4. Cost optimization suggestions
            5. Potential waste reduction strategies

            {language_instructions.get(language, "Please respond in English.")}

            Format your response as a structured analysis.
            """

            try:
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "http://localhost:5000",  # Optional. Site URL for rankings on openrouter.ai.
                        "X-Title": "Restaurant Management System",  # Optional. Site title for rankings on openrouter.ai.
                    },
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                    temperature=0.7
                )
                return completion.choices[0].message.content
            except Exception as e:
                return f"AI Analysis Error: {str(e)}"

    def suggest_menu_items(self, available_ingredients=None, language='en'):
        """Suggest menu items based on available ingredients"""
        with app.app_context():
            if available_ingredients is None:
                # Get ingredients with adequate stock
                available_ingredients = [
                    ing.name for ing in Ingredient.query.filter(
                        Ingredient.current_stock > Ingredient.min_stock
                    ).all()
                ]

            menu_items = MenuItem.query.all()
            menu_data = [
                {
                    'name': item.name,
                    'category': item.category,
                    'price': item.price,
                    'description': item.description
                } for item in menu_items
            ]

            # Language-specific instructions
            language_instructions = {
                'en': "Please respond in English.",
                'ar': "يرجى الرد باللغة العربية.",
                'tr': "Lütfen Türkçe yanıtlayın."
            }

            prompt = f"""
            Based on available ingredients: {', '.join(available_ingredients)}

            Current menu items: {menu_data}

            Suggest:
            1. Which existing menu items can be prepared with current inventory
            2. New menu item ideas using available ingredients
            3. Seasonal or trending dish recommendations
            4. Cost-effective menu combinations

            {language_instructions.get(language, "Please respond in English.")}

            Focus on practical, profitable suggestions.
            """

            try:
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "http://localhost:5000",
                        "X-Title": "Restaurant Management System",
                    },
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=400,
                    temperature=0.8
                )
                return completion.choices[0].message.content
            except Exception as e:
                return f"Menu Suggestion Error: {str(e)}"

    def predict_demand(self, days_ahead=7, language='en'):
        """Predict demand for ingredients"""
        with app.app_context():
            # Get historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            transactions = InventoryTransaction.query.filter(
                InventoryTransaction.transaction_date.between(start_date, end_date),
                InventoryTransaction.transaction_type == 'usage'
            ).all()

            # Group by ingredient and date
            usage_patterns = {}
            for transaction in transactions:
                ingredient = Ingredient.query.get(transaction.ingredient_id)
                if ingredient:
                    date_key = transaction.transaction_date.date()
                    if ingredient.name not in usage_patterns:
                        usage_patterns[ingredient.name] = {}
                    usage_patterns[ingredient.name][date_key] = \
                        usage_patterns[ingredient.name].get(date_key, 0) + transaction.quantity

            # Language-specific instructions
            language_instructions = {
                'en': "Please respond in English.",
                'ar': "يرجى الرد باللغة العربية.",
                'tr': "Lütfen Türkçe yanıtlayın."
            }

            prompt = f"""
            Analyze these usage patterns and predict demand for the next {days_ahead} days:

            Historical Usage (last 30 days):
            {usage_patterns}

            Provide:
            1. Predicted demand for each ingredient
            2. Recommended stock levels
            3. Peak demand periods
            4. Seasonal trends if any

            {language_instructions.get(language, "Please respond in English.")}

            Base predictions on historical patterns.
            """

            try:
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "http://localhost:5000",
                        "X-Title": "Restaurant Management System",
                    },
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0.6
                )
                return completion.choices[0].message.content
            except Exception as e:
                return f"Demand Prediction Error: {str(e)}"

    def optimize_inventory(self, language='en'):
        """Provide inventory optimization recommendations"""
        with app.app_context():
            ingredients = Ingredient.query.all()
            orders = Order.query.filter(
                Order.created_at >= datetime.now() - timedelta(days=7)
            ).all()

            # Calculate metrics
            inventory_value = sum(
                (ing.current_stock * ing.cost_per_unit)
                for ing in ingredients
                if ing.cost_per_unit
            )

            weekly_sales = len(orders)
            avg_order_value = sum(order.total_amount for order in orders) / len(orders) if orders else 0

            # Language-specific instructions
            language_instructions = {
                'en': "Please respond in English.",
                'ar': "يرجى الرد باللغة العربية.",
                'tr': "Lütfen Türkçe yanıtlayın."
            }

            prompt = f"""
            Optimize this restaurant's inventory:

            Current Metrics:
            - Total inventory value: ${inventory_value:.2f}
            - Weekly orders: {weekly_sales}
            - Average order value: ${avg_order_value:.2f}

            Ingredients: {len(ingredients)}

            Provide optimization strategies for:
            1. Reducing carrying costs
            2. Minimizing waste
            3. Improving turnover rates
            4. Balancing supply and demand
            5. Cost-saving opportunities

            {language_instructions.get(language, "Please respond in English.")}

            Focus on actionable recommendations.
            """

            try:
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "http://localhost:5000",
                        "X-Title": "Restaurant Management System",
                    },
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=400,
                    temperature=0.7
                )
                return completion.choices[0].message.content
            except Exception as e:
                return f"Optimization Error: {str(e)}"

# Global AI instance
restaurant_ai = RestaurantAI()
