"""
服务器用户管理模块
自动化服务器用户创建和权限配置
"""

import paramiko
import secrets
import string
import logging
import re
import shlex
from datetime import datetime
from models import db, Server, User, PermissionType, Application
from operation_log import OperationLogger

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServerUserManager:
    """服务器用户管理类"""
    
    def __init__(self, server):
        self.server = server
        self.ssh_client = None
    
    def validate_username(self, username):
        """验证用户名是否合法"""
        # Linux用户名规则：只能包含字母、数字、下划线、连字符，以字母开头，长度3-32
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]{2,31}$', username):
            return False, "用户名不符合Linux命名规范（3-32位，字母开头，只能包含字母数字下划线连字符）"
        
        # 检查保留用户名
        reserved_names = ['root', 'daemon', 'bin', 'sys', 'sync', 'games', 'man', 'lp', 'mail', 
                         'news', 'uucp', 'proxy', 'backup', 'nobody', 'www-data', 'mysql', 
                         'postgres', 'redis', 'mongodb', 'docker', 'admin', 'administrator']
        if username.lower() in reserved_names:
            return False, f"用户名 '{username}' 是系统保留用户名，不能使用"
            
        return True, "用户名合法"
    
    def validate_group_name(self, group):
        """验证组名是否合法"""
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]{0,31}$', group):
            return False, "组名不符合Linux命名规范"
        return True, "组名合法"
        
    def connect(self):
        """连接到服务器"""
        try:
            self.ssh_client = paramiko.SSHClient()
            # 设置主机密钥策略 - 在生产环境中应该使用更严格的策略
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 基础连接配置
            connect_params = {
                'hostname': self.server.host,
                'port': self.server.port,
                'username': self.server.username,
                'timeout': 30,
                'auth_timeout': 30,
                'banner_timeout': 30
            }
            
            # 根据认证类型设置认证参数
            auth_type = getattr(self.server, 'auth_type', 'password') or 'password'
            
            if auth_type == 'key':
                # 密钥认证
                key_path = getattr(self.server, 'key_path', None)
                if not key_path:
                    raise ValueError("密钥认证需要提供密钥文件路径")
                
                try:
                    # 尝试加载私钥
                    private_key = paramiko.RSAKey.from_private_key_file(key_path)
                    connect_params['pkey'] = private_key
                except paramiko.SSHException:
                    try:
                        # 尝试DSA密钥
                        private_key = paramiko.DSSKey.from_private_key_file(key_path)
                        connect_params['pkey'] = private_key
                    except paramiko.SSHException:
                        try:
                            # 尝试ECDSA密钥
                            private_key = paramiko.ECDSAKey.from_private_key_file(key_path)
                            connect_params['pkey'] = private_key
                        except paramiko.SSHException:
                            try:
                                # 尝试Ed25519密钥
                                private_key = paramiko.Ed25519Key.from_private_key_file(key_path)
                                connect_params['pkey'] = private_key
                            except paramiko.SSHException:
                                raise ValueError(f"无法解析密钥文件: {key_path}")
                
                logger.info(f"使用密钥认证连接服务器 {self.server.name}")
            else:
                # 密码认证
                if not self.server.password:
                    raise ValueError("密码认证需要提供密码")
                connect_params['password'] = self.server.password
                logger.info(f"使用密码认证连接服务器 {self.server.name}")
            
            # 验证基础连接参数
            if not all([self.server.host, self.server.username]):
                raise ValueError("服务器连接参数不完整")
            
            self.ssh_client.connect(**connect_params)
            
            # 验证连接是否真正可用
            test_command = "echo 'connection_test'"
            stdin, stdout, stderr = self.ssh_client.exec_command(test_command, timeout=10)
            if stdout.channel.recv_exit_status() != 0:
                raise Exception("连接测试失败")
                
            logger.info(f"成功连接到服务器 {self.server.name}")
            return True
            
        except paramiko.AuthenticationException:
            logger.error(f"服务器 {self.server.name} 认证失败")
            return False
        except paramiko.SSHException as e:
            logger.error(f"SSH连接异常 {self.server.name}: {e}")
            return False
        except Exception as e:
            logger.error(f"连接服务器 {self.server.name} 失败: {e}")
            return False
    
    def disconnect(self):
        """断开服务器连接"""
        if self.ssh_client:
            self.ssh_client.close()
            logger.info(f"断开与服务器 {self.server.name} 的连接")
    
    def execute_command(self, command, require_sudo=False, timeout=60):
        """执行SSH命令"""
        if not self.ssh_client:
            return False, "SSH连接未建立"
        
        # 验证命令安全性 - 防止命令注入
        if not self._is_safe_command(command):
            return False, "命令包含不安全字符，已拒绝执行"
        
        try:
            if require_sudo:
                # 对于需要sudo的命令，使用echo密码的方式
                # 使用shlex.quote确保密码安全传递
                import shlex
                safe_password = shlex.quote(self.server.password)
                command = f"echo {safe_password} | sudo -S {command}"
            
            stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            
            # 等待命令执行完成，设置超时
            exit_status = stdout.channel.recv_exit_status()
            
            stdout_output = stdout.read().decode('utf-8').strip()
            stderr_output = stderr.read().decode('utf-8').strip()
            
            # 记录命令执行日志
            OperationLogger.log_command_execution(
                self.server, command, exit_status == 0, 
                stdout_output if exit_status == 0 else stderr_output, 
                require_sudo
            )
            
            if exit_status == 0:
                logger.info(f"命令执行成功: {command[:50]}...")
                return True, stdout_output
            else:
                logger.error(f"命令执行失败: {command[:50]}..., Error: {stderr_output}")
                return False, stderr_output
                
        except Exception as e:
            logger.error(f"执行命令异常: {e}")
            OperationLogger.log_command_execution(self.server, command, False, str(e), require_sudo)
            return False, str(e)
    
    def _is_safe_command(self, command):
        """检查命令是否安全"""
        # 基本的命令安全检查
        dangerous_patterns = [
            r'rm\s+-rf\s+/',  # 危险的删除命令
            r';.*rm\s',        # 命令链中的删除
            r'\|.*rm\s',       # 管道中的删除
            r'>\s*/dev/',      # 重定向到设备文件
            r'wget\s+http',    # 网络下载
            r'curl\s+http',    # 网络请求
            r'\$\(',           # 命令替换
            r'`[^`]*`',        # 反引号命令替换
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                logger.warning(f"检测到潜在危险命令: {command}")
                return False
        
        return True
    
    def user_exists(self, username):
        """检查用户是否存在"""
        import shlex
        safe_username = shlex.quote(username)
        success, output = self.execute_command(f"id {safe_username}")
        return success
    
    def generate_password(self, length=16):
        """生成随机密码"""
        # 使用更安全的字符集，避免可能引起shell问题的特殊字符
        alphabet = string.ascii_letters + string.digits + "@#%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password
    
    def create_user(self, username, password=None):
        """创建Linux用户"""
        # 验证用户名
        valid, msg = self.validate_username(username)
        if not valid:
            return False, msg
            
        if self.user_exists(username):
            logger.info(f"用户 {username} 已存在，跳过创建")
            return True, "用户已存在"
        
        if not password:
            password = self.generate_password()
        
        try:
            # 创建用户
            import shlex
            safe_username = shlex.quote(username)
            success, output = self.execute_command(
                f"useradd -m -s /bin/bash {safe_username}", 
                require_sudo=True
            )
            
            if not success:
                return False, f"创建用户失败: {output}"
            
            # 设置密码 - 使用更安全的方式
            import shlex
            safe_username = shlex.quote(username)
            safe_password = shlex.quote(password)
            success, output = self.execute_command(
                f"sh -c \"echo {safe_username}:{safe_password} | chpasswd\"", 
                require_sudo=True
            )
            
            if not success:
                return False, f"设置密码失败: {output}"
            
            logger.info(f"成功创建用户 {username}")
            return True, password
            
        except Exception as e:
            logger.error(f"创建用户异常: {e}")
            return False, str(e)
    
    def add_user_to_group(self, username, group):
        """将用户添加到指定组"""
        # 验证用户名和组名
        valid, msg = self.validate_username(username)
        if not valid:
            return False, f"用户名验证失败: {msg}"
            
        valid, msg = self.validate_group_name(group)
        if not valid:
            return False, f"组名验证失败: {msg}"
            
        import shlex
        safe_username = shlex.quote(username)
        safe_group = shlex.quote(group)
        success, output = self.execute_command(
            f"usermod -a -G {safe_group} {safe_username}", 
            require_sudo=True
        )
        
        if success:
            logger.info(f"用户 {username} 已添加到组 {group}")
        else:
            logger.error(f"添加用户 {username} 到组 {group} 失败: {output}")
        
        return success, output
    
    def remove_user_from_group(self, username, group):
        """从指定组移除用户"""
        # 验证用户名和组名
        valid, msg = self.validate_username(username)
        if not valid:
            return False, f"用户名验证失败: {msg}"
            
        valid, msg = self.validate_group_name(group)
        if not valid:
            return False, f"组名验证失败: {msg}"
            
        import shlex
        safe_username = shlex.quote(username)
        safe_group = shlex.quote(group)
        success, output = self.execute_command(
            f"gpasswd -d {safe_username} {safe_group}", 
            require_sudo=True
        )
        
        if success:
            logger.info(f"用户 {username} 已从组 {group} 移除")
        else:
            logger.error(f"从组 {group} 移除用户 {username} 失败: {output}")
        
        return success, output
    
    def configure_sudo_access(self, username, enable=True):
        """配置sudo权限"""
        if enable:
            # 添加到sudo组
            return self.add_user_to_group(username, "sudo")
        else:
            # 从sudo组移除
            return self.remove_user_from_group(username, "sudo")
    
    def configure_docker_access(self, username, enable=True):
        """配置Docker权限"""
        if enable:
            # 检查docker组是否存在，不存在则创建
            success, output = self.execute_command("getent group docker")
            if not success:
                logger.info("Docker组不存在，创建docker组")
                success, output = self.execute_command("groupadd docker", require_sudo=True)
                if not success:
                    return False, f"创建docker组失败: {output}"
            
            # 添加到docker组
            return self.add_user_to_group(username, "docker")
        else:
            # 从docker组移除
            return self.remove_user_from_group(username, "docker")
    
    def get_user_groups(self, username):
        """获取用户所在的组"""
        import shlex
        safe_username = shlex.quote(username)
        success, output = self.execute_command(f"groups {safe_username}")
        if success:
            # 输出格式: username : group1 group2 group3
            groups = output.split(':')[1].strip().split() if ':' in output else []
            return True, groups
        return False, []


def configure_user_permissions_batch(applications):
    """
    批量配置用户权限的主函数
    处理同一用户在同一服务器的多个权限申请，只建立一次SSH连接
    """
    if not applications:
        return []
    
    # 按服务器和用户分组
    server_user_groups = {}
    for app in applications:
        key = (app.server.id, app.user.id)
        if key not in server_user_groups:
            server_user_groups[key] = []
        server_user_groups[key].append(app)
    
    results = []
    
    for (server_id, user_id), apps in server_user_groups.items():
        server = apps[0].server
        user = apps[0].user
        
        # 获取服务器账户名（优先使用自定义的server_username）
        server_username = apps[0].server_username or user.username
        logger.info(f"开始批量配置用户 {user.username} (服务器账户: {server_username}) 在服务器 {server.name} 的权限")
        
        # 创建服务器管理器
        manager = ServerUserManager(server)
        
        # 连接服务器
        if not manager.connect():
            OperationLogger.log_ssh_connection(server, False, "SSH连接失败")
            for app in apps:
                results.append((app, False, "无法连接到服务器"))
            continue
        
        OperationLogger.log_ssh_connection(server, True, "SSH连接成功")
        
        try:
            # 生成用户密码（如果用户不存在）
            user_password = None
            
            # 检查并创建用户（使用服务器账户名）
            if not manager.user_exists(server_username):
                success, result = manager.create_user(server_username)
                if not success:
                    OperationLogger.log_user_creation(server, server_username, False, result)
                    for app in apps:
                        results.append((app, False, f"创建用户失败: {result}"))
                    continue
                user_password = result
                OperationLogger.log_user_creation(server, server_username, True, "用户创建成功", password_generated=True)
            else:
                logger.info(f"用户 {server_username} 已存在")
                OperationLogger.log_user_creation(server, server_username, True, "用户已存在，跳过创建")
            
            # 批量配置所有权限
            for app in apps:
                permission_type = app.permission_type
                
                # 根据权限类型配置权限（使用服务器账户名）
                success, message = configure_permission_by_type(manager, server_username, permission_type.name)
                
                if not success:
                    OperationLogger.log_permission_grant(app, False, message)
                    results.append((app, False, message))
                    continue
                
                # 记录操作结果
                operation_log = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'server': server.name,
                    'user': server_username,
                    'permission': permission_type.name,
                    'action': 'granted',
                    'password_generated': user_password is not None,
                    'message': message
                }
                
                # 如果生成了新密码，将其保存到第一个application的admin_comment中
                if user_password and app == apps[0]:
                    current_comment = app.admin_comment or ""
                    app.admin_comment = f"{current_comment}\n[系统生成] 用户密码: {user_password}".strip()
                    db.session.commit()
                
                logger.info(f"权限配置完成: {operation_log}")
                OperationLogger.log_permission_grant(app, True, message, details={'password_generated': user_password is not None})
                results.append((app, True, f"{permission_type.name} 权限配置成功"))
            
        finally:
            manager.disconnect()
    
    return results


