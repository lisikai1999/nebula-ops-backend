# Create your views here.
import json
from django import forms
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required

from utils import iam
from .models import AWSUser, AWSCloudWatch, AWSecs, AWSRoute53, AWSAthena
from settings import emailList, access_list

# 封装api接口
def login_required_401(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"code": 401, "error": "未登录"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


# Create your views here.

# @api_view(['POST'])
def custom_login(request):
    if request.method == 'POST':
      body = json.loads(request.body)
      # 获取用户名和密码
      username = body['username']
      password = body['password']
      
      # 认证用户（参考 Django 的 auth_views 逻辑）
      user = authenticate(request, username=username, password=password)
      if user is not None:
          login(request, user)
          return JsonResponse({'code': 200, 'msg': '登录成功'})
      else:
          return JsonResponse({'code': 401, 'msg': '用户名或密码错误'}, status=401)
      
    else:
        return HttpResponse("None")


@login_required(login_url='/login/')
def userManage(request):
    """
        aws用户管理界面
    """
    return render(request, 'aws/securityHub/usermange.html')

@login_required(login_url='/login/')
def logDownLoad(request):
    """
        aws用户管理界面
    """
    return render(request, 'aws/cloudwatch/logdown.html')

@login_required(login_url='/login/')
def ecsInfo(request):
    """
        aws ecs信息界面
    """
    return render(request, 'aws/ecs/ecsinfo.html')



@login_required_401
def get_env_group(request):
    """
        获取某个环境的所有日志组
    """
    env = request.GET.get('env', None)
    result = AWSCloudWatch.getEnvGroup(env)
    return JsonResponse(result, safe=False)

@login_required_401
def route_path(request):
    env = request.GET.get('env', None)
    ZoneId = request.GET.get('ZoneId', None)
    port = request.GET.get('port', None)

    # result = {
    #     "nodes": [{'id': 'carehub-dms1.zktecoiotdev.com', 'name': 'carehub-dms1.zktecoiotdev.com', 'category': 0, 'symbolSize': 30}, {'id': 'tg-carehub-dms', 'name': 'tg-carehub-dms', 'category': 1, 'symbolSize': 30}, {'id': 'ecs-cluster-carehub-dms/carehub-dms', 'name': 'ecs-cluster-carehub-dms/carehub-dms', 'category': 2, 'symbolSize': 30}, {'id': 'carehub.zktecoiotdev.com', 'name': 'carehub.zktecoiotdev.com', 'category': 0, 'symbolSize': 30}, {'id': 'tg-carehub-web-startup', 'name': 'tg-carehub-web-startup', 'category': 1, 'symbolSize': 30}, {'id': 'ecs-cluster-carehub-web-startup/carehub-web-startup', 'name': 'ecs-cluster-carehub-web-startup/carehub-web-startup', 'category': 2, 'symbolSize': 30}, {'id': 'tg-carehub-web', 'name': 'tg-carehub-web', 'category': 1, 'symbolSize': 30}, {'id': 'ecs-cluster-cn-northwest-1-carehub-web/carehub-web', 'name': 'ecs-cluster-cn-northwest-1-carehub-web/carehub-web', 'category': 2, 'symbolSize': 30}, {'id': 'ngtecoapi.zktecoiotdev.com', 'name': 'ngtecoapi.zktecoiotdev.com', 'category': 0, 'symbolSize': 30}, {'id': 'tg-ngteco-system', 'name': 'tg-ngteco-system', 'category': 1, 'symbolSize': 30}, {'id': 'ecs-cluster-cn-northwest-1-ngteco-system/ngteco-system', 'name': 'ecs-cluster-cn-northwest-1-ngteco-system/ngteco-system', 'category': 2, 'symbolSize': 30}, {'id': 'ngtecojms.zktecoiotdev.com', 'name': 'ngtecojms.zktecoiotdev.com', 'category': 0, 'symbolSize': 30}, {'id': 'tg-ngteco-jms', 'name': 'tg-ngteco-jms', 'category': 1, 'symbolSize': 30}, {'id': 'ecs-cluster-cn-northwest-1-ngteco-jms/ngteco-jms', 'name': 'ecs-cluster-cn-northwest-1-ngteco-jms/ngteco-jms', 'category': 2, 'symbolSize': 30}, {'id': 'ufo.zktecoiotdev.com', 'name': 'ufo.zktecoiotdev.com', 'category': 0, 'symbolSize': 30}, {'id': 'tg-carehub-best', 'name': 'tg-carehub-best', 'category': 1, 'symbolSize': 30}, {'id': 'carehub-best-dev/carehub-best-dev', 'name': 'carehub-best-dev/carehub-best-dev', 'category': 2, 'symbolSize': 30}, {'id': 'zkcloudmall-qr01.zktecoiotdev.com', 'name': 'zkcloudmall-qr01.zktecoiotdev.com', 'category': 0, 'symbolSize': 30}, {'id': 'chuangying-external-project', 'name': 'chuangying-external-project', 'category': 1, 'symbolSize': 30}, {'id': 'zkcloudmall.zktecoiotdev.com', 'name': 'zkcloudmall.zktecoiotdev.com', 'category': 0, 'symbolSize': 30}, {'id': 'zkmall-api.zktecoiotdev.com', 'name': 'zkmall-api.zktecoiotdev.com', 'category': 0, 'symbolSize': 30}, {'id': 'zkapp-zk-mall-backend-dev', 'name': 'zkapp-zk-mall-backend-dev', 'category': 1, 'symbolSize': 30}, {'id': 'zkapp-zk-activity-backend-dev', 'name': 'zkapp-zk-activity-backend-dev', 'category': 1, 'symbolSize': 30}, {'id': 'zkmall.zktecoiotdev.com', 'name': 'zkmall.zktecoiotdev.com', 'category': 0, 'symbolSize': 30}, {'id': 'zkapp-zk-mall-frontend-dev', 'name': 'zkapp-zk-mall-frontend-dev', 'category': 1, 'symbolSize': 30}],
    #     "links": [{'source': 'carehub-dms1.zktecoiotdev.com', 'target': 'tg-carehub-dms', 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'tg-carehub-dms', 'target': ['ecs-cluster-carehub-dms/carehub-dms'], 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'carehub.zktecoiotdev.com', 'target': 'tg-carehub-web-startup', 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'tg-carehub-web-startup', 'target': ['ecs-cluster-carehub-web-startup/carehub-web-startup'], 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'carehub.zktecoiotdev.com', 'target': 'tg-carehub-web', 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'tg-carehub-web', 'target': ['ecs-cluster-cn-northwest-1-carehub-web/carehub-web'], 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'ngtecoapi.zktecoiotdev.com', 'target': 'tg-ngteco-system', 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'tg-ngteco-system', 'target': ['ecs-cluster-cn-northwest-1-ngteco-system/ngteco-system'], 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'ngtecojms.zktecoiotdev.com', 'target': 'tg-ngteco-jms', 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'tg-ngteco-jms', 'target': ['ecs-cluster-cn-northwest-1-ngteco-jms/ngteco-jms'], 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'ufo.zktecoiotdev.com', 'target': 'tg-carehub-best', 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'tg-carehub-best', 'target': ['carehub-best-dev/carehub-best-dev'], 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'zkcloudmall-qr01.zktecoiotdev.com', 'target': 'chuangying-external-project', 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'zkmall-api.zktecoiotdev.com', 'target': 'zkapp-zk-mall-backend-dev', 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'zkmall-api.zktecoiotdev.com', 'target': 'zkapp-zk-activity-backend-dev', 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}, {'source': 'zkmall.zktecoiotdev.com', 'target': 'zkapp-zk-mall-frontend-dev', 'label': {'show': True, 'formatter': '调用', 'color': '#666'}}]
    # }

    result = AWSRoute53().get_route_path(env, ZoneId, port)
    return JsonResponse(result, safe=False)

@login_required_401
def list_zone(request):
    env = request.GET.get('env', None)

    result = AWSRoute53().list_zone_id(env)
    return JsonResponse(result, safe=False)

@login_required(login_url='/login/')
def get_cloudwatch_IncomingBytes(request):
    """
        获取所有环境的incomingBytes
    """
    result = AWSCloudWatch.getIncomingBytes()
    return JsonResponse(result, safe=False)



@login_required(login_url='/login/')
def get_user_info(request):
    users = AWSUser.get_user_info()
    return JsonResponse(users, safe=False)


@login_required(login_url='/login/')
def get_ecs_info(request):
    env = request.GET.get("env")
    ecsInfo = AWSecs.ecs_info(env)
    return JsonResponse(ecsInfo, safe=False)
  


@login_required(login_url='/login/')
def describe_ecs_taskdefine(request):
    env = request.GET.get("env")
    taskarn = request.GET.get("taskarn")
    taskdefineInfo = AWSecs.describetaskdefine(env, taskarn)
    print(taskdefineInfo)
    return JsonResponse(taskdefineInfo, safe=False)

  


@login_required(login_url='/login/')
def disable_console(request, id):
    """
        禁用aws用户控制台登陆
    """
    if request.method == 'POST':
        env = request.POST.get('env')
        
        if env == None:
            return HttpResponse("None")
        else:
            # 根据环境寻找key，对对应环境的用户进行操作
            for access in access_list:
                if access['env'] == env:
                    # proc = iam.proc(access['region'], access['access_key'], access['secret_key'])
                    # proc.delete_login_profile(id)
                    pass
        return HttpResponse("")
    else:
        return HttpResponse("")
    

@login_required(login_url='/login/')
def reset_password(request, id):
    """
        重置aws用户密码
    """
    if request.method == 'POST':
        env = request.POST.get('env')
        
        if env == None:
            return HttpResponse("None")
        else:
            # 根据环境寻找key，对对应环境的用户进行操作
            for access in access_list:
                if access['env'] == env:
                    # proc = iam.proc(access['region'], access['access_key'], access['secret_key'])
                    # proc.create_login_profile(id)
                    pass
        return HttpResponse("")
    else:
        return HttpResponse("")

@login_required(login_url='/login/')
def download(request):
    """
        下载日志组日志
    """
    env = request.GET.get('env', None)
    end_time = request.GET.get('end_time', None)
    start_time = request.GET.get('start_time', None)
    log_group_name = request.GET.get('log_group_name', None)
    filterPattern = request.GET.get('filterPattern', None)
    
    parameterList = [env, end_time, start_time, log_group_name, filterPattern]
    # 判断参数是否全都不为None
    if all([parameter is not None for parameter in parameterList]):
        file_path = AWSCloudWatch.download_file(env, end_time, start_time, log_group_name, filterPattern)
        print(file_path)
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type='application/txt')
            response['Content-Disposition'] = 'attachment; filename=' + file_path.split('/')[-1]
            response["Access-Control-Expose-Headers"] = "Content-Disposition"  # 为了使前端获取到Content-Disposition属性
            return response
    else:
        return JsonResponse([], safe=False)


