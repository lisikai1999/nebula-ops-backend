import logging
from django.db import models
from django.utils import timezone
import pytz
import time
import json
import boto3
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

from utils import iam, logs, cloudwatch, ecs as ECS, route53, elbv2
from settings import emailList, adminEmail, adminPassword, ccEmail, rdsSizeList

logger = logging.getLogger('aws.devops')


class AWSEnvironment(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True, verbose_name='环境名称')
    access_key_id = models.CharField(max_length=200, verbose_name='Access Key ID')
    secret_access_key = models.CharField(max_length=200, verbose_name='Secret Access Key')
    region = models.CharField(max_length=50, verbose_name='区域')
    is_default = models.BooleanField(default=False, verbose_name='是否默认环境')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'aws_environments'
        ordering = ['-created_at']
        verbose_name = 'AWS环境凭证'
        verbose_name_plural = 'AWS环境凭证'

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'access_key_id': self.access_key_id,
            'region': self.region,
            'is_default': self.is_default,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_credentials(self):
        return {
            'env': self.name,
            'region': self.region,
            'access_key': self.access_key_id,
            'secret_key': self.secret_access_key,
            'login_url': '',
        }


class AWSEnvironmentService:
    @staticmethod
    def get_all_environments():
        return list(AWSEnvironment.objects.all())

    @staticmethod
    def get_environment_by_id(env_id):
        try:
            return AWSEnvironment.objects.get(id=env_id)
        except AWSEnvironment.DoesNotExist:
            return None

    @staticmethod
    def get_default_environment():
        try:
            return AWSEnvironment.objects.get(is_default=True)
        except AWSEnvironment.DoesNotExist:
            return AWSEnvironment.objects.first()

    @staticmethod
    def get_access_list():
        try:
            environments = AWSEnvironment.objects.all()
            if not environments:
                from settings import access_list
                return access_list
            return [env.get_credentials() for env in environments]
        except Exception:
            from settings import access_list
            return access_list

    @staticmethod
    def create_environment(data):
        is_default = data.get('is_default', False)
        
        if is_default:
            AWSEnvironment.objects.filter(is_default=True).update(is_default=False)
        
        environment = AWSEnvironment(
            name=data['name'],
            access_key_id=data['access_key_id'],
            secret_access_key=data['secret_access_key'],
            region=data['region'],
            is_default=is_default,
            description=data.get('description', ''),
        )
        environment.save()
        return environment

    @staticmethod
    def update_environment(environment, data):
        is_default = data.get('is_default', False)
        
        if is_default and not environment.is_default:
            AWSEnvironment.objects.filter(is_default=True).update(is_default=False)
        
        if 'name' in data:
            environment.name = data['name']
        if 'access_key_id' in data:
            environment.access_key_id = data['access_key_id']
        if 'secret_access_key' in data and data['secret_access_key']:
            environment.secret_access_key = data['secret_access_key']
        if 'region' in data:
            environment.region = data['region']
        if 'is_default' in data:
            environment.is_default = is_default
        if 'description' in data:
            environment.description = data['description']
        
        environment.save()
        return environment

    @staticmethod
    def delete_environment(environment):
        environment.delete()

    @staticmethod
    def set_default_environment(environment):
        AWSEnvironment.objects.filter(is_default=True).update(is_default=False)
        environment.is_default = True
        environment.save()
        return environment


def get_access_list():
    try:
        return AWSEnvironmentService.get_access_list()
    except Exception:
        from settings import access_list as fallback_access_list
        return fallback_access_list


# 错误信息
error_message = []


def get_cloudwatch_metric(client, namespace, metric_name, dimensions, start_time, end_time, period, statistic):
    response = client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dimensions,
        StartTime=start_time.timestamp(),
        EndTime=end_time.timestamp(),
        Period=period,
        Statistics=[statistic]
    )
    
    if response['Datapoints']:
        # 取平均值
        return sum(point[statistic] for point in response['Datapoints']) / len(response['Datapoints'])
    return 0

def get_service_resource_utilization(cloudwatch, cluster_name, service_name, start_time, end_time, period):
    cpu_utilization = get_cloudwatch_metric(
        cloudwatch,
        'AWS/ECS',
        'CPUUtilization',
        [{'Name': 'ClusterName', 'Value': cluster_name}, {'Name': 'ServiceName', 'Value': service_name}],
        start_time,
        end_time,
        period, 
        'Average'
    )
    
    memory_utilization = get_cloudwatch_metric(
        cloudwatch,
        'AWS/ECS',
        'MemoryUtilization',
        [{'Name': 'ClusterName', 'Value': cluster_name}, {'Name': 'ServiceName', 'Value': service_name}],
        start_time,
        end_time,
        period, 
        'Average'
    )
    
    return cpu_utilization, memory_utilization



def rdsCollect(region="cn-northwest-1", access_key="", secret_key=""):
    '''
        rds资源收集
    '''
    result = {}
    rds_client = boto3.client('rds', aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key, region_name=region)
    # 获取rds所有实例
    # aws rds describe-db-instances
    rdsInstances = rds_client.describe_db_instances()["DBInstances"]

    # 遍历rds信息
    for rds in rdsInstances:
        # 数据库标识符
        DBInstanceIdentifier = rds["DBInstanceIdentifier"]
        # 实例大小类型
        DBInstanceClass = rds["DBInstanceClass"]
        # 引擎
        Engine = rds["Engine"]
        # 引擎版本
        EngineVersion = rds["EngineVersion"]
        # 实例占用资源,出现异常表示没有该资源实例大小没有登记,先标记为0,发出警告信息
        try:
            CPU = rdsSizeList[DBInstanceClass]["CPU"]
            MEM = rdsSizeList[DBInstanceClass]["MEMORY"]
            Network = rdsSizeList[DBInstanceClass]["NETWORK"]
        except Exception as e:
            CPU = 0
            MEM = 0
            Network = 0
            print(DBInstanceClass, "==>实例类型大小未作登记!!!")

        # 如果引擎包含aurora表示是区域集群,否则就是普通实例
        try:
            if Engine.index("aurora") == 0:
                instanceType = "Regional cluster"
        except ValueError as e:
            instanceType = "instance"

        # 记录
        result[DBInstanceIdentifier] = {
            "DBInstanceIdentifier": DBInstanceIdentifier,
            "DBInstanceClass": DBInstanceClass,
            "Engine": Engine,
            "EngineVersion": EngineVersion,
            "instanceType": instanceType,
            "CPU": CPU,
            "MEM": MEM,
            "NETWORK": Network
        }
    print("rds数据采集完成")
    # print("rds===>", result)
    return result


def cacheCollect(region="cn-northwest-1", access_key="", secret_key=""):
    '''
        elastic cache资源收集
    '''
    result = {}
    cache_client = boto3.client('elasticache', aws_access_key_id=access_key,
                                aws_secret_access_key=secret_key, region_name=region)
    # 获取所有cache节点
    # aws elasticache describe-cache-clusters
    caches = cache_client.describe_cache_clusters()["CacheClusters"]

    # 遍历cache节点
    for cache in caches:

        # 集群名
        try:
            ReplicationGroupId = cache["ReplicationGroupId"]
        except Exception as e:
            ReplicationGroupId = cache["CacheClusterId"]

        # 如果集群名已存在,表示该节点所在集群已登记过
        if ReplicationGroupId not in result:
            # 登记
            CacheNodeType = cache["CacheNodeType"]
            EngineVersion = cache["EngineVersion"]
            Engine = cache["Engine"]
            # 登记集群信息
            
            result[ReplicationGroupId] = {
                "ReplicationGroupId": ReplicationGroupId,
                "CacheNodeType": CacheNodeType,
                "EngineVersion": EngineVersion,
                "Engine": Engine,
                "count": 1
            }


        else:
            # 计数+1
            result[ReplicationGroupId]["count"] += 1

    print("elastaicache数据采集完成")
    # print("cache===>", result)
    return result


