import json
import uuid
import time
import threading
from datetime import datetime
from django.db import models
from django.contrib.auth.models import User


WORKFLOW_STATUS_CHOICES = [
    ('idle', '空闲'),
    ('running', '执行中'),
    ('paused', '已暂停'),
    ('completed', '已完成'),
    ('failed', '执行失败'),
    ('cancelled', '已取消'),
]

STEP_STATUS_CHOICES = [
    ('pending', '等待执行'),
    ('running', '执行中'),
    ('completed', '已完成'),
    ('failed', '执行失败'),
    ('skipped', '已跳过'),
]


def generate_workflow_id():
    return f"workflow_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def generate_execution_id():
    return f"exec_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def format_datetime(dt):
    if dt is None:
        return None
    return dt.isoformat() + 'Z' if dt.tzinfo else dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')


class Workflow(models.Model):
    id = models.CharField(max_length=100, primary_key=True, default=generate_workflow_id)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    template_id = models.CharField(max_length=100, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workflows')
    steps = models.JSONField(default=list)
    variables = models.JSONField(default=dict)
    triggers = models.JSONField(default=list)
    settings = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=1)

    class Meta:
        ordering = ['-created_at']

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'templateId': self.template_id,
            'steps': self.steps,
            'variables': self.variables,
            'triggers': self.triggers,
            'settings': self.settings or {
                'maxRetries': 3,
                'retryDelay': 1000,
                'timeout': 300000
            },
            'createdAt': format_datetime(self.created_at),
            'updatedAt': format_datetime(self.updated_at),
            'version': self.version,
        }


class Execution(models.Model):
    id = models.CharField(max_length=100, primary_key=True, default=generate_execution_id)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='executions', null=True)
    workflow_id_str = models.CharField(max_length=100)
    workflow_snapshot = models.JSONField(default=dict)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='executions')
    status = models.CharField(max_length=20, choices=WORKFLOW_STATUS_CHOICES, default='idle')
    variables = models.JSONField(default=dict)
    step_results = models.JSONField(default=dict)
    step_statuses = models.JSONField(default=dict)
    logs = models.JSONField(default=list)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    saved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def add_log(self, log_type, message, step_id=None, workflow_id=None, workflow_name=None):
        log_entry = {
            'type': log_type,
            'message': message,
            'timestamp': format_datetime(datetime.now()),
        }
        if step_id:
            log_entry['stepId'] = step_id
        if workflow_id:
            log_entry['workflowId'] = workflow_id
        if workflow_name:
            log_entry['workflowName'] = workflow_name
        
        self.logs.append(log_entry)
        self.save(update_fields=['logs'])

    def to_dict(self):
        return {
            'id': self.id,
            'workflowId': self.workflow_id_str,
            'workflowSnapshot': self.workflow_snapshot,
            'status': self.status,
            'variables': self.variables,
            'stepResults': self.step_results,
            'stepStatuses': self.step_statuses,
            'logs': self.logs[-100:] if len(self.logs) > 100 else self.logs,
            'startTime': format_datetime(self.start_time),
            'endTime': format_datetime(self.end_time),
            'error': self.error,
            'createdAt': format_datetime(self.created_at),
        }

    def to_history_dict(self):
        workflow_name = self.workflow_snapshot.get('name', '') if self.workflow_snapshot else ''
        return {
            'id': self.id,
            'workflowId': self.workflow_id_str,
            'workflowName': workflow_name,
            'status': self.status,
            'startTime': format_datetime(self.start_time),
            'endTime': format_datetime(self.end_time),
            'savedAt': format_datetime(self.saved_at or self.created_at),
        }


