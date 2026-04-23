# kinesis firehose相关
import boto3

# 设置密钥

class proc():
    def __init__(self, region, access_key, secret_key) -> None:
        """
            初始化aws连接
        """
        self.iam_client = boto3.client('iam', aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key, region_name=region)


    def list_users(self):
        """
            用户基本信息列表
        """
        return self.iam_client.list_users()

    def get_login_profile(self, username):
        """
            查看是否有登陆控制台权限
        """
        try:
            # 查询正常表示用户可以正常登陆控制台
            self.iam_client.get_login_profile(UserName=username)
            return True
        # 查询异常表示aws没有该用户的登陆配置文件。
        except Exception as e:
            # print(e)
            return False

    def list_user_tags(self, username):
        """
            查询用户tag
        """
        self.iam_client.list_user_tags(UserName=username)

    
    def create_login_profile(self, username):
        # 创建用户登陆凭证
        password = self._generate_pw(14)    # 随机生成符合要求的14位密码
        self.iam_client.create_login_profile(UserName=username, Password=password)
        return password

    def delete_login_profile(self, username):
        # 删除用户登陆凭证（取消web控制台登陆权限）
        return self.iam_client.delete_login_profile(UserName=username)

    def _generate_pw(self, length=14):
        '''
            生成符合要求的密码
                长度必须至少为 14 个字符
                必须至少包含一个大写字母(A-Z)
                必须至少包含一个小写字母(a-z)
                必须至少包含一个数字 (0-9)
                必须至少包含一个非字母数字字符(! @ # $ % ^ & * ( ) _ + - = [ ] { } | ')
        '''
        import random
        import string
        if length < 14:
            raise ValueError("密码长度至少为4，以确保包含所有要求的字符类型")
        
        # 定义字符类别
        lowercase_letters = string.ascii_lowercase
        uppercase_letters = string.ascii_uppercase
        digits = string.digits
        special_characters = "!@#$%&*()_+-=[]{}|'"
        
        # 确保密码包含至少一个小写字母、一个大写字母、一个数字和一个特殊字符
        password = [
            random.choice(lowercase_letters),
            random.choice(uppercase_letters),
            random.choice(digits),
            random.choice(special_characters),
        ]
        
        # 填充剩余的部分
        all_characters = lowercase_letters + uppercase_letters + digits + special_characters
        password += random.choices(all_characters, k=length-4)
        # 打乱密码中的字符顺序
        random.shuffle(password)
        
        # 将密码列表转换为字符串
        return ''.join(password)
    



