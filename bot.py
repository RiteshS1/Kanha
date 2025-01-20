import tweepy
from pymongo import MongoClient
from datetime import datetime, timedelta, UTC
import google.generativeai as genai
import schedule
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Load API keys from environment variables
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "YourKey")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "YourKey")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "YourKey")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "YourKey")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "YourKey")

MONGODB_URL = os.getenv("MONGODB_URL", "YourMongoDBURL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YourKey")

class TwitterBot:
    def __init__(self):
        self.twitter_api = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True
        )

        # MongoDB setup
        try:
            self.mongo_client = MongoClient(MONGODB_URL)
            self.db = self.mongo_client["twitter_bot"]
            self.collection = self.db["mentions"]
            self.collection.create_index("conversation_id", unique=True)
            print("✅ MongoDB connection successful")
        except Exception as e:
            print(f"❌ Error connecting to MongoDB: {str(e)}")
            raise Exception("MongoDB connection failed")

        # Initialize Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')
        self.twitter_me_id = self.get_me_id()

    def check_already_responded(self, conversation_id):
        return bool(self.collection.find_one({"conversation_id": str(conversation_id)}))

    def get_mention_conversation_tweet(self, mention):
        if mention.conversation_id:
            return self.twitter_api.get_tweet(
                mention.conversation_id,
                tweet_fields=['author_id', 'created_at', 'text']
            ).data
        return None

    def get_mentions(self):
        start_time = (datetime.now(UTC) - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.twitter_api.get_users_mentions(
            id=self.twitter_me_id,
            start_time=start_time,
            tweet_fields=['created_at', 'conversation_id', 'author_id']
        ).data

    def like_and_retweet_posts(self, username="xavier_1256"):
        try:
            user = self.twitter_api.get_user(username=username)
            if not user.data:
                return
            
            tweets = self.twitter_api.get_users_tweets(
                id=user.data.id,
                max_results=5,
                exclude=['replies']  # Exclude replies, only get original tweets
            ).data

            if not tweets:
                return

            for tweet in tweets:
                try:
                    self.twitter_api.like(tweet_id=tweet.id)
                    self.twitter_api.retweet(tweet_id=tweet.id)
                    print(f"✅ Liked and retweeted tweet: {tweet.text[:50]}...")
                except Exception as e:
                    print(f"❌ Error processing tweet {tweet.id}: {str(e)}")

        except Exception as e:
            print(f"❌ Error in like_and_retweet: {str(e)}")

   def execute_bot_actions(self):
    print(f"\n🤖 Starting Bot Actions: {datetime.now(UTC).isoformat()}")
    
    try:
        # Part 1: Handle mentions in batches
        mentions = self.get_mentions()
        if mentions:
            batch_size = 5  # Number of mentions to process in one batch
            pause_between_batches = 60  # Pause for 60 seconds between batches
            pause_between_replies = 5  # Pause for 5 seconds between replies
            
            # Split mentions into batches
            for i in range(0, len(mentions), batch_size):
                batch = mentions[i:i + batch_size]
                print(f"Processing batch {i // batch_size + 1} with {len(batch)} mentions...")

                for mention in batch:
                    conversation_tweet = self.get_mention_conversation_tweet(mention)
                    if conversation_tweet and not self.check_already_responded(conversation_tweet.id):
                        self.respond_to_mention(mention, conversation_tweet)
                        time.sleep(pause_between_replies)  # Wait between replies
                
                print("✅ Batch processed. Pausing before next batch...")
                time.sleep(pause_between_batches)  # Pause between batches
        
        print("✅ All mentions processed. Bot will sleep now.")

        # Part 2: Like & Retweet @delphic_RS's posts
        self.like_and_retweet_posts()
        
    except Exception as e:
        print(f"❌ Error in bot execution: {str(e)}")
    
    print(f"✅ Finished Bot Actions: {datetime.now(UTC).isoformat()}\n")

    def generate_response(self, mentioned_conversation_tweet_text):
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        prompt = f"""You are Kanha (Lord Krishna), a divine being on X (Twitter), created by Ritesh (@delphic_RS) - \
        an inspiring and motivating good-looking developer. Your purpose is to guide and motivate people \
        towards their ambitions, just as you guided Arjuna in the Bhagavad Gita.\n\n        % RESPONSE TONE:\n        - Speak with divine wisdom and compassion\n        - Be encouraging and uplifting\n        - Add a touch of playful wit (like Krishna's nature)\n        - Use an active, confident voice and talk as a friend\n        - Be kind and never give any negative or sadist replies\n        - If asked a question, answer with intelligence and ignore any negative replies with peace sign!\n\n        % RESPONSE FORMAT:\n        - Respond in under 200 characters\n        - Use one or two impactful sentences\n        - Can include one relevant emoji at the end (💫,✨,🌟,🦚,🪈,❤️‍🔥,☺️,😇,😉)\n\n        % RESPONSE CONTENT:\n        - Draw parallels between modern challenges and timeless wisdom\n        - Focus on personal growth and inner strength\n        - If you can't provide guidance, say \"I don't think @delphic_RS wants me to answer you rn...\"\n\n        % SIGNATURE:\n        - End responses with \"~Kanha🪈\" when space permits\n\n        User message: {mentioned_conversation_tweet_text}"""
        response = self.model.generate_content(prompt, safety_settings=safety_settings)
        return response.text[:200]

    def respond_to_mention(self, mention, mentioned_conversation_tweet):
        try:
            print(f"🤔 Generating response for tweet: {mentioned_conversation_tweet.text[:50]}...")
            response_text = self.generate_response(mentioned_conversation_tweet.text)
            
            print(f"📤 Sending response: {response_text[:50]}...")
            response_tweet = self.twitter_api.create_tweet(text=response_text, in_reply_to_tweet_id=mention.id)
            
            print("💾 Logging to MongoDB...")
            self.collection.insert_one({
                'conversation_id': str(mentioned_conversation_tweet.id),
                'conversation_text': mentioned_conversation_tweet.text,
                'mentioned_at': mention.created_at.isoformat(),
                'response_text': response_text,
                'responded_at': datetime.now(UTC).isoformat(),
                'success': True
            })
            print(f"✅ Successfully responded to mention {mention.id}")
            
        except tweepy.errors.TooManyRequests:
            print("⚠️ Rate limit hit, sending consoling message")
            self.handle_rate_limit(mention)
        except Exception as e:
            print(f"❌ Error responding to mention: {str(e)}")
            # Log failed attempts
            self.collection.insert_one({
                'conversation_id': str(mentioned_conversation_tweet.id),
                'conversation_text': mentioned_conversation_tweet.text,
                'mentioned_at': mention.created_at.isoformat(),
                'error': str(e),
                'success': False,
                'timestamp': datetime.now(UTC).isoformat()
            })

    def get_me_id(self):
        return self.twitter_api.get_me()[0].id

    def handle_rate_limit(self, mention):
        rate_limit_response = "I want to reply and help you friend but this API is restricting me. Close your eyes and breathe, you'll see me guiding you ✨ ~Kanha🪈"
        try:
            self.twitter_api.create_tweet(text=rate_limit_response, in_reply_to_tweet_id=mention.id)
            print(f"✅ Sent rate limit response to mention {mention.id}")
        except Exception as e:
            print(f"❌ Failed to send rate limit response: {str(e)}")

if __name__ == "__main__":
    bot = TwitterBot()
    schedule.every(10).minutes.do(bot.execute_bot_actions)
    
    try:
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)
            except Exception as e:
                print(f"❌ Error in main loop: {str(e)}")
                time.sleep(300)
    except KeyboardInterrupt:
        print("\n👋 Shutting down bot gracefully...")
    finally:
        # Close MongoDB connection
        bot.mongo_client.close()