class WorkflowService:
    @staticmethod
    def get_user_workflows(user):
        workflows = Workflow.objects.filter(user=user)
        return [w.to_dict() for w in workflows]

    @staticmethod
    def get_workflow_by_id(workflow_id, user=None):
        try:
            workflow = Workflow.objects.get(id=workflow_id)
            if user and workflow.user != user:
                return None
            return workflow
        except Workflow.DoesNotExist:
            return None

    @staticmethod
    def create_workflow(user, data):
        workflow = Workflow(
            user=user,
            name=data.get('name', ''),
            description=data.get('description', ''),
            template_id=data.get('templateId'),
            steps=data.get('steps', []),
            variables=data.get('variables', {}),
            triggers=data.get('triggers', []),
            settings=data.get('settings', {
                'maxRetries': 3,
                'retryDelay': 1000,
                'timeout': 300000
            }),
        )
        workflow.save()
        return workflow

    @staticmethod
    def update_workflow(workflow, data):
        if 'name' in data:
            workflow.name = data['name']
        if 'description' in data:
            workflow.description = data['description']
        if 'steps' in data:
            workflow.steps = data['steps']
        if 'variables' in data:
            workflow.variables = data['variables']
        if 'settings' in data:
            workflow.settings = data['settings']
        if 'templateId' in data:
            workflow.template_id = data['templateId']
        workflow.version += 1
        workflow.save()
        return workflow

    @staticmethod
    def delete_workflow(workflow):
        workflow.delete()


