# AI Doctor Bot

## Configuration

### Secret Values

The application requires several secret configuration values that should be stored in a values-secret.yaml file. This
file is excluded from version control (via .gitignore).
Create a values-secret.yaml file in the charts/chart/ directory with the following structure:

```yaml
apps:
  - name: ai-doctor-bot
    replicaCount: 1
    env:
      # Database configuration
      DATABASE_URL: "postgresql://username:password@hostname:5432/database_name"

      # Reddit API credentials
      REDDIT_USERNAME: "your_reddit_username"
      REDDIT_PASSWORD: "your_reddit_password"
      REDDIT_USER_AGENT: "your_user_agent" # e.g., "AI Doctor Bot v1.0 by /u/your_username"
      REDDIT_CLIENT_ID: "your_reddit_client_id"
      REDDIT_CLIENT_SECRET: "your_reddit_client_secret"
      REDDIT_SUBREDDIT: "subreddit_name" # e.g., "askdocs" (without the r/)

      # Application configuration
      SLEEP_DURATION: "60" # Time in seconds to wait between processing posts
      ASSISTANT_MODE_ID: "your_assistant_mode_id" # ID from the database for the assistant mode to use

      # LangChain configuration (if using LangSmith)
      LANGCHAIN_API_KEY: "your_langchain_api_key" # Optional
      LANGCHAIN_PROJECT: "ai-doctor-bot" # Optional
      LANGCHAIN_TRACING_V2: "true" # Optional
```

Replace the placeholder values with your actual configuration. The application uses these environment variables to
connect to the PostgreSQL database, authenticate with Reddit's API, and configure the behavior of the AI doctor bot.

## Deployment

```shell
$ helm upgrade --install ai-doctor-bot ./chart -f ./chart/values.yaml -f ./chart/values-secret.yaml
```

## Uninstall

```shell
helm uninstall ai-doctor-bot
```