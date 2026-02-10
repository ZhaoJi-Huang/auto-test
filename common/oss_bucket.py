# -*- coding: utf-8 -*-
# https://help.aliyun.com/zh/oss/developer-reference/download-objects-as-files-1?spm=a2c4g.11186623.0.0.2b0a2f8dCvyGIf#concept-88442-zh
import os
import time
import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider

# OSS访问凭证从环境变量读取：OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET
# 启动前请先设置环境变量，例如：
#   set OSS_ACCESS_KEY_ID=your_key_id
#   set OSS_ACCESS_KEY_SECRET=your_key_secret

class OSSBucket:
    def __init__(self) -> None:
        auth = oss2.ProviderAuthV4(EnvironmentVariableCredentialsProvider())
        endpoint = "https://oss-cn-wulanchabu.aliyuncs.com"
        region = "cn-wulanchabu"
        bucket_name = "cloudtest-wlcb-prod-01"
        self.bucket = oss2.Bucket(auth, endpoint, bucket_name, region=region)

    def get_url(self, object_name):
        url = self.bucket.sign_url('GET', object_name, 36000, slash_safe=True)
        return url
    
    def download(self, object_name, local_file_path):
        self.bucket.get_object_to_file(object_name, local_file_path)
        return local_file_path
    
    def upload(self, object_name, local_file_path, max_retries=3, retry_delay=1.0):
        """
        上传文件到 OSS，失败时自动重试
        :param object_name: OSS 对象名称
        :param local_file_path: 本地文件路径
        :param max_retries: 最大重试次数（默认3次，即1次初始 + 2次重试）
        :param retry_delay: 重试间隔秒数
        :return: 成功返回 object_name，失败返回 None
        """
        for attempt in range(1, max_retries + 1):
            try:
                result = self.bucket.put_object_from_file(object_name, local_file_path)
                if result.status == 200:
                    return object_name
            except Exception as e:
                print(f"[OSSBucket] Upload attempt {attempt}/{max_retries} failed: {e}")
            
            if attempt < max_retries:
                time.sleep(retry_delay)
        
        print(f"[OSSBucket] Failed to upload {local_file_path} after {max_retries} attempts")
        return None
    
    def download_url(self, url, local_file_path):
        object_name = url.split('?')[0].replace("https://cloudtest-wlcb-prod-01.oss-cn-wulanchabu.aliyuncs.com/", "")
        object_name = object_name.replace('%3A', ':')
        # import pdb; pdb.set_trace()
        self.download(object_name, local_file_path)
        return local_file_path

    def renew_url(self, url):
        if url and url.startswith("https://cloudtest-wlcb-prod-01.oss-cn-wulanchabu.aliyuncs.com/"):
            object_name = url.split('?')[0].replace("https://cloudtest-wlcb-prod-01.oss-cn-wulanchabu.aliyuncs.com/", "")
            object_name = object_name.replace('%3A', ':')
            # import pdb; pdb.set_trace()
            new_url = self.get_url(object_name)
            return new_url
        return url
    
if __name__ == "__main__":
    # yourBucketName填写存储空间名称。
    bucket = OSSBucket()

    local_file_path = 'test.mp4'
    url = "https://cloudtest-wlcb-prod-01.oss-cn-wulanchabu.aliyuncs.com/ui_autotest/pro/image/2025/11/22/4c%3A49%3A29%3A33%3Ad4%3Af0/20251122110803.jpg?x-oss-date=20251122T030805Z&x-oss-expires=36000&x-oss-signature-version=OSS4-HMAC-SHA256&x-oss-credential=LTAI5t9dAxAuGWFB59u1pBnp%2F20251122%2Fcn-wulanchabu%2Foss%2Faliyun_v4_request&x-oss-signature=428ba943aef80591bffcd4dea720c2d5e0c13d4e05acc7abab073846d0f6af77"
    url = bucket.renew_url(url)
    local_file_path = bucket.download_url(url, local_file_path)
    print(url)
    print(local_file_path)
    '''
    local_file_path = 'test.mp4'
    object_name = "ui_autotest/wangxinbo/test.mp4"
    import pdb; pdb.set_trace()
    object_name = bucket.upload(object_name, local_file_path)
    url = bucket.get_url(object_name)
    print('预签名URL的地址为：', url)   

    bucket.download(object_name, local_file_path) 
    '''
