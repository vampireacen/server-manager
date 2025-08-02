#!/usr/bin/env python3
"""
测试信息检索功能的脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server_monitor import ServerMonitor
from models import db, Server

def test_server_info_retrieval():
    """测试服务器信息检索功能"""
    print("🧪 开始测试服务器信息检索功能...")
    
    # 创建一个测试服务器对象
    test_server = Server()
    test_server.name = "测试服务器"
    test_server.host = "127.0.0.1"  # 本地测试
    test_server.port = 22
    test_server.username = "testuser"
    test_server.password = "testpass"
    
    # 创建监控器实例
    monitor = ServerMonitor(test_server)
    
    print(f"📡 尝试连接到 {test_server.host}...")
    
    # 测试连接（可能会失败，因为我们只是测试检测逻辑）
    try:
        if monitor.connect():
            print("✅ 连接成功！")
            
            # 测试完整信息检索
            print("🔍 开始检索完整硬件和系统信息...")
            complete_info = monitor.get_complete_info()
            
            print(f"📊 检索结果:")
            for key, value in complete_info.items():
                print(f"  - {key}: {value}")
                
            monitor.disconnect()
        else:
            print("❌ 连接失败，但我们可以测试检测命令...")
            
            # 即使连接失败，我们也可以测试命令构建逻辑
            print("🧪 测试内存检测逻辑...")
            try:
                memory_info = monitor.get_memory_info()
                print(f"内存信息: {memory_info}")
            except Exception as e:
                print(f"内存检测异常: {e}")
                
            print("🧪 测试磁盘检测逻辑...")
            try:
                disk_info = monitor.get_disk_info()
                print(f"磁盘信息: {disk_info}")
            except Exception as e:
                print(f"磁盘检测异常: {e}")
    
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        
        # 即使出现异常，也尝试测试本地命令
        print("🧪 尝试执行本地检测命令...")
        
        # 测试本地命令执行
        import subprocess
        
        print("📝 测试本地内存检测命令...")
        try:
            # 测试free命令
            result = subprocess.run(['free', '-g'], capture_output=True, text=True, timeout=5)
            print(f"free -g 输出: {result.stdout}")
        except Exception as e:
            print(f"free命令失败: {e}")
            
        try:
            # 测试dmidecode命令  
            result = subprocess.run(['dmidecode', '-t', 'memory'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"dmidecode输出前几行: {result.stdout[:200]}...")
            else:
                print(f"dmidecode失败，错误: {result.stderr}")
        except Exception as e:
            print(f"dmidecode命令失败: {e}")
            
        print("📝 测试本地磁盘检测命令...")
        try:
            # 测试lsblk命令
            result = subprocess.run(['lsblk', '-d', '-o', 'NAME,SIZE,MODEL,TYPE'], capture_output=True, text=True, timeout=5)
            print(f"lsblk输出: {result.stdout}")
        except Exception as e:
            print(f"lsblk命令失败: {e}")
            
        try:
            # 测试df命令
            result = subprocess.run(['df', '-BG', '/'], capture_output=True, text=True, timeout=5)
            print(f"df输出: {result.stdout}")
        except Exception as e:
            print(f"df命令失败: {e}")

if __name__ == "__main__":
    test_server_info_retrieval()