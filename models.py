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

class PermissionType(db.Model):
    __tablename__ = 'permission_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(200))
    requires_reason = db.Column(db.Boolean, default=False)  # 是否需要填写申请理由

class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    permission_type_id = db.Column(db.Integer, db.ForeignKey('permission_types.id'), nullable=False)
    reason = db.Column(db.Text)  # 申请理由
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