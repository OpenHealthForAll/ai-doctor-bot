import asyncio
import time
from datetime import datetime, timedelta

import asyncpraw
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import HumanMessagePromptTemplate, ChatPromptTemplate
from pydantic import BaseModel, Field

from config import REDDIT_PASSWORD, REDDIT_USERNAME, REDDIT_SUBREDDIT, REDDIT_USER_AGENT, REDDIT_CLIENT_ID, \
    REDDIT_CLIENT_SECRET, SLEEP_DURATION, ASSISTANT_MODE_ID
from log import logger
from prisma import Client as PrismaClient

prisma = PrismaClient()


class IsNeedMedicalAdvice(BaseModel):
    is_need_advice: bool = Field(description="Determine whether the following Reddit post requires a medical response.")


class Submission(BaseModel):
    id: str = Field(description="The ID of the Reddit submission.")
    title: str = Field(description="The title of the Reddit submission.")
    content: str = Field(description="The content of the Reddit submission.")


async def is_need_medical_advice(post_id: str, title: str, content: str) -> bool:
    reddit_post = await prisma.redditpost.find_first(where={'postId': post_id})
    if reddit_post is not None:
        return reddit_post.isMedicalAdviceRequired

    model = init_chat_model('gpt-4o-mini', model_provider='openai')
    messages = ChatPromptTemplate.from_messages([
        HumanMessagePromptTemplate.from_template(
            """Determine whether the following Reddit post requires a medical response. Reply with 'true' if a medical response is needed, otherwise reply with 'false'. Answer only with 'true' or 'false', nothing else.\nTitle: {title}\nContent: {content}""")
    ])
    structured_llm = model.with_structured_output(IsNeedMedicalAdvice)
    chain = messages | structured_llm
    response = chain.invoke({'title': title, 'content': content}, config={'run_name': 'reddit-medical-advice'})
    return response.is_need_advice


async def get_submission_title_and_content(reddit, submission_id: str) -> [Submission, Submission | None]:
    submission = await reddit.submission(id=submission_id)

    title = submission.title
    content = submission.selftext
    cross_post_parent = None

    try:
        if submission.crosspost_parent is not None:
            cross_post_parent_id = submission.crosspost_parent[3:]

            cross_post = await reddit.submission(id=cross_post_parent_id)
            cross_post_parent = Submission(id=cross_post_parent_id, title=cross_post.title, content=cross_post.selftext)
    except AttributeError:
        cross_post_parent = None

    return Submission(id=submission_id, title=title, content=content), cross_post_parent


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
        user_agent=REDDIT_USER_AGENT,
        ratelimit_seconds=600,
    )
    await prisma.connect()

    while True:
        subreddit = await reddit.subreddit(REDDIT_SUBREDDIT)

        # Save reddit posts
        async for post in subreddit.new():
            post_id = post.id
            title = post.title
            content = post.selftext
            created_at = post.created_utc

            # Check if post requires medical advice
            is_need_advice = await is_need_medical_advice(post_id=post_id, title=title, content=content)

            # Upsert post
            await prisma.redditpost.upsert(
                where={'postId': post_id},
                data={
                    'create': {
                        'postId': post_id,
                        'title': title,
                        'content': content,
                        'isMedicalAdviceRequired': is_need_advice,
                        'createdAt': datetime.fromtimestamp(created_at),
                        'updatedAt': datetime.fromtimestamp(created_at)
                    },
                    'update': {
                        'isMedicalAdviceRequired': is_need_advice,
                    }
                }
            )

            # Skip if post does not require medical advice
            if is_need_advice is False:
                continue

            # Check if post already exists
            reddit_post_comment = await prisma.redditpostcomment.find_first(where={
                'postId': post_id,
                'assistantModeId': ASSISTANT_MODE_ID
            })
            if reddit_post_comment is not None:
                continue

            logger.info('New post: {}'.format(title))

            # Get the assistant mode
            assistant_mode = await prisma.assistantmode.find_unique(
                where={'id': ASSISTANT_MODE_ID},
                include={'llmProvider': True}
            )
            model_provider = assistant_mode.llmProvider.providerId if assistant_mode.llmProvider is not None else 'openai'
            model = assistant_mode.llmProviderModelId if assistant_mode.llmProvider is not None else 'gpt-4o-mini'

            # Get the submission title and content
            self, parent = await get_submission_title_and_content(reddit, submission_id=post_id)
            message_template = 'Please write your answer to this post. \n\n{title}\n{content}' if parent is None else 'Please write your answer to this post. \n\n{title}\n{content}\n\nParent post: {parent_title}\n{parent_content}'

            # Generate comment content
            logger.info('Generating comment for post: {}'.format(title))
            chat_model = init_chat_model(model, model_provider=model_provider)
            messages = ChatPromptTemplate.from_messages([
                SystemMessage(assistant_mode.systemPrompt),
                HumanMessagePromptTemplate.from_template(message_template)
            ])
            chain = messages | chat_model | StrOutputParser()
            comment = chain.invoke(
                {
                    'content': self.content,
                    'title': self.title,
                    'parent_content': parent.content if parent is not None else None,
                    'parent_title': parent.title if parent is not None else None
                },
                config={'run_name': 'reddit-comment'}
            )
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
