"""
智能用户名生成器
根据中文姓名生成符合Linux命名规范的用户名
"""

import re
import logging
from pypinyin import lazy_pinyin, Style

logger = logging.getLogger(__name__)

class UsernameGenerator:
    """用户名生成器类"""
    
    def __init__(self):
        # 保留用户名列表
        self.reserved_names = {
            'root', 'daemon', 'bin', 'sys', 'sync', 'games', 'man', 'lp', 
            'mail', 'news', 'uucp', 'proxy', 'backup', 'nobody', 'www-data', 
            'mysql', 'postgres', 'redis', 'mongodb', 'docker', 'admin', 
            'administrator', 'test', 'user', 'guest', 'ftp', 'ssh'
        }
    
    def validate_chinese_name(self, name):
        """验证中文姓名格式"""
        if not name or not isinstance(name, str):
            return False, "姓名不能为空"
        
        name = name.strip()
        if len(name) < 2 or len(name) > 10:
            return False, "姓名长度应在2-10字符之间"
        
        # 检查是否包含中文字符
        if not re.search(r'[\u4e00-\u9fff]', name):
            return False, "姓名应包含中文字符"
        
        return True, "姓名格式正确"
    
    def chinese_to_pinyin(self, chinese_text, full=True):
        """将中文转换为拼音"""
        try:
            if full:
                # 全拼
                pinyin_list = lazy_pinyin(chinese_text, style=Style.NORMAL)
            else:
                # 首字母缩写
                pinyin_list = lazy_pinyin(chinese_text, style=Style.FIRST_LETTER)
            
            # 合并拼音，去除数字和特殊字符
            result = ''.join(pinyin_list).lower()
            result = re.sub(r'[^a-z]', '', result)
            return result
        except Exception as e:
            logger.error(f"拼音转换失败: {e}")
            return ""
    
    def generate_username_candidates(self, chinese_name):
        """
        根据中文姓名生成用户名候选列表
        规则：
        1. 姓名第一个字的全拼 + 后面字的缩写
        2. 如果1重复，则使用全部字的全拼
        3. 如果2也重复，则使用全部字全拼 + 数字后缀（01-99）
        """
        valid, msg = self.validate_chinese_name(chinese_name)
        if not valid:
            return [], msg
        
        chinese_name = chinese_name.strip()
        candidates = []
        
        try:
            # 规则1：第一个字全拼 + 其他字首字母
            if len(chinese_name) >= 2:
                first_char = chinese_name[0]
                rest_chars = chinese_name[1:]
                
                first_pinyin = self.chinese_to_pinyin(first_char, full=True)
                rest_pinyin = self.chinese_to_pinyin(rest_chars, full=False)
                
                if first_pinyin and rest_pinyin:
                    username1 = first_pinyin + rest_pinyin
                    if self.is_valid_username(username1):
                        candidates.append(username1)
            
            # 规则2：全部字的全拼
            full_pinyin = self.chinese_to_pinyin(chinese_name, full=True)
            if full_pinyin and self.is_valid_username(full_pinyin):
                candidates.append(full_pinyin)
            
            # 规则3：全拼 + 数字后缀
            if full_pinyin:
                for i in range(1, 100):  # 01-99
                    suffix = f"{i:02d}" if i < 10 else str(i)
                    username_with_suffix = full_pinyin + suffix
                    if self.is_valid_username(username_with_suffix):
                        candidates.append(username_with_suffix)
            
            # 如果所有方法都失败，使用拼音首字母 + 随机数字
            if not candidates:
                initials = self.chinese_to_pinyin(chinese_name, full=False)
                if initials:
                    for i in range(1, 1000):
                        username_fallback = initials + str(i)
                        if self.is_valid_username(username_fallback):
                            candidates.append(username_fallback)
                            break
            
        except Exception as e:
            logger.error(f"生成用户名候选失败: {e}")
            return [], f"生成用户名失败: {str(e)}"
        
        if not candidates:
            return [], "无法生成有效的用户名"
        
        return candidates, "生成成功"
    
    def is_valid_username(self, username):
        """验证用户名是否符合Linux规范"""
        if not username:
            return False
        
        # Linux用户名规则：3-32字符，字母开头，只能包含字母数字下划线连字符
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]{2,31}$', username):
            return False
        
        # 检查是否为保留用户名
        if username.lower() in self.reserved_names:
            return False
        
        return True
    
    def generate_username(self, chinese_name, existing_usernames=None):
        """
        生成用户名（返回第一个可用的候选用户名）
        
        Args:
            chinese_name: 中文姓名
            existing_usernames: 已存在的用户名列表，用于避免重复
        
        Returns:
            tuple: (username, message)
        """
        candidates, msg = self.generate_username_candidates(chinese_name)
        if not candidates:
            return None, msg
        
        if not existing_usernames:
            existing_usernames = set()
        else:
            existing_usernames = set(existing_usernames)
        
        # 找到第一个不重复的用户名
        for candidate in candidates:
            if candidate not in existing_usernames:
                return candidate, "生成成功"
        
        return None, "所有候选用户名都已存在"
    
    def batch_generate_usernames(self, name_list, existing_usernames=None):
        """
        批量生成用户名
        
        Args:
            name_list: 中文姓名列表
            existing_usernames: 已存在的用户名列表
        
        Returns:
            dict: {chinese_name: (username, message)}
        """
        if not existing_usernames:
            existing_usernames = set()
        else:
            existing_usernames = set(existing_usernames)
        
        results = {}
        used_usernames = existing_usernames.copy()
        
        for chinese_name in name_list:
            username, message = self.generate_username(chinese_name, used_usernames)
            results[chinese_name] = (username, message)
            
            # 如果成功生成，加入已使用列表避免后续重复
            if username:
                used_usernames.add(username)
        
        return results


# 全局实例
username_generator = UsernameGenerator()


def generate_username_for_user(chinese_name, server_id=None, existing_usernames=None):
    """
    为用户生成服务器账户名的便捷函数
    
    Args:
        chinese_name: 用户的中文姓名
        server_id: 服务器ID（可选，用于获取该服务器已有用户名）
        existing_usernames: 已存在的用户名列表（可选）
    
    Returns:
        tuple: (username, message)
    """
    if not existing_usernames and server_id:
        # 从数据库获取该服务器的已有用户名
        try:
            from models import Application
            existing_apps = Application.query.filter_by(
                server_id=server_id,
                status='approved'
            ).all()
            existing_usernames = [app.server_username for app in existing_apps if app.server_username]
        except Exception as e:
            logger.error(f"获取已有用户名失败: {e}")
            existing_usernames = []
    
    return username_generator.generate_username(chinese_name, existing_usernames)


def validate_username_format(username):
    """验证用户名格式是否符合Linux规范"""
    return username_generator.is_valid_username(username)


if __name__ == "__main__":
    # 测试代码
    generator = UsernameGenerator()
    
    test_names = ["张三", "李四", "王小明", "赵子龙", "诸葛亮"]
    
    print("=== 用户名生成测试 ===")
    for name in test_names:
        candidates, msg = generator.generate_username_candidates(name)
        print(f"\n姓名: {name}")
        print(f"状态: {msg}")
        if candidates:
            print(f"候选用户名: {candidates[:5]}")  # 只显示前5个
            username, result_msg = generator.generate_username(name)
            print(f"推荐用户名: {username} ({result_msg})")
    
    print("\n=== 批量生成测试 ===")
    batch_results = generator.batch_generate_usernames(test_names)
    for name, (username, msg) in batch_results.items():
        print(f"{name}: {username} ({msg})")