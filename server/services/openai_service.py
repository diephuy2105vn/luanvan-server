import re
from typing import List
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from langchain.chains.combine_documents import create_stuff_documents_chain
from rouge_score import rouge_scorer
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain_openai import ChatOpenAI
from langchain.chains.question_answering import load_qa_chain
from server.config.logging import logging
from server.config.milvusdb import get_milvusdb
from server.settings import settings

# bge_rf = BGERerankFunction(
#             model_name="BAAI/bge-reranker-v2-m3",
# )

    
async def fetch_answer_by_file_ids_and_chat_id(
    query: str,
    file_ids: List[str],
    chat_id: str,
    response_model
) -> dict:
    from .file_service import get_similar_docs_by_file_ids

    try:

        milvusdb = get_milvusdb()
        if not milvusdb:
            raise Exception("Not connect milvus DB")

        similar_docs = await get_similar_docs_by_file_ids(
            query=query,
            file_ids=file_ids,
            top_k=5,
        )

        

        print('\n\n------------------------------------------------------SIMILAR DOCS------------------------------------------------------\n\n')
        
        print(f"Query: {query}\n")

        for doc in similar_docs:
            print(f"Text: {doc.page_content}\nDistance: {doc.metadata.get('distance')}\nFilename: {doc.metadata.get('file_name')}" )


        

        llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.1,
            max_tokens=512,
            openai_api_key=settings.openai_api_key,
        )

        chain = load_qa_chain(llm, "stuff")
        prompt = ChatPromptTemplate.from_template(
            """
            Bạn là một trợ lý ảo người Việt Nam, chuyên hỗ trợ trả lời các câu hỏi dựa trên tài liệu {context}
                - Nếu câu hỏi là một lời chào (ví dụ: "xin chào", "hello", "chào bạn"), hãy trả lời "Em là trợ lý AI, anh/chị cần em giúp điều gì ạ".
                - Nếu câu hỏi liên quan đến tài liệu hãy trả lời theo định dạng <<Nội dung câu trả lời của em, phải có câu dẫn ví dụ em xin trả lời câu hỏi của anh/chị>>
                - Nếu câu hỏi không liên quan đến tài liệu hãy trả lời  "Nội dung này em k có thông tin, mời anh/chị đặt câu hỏi khác --suggest_question: <<Câu hỏi gợi ý ngắn cho người dùng hỏi bạn liên quan đến tài liệu>>".
            Câu hỏi hiện tại: {question}
            * Quan trọng nội dung trong cặp ngoặc <<>> là nội dung cần thay đổi, Phải luôn xưng là em và gọi người dùng là anh/chị  
            """,
        )

        chain = create_stuff_documents_chain(llm, prompt)
        result = chain.invoke({"context": similar_docs, "question": query})

        cleaned_text = re.sub(r"<<|>>", "", result)
        if "--suggest_question:" in cleaned_text:
            answer, suggest_question = cleaned_text.split("--suggest_question:")
            message = {
                "answer": answer.strip(),
                "suggest_question": suggest_question.strip(),
            }

        else:
            message = {"answer": cleaned_text.strip()}

        return message

    except Exception as e:
        logging.error(f"Error: {e}")
        return {"answer": "Nội dung này tôi chưa có thông tin, mời bạn hỏi câu khác"}
