# route53 相关
import boto3


class proc():
    def __init__(self, region, access_key, secret_key) -> None:
        """
            初始化aws连接
        """
        self.route53_client = boto3.client('route53', aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key, region_name=region)


    def list_hosted_zones(self):
        """
            获取所有区域
        """
        return self.route53_client.list_hosted_zones(MaxItems="100")
    

    def get_all_A_resource_record(self, HostedZoneId):
        """
            获取区域所有A记录
        """
        reponse = self.route53_client.list_resource_record_sets(HostedZoneId=HostedZoneId,MaxItems="300")
        ResourceRecords = {}
        for ResourceRecordSet in reponse['ResourceRecordSets']:
            if ResourceRecordSet['Type'] == 'A':
                try:
                    ResourceRecords[ResourceRecordSet['Name']] = ResourceRecordSet
                except Exception as e:
                    print(e)
                    print(ResourceRecordSet)
                

        


        while 'NextRecordName' in reponse:
            reponse = self.route53_client.list_resource_record_sets(HostedZoneId=HostedZoneId,StartRecordName=reponse['NextRecordName'],StartRecordType=reponse['NextRecordType'],MaxItems="300")
            for ResourceRecordSet in reponse['ResourceRecordSets']:
                if ResourceRecordSet['Type'] == 'A':
                    try:
                        ResourceRecords[ResourceRecordSet['Name']] = ResourceRecordSet
                    except Exception as e:
                        print(e)
                        print(ResourceRecordSet)

        return ResourceRecords


