# elb相关
import boto3


class proc():
    def __init__(self, region, access_key, secret_key) -> None:
        """
            初始化aws连接
        """
        self.elbv2_client = boto3.client('elbv2', aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key, region_name=region)


    def describe_target_groups(self):
        """
            获取目标组列表
        """
        return self.elbv2_client.describe_target_groups()
    
    def describe_target_health(self, targetArn):
        """
            获取目标组健康状态
        """
        return self.elbv2_client.describe_target_health(TargetGroupArn=targetArn)
    
    def describe_load_balancers(self):
        """
            获取负载均衡器列表
        """
        return self.elbv2_client.describe_load_balancers()


    def port_loadarn_listeners(self, LoadBalancerArn, port):
        """
            根据端口和负载均衡器arn获取监听器arn
        """
        Listeners = self.elbv2_client.describe_listeners(LoadBalancerArn=LoadBalancerArn)['Listeners']
        for Listener in Listeners:
            if str(Listener['Port']) == port:
                return Listener['ListenerArn']
        return None

    # 获取侦听器规则列表
    def describe_rules(self, ListenerArn):
        return self.elbv2_client.describe_rules(ListenerArn=ListenerArn)

    # 根据域名找到对应的目标组
    def domain_get_target_group_arn(self, describe_rules, domain):
        
        result = {}
        # 遍历规则，找到域名对应的目标组
        for rule in describe_rules['Rules']:
            # Http主机标头为domain的规则
            if len(rule['Conditions']) != 0:
                # 判断主机标头条件
                for condition in rule['Conditions']:
                    if condition['Field'] == 'host-header':
                        if domain.rstrip(".") in rule['Conditions'][0]['Values']:
                            for action in rule['Actions']:
                                if action['Type'] == 'forward':
                                    if domain not in result:
                                        result[domain] = [action['TargetGroupArn']]
                                    else:
                                        result[domain].append(action['TargetGroupArn'])
        print(domain)                            
        print(result)                            
        
        return result