def configure_user_permissions(application):
    """
    配置用户权限的主函数
    在管理员批准申请后调用
    """
    try:
        # 获取相关对象
        server = application.server
        user = application.user
        permission_type = application.permission_type
        
        # 获取服务器账户名（优先使用自定义的server_username）
        server_username = application.server_username or user.username
        
        logger.info(f"开始为用户 {user.username} (服务器账户: {server_username}) 在服务器 {server.name} 配置 {permission_type.name}")
        
        # 创建服务器管理器
        manager = ServerUserManager(server)
        
        # 连接服务器
        if not manager.connect():
            OperationLogger.log_ssh_connection(server, False, "SSH连接失败")
            return False, "无法连接到服务器"
        
        OperationLogger.log_ssh_connection(server, True, "SSH连接成功")
        
        try:
            # 生成用户密码（如果用户不存在）
            user_password = None
            
            # 检查并创建用户（使用服务器账户名）
            if not manager.user_exists(server_username):
                success, result = manager.create_user(server_username)
                if not success:
                    OperationLogger.log_user_creation(server, server_username, False, result)
                    return False, f"创建用户失败: {result}"
                user_password = result
                OperationLogger.log_user_creation(server, server_username, True, "用户创建成功", password_generated=True)
            else:
                logger.info(f"用户 {server_username} 已存在")
                OperationLogger.log_user_creation(server, server_username, True, "用户已存在，跳过创建")
            
            # 根据权限类型配置权限（使用服务器账户名）
            success, message = configure_permission_by_type(manager, server_username, permission_type.name)
            
            if not success:
                OperationLogger.log_permission_grant(application, False, message)
                return False, message
            
            # 记录操作结果
            operation_log = {
                'timestamp': datetime.utcnow().isoformat(),
                'server': server.name,
                'user': server_username,
                'permission': permission_type.name,
                'action': 'granted',
                'password_generated': user_password is not None,
                'message': message
            }
            
            # 如果生成了新密码，将其保存到application的admin_comment中
            if user_password:
                current_comment = application.admin_comment or ""
                application.admin_comment = f"{current_comment}\n[系统生成] 用户密码: {user_password}".strip()
                db.session.commit()
            
            logger.info(f"用户权限配置完成: {operation_log}")
            OperationLogger.log_permission_grant(application, True, message, details={'password_generated': user_password is not None})
            return True, f"用户 {server_username} 的 {permission_type.name} 权限配置成功"
            
        finally:
            manager.disconnect()
            
    except Exception as e:
        logger.error(f"配置用户权限异常: {e}")
        return False, f"配置权限时发生异常: {str(e)}"


