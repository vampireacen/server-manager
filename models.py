from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # user, admin
    student_id = db.Column(db.String(50))  # 学号
    laboratory = db.Column(db.String(100))  # 实验室
    supervisor = db.Column(db.String(100))  # 导师
    contact = db.Column(db.String(100))  # 联系方式
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def is_admin(self):
        return self.role == 'admin'

class Server(db.Model):
    __tablename__ = 'servers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, default=22)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(200))  # 可选，也可以用密钥
    status = db.Column(db.String(20), default='unknown')  # online, offline, unknown
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 位置信息 (可选)
    location = db.Column(db.String(200))      # 部署位置
    datacenter = db.Column(db.String(100))    # 部署机房  
    rack = db.Column(db.String(50))           # 部署机柜
    rack_position = db.Column(db.String(20))  # 柜内位置
    
    # 配置信息 (可选)
    cpu_model = db.Column(db.String(100))     # CPU型号
    cpu_count = db.Column(db.Integer)         # CPU数量
    gpu_model = db.Column(db.String(100))     # GPU型号  
    gpu_count = db.Column(db.Integer)         # GPU数量
    memory_model = db.Column(db.String(100))  # 内存型号
    memory_count = db.Column(db.Integer)      # 内存数量
    ssd_model = db.Column(db.String(100))     # SSD型号
    ssd_count = db.Column(db.Integer)         # SSD数量

class PermissionType(db.Model):
    __tablename__ = 'permission_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(200))
    requires_reason = db.Column(db.Boolean, default=False)  # 是否需要填写申请理由

class ApplicationBatch(db.Model):
    """申请批次模型 - 一次申请的集合"""
    __tablename__ = 'application_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    reason = db.Column(db.Text)  # 申请理由
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系
    user = db.relationship('User', backref='application_batches')
    server = db.relationship('Server', backref='application_batches')
    applications = db.relationship('Application', backref='batch', lazy='dynamic')
    
    def get_status_summary(self):
        """获取批次状态摘要"""
        apps = self.applications.all()
        if not apps:
            return 'pending'
        
        statuses = [app.status for app in apps]
        if self.status == 'cancelled':
            return 'cancelled'
        elif all(s in ['approved', 'rejected'] for s in statuses):
            return 'completed'
        elif any(s in ['approved', 'rejected'] for s in statuses):
            return 'processing'
        else:
            return 'pending'
    
    def can_be_cancelled(self):
        """检查是否可以撤销"""
        return self.status == 'pending' and all(app.status == 'pending' for app in self.applications)

class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('application_batches.id'), nullable=False)  # 关联到申请批次
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    permission_type_id = db.Column(db.Integer, db.ForeignKey('permission_types.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    admin_comment = db.Column(db.Text)  # 管理员审核意见
    
    # 关系
    user = db.relationship('User', foreign_keys=[user_id], backref='applications')
    server = db.relationship('Server', backref='applications')
    permission_type = db.relationship('PermissionType', backref='applications')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

class ServerMetric(db.Model):
    __tablename__ = 'server_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    cpu_usage = db.Column(db.Float)  # CPU使用率百分比
    memory_usage = db.Column(db.Float)  # 内存使用率百分比
    disk_usage = db.Column(db.Float)  # 磁盘使用率百分比
    load_average = db.Column(db.String(50))  # 系统负载
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    server = db.relationship('Server', backref='metrics')

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'))  # 关联的申请ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    admin = db.relationship('User', backref='notifications')
    application = db.relationship('Application', backref='notifications')