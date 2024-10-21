import asyncio
import re
from typing import List

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain_openai import ChatOpenAI
from pymilvus.model.reranker import BGERerankFunction

from server.config.logging import logging
from server.config.milvusdb import get_milvusdb
from server.settings import settings

# model_name_or_path = "Alibaba-NLP/gte-multilingual-reranker-base"

# tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
# model = AutoModelForSequenceClassification.from_pretrained(
#     model_name_or_path, trust_remote_code=True, torch_dtype=torch.float16
# )


async def fetch_answer_by_file_ids_and_chat_id(
    query: str,
    file_ids: List[str],
    chat_id: str,
) -> dict:
    from .file_service import get_similar_docs_by_file_ids, insert_doc_by_qa_and_chat_id

    try:

        milvusdb = get_milvusdb()
        if not milvusdb:
            raise Exception("Not connect milvus DB")

        similar_docs = await get_similar_docs_by_file_ids(
            query=query,
            file_ids=file_ids,
            top_k=5,
        )
        # pairs = [(query, doc.page_content) for doc in similar_docs]

        # inputs = tokenizer(
        #     pairs,
        #     padding=True,
        #     truncation=True,
        #     return_tensors="pt",
        #     max_length=1024,
        # )
        bge_rf = BGERerankFunction(
            model_name="BAAI/bge-reranker-v2-m3",
        )

        rerank_result = bge_rf(
            query=query,
            documents=[(doc.page_content) for doc in similar_docs],
            top_k=3,
        )
        reranked_docs = []
        for i, result in enumerate(rerank_result):
            print(f"Text: {result.text}, Score: {result.score}")
            reranked_docs.append(
                Document(
                    result.text,
                    metadata={
                        "score": result.score,
                    },
                ),
            )

        # history_docs = await get_history_docs_by_chat_id(
        #     query=query, chat_id=chat_id, top_k=3
        # )

        llm = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            temperature=0.1,
            max_tokens=512,
            openai_api_key=settings.openai_api_key,
        )

        chain = load_qa_chain(llm, "stuff")
        prompt = ChatPromptTemplate.from_template(
            """
            Bạn là một trợ lý ảo người Việt Nam, chuyên hỗ trợ trả lời các câu hỏi dựa trên tài liệu {context}.
                - Nếu câu hỏi là một lời chào (ví dụ: "xin chào", "hello", "chào bạn"), hãy trả lời "Xin chào! Chào bạn, có điều gì tôi có thể giúp bạn hôm nay không?".
                - Nếu câu hỏi liên quan đến tài liệu hãy trả lời theo định dạng "<<Nội dung câu trả lời của bạn>> --suggest_question: <<Câu hỏi gợi ý ngắn liên quan đến các tài liệu không được trùng ý với câu hỏi của người người dùng>>"
                - Nếu câu hỏi không liên quan đến tài liệu hãy trả lời theo định dạng "Nội dung này tôi k có thông tin, mời bạn hỏi câu khác --suggest_question: <<Câu hỏi gợi ý ngắn cho người dùng hỏi bạn liên quan đến tài liệu>>".
                - Hạn chế nhắc lại thông tin trong lịch sử trò chuyện nếu người dùng không hỏi thêm.
            Câu hỏi hiện tại: {question}
            * Quan trọng nội dung trong cặp ngoặc <<>> là nội dung cần thay đổi
            """,
        )

        chain = create_stuff_documents_chain(llm, prompt)
        result = chain.invoke({"context": reranked_docs, "question": query})

        cleaned_text = re.sub(r"<<|>>", "", result)

        if "--suggest_question:" in cleaned_text:
            answer, suggest_question = cleaned_text.split("--suggest_question:")
            message = {
                "answer": answer.strip(),
                "suggest_question": suggest_question.strip(),
            }

        else:
            message = {"answer": cleaned_text.strip()}

        asyncio.create_task(
            insert_doc_by_qa_and_chat_id(
                question=query, answer=result, chat_id=chat_id
            ),
        )

        return message

    except Exception as e:
        logging.error(f"Error: {e}")
        return {"answer": "Nội dung này tôi chưa có thông tin, mời bạn hỏi câu khác"}