def configure_permission_by_type(manager, username, permission_type_name):
    """根据权限类型配置具体权限"""
    
    if permission_type_name == "普通用户":
        # 普通用户只需要基本的shell访问权限，无需特殊配置
        return True, "普通用户权限配置完成"
    
    elif permission_type_name == "管理员权限":
        # 配置sudo权限
        success, output = manager.configure_sudo_access(username, enable=True)
        if success:
            return True, "管理员权限(sudo)配置完成"
        else:
            return False, f"配置sudo权限失败: {output}"
    
    elif permission_type_name == "Docker权限":
        # 配置Docker权限
        success, output = manager.configure_docker_access(username, enable=True)
        if success:
            return True, "Docker权限配置完成"
        else:
            return False, f"配置Docker权限失败: {output}"
    
    elif permission_type_name == "数据库权限":
        # 数据库权限通常需要应用层面的配置，这里只做基本的用户组配置
        # 可以根据实际需求创建数据库专用组
        success, output = manager.execute_command("getent group database")
        if not success:
            # 创建database组
            success, output = manager.execute_command("groupadd database", require_sudo=True)
            if not success:
                return False, f"创建database组失败: {output}"
        
        # 添加用户到database组
        success, output = manager.add_user_to_group(username, "database")
        if success:
            return True, "数据库权限配置完成"
        else:
            return False, f"配置数据库权限失败: {output}"
    
    elif permission_type_name == "自定义权限":
        # 自定义权限保持基本权限，具体配置可能需要管理员手动处理
        return True, "自定义权限配置完成（可能需要管理员手动配置特定权限）"
    
    else:
        return False, f"未知的权限类型: {permission_type_name}"


