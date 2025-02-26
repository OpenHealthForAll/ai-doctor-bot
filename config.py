from dotenv import dotenv_values

config = dotenv_values(".env")

REDDIT_USERNAME = config.get('REDDIT_USERNAME')
REDDIT_PASSWORD = config.get('REDDIT_PASSWORD')
REDDIT_USER_AGENT = config.get('REDDIT_USER_AGENT')
REDDIT_CLIENT_ID = config.get('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = config.get('REDDIT_CLIENT_SECRET')
REDDIT_SUBREDDIT = config.get('REDDIT_SUBREDDIT')
SLEEP_DURATION = config.get('SLEEP_DURATION')
