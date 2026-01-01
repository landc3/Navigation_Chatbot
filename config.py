"""
配置文件
从环境变量读取配置信息
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Config:
    """应用配置"""
    
    # 通义千问 API 配置
    ALI_QWEN_API_KEY = os.getenv('ALI_QWEN_API_KEY', 'sk-7e1aeb711dec4355b53ecd8ff0116057')
    # 使用最新的 Qwen-Plus 版本（2025-07-28），支持1M上下文，阶梯计费
    ALI_QWEN_MODEL = os.getenv('ALI_QWEN_MODEL', 'qwen-plus-2025-07-28')  # 最新版本
    
    # 后端服务配置
    BACKEND_HOST = os.getenv('BACKEND_HOST', '0.0.0.0')
    BACKEND_PORT = int(os.getenv('BACKEND_PORT', 8000))
    
    # 前端配置
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3500')
    
    # 数据文件路径
    DATA_CSV_PATH = os.getenv('DATA_CSV_PATH', '资料清单.csv')
    KEYWORDS_PATH = os.getenv('KEYWORDS_PATH', 'keywords.txt')
    # 同义/包含词族配置（JSON文件路径，相对项目根目录）
    SYNONYM_FAMILIES_PATH = os.getenv('SYNONYM_FAMILIES_PATH', 'synonyms.json')
    
    # LLM 调用配置
    MAX_TOKENS = int(os.getenv('MAX_TOKENS', 1500))  # 最大输出 token 数
    TEMPERATURE = float(os.getenv('TEMPERATURE', 0.7))  # 温度参数（0-1，越高越随机）
    
    # 检索配置
    MAX_SEARCH_RESULTS = int(os.getenv('MAX_SEARCH_RESULTS', 20))  # 最大搜索结果数
    MAX_FINAL_RESULTS = int(os.getenv('MAX_FINAL_RESULTS', 5))  # 最终返回的最大结果数
    
    # 选择题配置
    MIN_CHOICES = int(os.getenv('MIN_CHOICES', 3))  # 最少选项数
    MAX_CHOICES = int(os.getenv('MAX_CHOICES', 5))  # 最多选项数
    
    @classmethod
    def validate(cls):
        """验证配置"""
        if not cls.ALI_QWEN_API_KEY:
            raise ValueError("ALI_QWEN_API_KEY 未设置")
        
        if not cls.ALI_QWEN_API_KEY.startswith('sk-'):
            print("⚠️  警告：API Key 格式可能不正确（应以 'sk-' 开头）")
        
        return True


# 创建配置实例
config = Config()