@login_required_401
def get_athena_environments(request):
    """
        获取所有可用的 AWS 环境列表
    """
    try:
        environments = AWSAthena.get_environments()
        return JsonResponse({
            "status": "success",
            "data": environments
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": "获取环境列表失败",
            "detail": str(e)
        }, status=500)


@login_required_401
def get_athena_databases(request):
    """
        获取指定环境下的所有 Athena 数据库
    """
    try:
        env = request.GET.get('env', None)
        if not env:
            return JsonResponse({
                "status": "error",
                "message": "参数缺失",
                "detail": "env 参数是必需的"
            }, status=400)
        
        databases = AWSAthena.get_databases(env)
        return JsonResponse({
            "status": "success",
            "data": databases
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": "获取数据库列表失败",
            "detail": str(e)
        }, status=500)


@login_required_401
def get_athena_tables(request):
    """
        获取指定数据库下的所有数据表
    """
    try:
        env = request.GET.get('env', None)
        database = request.GET.get('database', None)
        
        if not env or not database:
            return JsonResponse({
                "status": "error",
                "message": "参数缺失",
                "detail": "env 和 database 参数是必需的"
            }, status=400)
        
        tables = AWSAthena.get_tables(env, database)
        return JsonResponse({
            "status": "success",
            "data": tables
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": "获取数据表列表失败",
            "detail": str(e)
        }, status=500)


