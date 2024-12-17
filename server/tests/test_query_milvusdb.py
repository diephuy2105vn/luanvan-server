import json

from dotenv import load_dotenv
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from server.settings import settings

load_dotenv()


def connect_to_milvus():
    connections.connect(
        user=settings.milvus_db_username,
        password=settings.milvus_db_password,
        host=settings.milvus_db_host,
        port=settings.milvus_db_port,
        db_name=settings.milvus_db_name,
    )


def list_collections():
    try:
        connect_to_milvus()
        collections = utility.list_collections()
        print("Collections:", collections)
    except Exception as e:
        print(f"Error listing collections: {str(e)}")


def create_collection(collection_name):
    try:
        connect_to_milvus()

        if utility.has_collection(collection_name):
            print(f"Collection {collection_name} already exists.")
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=768),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="chat_id", dtype=DataType.VARCHAR, max_length=500),
        ]

        schema = CollectionSchema(fields=fields, description="File collection")

        collection = Collection(name=collection_name, schema=schema)
        print(f"Collection {collection_name} created successfully.")

        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        }

        collection.create_index(field_name="vector", index_params=index_params)
        print(f"Index created for collection {collection_name}.")

    except Exception as e:
        print(f"Error creating collection {collection_name}: {str(e)}")


def drop_collection(collection_name):
    try:
        connect_to_milvus()
        if utility.has_collection(collection_name):
            collection = Collection(collection_name)
            collection.drop()
            print(f"Collection {collection_name} dropped successfully")
        else:
            print(f"Collection {collection_name} does not exist")
    except Exception as e:
        print(f"Error dropping collection {collection_name}: {str(e)}")


def check_data(collection_name):
    try:

        connect_to_milvus()

        if not utility.has_collection(collection_name):
            print(f"Collection {collection_name} does not exist.")
            return

        collection = Collection(collection_name)

        collection.load()
        num_entities = collection.num_entities

        results = list(
            collection.query(
                expr="",
                output_fields=["id", "text", "vector"],
                limit=100,
            ),
        )

        output_data = {
            "total": num_entities,
            "data": [dict(result) for result in results],
        }
        print(output_data)
        print(json.dumps(output_data, indent=2))

    except Exception as e:
        print(f"Lỗi khi kiểm tra dữ liệu: {str(e)}")


def drop_collection_data(collection_name):
    try:
        # Kết nối tới Milvus
        connect_to_milvus()

        collection = Collection(collection_name)

        # Xóa hết dữ liệu trong collection
        collection.drop()

        print(f"Dữ liệu trong collection {collection_name} đã được xóa thành công")
    except Exception as e:
        print(f"Lỗi khi xóa dữ liệu: {str(e)}")


if __name__ == "__main__":
    create_collection("project_collection")