class ExecutionService:
    @staticmethod
    def create_execution(user, workflow_id, workflow_snapshot, variables=None):
        try:
            workflow = Workflow.objects.get(id=workflow_id)
        except Workflow.DoesNotExist:
            workflow = None

        execution = Execution(
            workflow=workflow,
            workflow_id_str=workflow_id,
            workflow_snapshot=workflow_snapshot,
            user=user,
            status='idle',
            variables=variables or {},
            step_results={},
            step_statuses={},
            logs=[],
        )
        execution.save()
        return execution

    @staticmethod
    def get_execution_by_id(execution_id, user=None):
        try:
            execution = Execution.objects.get(id=execution_id)
            if user and execution.user != user:
                return None
            return execution
        except Execution.DoesNotExist:
            return None

    @staticmethod
    def get_user_executions(user, workflow_id=None):
        if workflow_id:
            executions = Execution.objects.filter(user=user, workflow_id_str=workflow_id)
        else:
            executions = Execution.objects.filter(user=user)
        return [e.to_history_dict() for e in executions]

    @staticmethod
    def start_execution(execution):
        execution.status = 'running'
        execution.start_time = datetime.now()
        
        workflow_name = execution.workflow_snapshot.get('name', '') if execution.workflow_snapshot else ''
        execution.add_log(
            'workflow_started',
            '工作流已提交到后端执行',
            workflow_id=execution.workflow_id_str,
            workflow_name=workflow_name
        )
        
        execution.save()
        
        thread = threading.Thread(target=ExecutionService._execute_workflow, args=(execution.id,))
        thread.daemon = True
        thread.start()
        
        return execution

    @staticmethod
    def _execute_workflow(execution_id):
        from django.utils import timezone
        
        try:
            execution = Execution.objects.get(id=execution_id)
        except Execution.DoesNotExist:
            return

        steps = execution.workflow_snapshot.get('steps', []) if execution.workflow_snapshot else []
        
        step_statuses = {}
        for step in steps:
            step_id = step.get('id')
            step_statuses[step_id] = {
                'status': 'pending',
                'startTime': None,
                'endTime': None,
                'retries': 0,
                'error': None,
            }
        execution.step_statuses = step_statuses
        execution.save()

        completed_steps = set()
        failed_steps = set()

        while True:
            ready_steps = []
            for step in steps:
                step_id = step.get('id')
                if step_id in completed_steps or step_id in failed_steps:
                    continue
                
                depends_on = step.get('dependsOn', [])
                all_deps_completed = all(dep in completed_steps for dep in depends_on)
                any_dep_failed = any(dep in failed_steps for dep in depends_on)
                
                if any_dep_failed:
                    execution.step_statuses[step_id]['status'] = 'skipped'
                    execution.add_log(
                        'info',
                        f"步骤 {step.get('name', step_id)} 已跳过: 依赖步骤失败",
                        step_id=step_id
                    )
                    failed_steps.add(step_id)
                    continue
                
                if all_deps_completed:
                    ready_steps.append(step)

            if not ready_steps:
                break

            for step in ready_steps:
                step_id = step.get('id')
                step_name = step.get('name', step_id)
                
                execution.step_statuses[step_id]['status'] = 'running'
                execution.step_statuses[step_id]['startTime'] = format_datetime(datetime.now())
                execution.add_log('info', f"开始执行步骤: {step_name}", step_id=step_id)
                execution.save()

                try:
                    result = ExecutionService._execute_step(step, execution)
                    
                    execution.step_statuses[step_id]['status'] = 'completed'
                    execution.step_statuses[step_id]['endTime'] = format_datetime(datetime.now())
                    execution.step_results[step_id] = result
                    execution.add_log('info', f"步骤 {step_name} 执行完成", step_id=step_id)
                    completed_steps.add(step_id)
                    
                except Exception as e:
                    execution.step_statuses[step_id]['status'] = 'failed'
                    execution.step_statuses[step_id]['endTime'] = format_datetime(datetime.now())
                    execution.step_statuses[step_id]['error'] = str(e)
                    execution.error = f"步骤 {step_name} 执行失败: {str(e)}"
                    execution.add_log('error', f"步骤 {step_name} 执行失败: {str(e)}", step_id=step_id)
                    failed_steps.add(step_id)
                
                execution.save()

        execution.end_time = datetime.now()
        execution.saved_at = datetime.now()
        
        if failed_steps:
            execution.status = 'failed'
            execution.add_log('error', '工作流执行失败')
        else:
            execution.status = 'completed'
            execution.add_log('info', '工作流执行完成')
        
        execution.save()

    @staticmethod
    def _execute_step(step, execution):
        action_type = step.get('actionType')
        config = step.get('config', {})
        
        variables = {}
        variables.update(execution.workflow_snapshot.get('variables', {}))
        variables.update(execution.variables)
        
        def replace_variables(value):
            if isinstance(value, str):
                import re
                pattern = r'\{\{(\w+)\}\}'
                def replace_match(match):
                    var_name = match.group(1)
                    return str(variables.get(var_name, match.group(0)))
                return re.sub(pattern, replace_match, value)
            elif isinstance(value, dict):
                return {k: replace_variables(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_variables(v) for v in value]
            return value
        
        config = replace_variables(config)
        
        if action_type == 'delay':
            delay_ms = config.get('delay', 1000)
            time.sleep(delay_ms / 1000.0)
            return {'delayed': delay_ms}
        
        elif action_type == 'webhook':
            import requests
            url = config.get('url')
            method = config.get('method', 'POST')
            headers = config.get('headers', {})
            payload = config.get('payload', {})
            timeout = config.get('timeout', 30000) / 1000.0
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=payload, timeout=timeout)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
            else:
                response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            
            return {
                'status_code': response.status_code,
                'response': response.text[:1000] if len(response.text) > 1000 else response.text,
            }
        
        elif action_type == 'jenkins_execute':
            return {
                'status': 'simulated',
                'message': 'Jenkins 执行模拟完成',
                'buildNumber': 1,
            }
        
        elif action_type == 'aws_ecs_check':
            return {
                'status': 'simulated',
                'message': 'ECS 检查模拟完成',
                'runningCount': 2,
            }
        
        elif action_type == 'wework_notification':
            return {
                'status': 'simulated',
                'message': '企业微信通知模拟发送',
            }
        
        elif action_type == 'custom_action':
            return {
                'status': 'simulated',
                'message': '自定义动作模拟执行',
            }
        
        else:
            return {
                'status': 'simulated',
                'message': f'未知动作类型: {action_type}',
            }

    @staticmethod
    def cancel_execution(execution):
        if execution.status in ['running', 'idle']:
            execution.status = 'cancelled'
            execution.end_time = datetime.now()
            execution.add_log('info', '执行已被取消')
            execution.save()
            return True
        return False

    @staticmethod
    def pause_execution(execution):
        if execution.status == 'running':
            execution.status = 'paused'
            execution.add_log('info', '执行已暂停')
            execution.save()
            return True
        return False

    @staticmethod
    def resume_execution(execution):
        if execution.status == 'paused':
            execution.status = 'running'
            execution.add_log('info', '执行已恢复')
            execution.save()
            
            thread = threading.Thread(target=ExecutionService._execute_workflow, args=(execution.id,))
            thread.daemon = True
            thread.start()
            
            return True
        return False
