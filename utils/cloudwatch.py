# cloudwatch相关
import boto3

# 设置密钥

class proc():
    def __init__(self, region, access_key, secret_key) -> None:
        """
            初始化aws连接
        """
        self.cw_client = boto3.client('cloudwatch', aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key, region_name=region)


    def get_metric_data(self, MetricName, InstanceId, StartTime, EndTime, Period=900, Stat="Maximum"):
        """
            监控指标数据
            Namespace: 指标所在名称空间, AWS的名称空间需要加上AWS/, 如AWS/EC2。
            MetricName: 指标名
            InstanceId: 实例id
            Period: 聚合时间
            Stat: 统计模式
            StartTime: 开始时间，时间格式可以是08:05:34, 也可以是时间戳，时区是UTC-0
            EndTime: 结束时间
        """
        # aws cloudwatch get-metric-data --metric-data-queries '[{"Id": "query","MetricStat":{"Metric": {"Namespace": "AWS/EC2","MetricName": "CPUUtilization","Dimensions": [{"Name": "InstanceId","Value": "i-0bef500f7dffd93f1"}]},"Period": 300,"Stat": "Average"}}]' --start-time 8:00:34 --end-time 8:05:34
        return self.cw_client.get_metric_data(MetricDataQueries=[
                                                {
                                                    "Id": "local_exporter",
                                                    "MetricStat":{
                                                        "Metric": {
                                                            "Namespace": "AWS/EC2",
                                                            "MetricName": MetricName,
                                                            "Dimensions": [
                                                                {
                                                                    "Name": "InstanceId",
                                                                    "Value": InstanceId
                                                                }
                                                            ]
                                                        },
                                                        "Period": Period,
                                                        "Stat": Stat
                                                    }
                                                }
                                            ], StartTime=StartTime, EndTime=EndTime)
    

    def get_metric_data_v2(self, Namespace, MetricName, StartTime, EndTime, Period=900, Stat="Maximum"):
        """
            监控指标数据
            Namespace: 指标所在名称空间, AWS的名称空间需要加上AWS/, 如AWS/EC2。
            MetricName: 指标名
            InstanceId: 实例id
            Period: 聚合时间
            Stat: 统计模式
            StartTime: 开始时间，时间格式可以是08:05:34, 也可以是时间戳，时区是UTC-0
            EndTime: 结束时间
        """
        # aws cloudwatch get-metric-data --metric-data-queries '[{"Id": "query","MetricStat":{"Metric": {"Namespace": "AWS/EC2","MetricName": "CPUUtilization","Dimensions": [{"Name": "InstanceId","Value": "i-0bef500f7dffd93f1"}]},"Period": 300,"Stat": "Average"}}]' --start-time 8:00:34 --end-time 8:05:34
        return self.cw_client.get_metric_data(MetricDataQueries=[
                                                {
                                                    "Id": "local_exporter",
                                                    "MetricStat":{
                                                        "Metric": {
                                                            "Namespace": Namespace,
                                                            "MetricName": MetricName,
                                                            "Dimensions": [
                                                                
                                                            ]
                                                        },
                                                        "Period": Period,
                                                        "Stat": Stat
                                                    }
                                                }
                                            ], StartTime=StartTime, EndTime=EndTime)
    
     
    
    
