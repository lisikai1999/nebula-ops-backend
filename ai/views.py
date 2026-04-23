# Create your views here.
import json
import uuid

from django import forms
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required

from .models import KnowledgeBase, LLMModel
from settings import CHROMA_HOST, CHROMA_PORT, CHROMA_COLLECTION, ApiKey

# 封装api接口
def login_required_401(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"code": 401, "error": "未登录"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper



@login_required_401
def insert_knowledge_base(request):
    """
        写入数据到知识库
    """
    if request.method == "POST":
        # 获取前端参数
        data = json.loads(request.body)
        title = data['title']  # 标题
        content = data['content']  # 内容
        category = data['category']  # 分类
        tags = data['tags']  # 标签
        
        ids = str(uuid.uuid4())

        # 数据校验（示例）
        if not content:
            return JsonResponse({"status": "error", "msg": "参数不完整或长度不一致"})
        
        # 调用ChromaDB写入逻辑
        try:
           Knowledge = KnowledgeBase("10.8.51.123", 8000, "test")
           
           result = Knowledge.insert_collection(content, {"tags": tags, "category": category, "title": title}, ids)
           return JsonResponse({"status": "success", "data": result})
        except Exception as e:
           return JsonResponse({"status": "error", "msg": str(e)})
    return JsonResponse({"status": "error", "msg": '401'})


@login_required_401
def delete_knowledge_base(request):

    if request.method == "POST":
        # 获取前端参数
        data = json.loads(request.body)
        id = data['id']  # 获取id
        
        if not id:
            return JsonResponse({"status": "error", "msg": "参数不完整或长度不一致"})
        
        Knowledge = KnowledgeBase("10.8.51.123", 8000, "test")
        try:
            result = Knowledge.delete_collection([id])
            return JsonResponse({"status": "success", "data": result})
        except Exception as e:
            return JsonResponse({"status": "error", "msg": str(e)})
        
    return JsonResponse({"status": "error", "msg": '401'})


@login_required_401
def search_knowledge_base(request):
    
    if request.method == "GET":
        # 获取前端参数
        query = request.GET.get('keyword', None)
        

        if not query:
            return JsonResponse({"status": "error", "msg": "参数不完整或长度不一致"})
        
        Knowledge = KnowledgeBase("10.8.51.123", 8000, "test")
        try:
            result = Knowledge.search_collection(query, 5)
            return JsonResponse({"status": 200, "data": result})
        except Exception as e:
            return JsonResponse({"status": "error", "msg": str(e)})
        
    return JsonResponse({"status": "error", "msg": '401'})



# ai问答

@login_required_401
def ai_answer(request):
    if request.method == "POST":
        # 获取前端参数
        data = json.loads(request.body)
        question = data['question']  # 获取id
        top_k = data['top_k']  # 获取id
        
        if not question:
            return JsonResponse({"status": "error", "msg": "参数不完整或长度不一致"})
        
        # RAG流程
        try:
            # 查询向量数据库，获取上下文
            Knowledge = KnowledgeBase(CHROMA_HOST, CHROMA_PORT, CHROMA_COLLECTION)
            context = Knowledge.search_collection(question, top_k)  # 上下文

            # 利用向量数据库返回的上下文，进行问答
            LLMclient = LLMModel(ApiKey)
            response = LLMclient.chat(context, question)
            
            answer = response.choices[0].message.content    # 回答
            

            return JsonResponse({"status": "success", "context": context, "answer": answer})
        except Exception as e:
           return JsonResponse({"status": "error", "msg": str(e)})
    return JsonResponse({"status": "error", "msg": '401'})

