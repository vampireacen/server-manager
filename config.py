import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SSH连接超时设置
    SSH_TIMEOUT = 10
    
    # 监控数据刷新间隔（秒）
    MONITOR_REFRESH_INTERVAL = 30
    
    # 分页设置
    APPLICATIONS_PER_PAGE = 20