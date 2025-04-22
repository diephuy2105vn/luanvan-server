import asyncio
import io
import os
from typing import List
from uuid import uuid4

import pymupdf
import pytesseract
from bson import ObjectId
from fastapi import UploadFile
from langchain.schema import Document

from langchain_text_splitters import RecursiveCharacterTextSplitter
from PIL import Image
from pymilvus import Collection
from pymongo.collection import Collection

from server.config.logging import logging
from server.config.milvusdb import get_milvusdb
from server.config.mongodb import get_db
from server.web.api.file.schema import FileSchema, FileStatus


import re

from sentence_transformers import SentenceTransformer

model = SentenceTransformer("Alibaba-NLP/gte-multilingual-base",  trust_remote_code=True)



async def insert_file(file: UploadFile, user_id: str) -> FileSchema:
    try:

        files_collection: Collection = get_db().get_collection("files")
        file_name, file_extension = os.path.splitext(file.filename)
    
        save_dir = os.path.join("server/stores/file/")
        os.makedirs(save_dir, exist_ok=True)
        file_uuid = uuid4()
        file_path = os.path.join(save_dir, f"{file_uuid}{file_extension}")

        file_new = FileSchema(
            name=file_name,
            extension=file_extension[1:],
            size=file.size,
            path=file_path,
            owner=user_id,
            status=FileStatus.loading,
        )

        await file.seek(0)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        result_file = await files_collection.insert_one(
            file_new.model_dump(by_alias=True, exclude=["id"]),
        )
        inserted_file = FileSchema(
            **await files_collection.find_one({"_id": result_file.inserted_id})
        )

        asyncio.create_task(insert_docs(inserted_file))
        return inserted_file

    except Exception as e:
        logging.error(e)


async def delete_file_by_file_id(file_id: str, user_id: str) -> bool:
    try:

        files_collection: Collection = get_db().get_collection("files")

        existing_file = await files_collection.find_one(
            {"_id": ObjectId(file_id), "disabled": True},
        )

        if not existing_file:
            raise FileNotFoundError(
                f"File with ID {file_id} not found in the database.",
            )

        file = FileSchema(**existing_file)

        delete_file_result = await files_collection.delete_one(
            {"_id": ObjectId(file_id)},
        )
        if delete_file_result.deleted_count == 0:
            raise Exception(
                f"Failed to delete the file with ID {file_id} from the database.",
            )

        if file.path and os.path.exists(file.path):
            os.remove(file.path)
        else:
            raise FileNotFoundError(
                f"File path {file.path} not found on the filesystem.",
            )
        delete_docs_result = delete_docs_by_file_id(file_id)

        if delete_docs_result:
            return True
        else:
            raise Exception(
                f"Failed to delete docs of file with ID {file_id} from the milvusdb.",
            )
    except Exception as e:
        logging.error(e)
        return False

    


async def extract_text_from_pdf(pdf_path):
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, _extract_text_from_pdf, pdf_path)
    return text

def _extract_text_from_pdf(pdf_path):
    doc = pymupdf.open(pdf_path)
    text = ""
    for page_num in range(doc.page_count):
        page = doc[page_num]
        text += " " + page.get_text()
    doc.close()
    return text

async def extract_images_from_pdf(pdf_path):
    loop = asyncio.get_event_loop()
    images = await loop.run_in_executor(None, _extract_images_from_pdf, pdf_path)
    return images

def _extract_images_from_pdf(pdf_path):
    doc = pymupdf.open(pdf_path)
    images = []
    for i in range(len(doc)):
        for img in doc.get_page_images(i):
            base_image = doc.extract_image(img[0])
            images.append(base_image["image"])
    doc.close()
    return images

async def ocr_from_images(images):
    loop = asyncio.get_event_loop()
    texts = await loop.run_in_executor(None, _ocr_from_images, images)
    return texts

def _ocr_from_images(images):
    texts = []
    for img_data in images:
        image = Image.open(io.BytesIO(img_data))
        text = pytesseract.image_to_string(image, lang="vie")
        texts.append(text)
    return texts

async def extract_all_content(pdf_path):
    text = await extract_text_from_pdf(pdf_path)
    images = await extract_images_from_pdf(pdf_path)
    ocr_texts = await ocr_from_images(images)

    all_text = text + "\n" + "\n".join(ocr_texts)
    return all_text


def merge_sentences_into_chunks(sentences, min_length=500, max_length=800):
    paragraphs = []
    current_sentence = ""

    for sentence in sentences:
        if len(current_sentence) < min_length:
            if current_sentence:
                current_sentence += " " + sentence
            else:
                current_sentence = sentence
        else:
            paragraphs.append(current_sentence)
            current_sentence = sentence

    if current_sentence:
        if len(current_sentence) < min_length and paragraphs:
            paragraphs[-1] += " " + current_sentence
        else:
            paragraphs.append(current_sentence)

    chunks = []
    for paragraph in paragraphs:
        paragraph_length = len(paragraph)
        print(f"Paragraph lenght:  {paragraph_length}")

        if paragraph_length > max_length:
            ext_splitter = RecursiveCharacterTextSplitter(
                chunk_size=min_length,
                chunk_overlap=50,
            )
            chunks.extend(ext_splitter.split_text(paragraph))
        else:
            chunks.append(paragraph)
            

    return chunks