def revoke_user_permissions(application):
    """
    撤销用户权限
    在权限被撤销或用户被删除时调用
    """
    try:
        server = application.server
        user = application.user
        permission_type = application.permission_type
        
        logger.info(f"开始撤销用户 {user.username} 在服务器 {server.name} 的 {permission_type.name}")
        
        manager = ServerUserManager(server)
        
        if not manager.connect():
            return False, "无法连接到服务器"
        
        try:
            # 检查用户是否存在
            if not manager.user_exists(user.username):
                return True, "用户不存在，无需撤销权限"
            
            # 根据权限类型撤销权限
            success, message = revoke_permission_by_type(manager, user.username, permission_type.name)
            
            logger.info(f"权限撤销完成: {user.username} - {permission_type.name}")
            return success, message
            
        finally:
            manager.disconnect()
            
    except Exception as e:
        logger.error(f"撤销用户权限异常: {e}")
        return False, f"撤销权限时发生异常: {str(e)}"


def revoke_permission_by_type(manager, username, permission_type_name):
    """根据权限类型撤销具体权限"""
    
    if permission_type_name == "普通用户":
        return True, "普通用户权限撤销完成"
    
    elif permission_type_name == "管理员权限":
        success, output = manager.configure_sudo_access(username, enable=False)
        if success:
            return True, "管理员权限撤销完成"
        else:
            return False, f"撤销sudo权限失败: {output}"
    
    elif permission_type_name == "Docker权限":
        success, output = manager.configure_docker_access(username, enable=False)
        if success:
            return True, "Docker权限撤销完成"
        else:
            return False, f"撤销Docker权限失败: {output}"
    
    elif permission_type_name == "数据库权限":
        success, output = manager.remove_user_from_group(username, "database")
        if success:
            return True, "数据库权限撤销完成"
        else:
            return False, f"撤销数据库权限失败: {output}"
    
    elif permission_type_name == "自定义权限":
        return True, "自定义权限撤销完成"
    
    else:
        return False, f"未知的权限类型: {permission_type_name}"


