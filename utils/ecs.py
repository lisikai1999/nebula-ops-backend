# ecs相关
import boto3

class proc():
    def __init__(self, region, access_key, secret_key) -> None:
        """
            初始化aws连接
        """
        self.ecs_client = boto3.client('ecs', aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key, region_name=region)

    def get_cluster_list(self):
        """
            获取集群arn列表
        """
        return self.ecs_client.list_clusters()['clusterArns']
    
    def get_service_state(self):
        """
            获取服务状态
        """
        return self.ecs_client


    def get_service_list(self, cluster_name):
        """
            获取服务arn列表
                cluster_name: 集群arn
        """
        return self.ecs_client.list_services(cluster=cluster_name)['serviceArns']
    

    def describe_services(self, cluster_name, service_name):
        """
            获取服务列表详细信息
                cluster_name: 集群arn
                service_name: 服务arn
        """

        return self.ecs_client.describe_services(cluster=cluster_name, services=[service_name]) 
    
    def describe_taskdefine(self, taskdefineArn):
        """
            获取服务列表详细信息
        """

        return self.ecs_client.describe_task_definition(taskDefinition=taskdefineArn) 
    
    def get_service_tasks(self, cluster, service):
        """获取服务任务列表"""
        return self.ecs_client.list_tasks(cluster=cluster, serviceName=service)

    def get_service_container_info(self, cluster, taskarn):
        """
            taskarn：任务id，有get_service_tasks得到
        """
        return self.ecs_client.describe_tasks(cluster=cluster, tasks=taskarn)

    def exec_for_cluster_service(self, execdef, result=[], env=""):
        """
            对一个环境中的所有服务执行传递进来的方法
                execdef: 对服务执行的方法,传递进来的方法需要接收cluster与service两个参数
                result:  返回值为数组，数组中的每一个值都是execdef中返回的值
        """
        # 获取所有集群arn列表
        clusters = self.get_cluster_list()
        for cluster in clusters:
            # 获取集群中所有服务arn列表
            services = self.get_service_list(cluster)
            for service in services:
                result.append(execdef(cluster, service, self, env))
        return result
    

    def exec_for_cluster_service_custom(self, execdef, result={}, env=""):
        """
            对一个环境中的所有服务执行传递进来的方法
                execdef: 对服务执行的方法,传递进来的方法需要接收cluster与service两个参数
                result:  返回值为不固定，由execdef来处理result返回
        """
        # 获取所有集群arn列表
        clusters = self.get_cluster_list()
        for cluster in clusters:
            # 获取集群中所有服务arn列表
            services = self.get_service_list(cluster)
            for service in services:
                execdef(cluster, service, self, env, result)
        return result
        