@login_required_401
def execute_athena_query(request):
    """
        执行 Athena SQL 查询并返回结果
    """
    if request.method != 'POST':
        return JsonResponse({
            "status": "error",
            "message": "方法不允许",
            "detail": "只支持 POST 请求"
        }, status=405)
    
    try:
        body = json.loads(request.body)
        environment = body.get('environment', None)
        database = body.get('database', None)
        sql = body.get('sql', None)
        limit = body.get('limit', 100)
        
        if not environment or not sql:
            return JsonResponse({
                "status": "error",
                "message": "参数缺失",
                "detail": "environment 和 sql 参数是必需的"
            }, status=400)
        
        result = AWSAthena.execute_query(environment, database, sql, limit)
        
        if result["query_info"].get("status") == "FAILED":
            return JsonResponse({
                "status": "error",
                "message": "查询执行失败",
                "detail": result["query_info"].get("state_change_reason", "未知错误")
            }, status=500)
        
        return JsonResponse({
            "status": "success",
            "data": result
        })
    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "message": "请求体格式错误",
            "detail": "请提供有效的 JSON 格式"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": "执行查询失败",
            "detail": str(e)
        }, status=500)


@login_required_401
def get_athena_query_status(request):
    """
        获取查询状态
    """
    try:
        env = request.GET.get('env', None)
        query_id = request.GET.get('query_id', None)
        
        if not env or not query_id:
            return JsonResponse({
                "status": "error",
                "message": "参数缺失",
                "detail": "env 和 query_id 参数是必需的"
            }, status=400)
        
        status = AWSAthena.get_query_status(env, query_id)
        return JsonResponse({
            "status": "success",
            "data": status
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": "获取查询状态失败",
            "detail": str(e)
        }, status=500)
