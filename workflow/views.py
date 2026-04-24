import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from .models import WorkflowService, ExecutionService, Execution


def login_required_401(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"code": 401, "message": "未授权，请先登录"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required_401
def get_workflow_list(request):
    """
    获取当前用户的所有工作流列表
    GET /api/workflow/list
    """
    try:
        workflows = WorkflowService.get_user_workflows(request.user)
        return JsonResponse({
            "code": 200,
            "data": workflows
        })
    except Exception as e:
        return JsonResponse({
            "code": 500,
            "message": f"获取工作流列表失败: {str(e)}"
        }, status=500)


@login_required_401
def workflow_detail(request, workflow_id):
    """
    工作流详情接口，支持 GET/PUT/DELETE 方法
    GET /api/workflow/{workflowId} - 获取工作流详情
    PUT /api/workflow/{workflowId} - 更新工作流
    DELETE /api/workflow/{workflowId} - 删除工作流
    """
    if request.method == 'GET':
        try:
            workflow = WorkflowService.get_workflow_by_id(workflow_id, request.user)
            if workflow is None:
                return JsonResponse({
                    "code": 404,
                    "message": "工作流不存在"
                }, status=404)
            
            return JsonResponse({
                "code": 200,
                "data": workflow.to_dict()
            })
        except Exception as e:
            return JsonResponse({
                "code": 500,
                "message": f"获取工作流详情失败: {str(e)}"
            }, status=500)
    
    elif request.method == 'PUT':
        try:
            workflow = WorkflowService.get_workflow_by_id(workflow_id, request.user)
            if workflow is None:
                return JsonResponse({
                    "code": 404,
                    "message": "工作流不存在"
                }, status=404)
            
            body = json.loads(request.body)
            workflow = WorkflowService.update_workflow(workflow, body)
            
            return JsonResponse({
                "code": 200,
                "data": workflow.to_dict()
            })
        except json.JSONDecodeError:
            return JsonResponse({
                "code": 400,
                "message": "请求体格式错误，请提供有效的 JSON 格式"
            }, status=400)
        except Exception as e:
            return JsonResponse({
                "code": 500,
                "message": f"更新工作流失败: {str(e)}"
            }, status=500)
    
    elif request.method == 'DELETE':
        try:
            workflow = WorkflowService.get_workflow_by_id(workflow_id, request.user)
            if workflow is None:
                return JsonResponse({
                    "code": 404,
                    "message": "工作流不存在"
                }, status=404)
            
            WorkflowService.delete_workflow(workflow)
            
            return JsonResponse({
                "code": 200,
                "message": "删除成功"
            })
        except Exception as e:
            return JsonResponse({
                "code": 500,
                "message": f"删除工作流失败: {str(e)}"
            }, status=500)
    
    else:
        return JsonResponse({
            "code": 405,
            "message": "方法不允许"
        }, status=405)


@login_required_401
def create_workflow(request):
    """
    创建新的工作流
    POST /api/workflow/create
    """
    if request.method != 'POST':
        return JsonResponse({
            "code": 405,
            "message": "方法不允许"
        }, status=405)
    
    try:
        body = json.loads(request.body)
        
        name = body.get('name')
        if not name:
            return JsonResponse({
                "code": 400,
                "message": "工作流名称不能为空"
            }, status=400)
        
        workflow = WorkflowService.create_workflow(request.user, body)
        
        return JsonResponse({
            "code": 200,
            "data": workflow.to_dict()
        })
    except json.JSONDecodeError:
        return JsonResponse({
            "code": 400,
            "message": "请求体格式错误，请提供有效的 JSON 格式"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "code": 500,
            "message": f"创建工作流失败: {str(e)}"
        }, status=500)


@login_required_401
def execute_workflow(request):
    """
    启动工作流执行
    POST /api/workflow/execute
    """
    if request.method != 'POST':
        return JsonResponse({
            "code": 405,
            "message": "方法不允许"
        }, status=405)
    
    try:
        body = json.loads(request.body)
        
        workflow_id = body.get('workflowId')
        workflow_snapshot = body.get('workflowSnapshot')
        
        if not workflow_id:
            return JsonResponse({
                "code": 400,
                "message": "workflowId 参数是必需的"
            }, status=400)
        
        if not workflow_snapshot:
            return JsonResponse({
                "code": 400,
                "message": "workflowSnapshot 参数是必需的"
            }, status=400)
        
        variables = body.get('variables', {})
        
        execution = ExecutionService.create_execution(
            request.user,
            workflow_id,
            workflow_snapshot,
            variables
        )
        
        execution = ExecutionService.start_execution(execution)
        
        return JsonResponse({
            "code": 200,
            "data": {
                "executionId": execution.id
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({
            "code": 400,
            "message": "请求体格式错误，请提供有效的 JSON 格式"
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "code": 500,
            "message": f"执行工作流失败: {str(e)}"
        }, status=500)


@login_required_401
def get_execution_status(request, execution_id):
    """
    获取执行实例的当前状态（轮询接口）
    GET /api/workflow/execution/{executionId}
    """
    try:
        execution = ExecutionService.get_execution_by_id(execution_id, request.user)
        if execution is None:
            return JsonResponse({
                "code": 404,
                "message": "执行实例不存在"
            }, status=404)
        
        return JsonResponse({
            "code": 200,
            "data": execution.to_dict()
        })
    except Exception as e:
        return JsonResponse({
            "code": 500,
            "message": f"获取执行状态失败: {str(e)}"
        }, status=500)


@login_required_401
def get_execution_logs(request, execution_id):
    """
    获取执行实例的完整日志
    GET /api/workflow/execution/{executionId}/logs
    """
    try:
        execution = ExecutionService.get_execution_by_id(execution_id, request.user)
        if execution is None:
            return JsonResponse({
                "code": 404,
                "message": "执行实例不存在"
            }, status=404)
        
        return JsonResponse({
            "code": 200,
            "data": execution.logs
        })
    except Exception as e:
        return JsonResponse({
            "code": 500,
            "message": f"获取执行日志失败: {str(e)}"
        }, status=500)


@login_required_401
def cancel_execution(request, execution_id):
    """
    取消正在执行的工作流
    POST /api/workflow/execution/{executionId}/cancel
    """
    if request.method != 'POST':
        return JsonResponse({
            "code": 405,
            "message": "方法不允许"
        }, status=405)
    
    try:
        execution = ExecutionService.get_execution_by_id(execution_id, request.user)
        if execution is None:
            return JsonResponse({
                "code": 404,
                "message": "执行实例不存在"
            }, status=404)
        
        success = ExecutionService.cancel_execution(execution)
        
        if success:
            return JsonResponse({
                "code": 200,
                "data": {
                    "status": "cancelled",
                    "message": "执行已取消"
                }
            })
        else:
            return JsonResponse({
                "code": 400,
                "message": "无法取消当前状态的执行"
            }, status=400)
    except Exception as e:
        return JsonResponse({
            "code": 500,
            "message": f"取消执行失败: {str(e)}"
        }, status=500)


@login_required_401
def pause_execution(request, execution_id):
    """
    暂停正在执行的工作流
    POST /api/workflow/execution/{executionId}/pause
    """
    if request.method != 'POST':
        return JsonResponse({
            "code": 405,
            "message": "方法不允许"
        }, status=405)
    
    try:
        execution = ExecutionService.get_execution_by_id(execution_id, request.user)
        if execution is None:
            return JsonResponse({
                "code": 404,
                "message": "执行实例不存在"
            }, status=404)
        
        success = ExecutionService.pause_execution(execution)
        
        if success:
            return JsonResponse({
                "code": 200,
                "data": {
                    "status": "paused",
                    "message": "执行已暂停"
                }
            })
        else:
            return JsonResponse({
                "code": 400,
                "message": "无法暂停当前状态的执行"
            }, status=400)
    except Exception as e:
        return JsonResponse({
            "code": 500,
            "message": f"暂停执行失败: {str(e)}"
        }, status=500)


@login_required_401
def resume_execution(request, execution_id):
    """
    恢复已暂停的工作流
    POST /api/workflow/execution/{executionId}/resume
    """
    if request.method != 'POST':
        return JsonResponse({
            "code": 405,
            "message": "方法不允许"
        }, status=405)
    
    try:
        execution = ExecutionService.get_execution_by_id(execution_id, request.user)
        if execution is None:
            return JsonResponse({
                "code": 404,
                "message": "执行实例不存在"
            }, status=404)
        
        success = ExecutionService.resume_execution(execution)
        
        if success:
            return JsonResponse({
                "code": 200,
                "data": {
                    "status": "running",
                    "message": "执行已恢复"
                }
            })
        else:
            return JsonResponse({
                "code": 400,
                "message": "无法恢复当前状态的执行"
            }, status=400)
    except Exception as e:
        return JsonResponse({
            "code": 500,
            "message": f"恢复执行失败: {str(e)}"
        }, status=500)


@login_required_401
def get_execution_history(request):
    """
    获取执行历史记录
    GET /api/workflow/history
    """
    try:
        workflow_id = request.GET.get('workflowId', None)
        executions = ExecutionService.get_user_executions(request.user, workflow_id)
        
        return JsonResponse({
            "code": 200,
            "data": executions
        })
    except Exception as e:
        return JsonResponse({
            "code": 500,
            "message": f"获取执行历史失败: {str(e)}"
        }, status=500)
