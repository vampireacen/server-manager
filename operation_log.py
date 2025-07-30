"""
操作日志模块
记录服务器用户管理操作的详细日志
"""

import logging
import os
from datetime import datetime
from models import db, User, Server, Application, PermissionType

# 创建日志目录
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 配置操作日志记录器
operation_logger = logging.getLogger('server_operations')
operation_logger.setLevel(logging.INFO)

# 避免重复添加处理器
if not operation_logger.handlers:
    # 文件处理器 - 记录所有操作
    file_handler = logging.FileHandler(
        os.path.join(log_dir, 'server_operations.log'),
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # 错误文件处理器 - 只记录错误
    error_handler = logging.FileHandler(
        os.path.join(log_dir, 'server_operations_error.log'),
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)
    
    operation_logger.addHandler(file_handler)
    operation_logger.addHandler(error_handler)


class OperationLogger:
    """操作日志记录类"""
    
    @staticmethod
    def log_permission_grant(application, success, message, details=None):
        """记录权限授予操作"""
        log_entry = {
            'operation': 'GRANT_PERMISSION',
            'application_id': application.id,
            'user': application.user.username,
            'server': application.server.name,
            'server_host': application.server.host, 
            'permission_type': application.permission_type.name,
            'success': success,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        }
        
        if success:
            operation_logger.info(f"权限授予成功: {log_entry}")
        else:
            operation_logger.error(f"权限授予失败: {log_entry}")
    
    @staticmethod
    def log_permission_revoke(application, success, message, details=None):
        """记录权限撤销操作"""
        log_entry = {
            'operation': 'REVOKE_PERMISSION',
            'application_id': application.id,
            'user': application.user.username,
            'server': application.server.name,
            'server_host': application.server.host,
            'permission_type': application.permission_type.name,
            'success': success,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        }
        
        if success:
            operation_logger.info(f"权限撤销成功: {log_entry}")
        else:
            operation_logger.error(f"权限撤销失败: {log_entry}")
    
    @staticmethod
    def log_user_creation(server, username, success, message, password_generated=False):
        """记录用户创建操作"""
        log_entry = {
            'operation': 'CREATE_USER',
            'server': server.name,
            'server_host': server.host,
            'username': username,
            'success': success,
            'message': message,
            'password_generated': password_generated,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success:
            operation_logger.info(f"用户创建成功: {log_entry}")
        else:
            operation_logger.error(f"用户创建失败: {log_entry}")
    
    @staticmethod
    def log_ssh_connection(server, success, message):
        """记录SSH连接操作"""
        log_entry = {
            'operation': 'SSH_CONNECTION',
            'server': server.name,
            'server_host': server.host,
            'success': success,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success:
            operation_logger.info(f"SSH连接成功: {log_entry}")
        else:
            operation_logger.error(f"SSH连接失败: {log_entry}")
    
    @staticmethod
    def log_command_execution(server, command, success, output, require_sudo=False):
        """记录命令执行操作"""
        log_entry = {
            'operation': 'EXECUTE_COMMAND',
            'server': server.name,
            'server_host': server.host,
            'command': command[:100] + '...' if len(command) > 100 else command,  # 截断长命令
            'require_sudo': require_sudo,
            'success': success,
            'output': output[:500] + '...' if len(output) > 500 else output,  # 截断长输出
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success:
            operation_logger.info(f"命令执行成功: {log_entry}")
        else:
            operation_logger.error(f"命令执行失败: {log_entry}")
    
    @staticmethod
    def log_group_operation(server, username, group, operation, success, message):
        """记录组操作（添加到组或从组移除）"""
        log_entry = {
            'operation': f'{operation.upper()}_GROUP',
            'server': server.name,
            'server_host': server.host,
            'username': username,
            'group': group,
            'success': success,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success:
            operation_logger.info(f"组操作成功: {log_entry}")
        else:
            operation_logger.error(f"组操作失败: {log_entry}")
    
    @staticmethod
    def get_recent_logs(limit=100):
        """获取最近的操作日志"""
        try:
            log_file = os.path.join(log_dir, 'server_operations.log')
            if not os.path.exists(log_file):
                return []
            
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 返回最后N行
            return lines[-limit:]
        except Exception as e:
            operation_logger.error(f"读取日志失败: {e}")
            return []
    
    @staticmethod
    def get_error_logs(limit=50):
        """获取最近的错误日志"""
        try:
            error_log_file = os.path.join(log_dir, 'server_operations_error.log')
            if not os.path.exists(error_log_file):
                return []
            
            with open(error_log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 返回最后N行
            return lines[-limit:]
        except Exception as e:
            operation_logger.error(f"读取错误日志失败: {e}")
            return []
    
    @staticmethod
    def get_user_operation_history(username, limit=20):
        """获取特定用户的操作历史"""
        try:
            log_file = os.path.join(log_dir, 'server_operations.log')
            if not os.path.exists(log_file):
                return []
            
            user_logs = []
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if f"'user': '{username}'" in line or f'"user": "{username}"' in line:
                        user_logs.append(line.strip())
            
            # 返回最后N条记录
            return user_logs[-limit:]
        except Exception as e:
            operation_logger.error(f"读取用户操作历史失败: {e}")
            return []
    
    @staticmethod
    def get_server_operation_history(server_name, limit=20):
        """获取特定服务器的操作历史"""
        try:
            log_file = os.path.join(log_dir, 'server_operations.log')
            if not os.path.exists(log_file):
                return []
            
            server_logs = []
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if f"'server': '{server_name}'" in line or f'"server": "{server_name}"' in line:
                        server_logs.append(line.strip())
            
            # 返回最后N条记录
            return server_logs[-limit:]
        except Exception as e:
            operation_logger.error(f"读取服务器操作历史失败: {e}")
            return []


def cleanup_old_logs(days=30):
    """清理旧日志文件"""
    import time
    
    try:
        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 60 * 60)
        
        for log_file in ['server_operations.log', 'server_operations_error.log']:
            file_path = os.path.join(log_dir, log_file)
            if os.path.exists(file_path):
                # 如果文件太旧，重命名为归档文件
                if os.path.getctime(file_path) < cutoff_time:
                    archive_name = f"{log_file}.{datetime.now().strftime('%Y%m%d')}.old"
                    archive_path = os.path.join(log_dir, archive_name)
                    os.rename(file_path, archive_path)
                    operation_logger.info(f"日志文件已归档: {archive_name}")
                    
    except Exception as e:
        operation_logger.error(f"清理日志文件失败: {e}")


# 应用启动时清理旧日志
if __name__ != '__main__':
    try:
        cleanup_old_logs()
    except:
        pass  # 静默处理清理错误