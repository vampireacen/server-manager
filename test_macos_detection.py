#!/usr/bin/env python3
"""
测试macOS硬件检测功能
"""
import subprocess
import platform

def test_macos_commands():
    """测试macOS硬件检测命令"""
    print("🧪 开始测试macOS硬件检测命令...")
    print(f"操作系统: {platform.system()}")
    
    # 测试内存检测
    print("\n🔍 [DEBUG] 开始检测内存信息...")
    
    # 1. 测试sysctl命令获取内存大小
    print("🔍 [DEBUG] 执行sysctl命令...")
    try:
        result = subprocess.run(['sysctl', '-n', 'hw.memsize'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            memory_bytes = int(result.stdout.strip())
            memory_gb = round(memory_bytes / (1024**3))
            print(f"🔍 [DEBUG] sysctl hw.memsize结果: {result.stdout.strip()}")
            print(f"🔍 [DEBUG] 计算内存大小: {memory_gb}GB")
        else:
            print(f"🔍 [DEBUG] sysctl命令失败: {result.stderr}")
    except Exception as e:
        print(f"🔍 [DEBUG] sysctl命令异常: {e}")
    
    # 2. 测试system_profiler获取内存信息
    print("🔍 [DEBUG] 执行system_profiler SPMemoryDataType...")
    try:
        result = subprocess.run(['system_profiler', 'SPMemoryDataType'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"🔍 [DEBUG] system_profiler内存信息前300字符:")
            print(result.stdout[:300])
            print("...")
        else:
            print(f"🔍 [DEBUG] system_profiler失败: {result.stderr}")
    except Exception as e:
        print(f"🔍 [DEBUG] system_profiler异常: {e}")
    
    # 测试磁盘检测
    print("\n💿 [DEBUG] 开始检测磁盘信息...")
    
    # 1. 测试df命令
    print("💿 [DEBUG] 执行df命令...")
    try:
        result = subprocess.run(['df', '-g', '/'], capture_output=True, text=True, timeout=5)
        print(f"💿 [DEBUG] df -g /结果:\n{result.stdout}")
        
        # 解析磁盘大小
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 2:
            disk_line = lines[1].split()
            if len(disk_line) >= 2:
                size_gb = disk_line[1]
                print(f"💿 [DEBUG] 解析结果 - 磁盘大小: {size_gb}GB")
    except Exception as e:
        print(f"💿 [DEBUG] df命令异常: {e}")
    
    # 2. 测试system_profiler获取存储信息
    print("💿 [DEBUG] 执行system_profiler SPStorageDataType...")
    try:
        result = subprocess.run(['system_profiler', 'SPStorageDataType'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"💿 [DEBUG] system_profiler存储信息前300字符:")
            print(result.stdout[:300])
            print("...")
        else:
            print(f"💿 [DEBUG] system_profiler存储失败: {result.stderr}")
    except Exception as e:
        print(f"💿 [DEBUG] system_profiler存储异常: {e}")
    
    # 3. 测试diskutil命令
    print("💿 [DEBUG] 执行diskutil info /...")
    try:
        result = subprocess.run(['diskutil', 'info', '/'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"💿 [DEBUG] diskutil info前300字符:")
            print(result.stdout[:300])
            print("...")
        else:
            print(f"💿 [DEBUG] diskutil失败: {result.stderr}")
    except Exception as e:
        print(f"💿 [DEBUG] diskutil异常: {e}")

    print("\n✅ macOS命令测试完成！")

if __name__ == "__main__":
    test_macos_commands()