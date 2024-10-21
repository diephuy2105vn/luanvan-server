from langchain_community.vectorstores import Milvus
from langchain_openai import OpenAIEmbeddings
from pymilvus import Collection, connections, utility

from server.settings import settings


def get_milvusdb():
    try:
        connections.connect(
            alias="default",
            user=settings.milvus_db_username,
            password=settings.milvus_db_password,
            host=settings.milvus_db_host,
            port=settings.milvus_db_port,
            db_name="default",
        )
        print(utility.list_collections())
        print(settings.milvus_db_collection)
        if utility.has_collection(settings.milvus_db_collection):
            return Collection(settings.milvus_db_collection)

        return None
    except:
        return None
