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
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            # 如果有错误输出，记录下来
            if error:
                print(f"🔍 [DEBUG] 命令 '{command}' 错误输出: {error}")
            
            return output if output else None
        except Exception as e:
            print(f"执行命令失败: {e}")
            return None
    
    def execute_command_with_error(self, command):
        """执行命令并返回stdout和stderr"""
        if not self.ssh_client:
            return None, None
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            return output, error
        except Exception as e:
            print(f"执行命令失败: {e}")
            return None, str(e)
    
    def execute_sudo_command(self, command):
        """执行需要sudo权限的命令，自动处理密码输入"""
        if not self.ssh_client:
            return None, None
        
        try:
            # 首先尝试无密码sudo
            test_command = "sudo -n true"
            stdin, stdout, stderr = self.ssh_client.exec_command(test_command)
            test_error = stderr.read().decode('utf-8').strip()
            
            if not test_error:
                # 无密码sudo成功，直接执行命令
                print(f"🔍 [DEBUG] 无密码sudo可用，直接执行: {command}")
                return self.execute_command_with_error(command)
            
            # 需要密码的sudo，尝试使用服务器密码
            if hasattr(self.server, 'password') and self.server.password:
                print(f"🔍 [DEBUG] 尝试使用服务器密码执行sudo命令: {command}")
                
                # 使用echo将密码通过管道传递给sudo
                sudo_command = f"echo '{self.server.password}' | sudo -S {command.replace('sudo ', '')}"
                stdin, stdout, stderr = self.ssh_client.exec_command(sudo_command)
                
                output = stdout.read().decode('utf-8').strip()
                error = stderr.read().decode('utf-8').strip()
                
                # 检查是否是密码错误
                if 'Sorry, try again' in error or 'incorrect password' in error.lower():
                    print(f"🔍 [DEBUG] 服务器密码不能用于sudo，需要单独的sudo密码")
                    return None, "需要sudo密码"
                elif 'Password:' in error:
                    # 过滤掉密码提示，只保留实际错误
                    error_lines = error.split('\n')
                    filtered_error = '\n'.join([line for line in error_lines if 'Password:' not in line])
                    return output, filtered_error
                else:
                    print(f"🔍 [DEBUG] sudo命令执行成功")
                    return output, error
            else:
                print(f"🔍 [DEBUG] 服务器使用密钥认证，无密码可用于sudo")
                return None, "密钥认证无法用于sudo，需要sudo密码"
                
        except Exception as e:
            print(f"🔍 [DEBUG] 执行sudo命令失败: {e}")
            return None, str(e)
    
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
    
    def get_hostname(self):
        """获取主机名称"""
        command = "hostname"
        result = self.execute_command(command)
        if result:
            return result.strip()
        return None
    
    def get_system_version(self):
        """获取系统版本信息"""
        # 先尝试 lsb_release
        command = "lsb_release -d 2>/dev/null | cut -f2 | tr -d '\"'"
        result = self.execute_command(command)
        if result and result.strip():
            return result.strip()
        
        # 如果 lsb_release 不可用，尝试读取 /etc/os-release
        command = "cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'\"' -f2"
        result = self.execute_command(command)
        if result and result.strip():
            return result.strip()
        
        # 最后尝试 /etc/issue
        command = "head -n1 /etc/issue 2>/dev/null | sed 's/\\\\[a-z]//g' | tr -d '\n'"
        result = self.execute_command(command)
        if result and result.strip():
            return result.strip()
        
        return None
    
    def get_kernel_version(self):
        """获取内核版本"""
        command = "uname -r"
        result = self.execute_command(command)
        if result:
            return result.strip()
        return None
    
    def get_system_arch(self):
        """获取系统架构"""
        command = "uname -m"
        result = self.execute_command(command)
        if result:
            return result.strip()
        return None
    
    def get_cpu_info(self):
        """获取CPU信息"""
        # 获取CPU型号和数量
        command = "lscpu | grep 'Model name' | cut -d':' -f2 | sed 's/^ *//g'"
        cpu_model = self.execute_command(command)
        if not cpu_model:
            # 备用方法
            command = "cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d':' -f2 | sed 's/^ *//g'"
            cpu_model = self.execute_command(command)
        
        # 获取CPU数量
        command = "nproc"
        cpu_count = self.execute_command(command)
        if not cpu_count:
            command = "cat /proc/cpuinfo | grep processor | wc -l"
            cpu_count = self.execute_command(command)
        
        return {
            'cpu_model': cpu_model.strip() if cpu_model else None,
            'cpu_count': int(cpu_count) if cpu_count and cpu_count.isdigit() else None
        }
    
    def get_memory_info(self):
        """获取内存信息，包含详细型号和容量"""
        print(f"🔍 [DEBUG] 开始检测内存信息...")
        
        # 检测远程服务器操作系统类型
        uname_result = self.execute_command("uname -s")
        print(f"🔍 [DEBUG] 远程服务器操作系统: {uname_result}")
        
        if uname_result and 'darwin' in uname_result.lower():  # macOS
            return self._get_memory_info_macos()
        else:  # Linux (默认)
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
        """Linux系统的内存检测 - 使用分步骤的dmidecode命令"""
        print(f"🔍 [DEBUG] 使用Linux方法检测内存...")
        
        # 首先检查dmidecode是否存在
        check_cmd = "which dmidecode"
        dmidecode_path = self.execute_command(check_cmd)
        print(f"🔍 [DEBUG] dmidecode路径: {dmidecode_path}")
        
        if not dmidecode_path:
            print(f"🔍 [DEBUG] dmidecode命令不存在，跳过硬件检测")
            result = None
        else:
            # 使用新的sudo命令执行方法
            command = "sudo dmidecode -t 17"
            result, error = self.execute_sudo_command(command)
            
            if result:
                print(f"🔍 [DEBUG] sudo dmidecode成功，结果长度: {len(result)}")
                print(f"🔍 [DEBUG] dmidecode结果前500字符: {result[:500]}")
            elif error == "需要sudo密码" or error == "密钥认证无法用于sudo，需要sudo密码":
                print(f"🔍 [DEBUG] {error}")
                print(f"🔍 [DEBUG] 提示：为了获取精确的内存型号信息，建议管理员配置无密码sudo或提供sudo密码")
                result = None
            else:
                print(f"🔍 [DEBUG] sudo dmidecode失败: {error}")
                
                # 尝试直接使用dmidecode（通常会失败但可以确认）
                print(f"🔍 [DEBUG] 尝试直接dmidecode...")
                command = "dmidecode -t 17"
                result, error = self.execute_command_with_error(command)
                if result:
                    print(f"🔍 [DEBUG] 直接dmidecode成功: {result[:200]}")
                else:
                    print(f"🔍 [DEBUG] 直接dmidecode也失败: {error}")
                    result = None
        
        if result:
            memory_devices = []
            total_size_gb = 0
            
            # 使用Python解析dmidecode输出，更加可靠
            lines = result.split('\n')
            current_device = {}
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('Memory Device'):
                    # 开始新的内存设备
                    if current_device and current_device.get('size_gb', 0) > 0:
                        memory_devices.append(current_device)
                    current_device = {}
                    
                elif line.startswith('Size:'):
                    size_str = line.split(':', 1)[1].strip()
                    if ('No Module Installed' not in size_str and 
                        'Unknown' not in size_str and 
                        any(c.isdigit() for c in size_str)):
                        # 解析大小 (例如: "32 GB", "32768 MB")
                        if 'GB' in size_str:
                            try:
                                size_gb = int(''.join(filter(str.isdigit, size_str.split('GB')[0])))
                                if size_gb > 0:
                                    current_device['size_gb'] = size_gb
                                    total_size_gb += size_gb
                                    print(f"🔍 [DEBUG] 发现内存容量: {size_gb}GB")
                            except (ValueError, IndexError):
                                pass
                        elif 'MB' in size_str:
                            try:
                                size_mb = int(''.join(filter(str.isdigit, size_str.split('MB')[0])))
                                size_gb = size_mb // 1024
                                if size_gb > 0:
                                    current_device['size_gb'] = size_gb
                                    total_size_gb += size_gb
                                    print(f"🔍 [DEBUG] 发现内存容量: {size_mb}MB -> {size_gb}GB")
                            except (ValueError, IndexError):
                                pass
                                
                elif line.startswith('Manufacturer:'):
                    manufacturer = line.split(':', 1)[1].strip()
                    if manufacturer not in ['Unknown', 'Not Specified', '']:
                        current_device['manufacturer'] = manufacturer
                        print(f"🔍 [DEBUG] 发现制造商: {manufacturer}")
                        
                elif line.startswith('Part Number:'):
                    part_number = line.split(':', 1)[1].strip()
                    if part_number not in ['Unknown', 'Not Specified', '']:
                        current_device['part_number'] = part_number
                        print(f"🔍 [DEBUG] 发现型号: {part_number}")
            
            # 处理最后一个设备
            if current_device and current_device.get('size_gb', 0) > 0:
                memory_devices.append(current_device)
            
            print(f"🔍 [DEBUG] 总共发现 {len(memory_devices)} 个内存设备")
            
            # 生成内存信息字符串
            if memory_devices:
                # 获取第一个内存条的信息作为主要信息
                first_device = memory_devices[0]
                
                # 构建内存型号字符串，格式：Samsung M393A4K40EB3-CWE 32GB
                memory_model_parts = []
                if first_device.get('manufacturer'):
                    memory_model_parts.append(first_device['manufacturer'])
                if first_device.get('part_number'):
                    memory_model_parts.append(first_device['part_number'])
                
                if memory_model_parts:
                    memory_model = ' '.join(memory_model_parts)
                    # 添加单条容量信息
                    memory_model += f" {first_device['size_gb']}GB"
                    
                    # 如果有多条内存，添加标识
                    if len(memory_devices) > 1:
                        memory_model += " 和其他"
                else:
                    memory_model = f"DDR Memory {first_device['size_gb']}GB"
                    if len(memory_devices) > 1:
                        memory_model += " 和其他"
                
                print(f"🔍 [DEBUG] 解析内存信息 - 型号: {memory_model}, 总大小: {total_size_gb}GB, 设备数量: {len(memory_devices)}")
                
                return {
                    'memory_count': total_size_gb,
                    'memory_model': memory_model
                }
        
        print(f"🔍 [DEBUG] dmidecode方法失败，尝试备用方法...")
        
        # 备用方法1：尝试从/proc/meminfo获取型号信息
        meminfo_result = self.execute_command("cat /proc/meminfo | grep MemTotal")
        print(f"🔍 [DEBUG] /proc/meminfo结果: {meminfo_result}")
        
        # 备用方法2：尝试lshw命令
        lshw_result = self.execute_command("lshw -class memory -short 2>/dev/null")
        print(f"🔍 [DEBUG] lshw -short命令结果: {lshw_result[:200] if lshw_result else 'None'}")
        
        # 尝试获取更详细的lshw输出
        lshw_detailed = self.execute_command("lshw -class memory 2>/dev/null")
        print(f"🔍 [DEBUG] lshw详细命令结果前300字符: {lshw_detailed[:300] if lshw_detailed else 'None'}")
        
        # 备用方法3：检查/sys/devices/system/memory/
        sys_memory = self.execute_command("ls /sys/devices/system/memory/ 2>/dev/null | wc -l")
        print(f"🔍 [DEBUG] /sys/devices/system/memory/块数: {sys_memory}")
        
        # 备用方法4：尝试不需要sudo的hardware命令
        hardware_info = self.execute_command("cat /proc/cpuinfo | grep 'model name' | head -1")
        print(f"🔍 [DEBUG] CPU信息作为参考: {hardware_info}")
        
        # 获取总内存容量
        command = "free -g | grep Mem | awk '{print $2}'"
        memory_size = self.execute_command(command)
        print(f"🔍 [DEBUG] free -g 命令结果: {memory_size}")
        
        if not memory_size or memory_size == '0':
            command = "free -m | grep Mem | awk '{print int($2/1024)}'"
            memory_size = self.execute_command(command)
            print(f"🔍 [DEBUG] free -m 命令结果: {memory_size}")
            
        # 尝试从lshw解析内存型号
        memory_model = None
        
        # 首先尝试解析详细的lshw输出
        if lshw_detailed:
            print(f"🔍 [DEBUG] 解析详细lshw输出...")
            lines = lshw_detailed.split('\n')
            current_memory_section = False
            for line in lines:
                line_stripped = line.strip()
                
                # 检测内存相关的section
                if 'description:' in line_stripped.lower() and 'memory' in line_stripped.lower():
                    current_memory_section = True
                    print(f"🔍 [DEBUG] 发现内存section: {line_stripped}")
                
                if current_memory_section:
                    # 查找product, vendor, size等信息
                    if line_stripped.startswith('product:'):
                        product = line_stripped.replace('product:', '').strip()
                        if product and product != 'Unknown':
                            memory_model = f"{product} (lshw检测)"
                            print(f"🔍 [DEBUG] 从lshw product提取: {memory_model}")
                            break
                    elif line_stripped.startswith('vendor:'):
                        vendor = line_stripped.replace('vendor:', '').strip()
                        if vendor and vendor != 'Unknown':
                            memory_model = f"{vendor} Memory (lshw检测)"
                            print(f"🔍 [DEBUG] 从lshw vendor提取: {memory_model}")
                    elif line_stripped.startswith('size:'):
                        size_info = line_stripped.replace('size:', '').strip()
                        if size_info and 'GiB' in size_info:
                            if not memory_model:  # 如果还没有型号信息
                                memory_model = f"Server Memory {size_info} (lshw检测)"
                                print(f"🔍 [DEBUG] 从lshw size提取: {memory_model}")
        
        # 如果详细输出没有找到，尝试short输出
        if not memory_model and lshw_result:
            lines = lshw_result.split('\n')
            for line in lines:
                if 'memory' in line.lower():
                    print(f"🔍 [DEBUG] 分析lshw行: {line}")
                    # 查找包含容量信息的行，如 "512GiB System"
                    if 'GiB' in line or 'GB' in line or 'system' in line.lower():
                        parts = line.split()
                        # 寻找描述部分
                        description_parts = []
                        for part in parts:
                            if part not in ['/0/0', 'memory'] and not part.startswith('/'):
                                description_parts.append(part)
                        
                        if description_parts:
                            potential_model = ' '.join(description_parts)
                            # 改进格式化
                            if 'GiB' in potential_model or 'GB' in potential_model:
                                # 提取容量和系统信息
                                if 'System' in potential_model:
                                    capacity = potential_model.replace('System', '').strip()
                                    memory_model = f"Server Memory {capacity}"
                                else:
                                    memory_model = f"Server Memory {potential_model}"
                                print(f"🔍 [DEBUG] 从lshw提取内存型号: {memory_model}")
                                break
                    # 也检查DIMM相关的行
                    elif 'dimm' in line.lower():
                        parts = line.split()
                        if len(parts) > 2:
                            potential_model = ' '.join(parts[2:])
                            if potential_model and len(potential_model) > 5:
                                memory_model = f"{potential_model}"
                                print(f"🔍 [DEBUG] 从lshw DIMM提取内存型号: {memory_model}")
                                break
        
        # 如果lshw没有找到，尝试其他方法
        if not memory_model:
            # 尝试从/sys/class/dmi/id/获取制造商信息
            dmi_vendor = self.execute_command("cat /sys/class/dmi/id/sys_vendor 2>/dev/null")
            dmi_product = self.execute_command("cat /sys/class/dmi/id/product_name 2>/dev/null")
            
            print(f"🔍 [DEBUG] DMI厂商: {dmi_vendor}")
            print(f"🔍 [DEBUG] DMI产品: {dmi_product}")
            
            if dmi_vendor and dmi_product:
                memory_model = f"{dmi_vendor} {dmi_product} Memory"
                print(f"🔍 [DEBUG] 组合DMI信息: {memory_model}")
            elif dmi_vendor:
                memory_model = f"{dmi_vendor} Server Memory"
                print(f"🔍 [DEBUG] 使用系统制造商信息: {memory_model}")
            else:
                # 基于CPU型号推断内存类型（Intel服务器通常用特定内存）
                if hardware_info and 'Intel' in hardware_info and 'Xeon' in hardware_info:
                    if memory_size and int(memory_size) >= 500:  # 大容量服务器
                        memory_model = f"DDR4 Server Memory {memory_size}GB"
                        print(f"🔍 [DEBUG] 基于CPU和容量推断: {memory_model}")
                    else:
                        memory_model = f"DDR4 Memory {memory_size}GB"
                        print(f"🔍 [DEBUG] 基于CPU推断: {memory_model}")
        
        return {
            'memory_count': int(memory_size) if memory_size and memory_size.isdigit() else None,
            'memory_model': memory_model
        }
    
    def get_gpu_info(self):
        """获取GPU信息"""
        # 先尝试nvidia-smi
        command = "nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null | head -1"
        gpu_model = self.execute_command(command)
        
        if gpu_model and gpu_model.strip():
            # 获取GPU数量
            command = "nvidia-smi --list-gpus 2>/dev/null | wc -l"
            gpu_count = self.execute_command(command)
            return {
                'gpu_model': gpu_model.strip(),
                'gpu_count': int(gpu_count) if gpu_count and gpu_count.isdigit() else 1
            }
        
        # 尝试lspci查找显卡
        command = "lspci | grep -i vga | head -1 | cut -d':' -f3 | sed 's/^ *//g'"
        gpu_model = self.execute_command(command)
        if gpu_model and gpu_model.strip():
            return {
                'gpu_model': gpu_model.strip(),
                'gpu_count': 1
            }
        
        return {'gpu_model': None, 'gpu_count': None}
    
    def get_disk_info(self):
        """获取磁盘信息，包含详细型号和容量"""
        print(f"💿 [DEBUG] 开始检测磁盘信息...")
        
        # 检测远程服务器操作系统类型
        uname_result = self.execute_command("uname -s")
        print(f"💿 [DEBUG] 远程服务器操作系统: {uname_result}")
        
        if uname_result and 'darwin' in uname_result.lower():  # macOS
            return self._get_disk_info_macos()
        else:  # Linux (默认)
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
                disk_model = "Internal Disk"
        
        # 组合型号和容量
        if disk_model and disk_size and disk_size.isdigit():
            model_with_size = f"{disk_model} {disk_size}GB"
        elif disk_size and disk_size.isdigit():
            model_with_size = f"Disk {disk_size}GB"
        else:
            model_with_size = disk_model
        
        print(f"💿 [DEBUG] 最终磁盘信息 - 型号: {model_with_size}, 大小: {disk_size}GB")
        
        return {
            'ssd_count': int(disk_size) if disk_size and disk_size.isdigit() else None,
            'ssd_model': model_with_size
        }
    
    def _get_disk_info_linux(self):
        """Linux系统的磁盘检测 - 使用简化的lsblk命令"""
        print(f"💿 [DEBUG] 使用Linux方法检测磁盘...")
        
        # 使用用户建议的lsblk命令获取磁盘信息
        command = "lsblk -d -o NAME,MODEL,VENDOR,TYPE,TRAN,SIZE 2>/dev/null"
        result = self.execute_command(command)
        print(f"💿 [DEBUG] lsblk 原始输出: {result[:500] if result else 'None'}")
        
        if result:
            lines = result.strip().split('\n')
            if len(lines) > 1:  # 跳过表头
                disks = []
                total_size_gb = 0
                
                for line in lines[1:]:  # 跳过表头行
                    parts = line.split()
                    if len(parts) >= 6 and parts[3] == 'disk':  # TYPE = disk
                        name = parts[0]
                        model = parts[1] if parts[1] != 'N/A' else ''
                        vendor = parts[2] if parts[2] != 'N/A' else ''
                        disk_type = parts[3]
                        transport = parts[4] if parts[4] != 'N/A' else ''
                        size_str = parts[5]
                        
                        # 解析磁盘大小
                        size_gb = 0
                        try:
                            if 'T' in size_str:
                                size_gb = int(float(size_str.replace('T', '')) * 1024)
                            elif 'G' in size_str:
                                size_gb = int(float(size_str.replace('G', '')))
                            elif 'M' in size_str:
                                size_gb = int(float(size_str.replace('M', '')) / 1024)
                        except (ValueError, IndexError):
                            size_gb = 0
                        
                        # 只处理大于10GB的磁盘
                        if size_gb > 10:
                            # 构建磁盘型号信息，格式：Samsung 980 Pro 1TB
                            disk_info = {
                                'name': name,
                                'model': model,
                                'vendor': vendor,
                                'transport': transport,
                                'size_gb': size_gb
                            }
                            
                            # 构建显示字符串
                            display_parts = []
                            if vendor and vendor.strip():
                                display_parts.append(vendor.strip())
                            if model and model.strip():
                                display_parts.append(model.strip())
                            
                            if display_parts:
                                disk_display = ' '.join(display_parts)
                                # 添加容量信息
                                if size_gb >= 1024:
                                    disk_display += f" {size_gb//1024}TB"
                                else:
                                    disk_display += f" {size_gb}GB"
                            else:
                                # 如果没有型号信息，使用设备名
                                if size_gb >= 1024:
                                    disk_display = f"{name} {size_gb//1024}TB"
                                else:
                                    disk_display = f"{name} {size_gb}GB"
                            
                            disk_info['display'] = disk_display
                            disks.append(disk_info)
                            total_size_gb += size_gb
                
                if disks:
                    # 获取第一个磁盘的信息作为主要信息
                    first_disk = disks[0]
                    ssd_model = first_disk['display']
                    
                    # 如果有多个磁盘，添加标识
                    if len(disks) > 1:
                        ssd_model += " 和其他"
                    
                    print(f"💿 [DEBUG] 解析磁盘信息 - 型号: {ssd_model}, 总大小: {total_size_gb}GB, 磁盘数量: {len(disks)}")
                    
                    return {
                        'ssd_count': total_size_gb,
                        'ssd_model': ssd_model
                    }
        
        print(f"💿 [DEBUG] lsblk方法失败，尝试备用方法...")
        # 备用方法：使用 df 获取根分区大小
        command = "df -BG / | tail -1 | awk '{print $2}' | sed 's/G//'"
        disk_size = self.execute_command(command)
        print(f"💿 [DEBUG] df命令结果: {disk_size}")
        
        # 尝试从 /sys 获取磁盘型号
        command = """for disk in /sys/block/sd* /sys/block/nvme*; do
            if [ -d "$disk" ]; then
                model_file="$disk/device/model"
                if [ -f "$model_file" ]; then
                    cat "$model_file" 2>/dev/null | head -1
                    break
                fi
            fi
        done"""
        disk_model = self.execute_command(command)
        print(f"💿 [DEBUG] /sys磁盘型号结果: {disk_model}")
        
        if disk_model and disk_model.strip():
            model_with_size = f"{disk_model.strip()} {disk_size}GB" if disk_size and disk_size.isdigit() else disk_model.strip()
        else:
            model_with_size = None
        
        print(f"💿 [DEBUG] 最终磁盘信息 - 型号: {model_with_size}, 大小: {disk_size}GB")
        
        return {
            'ssd_count': int(disk_size) if disk_size and disk_size.isdigit() else None,
            'ssd_model': model_with_size
        }
    
    def get_hardware_info(self):
        """获取所有硬件配置信息"""
        hardware_info = {}
        
        # 获取CPU信息
        cpu_info = self.get_cpu_info()
        hardware_info.update(cpu_info)
        
        # 获取内存信息
        memory_info = self.get_memory_info()
        hardware_info.update(memory_info)
        
        # 获取GPU信息
        gpu_info = self.get_gpu_info()
        hardware_info.update(gpu_info)
        
        # 获取磁盘信息
        disk_info = self.get_disk_info()
        hardware_info.update(disk_info)
        
        return hardware_info
    
    def get_system_info(self):
        """获取所有系统信息"""
        return {
            'hostname': self.get_hostname(),
            'system_version': self.get_system_version(),
            'kernel_version': self.get_kernel_version(),
            'system_arch': self.get_system_arch()
        }
    
    def get_complete_info(self):
        """获取完整的系统和硬件信息"""
        complete_info = {}
        complete_info.update(self.get_system_info())
        complete_info.update(self.get_hardware_info())
        return complete_info
    
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