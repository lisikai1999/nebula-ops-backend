from django.urls import path
from . import views

urlpatterns = [
    path('list', views.get_workflow_list, name='workflow_list'),
    path('create', views.create_workflow, name='workflow_create'),
    path('history', views.get_execution_history, name='execution_history'),
    path('execute', views.execute_workflow, name='workflow_execute'),
    
    path('execution/<str:execution_id>', views.get_execution_status, name='execution_status'),
    path('execution/<str:execution_id>/logs', views.get_execution_logs, name='execution_logs'),
    path('execution/<str:execution_id>/cancel', views.cancel_execution, name='execution_cancel'),
    path('execution/<str:execution_id>/pause', views.pause_execution, name='execution_pause'),
    path('execution/<str:execution_id>/resume', views.resume_execution, name='execution_resume'),
    
    path('<str:workflow_id>', views.workflow_detail, name='workflow_detail'),
]
