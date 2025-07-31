#!/usr/bin/env python3
"""
测试删除服务器账户功能的修复
"""

from app import app, db
from models import User, Application
from datetime import datetime

def check_user_applications(username):
    """检查用户的Application记录状态"""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"用户 {username} 不存在")
            return
        
        applications = Application.query.filter_by(user_id=user.id).all()
        print(f"用户 {username} 的权限记录:")
        print(f"{'ID':<5} {'服务器':<15} {'权限类型':<15} {'状态':<10} {'服务器用户名':<15}")
        print("-" * 70)
        
        for app in applications:
            server_name = app.server.name if app.server else "未知"
            permission_name = app.permission_type.name if app.permission_type else "未知"
            server_username = app.server_username or user.username
            print(f"{app.id:<5} {server_name:<15} {permission_name:<15} {app.status:<10} {server_username:<15}")
        
        # 统计
        approved_count = len([app for app in applications if app.status == 'approved'])
        revoked_count = len([app for app in applications if app.status == 'revoked'])
        pending_count = len([app for app in applications if app.status == 'pending'])
        rejected_count = len([app for app in applications if app.status == 'rejected'])
        
        print(f"\n统计: 已批准={approved_count}, 已撤销={revoked_count}, 待审核={pending_count}, 已拒绝={rejected_count}")
        
        return applications

def simulate_delete_server_account(username):
    """模拟删除服务器账户的过程"""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"用户 {username} 不存在")
            return
        
        # 显示删除前的状态
        print("=== 删除前的状态 ===")
        check_user_applications(username)
        
        # 模拟调用delete_user_from_servers函数
        print(f"\n=== 模拟删除用户 {username} 的服务器账户 ===")
        from server_operations import delete_user_from_servers
        
        try:
            success, message = delete_user_from_servers(user)
            print(f"删除结果: {'成功' if success else '失败'}")
            print(f"消息: {message}")
        except Exception as e:
            print(f"删除过程中出现异常: {e}")
        
        # 显示删除后的状态
        print(f"\n=== 删除后的状态 ===")
        check_user_applications(username)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("用法: python test_delete_fix.py <用户名>")
        print("示例: python test_delete_fix.py testuser")
        sys.exit(1)
    
    username = sys.argv[1]
    
    print(f"测试用户: {username}")
    print("=" * 50)
    
    # 检查当前状态
    print("=== 当前状态检查 ===")
    check_user_applications(username)
    
    # 询问是否执行删除测试
    response = input(f"\n是否要测试删除用户 {username} 的服务器账户? (y/N): ").strip().lower()
    if response == 'y':
        simulate_delete_server_account(username)
    else:
        print("取消测试")