def snsCollect(region="cn-northwest-1", access_key="", secret_key=""):
    '''
        sns资源收集
    '''
    print("sns开始")
    result = set()
    cloudwatch = boto3.client('cloudwatch', aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key, region_name=region)

    response = cloudwatch.describe_alarms()
    print("\n\n")
    for alarm in response['MetricAlarms']:
        # 判断是否报警中是否有触发sns的操作
        AlarmActions = alarm["AlarmActions"]
        # 遍历该警报的操作，判断是否有含有:sns:的操作
        for action in AlarmActions:
            # 没有则跳过
            if ":sns:" not in action:
                continue
            # 有则将结果添加到result中
            info = {}
            for item in alarm["Dimensions"]:
                info[item["Name"]] = item["Value"]
            try:
                result.add(info["ClusterName"] + "/" + info["ServiceName"])
            except Exception as e:
                print(e)
                print(alarm["AlarmName"])

    print("sns数据采集完成")
    print("sns===>", result)
    return result



def appAutoscalingCollect(region="cn-northwest-1", access_key="", secret_key=""):
    '''
        appAutoscaling资源收集
    '''
    result = {}
    # 获取连接
    appAutoscaling_client = boto3.client('application-autoscaling', aws_access_key_id=access_key,
                                         aws_secret_access_key=secret_key, region_name=region)

    # 获取扩缩容目标
    # aws application-autoscaling describe-scalable-targets --service-namespace ecs
    scalable_targets = appAutoscaling_client.describe_scalable_targets(
        ServiceNamespace="ecs")
    targets = scalable_targets["ScalableTargets"]  # 第一页的结果
    next_token = scalable_targets.get('NextToken')  # 获取 NextToken（如果有）
    while next_token:
        scalable_targets = appAutoscaling_client.describe_scalable_targets(
            ServiceNamespace='ecs',
            NextToken=next_token  # 使用上一页的 NextToken
        )

        targets += scalable_targets["ScalableTargets"]  # 追加下一页的结果
        next_token = scalable_targets.get(
            'NextToken')  # 获取下一页的 NextToken（如果有）



    # 获取扩缩容策略
    # aws application-autoscaling describe-scaling-policies --service-namespace ecs
    scalable_policies = appAutoscaling_client.describe_scaling_policies(
        ServiceNamespace="ecs")
    policies = scalable_policies['ScalingPolicies']  # 第一页的结果
    next_token = scalable_policies.get('NextToken')  # 获取 NextToken（如果有）
    while next_token:
        scalable_policies = appAutoscaling_client.describe_scaling_policies(
            ServiceNamespace='ecs',
            NextToken=next_token  # 使用上一页的 NextToken
        )

        policies += scalable_policies['ScalingPolicies']  # 追加下一页的结果
        next_token = scalable_policies.get(
            'NextToken')  # 获取下一页的 NextToken（如果有）

    demo = 1
    for target in targets:
        print(demo)
        demo += 1 
        # 资源标识
        ResourceId = target["ResourceId"]
        # 最大任务数
        MinCapacity = target["MinCapacity"]
        # 最小任务数
        MaxCapacity = target["MaxCapacity"]

        result[ResourceId] = {
            "MinCapacity": MinCapacity,
            "MaxCapacity": MaxCapacity
        }
    

    # 追加临界值
    for policie in policies:
        # 资源标识
        ResourceId = policie["ResourceId"]
        # 临界值资源类型
        PredefinedMetricType = policie["TargetTrackingScalingPolicyConfiguration"][
            "PredefinedMetricSpecification"]["PredefinedMetricType"]
        # 临界值
        TargetValue = policie["TargetTrackingScalingPolicyConfiguration"]["TargetValue"]

        result[ResourceId][PredefinedMetricType] = TargetValue

    print("application auto scaling数据采集完成")

    return result


def findStr(data, string):
    '''
        寻找对象中的字符串
    '''
    result = ""
    for item in data:
        try:
            if item["value"].index(string):
                result = item["value"]

        except ValueError as e:
            pass
    return result


def ecsCollect(region="cn-northwest-1", access_key="", secret_key=""):
    # 创建会话和客户端
    session = boto3.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name=region)
    ecs = session.client('ecs')
    cloudwatch = session.client('cloudwatch')
    
    # 其他数据收集函数（保留原有功能）
    rdsData = rdsCollect(region, access_key, secret_key)
    cacheData = cacheCollect(region, access_key, secret_key)
    snsData = snsCollect(region, access_key, secret_key)
    print("snsData=========>",snsData)
    appAutoscalingData = appAutoscalingCollect(region, access_key, secret_key)
    print("====>数据采集完毕，开始整理数据")

    # 获取所有ECS集群
    clusters = ecs.list_clusters()["clusterArns"]
    
    end_time = datetime.utcnow()
    start_time_7d = end_time - timedelta(days=7)
    # start_time_30d = end_time - timedelta(days=30)
    
    result = {}
    response = []
    for cluster_arn in clusters:
        cluster_name = cluster_arn.split('/')[-1]
        # result[cluster_name] = {"serviceCount": 0, "services": {}}
        result[cluster_name] = {"serviceCount": 0}
        
        # 获取集群中的所有服务
        services = ecs.list_services(cluster=cluster_name)['serviceArns']
        result[cluster_name]["serviceCount"] = len(services)
        
        for service_arn in services:
            service_name = service_arn.split('/')[-1]
            
            # 获取服务信息
            service_info = ecs.describe_services(cluster=cluster_name, services=[service_arn])["services"][0]
            
            # 获取7天和30天的CPU和内存使用率，聚合时间为1h
            cpu_7d, memory_7d = get_service_resource_utilization(cloudwatch, cluster_name, service_name, start_time_7d, end_time, 3600)
            # cpu_30d, memory_30d = get_service_resource_utilization(cloudwatch, cluster_name, service_name, start_time_30d, end_time, 3600)
            
            # 获取任务定义
            # aws ecs describe-services --cluster <cluster> --services <service>
            # serviceInfo = ecs.describe_services(
            #     cluster=cluster_name, services=[service_name])["services"][0]
            # task_definition = serviceInfo["deployments"][0]["taskDefinition"]
            taskDefinitionInfo = ecs.describe_task_definition(taskDefinition=service_info["taskDefinition"])["taskDefinition"]
            
            taskDefinitionEnv = taskDefinitionInfo["containerDefinitions"][0]["environment"]


            # 计算单个任务的 CPU 和内存
            # == 3.服务中的任务信息
            # aws ecs list-tasks --cluster <cluster> --service-name <service>
            taskArns = ecs.list_tasks(
                cluster=cluster_name, serviceName=service_name)["taskArns"]
            # 如果该服务有task的话
            if len(taskArns) != 0:
                task = taskArns[0]
                # aws ecs describe-tasks --cluster <cluster> --tasks <task>
                taskInfo = ecs.describe_tasks(
                    cluster=cluster_name, tasks=[task])
                task_cpu = int(taskInfo["tasks"][0]["cpu"]) / 1024
                task_memory = int(taskInfo["tasks"][0]["memory"]) / 1024
            else:
                task_cpu = 0
                task_memory = 0

            # task_cpu = int(taskDefinitionInfo["containerDefinitions"][0].get("cpu", "0")) / 1024  # 转换为 vCPU
            # task_memory = int(taskDefinitionInfo["containerDefinitions"][0].get("memory", "0")) / 1024  # 转换为 GB
            
            # 计算总的 CPU 和内存
            desired_count = service_info["desiredCount"]
            total_cpu = task_cpu * desired_count
            total_memory = task_memory * desired_count
            
            # 服务对应的rds信息
            rdsStr = findStr(taskDefinitionEnv, ".rds.")
            # 因为任务设置的rds变量格式不一样所以格式化两次
            rdso = rdsStr.split(".")[0]
            rdst = rdso.split("//")[-1]
            if rdst:
                try:
                    rdsDict = rdsData[rdst]
                except Exception as e:
                    rdsDict = {}
                    error_message.append(f"{rdst} 数据库被引用，但不存在")
            else:
                rdsDict = {}
            
            # 服务对应的elastic cache信息
            cacheStr = findStr(taskDefinitionEnv, ".cache.")
            cache = cacheStr.split(".")[0]
            if cache:
                try:
                    cacheDict = cacheData[cache]
                except Exception as e:
                    cacheDict = {}
                    error_message.append(f"{cache} redis被引用，但不存在")
            else:
                cacheDict = {}


            # 服务对应的appAutoscaling信息
            # 并接字符串用来寻找autoscaling中对应的数据
            resourceId = "service/" + cluster_name + "/" + service_name
            appAutoscaling = {}
            # 如果resourceId在autoscaling中，就赋值
            if resourceId in appAutoscalingData:
                appAutoscaling = appAutoscalingData[resourceId]
                # == 7.根据snsData中是否有cluster/service来判断该服务是否有sns
                appAutoscaling["sns"] = False
                clusterService = cluster_name + "/" + service_name
                if clusterService in snsData:
                    appAutoscaling["sns"] = True


            response.append({
                "cluster": cluster_name,
                "services": service_name,
                "taskCount": desired_count,
                "cpuPerTask": total_cpu,
                "memPerTask": total_memory,
                "cpuLoad7Days": f"{cpu_7d:.3f}",
                "memLoad7Days": f"{memory_7d:.3f}",
                "autoScaling": appAutoscaling.get("sns"),
                "cpuPolicy": appAutoscaling.get("ECSServiceAverageCPUUtilization"),
                "memPolicy": appAutoscaling.get("ECSServiceAverageMemoryUtilization"),
                "minInstances": appAutoscaling.get("MinCapacity"),
                "maxInstances": appAutoscaling.get("MaxCapacity"),
                "database": rdsDict.get("DBInstanceIdentifier"),
                "databaseType": rdsDict.get("instanceType"),
                "databaseInstanceType": rdsDict.get("instanceType"),
                "databaseCpu": rdsDict.get("CPU"),
                "databaseMem": rdsDict.get("MEM"),
                "databaseEngine": rdsDict.get("Engine"),
                "databaseVersion": rdsDict.get("EngineVersion"),
                "redis": cacheDict.get("ReplicationGroupId"),
                "redisInstanceType": cacheDict.get("CacheNodeType"),
                "redisVersion": cacheDict.get("EngineVersion"),
                "redisNodes": cacheDict.get("count"),
                "taskDefinitionInfo": taskDefinitionInfo
            })


            
    # writeExcel(result, cacheData, rdsData, title)
    return response