def delete_user_from_servers(user):
    """
    从所有服务器删除用户账户和权限
    用于完全删除用户时调用
    """
    try:
        # 获取用户的所有已批准申请
        approved_applications = Application.query.filter_by(
            user_id=user.id,
            status='approved'
        ).options(db.joinedload(Application.server), db.joinedload(Application.permission_type)).all()
        
        if not approved_applications:
            logger.info(f"用户 {user.username} 没有已批准的权限，无需删除服务器账户")
            return True, "用户没有服务器权限，删除完成"
        
        # 按服务器分组
        servers_to_process = {}
        for app in approved_applications:
            server_id = app.server.id
            if server_id not in servers_to_process:
                servers_to_process[server_id] = {
                    'server': app.server,
                    'applications': []
                }
            servers_to_process[server_id]['applications'].append(app)
        
        results = []
        success_count = 0
        total_servers = len(servers_to_process)
        
        logger.info(f"开始从 {total_servers} 台服务器删除用户 {user.username}")
        
        for server_id, data in servers_to_process.items():
            server = data['server']
            applications = data['applications']
            
            logger.info(f"处理服务器 {server.name} 上的用户 {user.username}")
            
            # 创建服务器管理器
            manager = ServerUserManager(server)
            
            # 连接服务器
            if not manager.connect():
                error_msg = f"无法连接到服务器 {server.name}"
                logger.error(error_msg)
                OperationLogger.log_ssh_connection(server, False, error_msg)
                results.append((server.name, False, error_msg))
                continue
            
            OperationLogger.log_ssh_connection(server, True, "SSH连接成功，准备删除用户")
            
            try:
                # 检查用户是否存在
                server_username = applications[0].server_username or user.username  # 使用正确的服务器账户名
                if not manager.user_exists(server_username):
                    logger.info(f"用户 {server_username} 在服务器 {server.name} 上不存在，跳过删除")
                    results.append((server.name, True, "用户不存在，无需删除"))
                    success_count += 1
                    
                    # 更新数据库状态，因为服务器上没有该账户
                    try:
                        for app in applications:
                            if app.status == 'approved':
                                app.status = 'revoked'
                                app.admin_comment = (app.admin_comment or '') + f'\n[系统检查] 服务器上账户不存在 - {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}'
                        db.session.commit()
                        logger.info(f"已更新服务器 {server.name} 上 {len(applications)} 个权限记录状态")
                    except Exception as db_error:
                        logger.error(f"更新数据库状态失败: {db_error}")
                        db.session.rollback()
                    
                    continue
                
                # 撤销所有权限（使用正确的服务器账户名）
                permissions_revoked = []
                for app in applications:
                    success, message = revoke_permission_by_type(manager, server_username, app.permission_type.name)
                    if success:
                        permissions_revoked.append(app.permission_type.name)
                        logger.info(f"撤销权限成功: {app.permission_type.name}")
                    else:
                        logger.warning(f"撤销权限失败: {app.permission_type.name} - {message}")
                
                # 删除用户账户（使用正确的服务器账户名）
                import shlex
                safe_username = shlex.quote(server_username)
                success, output = manager.execute_command(
                    f"userdel -r {safe_username}",  # -r 参数会删除用户主目录
                    require_sudo=True
                )
                
                if success:
                    success_count += 1
                    result_msg = f"用户账户删除成功"
                    if permissions_revoked:
                        result_msg += f"，撤销权限: {', '.join(permissions_revoked)}"
                    
                    logger.info(f"服务器 {server.name}: {result_msg}")
                    results.append((server.name, True, result_msg))
                    
                    # 记录操作日志
                    OperationLogger.log_user_deletion(server, server_username, True, result_msg)
                    
                    # 更新数据库中的Application记录状态为'revoked'
                    try:
                        for app in applications:
                            if app.status == 'approved':
                                app.status = 'revoked'
                                app.admin_comment = (app.admin_comment or '') + f'\n[系统操作] 服务器账户已删除 - {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}'
                        db.session.commit()
                        logger.info(f"已更新服务器 {server.name} 上 {len(applications)} 个权限记录状态为'revoked'")
                    except Exception as db_error:
                        logger.error(f"更新数据库状态失败: {db_error}")
                        db.session.rollback()
                else:
                    error_msg = f"删除用户账户失败: {output}"
                    logger.error(f"服务器 {server.name}: {error_msg}")
                    results.append((server.name, False, error_msg))
                    OperationLogger.log_user_deletion(server, server_username, False, error_msg)
                
            finally:
                manager.disconnect()
        
        # 汇总结果
        if success_count == total_servers:
            summary = f"成功从所有 {total_servers} 台服务器删除用户 {user.username}"
            logger.info(summary)
            return True, summary
        elif success_count > 0:
            summary = f"部分成功：从 {success_count}/{total_servers} 台服务器删除用户 {user.username}"
            logger.warning(summary)
            return False, summary
        else:
            summary = f"删除失败：无法从任何服务器删除用户 {user.username}"
            logger.error(summary)
            return False, summary
            
    except Exception as e:
        logger.error(f"删除用户服务器账户异常: {e}")
        return False, f"删除用户时发生异常: {str(e)}"


