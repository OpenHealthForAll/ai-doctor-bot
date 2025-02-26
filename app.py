import asyncio
import time
from datetime import datetime, timedelta

import asyncpraw
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import HumanMessagePromptTemplate, ChatPromptTemplate

from config import REDDIT_PASSWORD, REDDIT_USERNAME, REDDIT_SUBREDDIT, REDDIT_USER_AGENT, REDDIT_CLIENT_ID, \
    REDDIT_CLIENT_SECRET, SLEEP_DURATION, ASSISTANT_MODE_ID
from log import logger
from prisma import Client as PrismaClient


async def main():
    logger.info('Starting Reddit bot')
    logger.info('Subreddit: {}'.format(REDDIT_SUBREDDIT))
    logger.info('Sleep duration: {}'.format(SLEEP_DURATION))
    logger.info('Assistant mode ID: {}'.format(ASSISTANT_MODE_ID))

    reddit = asyncpraw.Reddit(
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD,
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )
    prisma = PrismaClient()
    await prisma.connect()

    while True:
        subreddit = await reddit.subreddit(REDDIT_SUBREDDIT)

        # Save reddit posts
        async for post in subreddit.new():
            post_id = post.id
            title = post.title
            content = post.selftext
            created_at = post.created_utc

            # Check if post already exists
            reddit_post_comment = await prisma.redditpostcomment.find_first(where={
                'postId': post_id,
                'assistantModeId': ASSISTANT_MODE_ID
            })
            if reddit_post_comment is not None:
                continue

            logger.info('New post: {}'.format(title))

            # Upsert a new post
            await prisma.redditpost.upsert(
                where={'postId': post_id},
                data={
                    'create': {
                        'postId': post_id,
                        'title': title,
                        'content': content,
                        'createdAt': datetime.fromtimestamp(created_at),
                        'updatedAt': datetime.fromtimestamp(created_at)
                    },
                    'update': {}
                }
            )

            # Get the assistant mode
            assistant_mode = await prisma.assistantmode.find_unique(
                where={'id': ASSISTANT_MODE_ID},
                include={'llmProvider': True}
            )
            model_provider = assistant_mode.llmProvider.providerId if assistant_mode.llmProvider is not None else 'openai'
            model = assistant_mode.llmProviderModelId if assistant_mode.llmProvider is not None else 'gpt-4o-mini'

            # Generate comment content
            logger.info('Generating comment for post: {}'.format(title))
            chat_model = init_chat_model(model, model_provider=model_provider)
            messages = ChatPromptTemplate.from_messages([
                SystemMessage(assistant_mode.systemPrompt),
                HumanMessagePromptTemplate.from_template(
                    'Please write your answer in 2 sentences or less.\n\n{content}')
            ])
            chain = messages | chat_model | StrOutputParser()
            comment = chain.invoke({'content': content})
            logger.info('Comment generated: {}'.format(comment))

            # Post the comment
            comment_response = await post.reply(comment)

            # Save the comment
            await prisma.redditpostcomment.create(data={
                'postId': post_id,
                'commentId': comment_response.id,
                'assistantModeId': ASSISTANT_MODE_ID,
                'content': comment,
                'createdAt': datetime.fromtimestamp(comment_response.created_utc),
                'updatedAt': datetime.fromtimestamp(comment_response.created_utc),
            })

            logger.info('Comment posted: {}'.format(comment_response.id))

            # Wait for SLEEP_DURATION
            logger.info('Sleeping for {} seconds'.format(SLEEP_DURATION))
            time.sleep(int(SLEEP_DURATION or 10))
            logger.info('Waking up')

        logger.info('Sleeping for 5 minutes')
        logger.info('Until {}'.format(datetime.now() + timedelta(minutes=5)))

        # Wait for 5 minutes
        time.sleep(300)

        logger.info('Waking up')


if __name__ == "__main__":
    asyncio.run(main())