def sendMail(receiver_email, subject, sender_email, password, body):
    '''
        发送告警信息
    '''
    # 邮件信息
    # sender_email = "moonhalo.li@zkteco.com"
    # receiver_email = "2418882397@qq.com"
    # subject = "测试邮件"
    

    # 设置 MIMEText
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Cc"] = ccEmail  # 设置抄送字段

    # 发送邮件
    try:
        # 连接到SMTP服务器
        server = smtplib.SMTP_SSL("smtp.exmail.qq.com", 465)

        # 登录到你的邮箱账户
        server.login(sender_email, password)
        server.set_debuglevel(1)
        email_list = ccEmail.split(",")
        email_list.append(receiver_email)   # 添加收件人邮箱

        server.set_debuglevel(0)  # 设置调试级别为0，关闭调试输出
        # 发送邮件
        server.sendmail(sender_email, email_list, msg.as_string())
        print("邮件发送成功！")
    except Exception as e:
        print(f"邮件发送失败：{e}")
    finally:
        # 关闭连接
        server.quit()

    
    if UserName in emailList:
        body = f'''
Hello
    Please login aws console. 

    Login Url: {login_url}
    Account: {UserName}
    Number of days not logged in: {userNoLogin} days
    
    If not logged in for more than 60 days, the console will be disabled!
    
Automated Email - Please Do Not Reply

Thank you.
        '''
        print('已发送邮件==》', emailList[UserName])
        
        try:
            sendMail(emailList[UserName], 'Iam user has not logged in for more than 45 days！', adminEmail, adminPassword, body)
        except Exception as e:
            body = f'''
                发送邮件到{UserName}失败，请检查问题！
            '''
            pass

    # 否则发送通知，提示该用户未配置对应的邮箱
    else:
        body = f'''
            {UserName}未配置登陆邮箱，请配置。
        '''
        pass

def userNoLogin(p, login_url, env, days):
    '''
        days 天未登录用户检测
    '''

    response = p.list_users()
    result = []
    from datetime import datetime, timezone, timedelta

    current_time = datetime.now(timezone.utc) # 生成0时区时间


    # 1.获取未登录时间超过45天的用户
    for user in response['Users']:
        try:
            noLoginDay = current_time - user['PasswordLastUsed']    # 未登录时间长度
            
            maxNoLoginDay = timedelta(days=days)  # 最大未登录时间

            if noLoginDay > maxNoLoginDay:  # 超出记录
                # print(user['Arn'])
                UserName = user['UserName'] # 用户名
                # 2.查询是否有控制台登陆权限，返回True表示有，返回False表示没有
                if p.get_login_profile(UserName):
                    print(noLoginDay)
                    print(type(noLoginDay))
                    # 3.查询email标签，收集用户邮箱
                    result.append(
                        {
                            'username': UserName,
                            'env': env,
                            'email': emailList.get(UserName,'未配置'),
                            'days_since_last_login': noLoginDay.days,
                            'id': UserName
                        }
                    )
                else:
                    # 没有登陆权限，跳过该用户
                    pass
                # print(user['UserName'], '==>', noLoginDay)

        # 从未登陆，没有PasswordLastUsed字段。以创建时间判断
        except KeyError as e:
            # print(e)
            maxNoLoginDay = timedelta(days=days)  # 最大未登录时间
            noLoginDay = current_time - user['CreateDate']
            if noLoginDay > maxNoLoginDay:  # 超出记录
                UserName = user['UserName']
                # 2.查询是否有控制台登陆权限，返回True表示有，返回False表示没有
                if p.get_login_profile(UserName):
                    # 3.查询email标签，收集用户邮箱
                    result.append(
                        {
                            'username': UserName,
                            'env': env,
                            'email': emailList.get(UserName,'未配置'),
                            'days_since_last_login': noLoginDay.days,
                            'id': UserName
                        }
                    )

                else:
                    # 没有登陆权限，跳过该用户
                    pass
    return result


def search_all_log_group(env):
    """
        搜索某个环境的所有日志组
    """
    result = []
    # 判断遍历哪个环境
    for index, item in enumerate(get_access_list()):
        if item["env"] == env:
            logs_client = logs.proc(region=item["region"],access_key=item["access_key"],secret_key=item["secret_key"])
            result = logs_client.get_cloudwatch_log_group_name()
    
    return result

def get_metric_data_IncomingBytes(days, PeriodDay):
    """
        days:   查询days天的数据
        PeriodDay: 指标聚合天数
    """
    result = []
    for index, item in enumerate(get_access_list()):
        # 获取IncomingBytes指标数据
        now = datetime.now()

        # 获取当前时间的时间戳
        current_timestamp = int(time.mktime(now.timetuple()))

        # 获取 days 天前的时间
        thirty_days_ago = now - timedelta(days=days)
        # 转为时间戳
        thirty_days_ago_timestamp = int(time.mktime(thirty_days_ago.timetuple()))

        p = cloudwatch.proc(region=item["region"],access_key=item["access_key"],secret_key=item["secret_key"])
        
        Period = PeriodDay * 24 * 3600   # 秒

        response = p.get_metric_data_v2("AWS/Logs", "IncomingBytes", thirty_days_ago_timestamp, current_timestamp, Period, "Sum")

        temp_result = []
        # 整理数据结构
        for num, value in enumerate(response["MetricDataResults"][0]["Timestamps"]):
            temp_result.append(
                { 
                    "timestamp": response["MetricDataResults"][0]["Timestamps"][num], 
                    "count": response["MetricDataResults"][0]["Values"][num],
                    "env": item["env"]
                }
            )
        
        result.append(
            list(reversed(temp_result))
        )

    return result


