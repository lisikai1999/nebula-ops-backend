# from django.db import models
import chromadb

from openai import OpenAI



# 错误信息
error_message = []



class KnowledgeBase():
    """
        向量数据库chromadb操作
    """
    
    def __init__(self, host, port, collection):
      self.client = chromadb.HttpClient(host=host, port=port)
      self.collection = self.client.get_or_create_collection(
            name=collection
        )


    # 插入数据到集合
    def insert_collection(self, documents, metadata, ids):
        
        # 文本分块处理（长文本需分割）
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, 
            chunk_overlap=50
        )
        
        split_docs = text_splitter.split_text(documents) 


        # 构建写入参数
        final_ids = [f"{ids}_{i}" for i in range(len(split_docs))]
        
        print("split_docs", split_docs)
        print("split_docs", len(split_docs))

        metadata_list = []
        # 将metadata转化为与ids长度相同的列表
        for _ in range(len(split_docs)):
            metadata_list.append(metadata)

        # 写入ChromaDB
        self.collection.add(
            documents=split_docs,
            ids=final_ids,
            metadatas=metadata_list  # 可包含来源、时间戳等字段
        )
        
        return {"count": len(final_ids)}


    # 搜索集合
    def search_collection(self, query, n_results=10):
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )

        result = []

        # 数据整理
        for i in range(len(results['ids'][0])):
            try:
                title = results['metadatas'][0][i]['title']
            except Exception as e:
                title = None
            
            try:
                category = results['metadatas'][0][i]['category']
            except Exception as e:
                category = None

            try:
                tags = results['metadatas'][0][i]['tags'].split(",") 
            except Exception as e:
                tags = None

            
            
            result.append(
                {
                    "title": title,
                    "category": category,
                    "tags": tags,
                    "content": results['documents'][0][i],
                    "id": results['ids'][0][i]
                }
            )

        print(result)
        return result
        
    # 删除数据
    def delete_collection(self, ids):
        self.collection.delete(
            ids=ids
        )
        return {"status": "success"}
    

# 大模型调用
class LLMModel():
    def __init__(self, ApiKey):
        self.client = OpenAI(api_key=ApiKey, base_url="https://api.deepseek.com")

    def chat(self, context, query):
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是用来执行RAG流程的大语言模型"},
                {"role": "user", "content": f"""请基于以下上下文回答问题:{context} ; 问题:{query}"""},
            ],
            stream=False
        )

        return response
    
