"""
训练数据API配置管理
"""
import os
import json

class TrainDataConfig:
    """训练数据API配置管理器"""
    
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self._ensure_config_file()
    
    def _ensure_config_file(self):
        """确保配置文件存在"""
        if not os.path.exists(self.config_file_path):
            default_config = {
                "api_base_url": "http://localhost:5001",
                "api_token": "your-token-here",
                "version": "0.0"
            }
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
        else:
            # 如果文件存在但缺少version字段，添加它
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if 'version' not in config:
                    config['version'] = '0.0'
                    with open(self.config_file_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Failed to check/update config file: {e}")
    
    def get_config(self):
        """获取配置"""
        return {
            "api_base_url": "http://10.74.193.42:8081",
            "api_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImV4X3lhbmdmYW4ud3UifQ.EtOPk0E2yTne9MHamaFSpE8KugASXcCCgrHkY3J4grM",
            "version": "0.0"
        }
    
    def _save_config(self, config):
        """保存配置到文件"""
        try:
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save config: {e}")
    
    
    def set_version(self, version):
        """设置版本号"""
        config = self.get_config()
        config['version'] = version
        self._save_config(config)
        return version
    
    def update_config(self, api_base_url, api_token):
        """更新配置"""
        config = self.get_config()
        config["api_base_url"] = api_base_url
        config["api_token"] = api_token
        # 确保version字段保留
        if 'version' not in config:
            config['version'] = '0.0'
        self._save_config(config)
        return config
    
    def get_headers(self):
        """获取请求头"""
        config = self.get_config()
        token = config.get('api_token', '')
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_base_url(self):
        """获取基础URL"""
        config = self.get_config()
        return config.get('api_base_url', 'http://localhost:5001')