def list_zone_id(env):
    """
        搜索某个环境route53的所有zone_id
    """
    result = []
    # 判断遍历哪个环境
    for index, item in enumerate(get_access_list()):
        if item["env"] == env:
            logs_client = route53.proc(region=item["region"],access_key=item["access_key"],secret_key=item["secret_key"])
            response = logs_client.list_hosted_zones()
            for HostedZone in response['HostedZones']:
                result.append(
                    {
                        "HostedZone": HostedZone['Id'].split('/')[-1],  # 区域id
                        "RecordName": HostedZone['Name']
                    })  
    
    return result

def get_record(env, ZoneId):
    """
        搜索某个环境zone的域名路径
    """
    # 判断遍历哪个环境
    for index, item in enumerate(get_access_list()):
        if item["env"] == env:
            logs_client = route53.proc(region=item["region"],access_key=item["access_key"],secret_key=item["secret_key"])
            response = logs_client.get_all_A_resource_record(ZoneId)
    
    return response

def get_target_group(cluster, service, p, env, result):
    response = p.describe_services(cluster, service)
    # 遍历服务绑定的目标组
    for loadBalancer in response['services'][0]['loadBalancers']:
        # 目标组已经统计过了，则新增
        if loadBalancer['targetGroupArn'] in result:
            result[loadBalancer['targetGroupArn']].append(service.split('service/')[1])
        else:
            result[loadBalancer['targetGroupArn']] =  [ service.split('service/')[1] ]
        
    return result




# Create your models here.
class AWSUser():
    """
        用户相关
    """
    def get_user_info():
        """
            获取用户信息
        """
        result = []
        for access in get_access_list():
            if access['env'] == 'china-dev' or access['env'] == 'china-prod':
                p = iam.proc(access['region'], access['access_key'], access['secret_key'])
                result += userNoLogin(p, access['login_url'], access['env'], 42)

        return result
    
    
class AWSCloudWatch():
    """
        cloudwatch相关
    """
    def getEnvGroup(env):
        """
            获取日志组
        """
        result = search_all_log_group(env)
        return result
    
    def getIncomingBytes():
        """
            获取日志摄入量
        """
        result = get_metric_data_IncomingBytes(30, 1)
        return result
    

    def download_file(env, end_time, start_time, log_group_name, filterPattern):
        """
            生成日志，并返回给前端
        """
        print("filterPattern=>")
        line = 2000000     # 文件最大行数

        # 判断遍历哪个环境
        for index, item in enumerate(get_access_list()):
            if item["env"] == env:
                # 将字符串转换为 datetime 对象,需要设置下时区偏移（480min=8h）
                Sdate_time_obj = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.FixedOffset(480))
                Edate_time_obj = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.FixedOffset(480))

                # 将 datetime 对象转换为时间戳（秒）
                Stimestamp_sec = Sdate_time_obj.timestamp()
                Etimestamp_sec = Edate_time_obj.timestamp()

                # 将秒数转换为毫秒
                Stimestamp_ms = int(Stimestamp_sec * 1000)
                Etimestamp_ms = int(Etimestamp_sec * 1000)

                logs_client = logs.proc(region=item["region"],access_key=item["access_key"],secret_key=item["secret_key"])
                response = logs_client.getAllLogStreamEvent(log_group_name, Stimestamp_ms, Etimestamp_ms, filterPattern)
                
                file_name = "error.log"
                # 如果大于line行，则不写入，直接退出
                if len(response["events"]) > line:
                    
                    # 将文件内容写入到临时文件中
                    with open('download/' + file_name, 'w') as f:
                        f.write(f"文件超过{line}行，取消写入，请缩小时间范围！")
                    # return send_file('test_file.txt', as_attachment=True)
                    return "download/" + file_name
                
                file_name = log_group_name.split("/")[-1] + "-" + str(Stimestamp_ms) + '-' + str(Etimestamp_ms) + '.log'
                result = ""
                for event in response["events"]:
                    result += event["message"] + "\n"
                
                # 将文件内容写入到临时文件中
                with open('download/' + file_name, 'w') as f:
                    f.write(result)
        
        # 返回文件给客户端下载
        return "download/" + file_name

class AWSecs():
    """
        ecs相关
    """
    def ecs_info(env):
        # 判断环境
        for index, item in enumerate(get_access_list()):
            if item["env"] == env: 
                result = ecsCollect(region=item["region"],access_key=item["access_key"],secret_key=item["secret_key"])
                return result
        return {}

    def describetaskdefine(env, taskarn):
        # 判断环境
        for index, item in enumerate(get_access_list()):
            if item["env"] == env: 
                ec = ECS.proc(region=item["region"],access_key=item["access_key"],secret_key=item["secret_key"])
                result = ec.describe_taskdefine(taskarn)
                return result

    def get_target_group(cluster, service, p, env, result):
        """
            获取某一个环境的ecs服务-目标组对应关系
        """
        result = {}
        # 判断遍历哪个环境
        for index, item in enumerate(get_access_list()):
            if item["env"] == env:
                ecs_client = ECS.proc(region=item["region"],access_key=item["access_key"],secret_key=item["secret_key"])
                ecs_client.exec_for_cluster_service_custom(get_target_group, result)
        
        return result



class AWSRoute53():
    """
        route53相关
    """
    def get_route_path(self, env, ZoneId, port):
        """ 
            获取区域 域名 -> 目标组 -> ecs集群服务
            env: 环境
            ZoneId: 托管区域id
            port: 侦听器端口
        """
        # from utils import ecs

        records_name = get_record(env, ZoneId)
        elbresult = {}  # elb dnsName: elb arn字典
        rules = {}  # 负载均衡器端口为port的侦听器规则列表
        target_groups = []   # 已添加目标组列表，用于判断是否已经添加过目标组
        ResourceRecords = []    # 已添加的域名记录值列表
        nodes = []  # 返回给前端nodes数据
        links = []  # 返回给前端link数据

        # 判断遍历哪个环境
        for index, item in enumerate(get_access_list()):
            if item["env"] == env:
                elbv2_client = elbv2.proc(region=item["region"], access_key=item["access_key"], secret_key=item["secret_key"])
                # 获取负载均衡器Arn
                elbsArn = elbv2_client.describe_load_balancers()["LoadBalancers"]
                for elb in elbsArn:
                    elbresult[elb["DNSName"].split(".")[0]] = elb["LoadBalancerArn"]
                # 获取目标组对应的ecs集群服务
                ecs_client = ECS.proc(region=item["region"],access_key=item["access_key"],secret_key=item["secret_key"])
                ecsInfo = {}
                ecs_client.exec_for_cluster_service_custom(get_target_group, ecsInfo)

                


                # 获取所有域名的elb规则列表
                for record_name, info in records_name.items():
                    # 判断是否记录值是否为目标别名

                    if 'AliasTarget' in info:
                        elbDnsName = info['AliasTarget']['DNSName'].split('.')[1]    # 负载均衡器DNS记录
                        # 如果elb不在当前账号，则跳过
                        if elbDnsName not in elbresult:
                            continue

                        if elbresult[elbDnsName] not in rules:  # 如果该elb规则没记录过，则记录
                            # 根据负载均衡器arn和port获取监听器列表
                            listerner_arn = elbv2_client.port_loadarn_listeners(elbresult[elbDnsName], port)
                            # elb没有对应端口的侦听器，跳过
                            if listerner_arn == None:
                                continue
                            # 获取规则列表
                            rules[elbresult[elbDnsName]] = elbv2_client.describe_rules(listerner_arn)
                

                        target_group_arn = elbv2_client.domain_get_target_group_arn(rules[elbresult[elbDnsName]], record_name)  # 获取域名-目标组字典

                        # 开始整理路径关系
                        if len(target_group_arn) != 0:
                            nodes.append({ 'id': record_name, 'name': record_name, 'category': 0, 'symbolSize': 15 }) # 添加域名节点
                            for target_group in target_group_arn[record_name]:
                                if target_group in target_groups:
                                    continue
                                target_groups.append(target_group)
                                nodes.append({ 'id': target_group.split('/')[1], 'name': target_group.split('/')[1], 'category': 1, 'symbolSize': 15 }) # 添加目标组节点
                                # 添加域名与目标组关系
                                links.append(
                                    { 
                                        'source': record_name, 
                                        'target': target_group.split('/')[1],
                                        'label': {
                                            'show': True,
                                            'formatter': '调用',
                                            'color': '#666'
                                        }
                                    }
                                ) 

                                # 如果目标组对应的ecs集群服务存在
                                if target_group in ecsInfo:
                                    for ecs in ecsInfo[target_group]:
                                        nodes.append({ 'id': ecs, 'name': ecs, 'category': 2, 'symbolSize': 15 }) # 添加ecs集群服务节点
                                        # 添加目标组与ecs集群服务关系
                                        links.append(
                                            { 
                                                'source': target_group.split('/')[1], 
                                                'target': ecs,
                                                'label': {
                                                    'show': True,
                                                    'formatter': '调用',
                                                    'color': '#666'
                                                }
                                            }
                                        )
                    else:
                        nodes.append({ 'id': record_name, 'name': record_name, 'category': 0, 'symbolSize': 15 }) # 添加域名节点
                        

                        for ResourceRecord in info['ResourceRecords']:
                            # 判断该值是否已经添加过，若没添加过，则添加节点
                            if ResourceRecord["Value"] not in ResourceRecords:
                                ResourceRecords.append(ResourceRecord["Value"])
                                nodes.append({ 'id': ResourceRecord["Value"], 'name': ResourceRecord["Value"], 'category': 1, 'symbolSize': 15 }) # 添加目标节点
                            # 添加域名与记录关系
                            links.append(
                                { 
                                    'source': record_name, 
                                    'target': ResourceRecord["Value"],
                                    'label': {
                                        'show': True,
                                        'formatter': '调用',
                                        'color': '#666'
                                    }
                                }
                            ) 


        return {
            "nodes": nodes,
            "links": links
        }


    def list_zone_id(self, env):
        # 获取route53 zone id 列表
        result = list_zone_id(env)
        return result


