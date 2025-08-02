#!/usr/bin/env python3
"""
简单的本地命令测试
"""
import subprocess
import os

def test_local_commands():
    """测试本地硬件检测命令"""
    print("🧪 开始测试本地硬件检测命令...")
    
    # 测试内存检测
    print("\n🔍 [DEBUG] 开始检测内存信息...")
    
    # 1. 测试dmidecode命令
    print("🔍 [DEBUG] 执行dmidecode命令...")
    try:
        result = subprocess.run(['sudo', 'dmidecode', '-t', 'memory'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"🔍 [DEBUG] dmidecode命令成功，输出前500字符:")
            print(result.stdout[:500])
            print("...")
        else:
            print(f"🔍 [DEBUG] dmidecode命令失败: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("🔍 [DEBUG] dmidecode命令超时")
    except FileNotFoundError:
        print("🔍 [DEBUG] dmidecode命令不存在")
    except Exception as e:
        print(f"🔍 [DEBUG] dmidecode命令异常: {e}")
    
    # 2. 测试free命令
    print("🔍 [DEBUG] 执行free命令...")
    try:
        result = subprocess.run(['free', '-g'], capture_output=True, text=True, timeout=5)
        print(f"🔍 [DEBUG] free -g 命令结果: {result.stdout}")
    except Exception as e:
        print(f"🔍 [DEBUG] free命令异常: {e}")
        
    try:
        result = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=5)
        memory_output = result.stdout
        print(f"🔍 [DEBUG] free -m 命令结果: {memory_output}")
        
        # 解析内存大小
        lines = memory_output.strip().split('\n')
        if len(lines) >= 2:
            mem_line = lines[1].split()
            if len(mem_line) >= 2:
                total_mb = int(mem_line[1])
                total_gb = int(total_mb / 1024)
                print(f"🔍 [DEBUG] 解析结果 - 总内存: {total_gb}GB")
    except Exception as e:
        print(f"🔍 [DEBUG] free -m命令异常: {e}")
    
    # 测试磁盘检测
    print("\n💿 [DEBUG] 开始检测磁盘信息...")
    
    # 1. 测试lsblk命令
    print("💿 [DEBUG] 执行lsblk命令...")
    try:
        result = subprocess.run(['lsblk', '-d', '-o', 'NAME,SIZE,MODEL,TYPE'], 
                              capture_output=True, text=True, timeout=5)
        print(f"💿 [DEBUG] lsblk命令结果:\n{result.stdout}")
    except Exception as e:
        print(f"💿 [DEBUG] lsblk命令异常: {e}")
    
    # 2. 测试df命令
    print("💿 [DEBUG] 执行df命令...")
    try:
        result = subprocess.run(['df', '-BG', '/'], capture_output=True, text=True, timeout=5)
        print(f"💿 [DEBUG] df命令结果:\n{result.stdout}")
        
        # 解析磁盘大小
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 2:
            disk_line = lines[1].split()
            if len(disk_line) >= 2:
                size_str = disk_line[1]  # 例如 "250G"
                size_gb = size_str.replace('G', '')
                print(f"💿 [DEBUG] 解析结果 - 磁盘大小: {size_gb}GB")
    except Exception as e:
        print(f"💿 [DEBUG] df命令异常: {e}")
    
    # 3. 测试/sys方法获取磁盘型号
    print("💿 [DEBUG] 尝试从/sys获取磁盘型号...")
    try:
        import glob
        block_devices = glob.glob('/sys/block/sd*') + glob.glob('/sys/block/nvme*')
        print(f"💿 [DEBUG] 找到的块设备: {block_devices}")
        
        for device in block_devices:
            model_file = os.path.join(device, 'device', 'model')
            if os.path.exists(model_file):
                with open(model_file, 'r') as f:
                    model = f.read().strip()
                    print(f"💿 [DEBUG] {device} 型号: {model}")
    except Exception as e:
        print(f"💿 [DEBUG] /sys方法异常: {e}")

    print("\n✅ 本地命令测试完成！")

if __name__ == "__main__":
    test_local_commands()