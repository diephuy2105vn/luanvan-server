from bson import ObjectId

from server.config.logging import logging
from server.config.mongodb import get_db


async def delete_messages_by_list_id(list_id):
    try:
        db = get_db()
        messages_collection = db.get_collection("chat_messages")

        # Xóa các tin nhắn trong líst_id
        await messages_collection.delete_many(
            {"_id": {"$in": [ObjectId(message_id) for message_id in list_id]}},
        )
        logging.info(f"Delete messsages {list_id} sucessfully")
        return True
    except Exception as e:
        logging.error(f"Error: {e}")
        return False