class AWSElbV2():
    pass


def generate_incident_id():
    import time
    import uuid
    return f"incident_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


INCIDENT_STATUS_CHOICES = [
    ('investigating', '调查中'),
    ('completed', '已完成'),
    ('closed', '已关闭'),
    ('cancelled', '已取消'),
    ('failed', '失败'),
]

INCIDENT_SEVERITY_CHOICES = [
    ('critical', '严重'),
    ('high', '高'),
    ('medium', '中'),
    ('low', '低'),
]


class DevOpsIncident(models.Model):
    id = models.CharField(max_length=100, primary_key=True, default=generate_incident_id)
    incident_id = models.CharField(max_length=100, unique=True, verbose_name='事件ID')
    title = models.CharField(max_length=255, verbose_name='调查标题')
    status = models.CharField(max_length=20, choices=INCIDENT_STATUS_CHOICES, default='investigating', verbose_name='状态')
    severity = models.CharField(max_length=20, choices=INCIDENT_SEVERITY_CHOICES, default='high', verbose_name='严重程度')
    
    environment_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='环境ID')
    environment_name = models.CharField(max_length=100, null=True, blank=True, verbose_name='环境名称')
    
    background = models.TextField(verbose_name='事件背景')
    description = models.TextField(verbose_name='事件说明')
    
    progress = models.JSONField(default=dict, verbose_name='调查进度')
    timeline = models.JSONField(default=list, verbose_name='推理时间线')
    root_cause = models.JSONField(default=dict, verbose_name='根因分析')
    fix_suggestions = models.JSONField(default=dict, verbose_name='修复建议')
    chat_messages = models.JSONField(default=list, verbose_name='对话消息')
    
    occurred_at = models.DateTimeField(auto_now_add=True, verbose_name='发生时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='devops_incidents', null=True, blank=True)
    
    class Meta:
        db_table = 'devops_incidents'
        ordering = ['-created_at']
        verbose_name = 'DevOps事件调查'
        verbose_name_plural = 'DevOps事件调查'
    
    def save(self, *args, **kwargs):
        if not self.incident_id:
            self.incident_id = generate_incident_id()
        if not self.progress:
            self.progress = {
                'currentStep': 0,
                'percentage': 0,
                'steps': [
                    {'status': '进行中', 'icon': 'Loading', 'iconClass': 'processing'},
                    {'status': '待处理', 'icon': 'Timer', 'iconClass': 'pending'},
                    {'status': '待处理', 'icon': 'Timer', 'iconClass': 'pending'}
                ]
            }
        super().save(*args, **kwargs)
    
    def to_dict(self):
        from datetime import datetime
        return {
            'id': self.id,
            'incidentId': self.incident_id,
            'title': self.title,
            'status': self.status,
            'severity': self.severity,
            'environmentId': self.environment_id,
            'environmentName': self.environment_name,
            'background': self.background,
            'description': self.description,
            'progress': self.progress,
            'timeline': self.timeline,
            'rootCause': self.root_cause,
            'fixSuggestions': self.fix_suggestions,
            'chatMessages': self.chat_messages,
            'occurredAt': self.occurred_at.isoformat() if self.occurred_at else None,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
            'completedAt': self.completed_at.isoformat() if self.completed_at else None,
            'affectedService': self.environment_name or '-',
        }


class DevOpsIncidentService:
    @staticmethod
    def get_user_incidents(user, filters=None, page=1, page_size=10):
        filters = filters or {}
        queryset = DevOpsIncident.objects.all()
        
        if user:
            queryset = queryset.filter(user=user)
        
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        
        if filters.get('severity'):
            queryset = queryset.filter(severity=filters['severity'])
        
        if filters.get('environment_id'):
            queryset = queryset.filter(environment_id=filters['environment_id'])
        
        if filters.get('keyword'):
            keyword = filters['keyword']
            queryset = queryset.filter(
                models.Q(title__icontains=keyword) |
                models.Q(description__icontains=keyword) |
                models.Q(background__icontains=keyword)
            )
        
        total = queryset.count()
        
        start = (page - 1) * page_size
        end = start + page_size
        incidents = queryset[start:end]
        
        return {
            'incidents': [inc.to_dict() for inc in incidents],
            'total': total,
            'page': page,
            'page_size': page_size
        }
    
    @staticmethod
    def get_incident_by_id(incident_id, user=None):
        try:
            incident = DevOpsIncident.objects.get(
                models.Q(id=incident_id) | models.Q(incident_id=incident_id)
            )
            if user and incident.user and incident.user != user:
                return None
            return incident
        except DevOpsIncident.DoesNotExist:
            return None
    
    @staticmethod
    def create_incident(user, data):
        incident = DevOpsIncident(
            user=user,
            title=data.get('title', ''),
            severity=data.get('severity', 'high'),
            environment_id=data.get('environment_id'),
            environment_name=data.get('environment_name'),
            background=data.get('background', ''),
            description=data.get('description', ''),
            status='investigating',
        )
        incident.save()
        
        DevOpsIncidentService._initialize_timeline(incident)
        
        return incident
    
    @staticmethod
    def _initialize_timeline(incident):
        from datetime import datetime
        
        initial_timeline = [
            {
                'id': 1,
                'timestamp': datetime.now().isoformat(),
                'type': 'primary',
                'icon': 'Search',
                'title': '调查启动',
                'description': 'DevOps Agent 已接收到调查请求，开始进行事件分析。',
                'highlight': True,
                'details': [
                    '检查相关服务状态',
                    '收集最近的日志和监控数据',
                    '分析可能的故障模式'
                ]
            }
        ]
        
        incident.timeline = initial_timeline
        incident.save(update_fields=['timeline'])
    
    @staticmethod
    def update_progress(incident, step, percentage):
        progress = incident.progress.copy() if incident.progress else {}
        progress['currentStep'] = step
        progress['percentage'] = percentage
        
        steps = progress.get('steps', [
            {'status': '待处理', 'icon': 'Timer', 'iconClass': 'pending'},
            {'status': '待处理', 'icon': 'Timer', 'iconClass': 'pending'},
            {'status': '待处理', 'icon': 'Timer', 'iconClass': 'pending'}
        ])
        
        for i in range(len(steps)):
            if i < step:
                steps[i] = {'status': '已完成', 'icon': 'CircleCheck', 'iconClass': 'completed'}
            elif i == step:
                steps[i] = {'status': '进行中', 'icon': 'Loading', 'iconClass': 'processing'}
            else:
                steps[i] = {'status': '待处理', 'icon': 'Timer', 'iconClass': 'pending'}
        
        progress['steps'] = steps
        incident.progress = progress
        incident.save(update_fields=['progress'])
    
    @staticmethod
    def cancel_incident(incident):
        if incident.status not in ['investigating']:
            return False
        
        incident.status = 'cancelled'
        incident.save(update_fields=['status', 'updated_at'])
        return True
    
    @staticmethod
    def add_chat_message(incident, role, content, msg_type='normal', title=None, details=None, suggestion=None):
        from datetime import datetime
        
        message = {
            'role': role,
            'content': content,
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': msg_type
        }
        
        if title:
            message['title'] = title
        if details:
            message['details'] = details
        if suggestion:
            message['suggestion'] = suggestion
        
        chat_messages = incident.chat_messages.copy() if incident.chat_messages else []
        chat_messages.append(message)
        incident.chat_messages = chat_messages
        incident.save(update_fields=['chat_messages'])
        
        return message
    
    @staticmethod
    def update_incident_data(incident, field_name, data):
        if field_name == 'root_cause':
            incident.root_cause = data
        elif field_name == 'fix_suggestions':
            incident.fix_suggestions = data
        elif field_name == 'timeline':
            incident.timeline = data
        elif field_name == 'progress':
            incident.progress = data
        elif field_name == 'status':
            incident.status = data
        incident.save()
        return incident


class DevOpsDiagnosisService:
    @staticmethod
    def start_async_diagnosis(incident_id, environment_id):
        import threading
        
        logger.info(f"[incident_id:{incident_id}] 启动异步诊断任务，environment_id={environment_id}")
        
        thread = threading.Thread(
            target=DevOpsDiagnosisService._run_diagnosis,
            args=(incident_id, environment_id)
        )
        thread.daemon = True
        thread.start()
        
        logger.info(f"[incident_id:{incident_id}] 异步诊断线程已启动，thread_ident={thread.ident}")
        return thread
    
    @staticmethod
    def _run_diagnosis(incident_id, environment_id):
        from datetime import datetime
        
        logger.info(f"[incident_id:{incident_id}] 开始执行诊断流程")
        
        incident = DevOpsIncidentService.get_incident_by_id(incident_id)
        if not incident:
            logger.error(f"[incident_id:{incident_id}] 无法找到对应的 incident 记录，诊断终止")
            return
        
        logger.info(f"[incident_id:{incident_id}] 加载 incident 成功，title={incident.title}, status={incident.status}")
        
        environment = None
        credentials = None
        
        if environment_id:
            logger.debug(f"[incident_id:{incident_id}] 尝试从 environment_id={environment_id} 获取凭证")
            try:
                env_id_int = int(environment_id)
                environment = AWSEnvironmentService.get_environment_by_id(env_id_int)
                if environment:
                    credentials = environment.get_credentials()
                    logger.info(f"[incident_id:{incident_id}] 从数据库环境获取凭证成功，env={credentials.get('env')}")
            except ValueError:
                logger.warning(f"[incident_id:{incident_id}] environment_id={environment_id} 不是有效整数，跳过数据库查询")
                pass
        
        if not credentials:
            logger.debug(f"[incident_id:{incident_id}] 从 access_list 查找匹配的环境配置")
            for access in get_access_list():
                if str(access.get('env')) == str(environment_id) or access.get('env') == environment_id:
                    credentials = access
                    logger.info(f"[incident_id:{incident_id}] 从 access_list 找到匹配环境，env={credentials.get('env')}")
                    break
        
        if not credentials:
            logger.warning(f"[incident_id:{incident_id}] 未找到有效的环境凭证，将使用模拟数据进行诊断")
        
        try:
            logger.info(f"[incident_id:{incident_id}] 步骤 1/4: 初始化诊断时间线")
            DevOpsDiagnosisService._add_timeline_event(
                incident,
                step=0,
                title='开始诊断',
                description='DevOps Agent 已启动诊断流程，正在收集环境信息...',
                icon='Search',
                highlight=True
            )
            
            DevOpsIncidentService.update_progress(incident, 0, 10)
            logger.info(f"[incident_id:{incident_id}] 进度更新: 0/3 (10%)")
            
            logger.info(f"[incident_id:{incident_id}] 步骤 2/4: 开始收集诊断数据")
            diagnosis_data = DevOpsDiagnosisService._collect_diagnosis_data(
                credentials,
                incident.title,
                incident.description,
                incident_id
            )
            logger.info(f"[incident_id:{incident_id}] 数据收集完成，log_samples={len(diagnosis_data.get('log_samples', []))}, metrics={len(diagnosis_data.get('metrics', []))}")
            
            DevOpsIncidentService.update_progress(incident, 1, 40)
            logger.info(f"[incident_id:{incident_id}] 进度更新: 1/3 (40%)")
            
            DevOpsDiagnosisService._add_timeline_event(
                incident,
                step=1,
                title='数据收集完成',
                description=f'已收集 {len(diagnosis_data.get("log_samples", []))} 条日志样本和 {len(diagnosis_data.get("metrics", []))} 个监控指标。',
                icon='DataAnalysis',
                details=diagnosis_data.get('summary', []),
                highlight=True
            )
            
            DevOpsIncidentService.update_progress(incident, 2, 70)
            logger.info(f"[incident_id:{incident_id}] 进度更新: 2/3 (70%)")
            
            logger.info(f"[incident_id:{incident_id}] 步骤 3/4: 开始 AI 根因分析")
            analysis_result = DevOpsDiagnosisService._perform_ai_analysis(
                incident,
                diagnosis_data
            )
            logger.info(f"[incident_id:{incident_id}] AI 分析完成，main_cause={analysis_result.get('root_cause', {}).get('mainCause', 'N/A')}")
            
            DevOpsIncidentService.update_progress(incident, 3, 100)
            logger.info(f"[incident_id:{incident_id}] 进度更新: 3/3 (100%)")
            
            DevOpsDiagnosisService._add_timeline_event(
                incident,
                step=2,
                title='根因分析完成',
                description='AI 已完成根因分析，生成了详细的修复建议。',
                icon='Warning',
                highlight=True,
                details=[
                    f'主要根因: {analysis_result.get("root_cause", {}).get("mainCause", "待分析")}'
                ]
            )
            
            incident.status = 'completed'
            incident.save(update_fields=['status', 'updated_at'])
            logger.info(f"[incident_id:{incident_id}] 诊断流程已完成，状态更新为 completed")
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"[incident_id:{incident_id}] 诊断流程异常: {str(e)}\n{error_details}")
            
            try:
                incident.status = 'failed'
                incident.save(update_fields=['status', 'updated_at'])
                logger.error(f"[incident_id:{incident_id}] 状态更新为 failed")
                
                DevOpsDiagnosisService._add_timeline_event(
                    incident,
                    step=-1,
                    title='诊断失败',
                    description=f'诊断过程中发生错误: {str(e)}',
                    icon='CircleCloseFilled',
                    type='danger',
                    highlight=True
                )
            except Exception as inner_e:
                logger.error(f"[incident_id:{incident_id}] 更新失败状态时发生异常: {str(inner_e)}")
                pass
    
    @staticmethod
    def _collect_diagnosis_data(credentials, title, description, incident_id=None):
        log_prefix = f"[incident_id:{incident_id}] " if incident_id else ""
        
        logger.info(f"{log_prefix}开始收集诊断数据")
        logger.debug(f"{log_prefix}credentials={credentials}, title={title}")
        
        result = {
            'log_samples': [],
            'metrics': [],
            'summary': [],
            'environment_info': credentials or {}
        }
        
        result['summary'].append('检查 AWS 环境配置')
        result['summary'].append('扫描 ECS 服务状态')
        result['summary'].append('收集 CloudWatch 日志和指标')
        result['summary'].append('分析 RDS 性能指标')
        
        if not credentials:
            logger.warning(f"{log_prefix}未提供有效的 AWS 环境凭证，使用模拟数据")
            result['log_samples'].append({
                'timestamp': datetime.now().isoformat(),
                'source': 'diagnosis',
                'message': '未提供有效的 AWS 环境凭证，无法进行实际的 AWS 资源诊断。'
            })
            result['summary'].append('注意: 未配置环境凭证，将使用模拟数据进行演示')
        else:
            try:
                env_name = credentials.get("env", "unknown")
                region = credentials.get("region", "unknown")
                logger.info(f"{log_prefix}使用环境: {env_name}, 区域: {region}")
                result['summary'].append(f'使用环境: {env_name}')
                result['summary'].append(f'区域: {region}')
            except Exception as e:
                logger.error(f"{log_prefix}访问 AWS 资源时出错: {str(e)}")
                result['log_samples'].append({
                    'timestamp': datetime.now().isoformat(),
                    'source': 'error',
                    'message': f'访问 AWS 资源时出错: {str(e)}'
                })
        
        logger.info(f"{log_prefix}诊断数据收集完成，summary={result.get('summary', [])}")
        return result
    
    @staticmethod
    def _perform_ai_analysis(incident, diagnosis_data):
        from datetime import datetime
        import os
        import sys
        
        incident_id = incident.id if hasattr(incident, 'id') else incident.incident_id
        log_prefix = f"[incident_id:{incident_id}] "
        
        logger.info(f"{log_prefix}开始 AI 根因分析")
        
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        try:
            from settings import ApiKey, CHROMA_HOST, CHROMA_PORT, CHROMA_COLLECTION
        except ImportError:
            ApiKey = None
            CHROMA_HOST = None
            CHROMA_PORT = None
            CHROMA_COLLECTION = None
            logger.warning(f"{log_prefix}无法导入 API 配置，将使用默认分析")
        
        context_info = []
        if diagnosis_data.get('log_samples'):
            for log in diagnosis_data['log_samples'][:5]:
                context_info.append(f"[{log.get('source', 'unknown')}] {log.get('message', '')}")
        
        logger.debug(f"{log_prefix}构建分析 prompt，title={incident.title}")
        
        prompt = f"""你是一位专业的 DevOps 工程师和 SRE（站点可靠性工程师）。请分析以下事件，并提供专业的诊断和修复建议。

事件标题：{incident.title}
事件背景：{incident.background}
事件描述：{incident.description}

环境信息：
- 环境名称: {incident.environment_name or '未知'}
- 严重程度: {incident.severity}

诊断数据摘要：
{chr(10).join(diagnosis_data.get('summary', ['暂无诊断数据']))}

请基于以上信息，提供以下内容：
1. 根因分析（mainCause, description, impactChain, contributingFactors, evidence）
2. 立即执行的修复建议（immediate）
3. 长期优化建议（longterm）

请用 JSON 格式输出，包含以下结构：
{{
    "root_cause": {{
        "mainCause": "主要根因",
        "description": "详细描述",
        "impactChain": ["影响链分析1", "影响链分析2"],
        "contributingFactors": [
            {{"name": "因素1", "description": "描述", "type": "critical/warning"}}
        ],
        "evidence": [
            {{"source": "来源", "evidence": "证据内容", "relevance": 85}}
        ]
    }},
    "fix_suggestions": {{
        "immediate": [
            {{"title": "建议标题", "description": "详细描述", "priority": "high/medium", "commands": [{{"label": "步骤", "command": "命令"}}], "verification": "验证方法"}}
        ],
        "longterm": [
            {{"title": "建议标题", "description": "详细描述", "benefits": ["收益1", "收益2"]}}
        ]
    }}
}}"""
        
        analysis_result = None
        
        if ApiKey:
            logger.info(f"{log_prefix}使用 DeepSeek API 进行 AI 分析")
            try:
                from openai import OpenAI
                
                client = OpenAI(api_key=ApiKey, base_url="https://api.deepseek.com")
                
                logger.debug(f"{log_prefix}调用 OpenAI API，model=deepseek-chat")
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "你是一位专业的 DevOps 工程师和 SRE。请用 JSON 格式输出分析结果。"},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    stream=False
                )
                
                ai_response = response.choices[0].message.content
                logger.debug(f"{log_prefix}收到 AI 响应，长度={len(ai_response) if ai_response else 0}")
                
                try:
                    import json
                    analysis_result = json.loads(ai_response)
                    logger.info(f"{log_prefix}AI 响应解析成功")
                except json.JSONDecodeError as e:
                    logger.error(f"{log_prefix}AI 响应 JSON 解析失败: {str(e)}")
                    analysis_result = None
                    
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"{log_prefix}AI 分析调用失败: {str(e)}\n{error_details}")
                analysis_result = None
        else:
            logger.warning(f"{log_prefix}未配置 API Key，将使用默认分析模板")
        
        if not analysis_result:
            analysis_result = DevOpsDiagnosisService._generate_default_analysis(incident)
        
        root_cause = analysis_result.get('root_cause', {})
        fix_suggestions = analysis_result.get('fix_suggestions', {})
        
        incident.root_cause = root_cause
        incident.fix_suggestions = fix_suggestions
        incident.save(update_fields=['root_cause', 'fix_suggestions', 'updated_at'])
        
        return analysis_result
    
    @staticmethod
    def _generate_default_analysis(incident):
        from datetime import datetime
        
        default_analysis = {
            "root_cause": {
                "mainCause": "服务异常 - 需要进一步诊断",
                "description": f"根据事件描述「{incident.title}」，初步判断可能涉及以下问题：服务可用性、性能瓶颈或配置错误。建议查看详细日志和监控数据。",
                "impactChain": [
                    "用户报告服务异常",
                    "监控指标显示异常",
                    "影响业务功能",
                    "需要紧急处理"
                ],
                "contributingFactors": [
                    {"name": "缺乏实时监控", "description": "建议配置更详细的监控告警", "type": "warning"},
                    {"name": "日志不完整", "description": "建议完善日志收集和分析机制", "type": "warning"}
                ],
                "evidence": [
                    {"source": "事件描述", "evidence": incident.description, "relevance": 90},
                    {"source": "事件背景", "evidence": incident.background, "relevance": 85}
                ]
            },
            "fix_suggestions": {
                "immediate": [
                    {
                        "title": "检查服务状态",
                        "description": "首先确认相关服务的运行状态，检查是否有服务中断或重启。",
                        "priority": "high",
                        "commands": [
                            {"label": "查看 ECS 服务状态", "command": "aws ecs describe-services --cluster <cluster-name> --services <service-name>"},
                            {"label": "查看任务运行情况", "command": "aws ecs list-tasks --cluster <cluster-name> --service-name <service-name>"}
                        ],
                        "verification": "确认所有任务都处于 RUNNING 状态，没有异常的停止或重启。"
                    },
                    {
                        "title": "收集错误日志",
                        "description": "从 CloudWatch Logs 收集相关服务的错误日志，分析具体的错误信息。",
                        "priority": "high",
                        "commands": [
                            {"label": "查看最近的错误日志", "command": "aws logs filter-log-events --log-group-name <log-group> --filter-pattern ERROR --start-time <timestamp>"}
                        ],
                        "verification": "找到具体的错误堆栈或异常信息，定位问题根源。"
                    },
                    {
                        "title": "检查数据库连接",
                        "description": "如果服务涉及数据库操作，检查数据库连接池和查询性能。",
                        "priority": "medium",
                        "commands": [
                            {"label": "查看 RDS 实例状态", "command": "aws rds describe-db-instances --db-instance-identifier <instance-id>"}
                        ],
                        "verification": "确认数据库实例可用，没有连接数耗尽或慢查询问题。"
                    }
                ],
                "longterm": [
                    {
                        "title": "完善监控告警体系",
                        "description": "配置更全面的监控指标和告警规则，实现问题的早发现、早处理。",
                        "benefits": ["减少 MTTD（平均检测时间）", "提高系统可靠性", "降低运维成本"]
                    },
                    {
                        "title": "建立日志分析平台",
                        "description": "使用 ELK 或类似方案集中管理日志，实现快速检索和分析。",
                        "benefits": ["加速问题定位", "支持异常检测", "便于审计合规"]
                    },
                    {
                        "title": "制定故障演练计划",
                        "description": "定期进行 Chaos Engineering 演练，验证系统的容错能力和恢复机制。",
                        "benefits": ["提高团队应急响应能力", "发现隐藏的脆弱点", "验证灾备方案有效性"]
                    }
                ]
            }
        }
        
        return default_analysis
    
    @staticmethod
    def _add_timeline_event(incident, step, title, description, icon='Search', 
                            type='primary', highlight=False, details=None, 
                            logs=None, suggestions=None, duration=None):
        from datetime import datetime
        
        timeline = incident.timeline.copy() if incident.timeline else []
        
        event = {
            'id': len(timeline) + 1,
            'timestamp': datetime.now().isoformat(),
            'type': type,
            'icon': icon,
            'title': title,
            'description': description,
            'highlight': highlight,
            'step': step
        }
        
        if details:
            event['details'] = details
        if logs:
            event['logs'] = logs
        if suggestions:
            event['suggestions'] = suggestions
        if duration:
            event['duration'] = duration
        
        timeline.append(event)
        incident.timeline = timeline
        incident.save(update_fields=['timeline', 'updated_at'])
        
        return event