def delete_user_account_only(username, server):
    """
    仅删除指定服务器上的用户账户（不撤销权限记录）
    用于单独的用户账户删除操作
    """
    try:
        logger.info(f"开始删除服务器 {server.name} 上的用户账户 {username}")
        
        # 创建服务器管理器
        manager = ServerUserManager(server)
        
        # 连接服务器
        if not manager.connect():
            error_msg = f"无法连接到服务器 {server.name}"
            logger.error(error_msg)
            return False, error_msg
        
        try:
            # 检查用户是否存在
            if not manager.user_exists(username):
                return True, "用户不存在，无需删除"
            
            # 删除用户账户
            import shlex
            safe_username = shlex.quote(username)
            success, output = manager.execute_command(
                f"userdel -r {safe_username}",  # -r 参数会删除用户主目录
                require_sudo=True
            )
            
            if success:
                logger.info(f"服务器 {server.name} 上的用户账户 {username} 删除成功")
                return True, "用户账户删除成功"
            else:
                error_msg = f"删除用户账户失败: {output}"
                logger.error(f"服务器 {server.name}: {error_msg}")
                return False, error_msg
                
        finally:
            manager.disconnect()
            
    except Exception as e:
        logger.error(f"删除用户账户异常: {e}")
        return False, f"删除用户账户时发生异常: {str(e)}"