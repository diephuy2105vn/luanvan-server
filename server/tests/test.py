from datasets import load_dataset
from pymilvus.model.reranker import BGERerankFunction
from pymilvus.model.reranker import CrossEncoderRerankFunction
from pymilvus import connections
import nltk
import json 

# connections.connect("default", host="localhost", port="19530",user="", password="")
dataset = load_dataset("microsoft/ms_marco", "v1.1", split="test")

bge_rf = BGERerankFunction(
    model_name="BAAI/bge-reranker-base",
    device="cpu"
)
ms_marco = CrossEncoderRerankFunction(model_name="cross-encoder/ms-marco-MiniLM-L-4-v2", device="cpu")




def main(): 
    correct_bge_rf = 0
    correct_ms_marco = 0
    error = 0
    num_samples =  1000
    for i in range(num_samples):
        query = dataset[i]["query"]
        
        passages_data = dataset[i]["passages"]
        if isinstance(passages_data, str):
            passages_data = json.loads(passages_data)
        passages = [p for p  in passages_data.get("passage_text")]
        selected_index = next((j for j, i in enumerate(passages_data.get("is_selected")) if i == 1), None)
        
        result_bge_rf = bge_rf(
            query=query,
            documents=passages,
            top_k=3
        )
        result_ms_marco = ms_marco(
            query=query,
            documents=passages,
            top_k=3
        )

        if selected_index == None: 
            error += 1
            continue
        

        if result_bge_rf[0].text == passages[selected_index] or result_bge_rf[1].text == passages[selected_index] or result_bge_rf[2].text == passages[selected_index]:
            correct_bge_rf += 1
        if result_ms_marco[0].text == passages[selected_index] or result_ms_marco[1].text == passages[selected_index] or  result_ms_marco[2].text == passages[selected_index]:
            correct_ms_marco += 1

        print(f"Query: {query}")
        print(f"Selected Index: {selected_index}")
        print("BGE RF Selected Index:", selected_index, "Count correct:", correct_bge_rf)
        print("MS MARCO Selected Index:", selected_index, "Count correct:", correct_ms_marco)

    accuracy_baaai = correct_bge_rf / num_samples * 100
    accuracy_ms_marco = correct_ms_marco / num_samples * 100
    print(f"Data Error: {error}" )
    print(f"\nBAAI Reranker Accuracy: {accuracy_baaai}%")
    print(f"MS MARCO Reranker Accuracy: {accuracy_ms_marco}%")

if __name__ == "__main__":
    main()