import os
import sys

def setup_ai():
    print("🤖 Restaurant AI Setup with OpenRouter + DeepSeek")
    print("=" * 60)

    # Check if OpenRouter API key is already set
    api_key = os.getenv('OPENROUTER_API_KEY')
    if api_key:
        print("✅ OpenRouter API key is already configured!")
        print(f"   Key starts with: {api_key[:10]}...")
        return

    print("\n📝 To use AI features, you need an OpenRouter API key:")
    print("   1. Go to https://openrouter.ai/keys")
    print("   2. Sign in or create an account")
    print("   3. Click 'Create Key'")
    print("   4. Copy the API key")

    print("\n🎯 Using FREE DeepSeek V3.1 model via OpenRouter!")
    print("   • No costs for basic usage")
    print("   • High-quality AI responses")
    print("   • Perfect for restaurant management")

    api_key = input("\n🔑 Enter your OpenRouter API key: ").strip()

    if not api_key:
        print("❌ No API key provided. AI features will not work without it.")
        return

    # Save to environment variable (this is temporary for this session)
    os.environ['OPENROUTER_API_KEY'] = api_key

    print("✅ OpenRouter API key configured successfully!")
    print("✅ Using DeepSeek V3.1 model (FREE!)")

    print("\n🚀 Your AI features are now ready:")
    print("   • 📊 Inventory Insights")
    print("   • 🍽️ Menu Suggestions")
    print("   • 🔮 Demand Prediction")
    print("   • ⚡ Inventory Optimization")
    print("   • 💬 AI Chat Assistant")

    print("\n💡 Tip: For permanent setup, add this to your system environment variables:")
    print(f"   OPENROUTER_API_KEY={api_key}")

    print("\n🎯 Next steps:")
    print("   1. Start your Flask server: python run.py")
    print("   2. Go to your dashboard and click '🤖 AI Assistant'")
    print("   3. Try the different AI features!")
    print("   4. Enjoy FREE AI-powered restaurant management! 🎉")

if __name__ == "__main__":
    setup_ai()