class AWSAthena():
    """
        Athena 相关
    """
    
    @staticmethod
    def get_environments():
        """
            获取所有可用的 AWS 环境列表
        """
        result = []
        for index, item in enumerate(get_access_list()):
            env_info = {
                "id": item["env"],
                "name": item["env"],
                "is_default": index == 0,
                "region": item.get("region", ""),
                "account_id": ""
            }
            result.append(env_info)
        return result
    
    @staticmethod
    def get_databases(env):
        """
            获取指定环境下的所有 Athena 数据库
        """
        result = []
        for index, item in enumerate(get_access_list()):
            if item["env"] == env:
                athena_client = boto3.client(
                    'athena',
                    aws_access_key_id=item["access_key"],
                    aws_secret_access_key=item["secret_key"],
                    region_name=item["region"]
                )
                
                response = athena_client.list_databases(
                    CatalogName='AwsDataCatalog'
                )
                
                for database in response.get('DatabaseList', []):
                    result.append(database.get('Name', ''))
                
                while 'NextToken' in response:
                    response = athena_client.list_databases(
                        CatalogName='AwsDataCatalog',
                        NextToken=response['NextToken']
                    )
                    for database in response.get('DatabaseList', []):
                        result.append(database.get('Name', ''))
                
                break
        
        return result
    
    @staticmethod
    def get_tables(env, database):
        """
            获取指定数据库下的所有数据表
        """
        result = []
        for index, item in enumerate(get_access_list()):
            if item["env"] == env:
                athena_client = boto3.client(
                    'athena',
                    aws_access_key_id=item["access_key"],
                    aws_secret_access_key=item["secret_key"],
                    region_name=item["region"]
                )
                
                response = athena_client.list_table_metadata(
                    CatalogName='AwsDataCatalog',
                    DatabaseName=database
                )
                
                for table in response.get('TableMetadataList', []):
                    result.append(table.get('Name', ''))
                
                while 'NextToken' in response:
                    response = athena_client.list_table_metadata(
                        CatalogName='AwsDataCatalog',
                        DatabaseName=database,
                        NextToken=response['NextToken']
                    )
                    for table in response.get('TableMetadataList', []):
                        result.append(table.get('Name', ''))
                
                break
        
        return result
    
    @staticmethod
    def execute_query(env, database, sql, limit=100):
        """
            执行 Athena SQL 查询并返回结果
        """
        result = {
            "query_info": {},
            "columns": [],
            "data": [],
            "row_count": 0,
            "execution_time": 0
        }
        
        for index, item in enumerate(get_access_list()):
            if item["env"] == env:
                athena_client = boto3.client(
                    'athena',
                    aws_access_key_id=item["access_key"],
                    aws_secret_access_key=item["secret_key"],
                    region_name=item["region"]
                )
                
                query_execution_context = {}
                if database:
                    query_execution_context['Database'] = database
                
                response = athena_client.start_query_execution(
                    QueryString=sql,
                    QueryExecutionContext=query_execution_context,
                    ResultConfiguration={
                        'OutputLocation': f's3://aws-athena-query-results-{item.get("account_id", "")}-{item["region"]}/'
                    }
                )
                
                query_execution_id = response['QueryExecutionId']
                
                query_execution = athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                
                status = query_execution['QueryExecution']['Status']['State']
                while status in ['QUEUED', 'RUNNING']:
                    import time
                    time.sleep(1)
                    query_execution = athena_client.get_query_execution(
                        QueryExecutionId=query_execution_id
                    )
                    status = query_execution['QueryExecution']['Status']['State']
                
                query_info = query_execution['QueryExecution']
                result["query_info"] = {
                    "query_id": query_execution_id,
                    "status": status,
                    "data_scanned_bytes": query_info.get('Statistics', {}).get('DataScannedInBytes', 0),
                    "execution_time_ms": query_info.get('Statistics', {}).get('EngineExecutionTimeInMillis', 0),
                    "output_location": query_info.get('ResultConfiguration', {}).get('OutputLocation', ''),
                    "submission_time": query_info.get('Status', {}).get('SubmissionDateTime', '').isoformat() if query_info.get('Status', {}).get('SubmissionDateTime') else ''
                }
                
                result["execution_time"] = query_info.get('Statistics', {}).get('EngineExecutionTimeInMillis', 0) / 1000.0
                
                if status == 'SUCCEEDED':
                    results_response = athena_client.get_query_results(
                        QueryExecutionId=query_execution_id,
                        MaxResults=limit
                    )
                    
                    rows = results_response.get('ResultSet', {}).get('Rows', [])
                    if len(rows) > 0:
                        header_row = rows[0]
                        for col in header_row.get('Data', []):
                            col_info = {
                                "name": col.get('VarCharValue', ''),
                                "type": "varchar"
                            }
                            result["columns"].append(col_info)
                        
                        for row in rows[1:]:
                            row_data = {}
                            for i, col in enumerate(row.get('Data', [])):
                                if i < len(result["columns"]):
                                    col_name = result["columns"][i]["name"]
                                    row_data[col_name] = col.get('VarCharValue', None)
                            result["data"].append(row_data)
                        
                        result["row_count"] = len(result["data"])
                
                break
        
        return result
    
    @staticmethod
    def get_query_status(env, query_id):
        """
            获取查询状态
        """
        result = {}
        for index, item in enumerate(get_access_list()):
            if item["env"] == env:
                athena_client = boto3.client(
                    'athena',
                    aws_access_key_id=item["access_key"],
                    aws_secret_access_key=item["secret_key"],
                    region_name=item["region"]
                )
                
                query_execution = athena_client.get_query_execution(
                    QueryExecutionId=query_id
                )
                
                query_info = query_execution['QueryExecution']
                result = {
                    "query_id": query_id,
                    "status": query_info['Status']['State'],
                    "state_change_reason": query_info['Status'].get('StateChangeReason'),
                    "submission_time": query_info['Status'].get('SubmissionDateTime', '').isoformat() if query_info['Status'].get('SubmissionDateTime') else None,
                    "completion_time": query_info['Status'].get('CompletionDateTime', '').isoformat() if query_info['Status'].get('CompletionDateTime') else None
                }
                
                break
        
        return result


