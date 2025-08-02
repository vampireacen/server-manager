#!/usr/bin/env python3
"""
完整的信息检索测试
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 模拟SSH连接类，直接在本地执行命令
class MockSSHClient:
    def exec_command(self, command):
        import subprocess
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            stdout = MockStdout(result.stdout)
            return None, stdout, None
        except Exception as e:
            stdout = MockStdout("")
            return None, stdout, None

class MockStdout:
    def __init__(self, content):
        self.content = content
    
    def read(self):
        return self.content.encode('utf-8')

# 模拟Server对象
class MockServer:
    def __init__(self):
        self.name = "本地测试服务器"
        self.host = "127.0.0.1"
        self.port = 22
        self.username = "testuser"
        self.password = "testpass"

# 创建简化的ServerMonitor用于测试
class TestServerMonitor:
    def __init__(self, server):
        self.server = server
        self.ssh_client = None
    
    def connect(self):
        """模拟连接成功"""
        self.ssh_client = MockSSHClient()
        return True
    
    def disconnect(self):
        """模拟断开连接"""
        self.ssh_client = None
    
    def execute_command(self, command):
        """直接在本地执行命令"""
        if not self.ssh_client:
            return None
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            return stdout.read().decode('utf-8').strip()
        except Exception as e:
            print(f"执行命令失败: {e}")
            return None
    
    def get_memory_info(self):
        """获取内存信息，包含详细型号和容量"""
        print(f"🔍 [DEBUG] 开始检测内存信息...")
        
        # 检测操作系统类型
        import platform
        system = platform.system().lower()
        print(f"🔍 [DEBUG] 检测到操作系统: {system}")
        
        if system == 'darwin':  # macOS
            return self._get_memory_info_macos()
        else:  # Linux
            return self._get_memory_info_linux()
    
    def _get_memory_info_macos(self):
        """macOS系统的内存检测"""
        print(f"🔍 [DEBUG] 使用macOS方法检测内存...")
        
        # 获取内存大小
        command = "sysctl -n hw.memsize"
        result = self.execute_command(command)
        print(f"🔍 [DEBUG] sysctl hw.memsize结果: {result}")
        
        if result and result.isdigit():
            memory_bytes = int(result)
            memory_gb = round(memory_bytes / (1024**3))
            print(f"🔍 [DEBUG] 计算内存大小: {memory_gb}GB")
            
            # 尝试获取内存类型信息
            command = "system_profiler SPMemoryDataType"
            memory_profile = self.execute_command(command)
            print(f"🔍 [DEBUG] system_profiler结果前200字符: {memory_profile[:200] if memory_profile else 'None'}...")
            
            # 从system_profiler输出中提取内存信息
            memory_model = None
            if memory_profile:
                lines = memory_profile.split('\n')
                for line in lines:
                    if 'Type:' in line:
                        memory_model = line.split(':')[1].strip()
                        break
                if not memory_model:
                    for line in lines:
                        if 'Speed:' in line:
                            speed = line.split(':')[1].strip()
                            memory_model = f"DDR {speed}"
                            break
            
            print(f"🔍 [DEBUG] 最终内存信息 - 型号: {memory_model}, 大小: {memory_gb}GB")
            return {
                'memory_count': memory_gb,
                'memory_model': memory_model
            }
        
        return {'memory_count': None, 'memory_model': None}
    
    def _get_memory_info_linux(self):
        """Linux系统的内存检测 - 简化版"""
        print(f"🔍 [DEBUG] 使用Linux方法检测内存...")
        
        # 备用方法：只获取总容量
        command = "free -g | grep Mem | awk '{print $2}'"
        memory_size = self.execute_command(command)
        print(f"🔍 [DEBUG] free -g 命令结果: {memory_size}")
        
        if not memory_size or memory_size == '0':
            command = "free -m | grep Mem | awk '{print int($2/1024)}'"
            memory_size = self.execute_command(command)
            print(f"🔍 [DEBUG] free -m 命令结果: {memory_size}")
        
        return {
            'memory_count': int(memory_size) if memory_size and memory_size.isdigit() else None,
            'memory_model': None
        }
    
    def get_disk_info(self):
        """获取磁盘信息，包含详细型号和容量"""
        print(f"💿 [DEBUG] 开始检测磁盘信息...")
        
        # 检测操作系统类型
        import platform
        system = platform.system().lower()
        print(f"💿 [DEBUG] 检测到操作系统: {system}")
        
        if system == 'darwin':  # macOS
            return self._get_disk_info_macos()
        else:  # Linux
            return self._get_disk_info_linux()
    
    def _get_disk_info_macos(self):
        """macOS系统的磁盘检测"""
        print(f"💿 [DEBUG] 使用macOS方法检测磁盘...")
        
        # 获取磁盘大小（使用df）
        command = "df -g / | tail -1 | awk '{print $2}'"
        disk_size = self.execute_command(command)
        print(f"💿 [DEBUG] df命令结果: {disk_size}")
        
        # 获取磁盘信息
        command = "system_profiler SPStorageDataType"
        storage_profile = self.execute_command(command)
        print(f"💿 [DEBUG] system_profiler存储信息前200字符: {storage_profile[:200] if storage_profile else 'None'}...")
        
        # 尝试从system_profiler中提取磁盘型号
        disk_model = None
        if storage_profile:
            lines = storage_profile.split('\n')
            for line in lines:
                line_lower = line.lower()
                if 'medium type:' in line_lower:
                    disk_model = line.split(':')[1].strip()
                    break
                elif 'solid state:' in line_lower and 'yes' in line_lower:
                    disk_model = "SSD"
                    break
        
        # 备用方法：获取磁盘信息
        if not disk_model:
            command = "diskutil info / | grep 'Device Node'"
            device_info = self.execute_command(command)
            print(f"💿 [DEBUG] diskutil info结果: {device_info}")
            
            if device_info and 'disk' in device_info:
                disk_model = "Internal SSD"
        
        # 组合型号和容量
        if disk_model and disk_size and disk_size.isdigit():
            model_with_size = f"{disk_model} {disk_size}GB"
        elif disk_size and disk_size.isdigit():
            model_with_size = f"Internal Disk {disk_size}GB"
        else:
            model_with_size = disk_model
        
        print(f"💿 [DEBUG] 最终磁盘信息 - 型号: {model_with_size}, 大小: {disk_size}GB")
        
        return {
            'ssd_count': int(disk_size) if disk_size and disk_size.isdigit() else None,
            'ssd_model': model_with_size
        }
    
    def _get_disk_info_linux(self):
        """Linux系统的磁盘检测 - 简化版"""
        print(f"💿 [DEBUG] 使用Linux方法检测磁盘...")
        
        # 备用方法：使用 df 获取根分区大小
        command = "df -BG / | tail -1 | awk '{print $2}' | sed 's/G//'"
        disk_size = self.execute_command(command)
        print(f"💿 [DEBUG] df命令结果: {disk_size}")
        
        return {
            'ssd_count': int(disk_size) if disk_size and disk_size.isdigit() else None,
            'ssd_model': f"Disk {disk_size}GB" if disk_size and disk_size.isdigit() else None
        }
    
    def get_complete_info(self):
        """获取完整的系统和硬件信息"""
        complete_info = {}
        
        # 获取内存信息
        memory_info = self.get_memory_info()
        complete_info.update(memory_info)
        
        # 获取磁盘信息
        disk_info = self.get_disk_info()
        complete_info.update(disk_info)
        
        return complete_info

def test_full_retrieval():
    """测试完整的信息检索功能"""
    print("🚀 开始测试完整的信息检索功能...")
    
    # 创建测试服务器
    test_server = MockServer()
    
    # 创建监控器
    monitor = TestServerMonitor(test_server)
    
    # 连接测试
    print(f"📡 尝试连接到 {test_server.host}...")
    if monitor.connect():
        print("✅ 连接成功！")
        
        try:
            # 获取完整信息
            print(f"🚀 [INFO] 开始检索服务器 {test_server.name} 的完整信息...")
            complete_info = monitor.get_complete_info()
            print(f"🚀 [INFO] 检索到的完整信息: {complete_info}")
            
            # 模拟更新字段
            system_updated = []
            hardware_updated = []
            
            # 检查硬件信息
            if complete_info.get('memory_count'):
                memory_info = f"内存: {complete_info['memory_count']}GB"
                if complete_info.get('memory_model'):
                    memory_info += f" {complete_info['memory_model']}"
                hardware_updated.append(memory_info)
            
            if complete_info.get('ssd_count'):
                storage_info = f"存储: {complete_info['ssd_model']}" if complete_info.get('ssd_model') else f"存储: {complete_info['ssd_count']}GB"
                hardware_updated.append(storage_info)
            
            # 构建消息
            message = '连接成功'
            if hardware_updated:
                message += f'\n\n硬件配置已检测：\n' + '\n'.join(hardware_updated)
            
            print(f"✅ 最终结果消息:\n{message}")
            
            monitor.disconnect()
            
        except Exception as e:
            print(f"❌ 检索过程中发生异常: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ 连接失败")

if __name__ == "__main__":
    test_full_retrieval()