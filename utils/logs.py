# cloudwatch 日志组相关
import boto3

# 设置密钥

class proc():
    def __init__(self, region, access_key, secret_key) -> None:
        """
            初始化aws连接
        """
        self.logs_client = boto3.client('logs', aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key, region_name=region)


    def create_logs_group(self, name, days, stream_name):
        """
            创建日志组
        """
        # 创建日志组异常
        try:
            self.logs_client.create_log_group(logGroupName=name)                            # 创建日志组
        except Exception as e:
            print(f"创建{name}日志组异常=>", e)
        self.logs_client.put_retention_policy(logGroupName=name, retentionInDays=days)  # 设置日志过期时间

        # 创建日志流异常
        try:
            self.logs_client.create_log_stream(logGroupName=name, logStreamName=stream_name)   # 创建日志流
        except Exception as e:
            print(f"创建{name}的日志流异常=>", e)


    def get_cloudwatch_log_group_name(self):
        """
            获取所有cloudwatch日志组名
        """ 
        result = []
        nextToken = ''
        logGroups = self.logs_client.describe_log_groups()
        
        # 获取所有日志组名
        result += self.__getLogName(logGroups)

        # 根据nextToken获取所有日志组
        while 'nextToken' in logGroups:
            nextToken = logGroups['nextToken']
                
            logGroups = self.logs_client.describe_log_groups(nextToken=nextToken)
            result += (self.__getLogName(logGroups))
        return result
    
    def get_cloudwatch_log_group_info(self):
        """
            获取所有cloudwatch日志组信息
        """ 
        result = []
        nextToken = ''
        logGroups = self.logs_client.describe_log_groups()
        
        # 获取所有日志组名
        result.extend(logGroups['logGroups'])

        # 根据nextToken获取所有日志组
        while 'nextToken' in logGroups:
            nextToken = logGroups['nextToken']
                
            logGroups = self.logs_client.describe_log_groups(nextToken=nextToken)
            result.extend(logGroups['logGroups'])
        return result

    
    def getAllLogStreamEvent(self, logGroup, startTime, endTime, filterPattern=""):
        """搜索日志组的所有日志流事件
            logGroup: 日志组名称
            startTime: 起始时间戳（毫秒）
            endTime: 结束时间戳（毫秒）
        """

        # result = self.logs_client.filter_log_events(logGroupName=logGroup, startTime=startTime,endTime=endTime)
        result = self.logs_client.filter_log_events(logGroupName=logGroup, startTime=startTime,endTime=endTime, filterPattern=filterPattern)
        print(len(result["events"]))
        try:
            while result["nextToken"]:
                temp = self.logs_client.filter_log_events(logGroupName=logGroup, startTime=startTime,endTime=endTime, filterPattern=filterPattern, nextToken=result["nextToken"])
                result["events"] += temp["events"]
                result["nextToken"] = temp["nextToken"]
                print(len(result["events"]))
        except KeyError as e:
            pass

        print("共有", len(result["events"]), "行数据。")
        return result


    def get_log_group_subscription_filters(self, logGroup):
        return self.logs_client.describe_subscription_filters(logGroupName=logGroup)


    def delete_subscription_filters(self, logGroup, filterName):
        '''
            删除日志组订阅筛选条件
        '''
        return self.logs_client.delete_subscription_filter(logGroupName=logGroup, filterName=filterName)        
    
    def delete_log_group(self, logGroup):
        '''
            删除日志组
        '''
        return self.logs_client.delete_log_group(logGroupName = logGroup)


    def __getLogName(self, logGroups):
        """
            获取日志组名
        """

        result = [logGroups['logGroupName'] for logGroups in logGroups['logGroups']]
        return result


if __name__ == "__main__":
    # p = proc('<region>', '<access_key>', '<secret_key>')
    # response = p.get_cloudwatch_log_group_name()
    # print(response)
    pass
