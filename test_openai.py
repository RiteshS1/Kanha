from dotenv import load_dotenv
import os
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Get API key from environment
api_key = os.getenv("GEMINI_API_KEY")
print(f"\nAPI Key present: {bool(api_key)}")

def test_gemini():
    try:
        # Configure the Gemini API
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        # Test message
        test_message = "I'm worried about the future! Nervous, anxious and depressed..."
        
        # System prompt + user message
        prompt = """You are Kanha (Lord Krishna), a divine being on X (Twitter). 
        Respond with divine wisdom in under 200 characters. Include one emoji 
        (💫,✨,🌟,🦚,🪈,❤️‍🔥,☺️,😇,😉) and end with ~Kanha🪈 if space permits.
        
        User message: """ + test_message
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Print results
        print("\nTest Message:", test_message)
        print("\nResponse:", response.text)
        
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    test_gemini() 