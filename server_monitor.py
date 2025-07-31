import paramiko
import json
import re
from datetime import datetime
from models import db, Server, ServerMetric

class ServerMonitor:
    def __init__(self, server):
        self.server = server
        self.ssh_client = None
    
    def connect(self):
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 基础连接参数
            connect_params = {
                'hostname': self.server.host,
                'port': self.server.port,
                'username': self.server.username,
                'timeout': 10
            }
            
            # 根据认证类型设置认证参数
            auth_type = getattr(self.server, 'auth_type', 'password') or 'password'
            
            if auth_type == 'key':
                # 密钥认证
                key_path = getattr(self.server, 'key_path', None)
                if key_path:
                    try:
                        # 尝试加载私钥
                        private_key = paramiko.RSAKey.from_private_key_file(key_path)
                        connect_params['pkey'] = private_key
                    except paramiko.SSHException:
                        try:
                            private_key = paramiko.DSSKey.from_private_key_file(key_path)
                            connect_params['pkey'] = private_key
                        except paramiko.SSHException:
                            try:
                                private_key = paramiko.ECDSAKey.from_private_key_file(key_path)
                                connect_params['pkey'] = private_key
                            except paramiko.SSHException:
                                try:
                                    private_key = paramiko.Ed25519Key.from_private_key_file(key_path)
                                    connect_params['pkey'] = private_key
                                except paramiko.SSHException:
                                    print(f"无法解析密钥文件: {key_path}")
                                    return False
            else:
                # 密码认证
                connect_params['password'] = self.server.password
            
            self.ssh_client.connect(**connect_params)
            return True
        except Exception as e:
            print(f"连接服务器 {self.server.name} 失败: {e}")
            return False
    
    def disconnect(self):
        if self.ssh_client:
            self.ssh_client.close()
    
    def execute_command(self, command):
        if not self.ssh_client:
            return None
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            return stdout.read().decode('utf-8').strip()
        except Exception as e:
            print(f"执行命令失败: {e}")
            return None
    
    def get_cpu_usage(self):
        # 获取CPU使用率
        command = "top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'"
        result = self.execute_command(command)
        if result:
            try:
                return float(result)
            except ValueError:
                # 备用方法
                command = "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4)} END {print usage}'"
                result = self.execute_command(command)
                if result:
                    try:
                        return float(result)
                    except ValueError:
                        return 0
        return 0
    
    def get_memory_usage(self):
        # 获取内存使用率
        command = "free | grep Mem | awk '{printf \"%.2f\", $3/$2 * 100.0}'"
        result = self.execute_command(command)
        if result:
            try:
                return float(result)
            except ValueError:
                return 0
        return 0
    
    def get_disk_usage(self):
        # 获取根分区磁盘使用率
        command = "df -h / | awk 'NR==2 {print $5}' | sed 's/%//'"
        result = self.execute_command(command)
        if result:
            try:
                return float(result)
            except ValueError:
                return 0
        return 0
    
    def get_load_average(self):
        # 获取系统负载
        command = "uptime | awk -F'load average:' '{print $2}'"
        result = self.execute_command(command)
        return result.strip() if result else "0.00, 0.00, 0.00"
    
    def collect_metrics(self):
        if not self.connect():
            return None
        
        try:
            cpu_usage = self.get_cpu_usage()
            memory_usage = self.get_memory_usage()
            disk_usage = self.get_disk_usage()
            load_average = self.get_load_average()
            
            # 保存监控数据到数据库
            metric = ServerMetric(
                server_id=self.server.id,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                load_average=load_average
            )
            
            db.session.add(metric)
            
            # 更新服务器状态
            self.server.status = 'online'
            db.session.commit()
            
            return {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'disk_usage': disk_usage,
                'load_average': load_average,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"收集监控数据失败: {e}")
            self.server.status = 'offline'
            db.session.commit()
            return None
        finally:
            self.disconnect()

def collect_all_servers_metrics():
    """收集所有服务器的监控数据"""
    servers = Server.query.all()
    results = {}
    
    for server in servers:
        monitor = ServerMonitor(server)
        metrics = monitor.collect_metrics()
        results[server.id] = metrics
    
    return results

def get_server_latest_metrics(server_id):
    """获取指定服务器的最新监控数据"""
    metric = ServerMetric.query.filter_by(server_id=server_id).order_by(ServerMetric.timestamp.desc()).first()
    if metric:
        return {
            'cpu_usage': metric.cpu_usage,
            'memory_usage': metric.memory_usage,
            'disk_usage': metric.disk_usage,
            'load_average': metric.load_average,
            'timestamp': metric.timestamp.isoformat()
        }
    return None

def get_server_metrics_history(server_id, hours=24):
    """获取指定服务器的历史监控数据"""
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=hours)
    
    metrics = ServerMetric.query.filter(
        ServerMetric.server_id == server_id,
        ServerMetric.timestamp >= since
    ).order_by(ServerMetric.timestamp).all()
    
    return [{
        'cpu_usage': m.cpu_usage,
        'memory_usage': m.memory_usage,
        'disk_usage': m.disk_usage,
        'timestamp': m.timestamp.isoformat()
    } for m in metrics]