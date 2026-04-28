"""OperationAndMaintenancePlatform URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('userManage', views.userManage, name='aws_user_list'),
    path('logDownLoad', views.logDownLoad, name='logDownLoad'),
    path('ecsInfo', views.ecsInfo, name='ecsInfo'),

    path('login', views.custom_login, name='custom_login'),

    path('route_path', views.route_path, name='route_path'),
    path('get_zones', views.list_zone, name='route_path'),
    path('download', views.download, name='download'),
    path('get_ecs_info', views.get_ecs_info, name='get_ecs_info'),
    path('describe_ecs_taskdefine', views.describe_ecs_taskdefine, name='describe_ecs_taskdefine'),
    path('get_env_group', views.get_env_group, name='get_env_group'),
    path('get_user_info', views.get_user_info, name='get_user_info'),
    path('reset_password/<str:id>', views.reset_password, name='reset_password'),
    path('disable_console/<str:id>', views.disable_console, name='disable_console'),
    path('get_cloudwatch_IncomingBytes', views.get_cloudwatch_IncomingBytes, name='get_cloudwatch_IncomingBytes'),
    
    path('athena/environments', views.get_athena_environments, name='athena_environments'),
    path('athena/databases', views.get_athena_databases, name='athena_databases'),
    path('athena/tables', views.get_athena_tables, name='athena_tables'),
    path('athena/query', views.execute_athena_query, name='athena_query'),
    path('athena/query_status', views.get_athena_query_status, name='athena_query_status'),
    
    path('environments', views.environments_list, name='environments_list'),
    path('environments/<int:env_id>', views.environments_detail, name='environments_detail'),
    path('environments/<int:env_id>/set-default', views.set_default_environment, name='set_default_environment'),
]
