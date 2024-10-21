import motor.motor_asyncio

from server.config.logging import logging
from server.settings import settings


def get_db():
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_url)
        db = client.CodeChat
        return db
    except Exception as e:
        logging.error("Could not connect to mongodb")