def split_content_to_sentences(content):
    content = content.strip().replace("\n", " ")
    sentences = re.split(r'(?<=[.?!])\s', content)
    return sentences


async def model_encode_text(text):
    loop = asyncio.get_event_loop()
    result =  await loop.run_in_executor(None, lambda: model.encode([text]))
    return result[0]

async def model_encode_texts(texts):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: model.encode(texts))

async def insert_to_milvus_by_file(file, chunks, vectors):
    db = get_milvusdb()

    db.insert(
        [
            {
                "text": chunk,
                "vector": vector,
                "file_name": file.name,
                "file_id": file.id,
            }
            for i, (chunk, vector) in enumerate(zip(chunks, vectors))
        ],
    )

    db.load()
    logging.info("Inserted chunks to milvus successfully")


async def insert_to_milvus_by_chat_id(chunk, vector, chat_id):
    db = get_milvusdb()
    if db is None:
        return
    db.insert(
        {
            "text": chunk,
            "vector": vector,
            "file_name": "",
            "file_id": "",
        },
    )
    db.load()

    logging.info("Inserted chunks to milvus successfully")


async def insert_docs(file: FileSchema):
    from server.config.socketio import socketio_app
    db = get_db()
    files_collection = db.get_collection("files")

    try:
        
        all_content = await extract_all_content(file.path) 
        sentences =  split_content_to_sentences(all_content)
        chunks =  merge_sentences_into_chunks(sentences)

        vectors = await model_encode_texts(chunks)
        print(f"Tên file: {file.name} --- Số chunks {len(chunks)}")
        for chunk in chunks: 
            print(f"Chunk: {chunk}")
            print(f"Length of chunk: {len(chunk)}\n")
        await insert_to_milvus_by_file(file, chunks, vectors)
        await files_collection.update_one(
            {"_id": ObjectId(file.id)},
            {"$set": {"status": FileStatus.success}},
        )
        await socketio_app.send_file_status(
            receiver_id=file.owner,
            file_id=file.id,
            status=FileStatus.success,
        )

    except Exception as e:
        logging.error(e)
        await files_collection.update_one(
            {"_id": ObjectId(file.id)},
            {"$set": {"status": FileStatus.error}},
        )
        await socketio_app.send_file_status(
            receiver_id=file.owner,
            file_id=file.id,
            status=FileStatus.error,
        )


async def insert_doc_by_qa_and_chat_id(question, answer, chat_id):
    qa = f"Câu hỏi: {question}, Trả lời: {answer}"
    vector =await model_encode_text(qa)
    await insert_to_milvus_by_chat_id(qa, vector, chat_id)



async def get_similar_docs_by_file_ids(
    query: str,
    file_ids: List[str],
    top_k: int = 5,
):

    try:
        query_vector =await model_encode_text(query)

        db = get_milvusdb()

        file_ids_expr = ", ".join(f'"{file_id}"' for file_id in file_ids)
        search_results = None
    
        search_results = db.search(
            expr=f"file_id in [{file_ids_expr}]",
            output_fields=["id", "file_name", "file_id", "text"],
            data=[query_vector],
            anns_field="vector",
            param={"metric_type": "COSINE" },
            limit=5,
        )

        docs = []

        for result in search_results:
            for hit in result:
                text = hit.entity.get("text")
                file_name = hit.entity.get("file_name")
                file_id = hit.entity.get("file_id")
                distance = hit.distance
                
                docs.append(
                    Document(
                        text,
                        metadata={
                            "file_name": file_name,
                            "file_id": file_id,
                            "distance": distance,
                        },
                    ),
                )

        return docs
    except Exception as e:
        print(f"Error: {e}")


async def get_history_docs_by_chat_id(query: str, chat_id: str, top_k: int = 5):
    try:
        query_vector = await model_encode_text(query)
        db = get_milvusdb()

        search_results = db.search(
            output_fields=["id", "file_name", "file_id", "text"],
            data=[query_vector],
            anns_field="vector",
            param={"metric_type": "COSINE",},
            limit=top_k,
            expr=f"chat_id == '{chat_id}'",
        )

        docs = []

        if search_results:
            for result in search_results:
                for hit in result:
                    text = hit.entity.get("text")
                    file_name = hit.entity.get("file_name")
                    file_id = hit.entity.get("file_id")
                    distance = hit.distance
                    docs.append(
                        Document(
                            text,
                            metadata={
                                "file_name": file_name,
                                "file_id": file_id,
                                "distance": distance,
                            },
                        ),
                    )

            for i, doc in enumerate(docs):
                print(f"History {i + 1}:")
                print(f"Text: {doc.page_content}")
                print(f"Metadata:")
                print(f"File Name: {doc.metadata['file_name']}")
                print(f"File ID: {doc.metadata['file_id']}")
                print(f"Distance: {doc.metadata['distance']}\n")

        return docs
    except Exception as e:
        print(f"Error: {e}")


def get_docs_by_file_id(file_id):
    milvusdb = get_milvusdb()
    docs = milvusdb.query(
        expr=f'file_id == "{file_id}"',
        output_fields=["id", "file_id", "text"],
    )

    return docs


def delete_docs_by_file_id(file_id):
    try:
        milvusdb = get_milvusdb()

        milvusdb.delete(
            expr=f'file_id == "{file_id}"',
        )
        milvusdb.flush()
        milvusdb.load()
        return True
    except Exception as e:
        return False
