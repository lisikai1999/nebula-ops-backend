# from django.db import models
import pytz
import time
import json
import boto3
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

from utils import iam, logs, cloudwatch, ecs as ECS, route53, elbv2
from settings import emailList, access_list, adminEmail, adminPassword, ccEmail, rdsSizeList




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
    for index, item in enumerate(access_list):
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
    for index, item in enumerate(access_list):
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
    for index, item in enumerate(access_list):
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
    for index, item in enumerate(access_list):
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
        for access in access_list:
            if access['env'] == 'china dev-staging' or access['env'] == 'china prod':
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
        for index, item in enumerate(access_list):
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
        for index, item in enumerate(access_list):
            if item["env"] == env: 
                result = ecsCollect(region=item["region"],access_key=item["access_key"],secret_key=item["secret_key"])
                return result
        return {}

    def describetaskdefine(env, taskarn):
        # 判断环境
        for index, item in enumerate(access_list):
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
        for index, item in enumerate(access_list):
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
        for index, item in enumerate(access_list):
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


