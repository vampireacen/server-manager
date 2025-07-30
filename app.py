from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from sqlalchemy.orm import joinedload
from models import db, User, Server, Application, PermissionType, ServerMetric, Notification
from server_monitor import collect_all_servers_metrics, get_server_latest_metrics, get_server_metrics_history
from config import Config
from datetime import datetime
import json

app = Flask(__name__)
app.config.from_object(Config)

# 初始化数据库
db.init_app(app)

def create_tables():
    """创建数据库表"""
    with app.app_context():
        db.create_all()
        
        # 创建默认管理员用户
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
        
        # 创建默认权限类型
        permission_types = [
            {'name': '普通用户', 'description': '基本SSH访问权限', 'requires_reason': False},
            {'name': '管理员权限', 'description': 'sudo权限和系统管理', 'requires_reason': True},
            {'name': 'Docker权限', 'description': 'Docker容器管理权限', 'requires_reason': True},
            {'name': '数据库权限', 'description': '数据库访问和管理权限', 'requires_reason': True},
            {'name': '自定义权限', 'description': '其他特殊权限需求', 'requires_reason': True}
        ]
        
        for ptype in permission_types:
            if not PermissionType.query.filter_by(name=ptype['name']).first():
                pt = PermissionType(**ptype)
                db.session.add(pt)
        
        db.session.commit()

def login_required(f):
    """登录验证装饰器"""
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def admin_required(f):
    """管理员权限验证装饰器"""
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin():
            flash('需要管理员权限', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    student_id = request.form['student_id']
    laboratory = request.form['laboratory']
    supervisor = request.form.get('supervisor', '')
    contact = request.form.get('contact', '')
    
    # 检查用户名是否已存在
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash('用户名已存在，请选择其他用户名', 'error')
        return redirect(url_for('login'))
    
    # 检查学号是否已存在
    existing_student = User.query.filter_by(student_id=student_id).first()
    if existing_student:
        flash('学号已被注册，请联系管理员', 'error')
        return redirect(url_for('login'))
    
    # 创建新用户
    new_user = User(
        username=username,
        student_id=student_id,
        laboratory=laboratory,
        supervisor=supervisor,
        contact=contact,
        role='user'  # 新注册用户默认为普通用户
    )
    new_user.set_password(password)
    
    try:
        db.session.add(new_user)
        db.session.commit()
        flash('注册成功，请登录', 'success')
    except Exception as e:
        db.session.rollback()
        flash('注册失败，请重试', 'error')
    
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # 获取当前用户
    user = User.query.get(session['user_id'])
    
    if user.is_admin():
        # 管理员看到所有服务器
        servers = Server.query.all()
        pending_applications = Application.query.filter_by(status='pending').count()
        
        return render_template('dashboard.html', 
                             servers=servers, 
                             user=user,
                             pending_applications=pending_applications)
    else:
        # 普通用户看到已批准的服务器访问权限
        approved_applications = Application.query.filter_by(
            user_id=session['user_id'], 
            status='approved'
        ).join(Server).join(PermissionType).all()
        
        # 最近的申请状态
        recent_applications = Application.query.filter_by(
            user_id=session['user_id']
        ).order_by(Application.created_at.desc()).limit(5).all()
        
        # 可申请的服务器（所有服务器）
        available_servers = Server.query.all()
        
        return render_template('user_dashboard.html', 
                             user=user,
                             approved_applications=approved_applications,
                             recent_applications=recent_applications,
                             available_servers=available_servers)

@app.route('/api/server_metrics/<int:server_id>')
@login_required
def api_server_metrics(server_id):
    """获取服务器实时监控数据API"""
    metrics = get_server_latest_metrics(server_id)
    return jsonify(metrics) if metrics else jsonify({})

@app.route('/api/server_metrics_history/<int:server_id>')
@login_required
def api_server_metrics_history(server_id):
    """获取服务器历史监控数据API"""
    hours = request.args.get('hours', 24, type=int)
    metrics = get_server_metrics_history(server_id, hours)
    return jsonify(metrics)

@app.route('/api/collect_metrics')
@admin_required
def api_collect_metrics():
    """手动触发监控数据收集API"""
    results = collect_all_servers_metrics()
    return jsonify(results)

@app.route('/apply', methods=['GET', 'POST'])
@login_required
def apply():
    if request.method == 'POST':
        server_id = request.form['server_id']
        permission_type_ids = request.form.getlist('permission_type_ids')  # 获取多个权限类型ID
        reason = request.form.get('reason', '')
        
        if not permission_type_ids:
            flash('请至少选择一个权限类型', 'error')
            return redirect(url_for('apply'))
        
        # 检查每个权限类型是否已有待处理的申请
        for permission_type_id in permission_type_ids:
            existing = Application.query.filter_by(
                user_id=session['user_id'],
                server_id=server_id,
                permission_type_id=permission_type_id,
                status='pending'
            ).first()
            
            if existing:
                permission_type = PermissionType.query.get(permission_type_id)
                flash(f'您已有一个 {permission_type.name} 的待处理申请，请等待审核', 'warning')
                return redirect(url_for('apply'))
        
        created_applications = []
        server = Server.query.get(server_id)
        user = User.query.get(session['user_id'])
        
        # 为每个权限类型创建单独的申请
        for permission_type_id in permission_type_ids:
            application = Application(
                user_id=session['user_id'],
                server_id=server_id,
                permission_type_id=permission_type_id,
                reason=reason
            )
            db.session.add(application)
            created_applications.append(application)
        
        # 提交应用记录
        db.session.flush()  # 获取application IDs
        
        # 创建管理员通知
        permission_names = []
        for app in created_applications:
            permission_type = PermissionType.query.get(app.permission_type_id)
            permission_names.append(permission_type.name)
        
        permission_list = '、'.join(permission_names)
        message = f"用户 {user.username} 申请服务器 {server.name} 的权限：{permission_list}"
        
        # 给所有管理员发送通知
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            # 为每个申请创建单独的通知
            for app in created_applications:
                permission_type = PermissionType.query.get(app.permission_type_id)
                individual_message = f"用户 {user.username} 申请服务器 {server.name} 的 {permission_type.name}"
                notification = Notification(
                    admin_id=admin.id,
                    message=individual_message,
                    application_id=app.id
                )
                db.session.add(notification)
        
        db.session.commit()
        flash(f'已成功提交 {len(permission_type_ids)} 个权限申请，请等待管理员审核', 'success')
        return redirect(url_for('my_applications'))
    
    servers = Server.query.all()
    permission_types = PermissionType.query.all()
    
    return render_template('apply.html', servers=servers, permission_types=permission_types)

@app.route('/my_applications')
@login_required
def my_applications():
    """用户查看自己的申请"""
    applications = Application.query.filter_by(user_id=session['user_id']).order_by(Application.created_at.desc()).all()
    return render_template('my_applications.html', applications=applications)

@app.route('/admin/review')
@admin_required
def admin_review():
    """管理员审核页面"""
    status_filter = request.args.get('status', 'pending')
    
    query = Application.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    applications = query.order_by(Application.created_at.desc()).all()
    
    # 标记通知为已读
    Notification.query.filter_by(admin_id=session['user_id'], is_read=False).update({'is_read': True})
    db.session.commit()
    
    return render_template('admin_review.html', applications=applications, status_filter=status_filter)

@app.route('/admin/review_application/<int:app_id>', methods=['POST'])
@admin_required
def admin_review_application(app_id):
    """管理员审核申请"""
    application = Application.query.get_or_404(app_id)
    action = request.form['action']
    admin_comment = request.form.get('admin_comment', '')
    
    if action in ['approved', 'rejected']:
        # 更新申请状态
        application.status = action
        application.reviewed_by = session['user_id']
        application.reviewed_at = datetime.utcnow()
        application.admin_comment = admin_comment
        
        # 如果是批准状态，自动配置服务器权限
        if action == 'approved':
            try:
                from server_operations import configure_user_permissions
                
                # 尝试自动配置用户权限
                success, message = configure_user_permissions(application)
                
                if success:
                    # 权限配置成功
                    flash(f'申请已批准，服务器权限配置成功: {message}', 'success')
                    
                    # 在管理员评论中记录自动化操作
                    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    auto_comment = f"\n[{timestamp}] 系统自动配置: {message}"
                    application.admin_comment = (application.admin_comment or '') + auto_comment
                    
                else:
                    # 权限配置失败，但申请状态保持为批准
                    flash(f'申请已批准，但服务器权限配置失败: {message}。请手动配置用户权限。', 'warning')
                    
                    # 在管理员评论中记录错误信息
                    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    error_comment = f"\n[{timestamp}] 自动配置失败: {message}，需要手动处理"
                    application.admin_comment = (application.admin_comment or '') + error_comment
                    
            except ImportError as e:
                flash('申请已批准，但自动化模块未就绪，请手动配置用户权限', 'warning')
            except Exception as e:
                flash(f'申请已批准，但权限配置过程中出现异常: {str(e)}。请手动配置用户权限。', 'warning')
                
                # 记录异常信息
                timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                error_comment = f"\n[{timestamp}] 配置异常: {str(e)}"
                application.admin_comment = (application.admin_comment or '') + error_comment
        else:
            # 拒绝申请
            flash('申请已拒绝', 'info')
        
        # 提交数据库更改
        db.session.commit()
    
    return redirect(url_for('admin_review'))

@app.route('/admin/revoke_permission/<int:app_id>', methods=['POST'])
@admin_required
def admin_revoke_permission(app_id):
    """管理员撤销权限"""
    application = Application.query.get_or_404(app_id)
    
    if application.status != 'approved':
        flash('只能撤销已批准的权限', 'error')
        return redirect(url_for('admin_review'))
    
    try:
        from server_operations import revoke_user_permissions
        
        # 尝试自动撤销服务器权限
        success, message = revoke_user_permissions(application)
        
        if success:
            # 更新申请状态为撤销
            application.status = 'revoked'
            application.reviewed_at = datetime.utcnow()
            
            # 记录撤销操作
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            revoke_comment = f"\n[{timestamp}] 权限已撤销: {message}"
            application.admin_comment = (application.admin_comment or '') + revoke_comment
            
            db.session.commit()
            flash(f'权限撤销成功: {message}', 'success')
        else:
            flash(f'权限撤销失败: {message}。请手动处理。', 'error')
            
    except Exception as e:
        flash(f'权限撤销过程中出现异常: {str(e)}', 'error')
    
    return redirect(url_for('admin_review'))

@app.route('/admin/servers', methods=['GET', 'POST'])
@admin_required
def admin_servers():
    """管理员服务器管理页面"""
    if request.method == 'POST':
        action = request.form.get('action', 'add')
        
        if action == 'add':
            # 添加新服务器
            server = Server(
                name=request.form['name'],
                host=request.form['host'],
                port=int(request.form.get('port', 22)),
                username=request.form['username'],
                password=request.form.get('password', '')
            )
            db.session.add(server)
            db.session.commit()
            flash('服务器添加成功', 'success')
            
        elif action == 'edit':
            # 编辑服务器
            server_id = request.form['server_id']
            server = Server.query.get_or_404(server_id)
            
            server.name = request.form['name']
            server.host = request.form['host']
            server.port = int(request.form.get('port', 22))
            server.username = request.form['username']
            
            # 只有提供了新密码才更新密码
            new_password = request.form.get('password', '').strip()
            if new_password:
                server.password = new_password
                
            db.session.commit()
            flash('服务器信息更新成功', 'success')
            
        elif action == 'delete':
            # 删除服务器
            server_id = request.form['server_id']
            server = Server.query.get_or_404(server_id)
            
            # 检查是否有相关的申请记录
            applications_count = Application.query.filter_by(server_id=server_id).count()
            if applications_count > 0:
                flash(f'无法删除服务器，存在 {applications_count} 个相关申请记录', 'warning')
            else:
                db.session.delete(server)
                db.session.commit()
                flash('服务器删除成功', 'success')
        
        return redirect(url_for('admin_servers'))
    
    servers = Server.query.all()
    return render_template('admin_servers.html', servers=servers)

@app.route('/admin/users', methods=['GET', 'POST'])
@admin_required
def admin_users():
    """管理员用户管理页面"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            # 添加新用户
            username = request.form['username']
            password = request.form['password']
            role = request.form.get('role', 'user')
            
            # 检查用户名是否已存在
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('用户名已存在', 'error')
            else:
                new_user = User(username=username, role=role)
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                flash('用户添加成功', 'success')
                
        elif action == 'toggle_role':
            # 切换用户角色
            user_id = request.form['user_id']
            new_role = request.form['role']
            user = User.query.get_or_404(user_id)
            
            if user.id == session['user_id']:
                flash('不能修改自己的角色', 'error')
            else:
                user.role = new_role
                db.session.commit()
                flash(f'用户 {user.username} 角色已更新为 {"管理员" if new_role == "admin" else "普通用户"}', 'success')
                
        elif action == 'delete':
            # 删除用户
            user_id = request.form['user_id']
            user = User.query.get_or_404(user_id)
            
            if user.id == session['user_id']:
                flash('不能删除自己的账户', 'error')
            else:
                # 删除相关的申请记录
                Application.query.filter_by(user_id=user_id).delete()
                # 删除相关的通知记录  
                Notification.query.filter_by(admin_id=user_id).delete()
                # 删除用户
                db.session.delete(user)
                db.session.commit()
                flash(f'用户 {user.username} 删除成功', 'success')
                
        elif action == 'reset_password':
            # 重置用户密码
            user_id = request.form['user_id']
            new_password = request.form['new_password']
            user = User.query.get_or_404(user_id)
            
            if len(new_password) < 8:
                flash('新密码至少需要8位字符', 'error')
            else:
                user.set_password(new_password)
                db.session.commit()
                flash(f'用户 {user.username} 密码重置成功', 'success')
        
        return redirect(url_for('admin_users'))
    
    users = User.query.all()
    
    # 获取每个用户的申请数量统计
    user_applications_count = {}
    for user in users:
        count = Application.query.filter_by(user_id=user.id).count()
        user_applications_count[user.id] = count
    
    return render_template('admin_users.html', 
                         users=users, 
                         user_applications_count=user_applications_count)

@app.route('/api/user_applications/<int:user_id>')
@admin_required
def api_user_applications(user_id):
    """获取指定用户的申请记录API"""
    applications = Application.query.filter_by(user_id=user_id).order_by(Application.created_at.desc()).all()
    
    result = []
    for app in applications:
        result.append({
            'id': app.id,
            'server_name': app.server.name,
            'permission_type_name': app.permission_type.name,
            'status': app.status,
            'created_at': app.created_at.isoformat(),
            'reviewed_at': app.reviewed_at.isoformat() if app.reviewed_at else None,
            'reason': app.reason
        })
    
    return jsonify({'applications': result})

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    """账户信息管理页面"""
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # 验证当前密码
            if not user.check_password(current_password):
                flash('当前密码不正确', 'error')
                return redirect(url_for('account'))
            
            # 验证新密码
            if new_password != confirm_password:
                flash('新密码两次输入不一致', 'error')
                return redirect(url_for('account'))
            
            if len(new_password) < 8:
                flash('新密码至少需要8位字符', 'error')
                return redirect(url_for('account'))
            
            # 更新密码
            user.set_password(new_password)
            db.session.commit()
            flash('密码修改成功', 'success')
            return redirect(url_for('account'))
    
    # 获取用户的服务器权限信息（仅显示已批准的申请）
    user_applications = Application.query.filter_by(
        user_id=session['user_id'], 
        status='approved'
    ).options(db.joinedload(Application.server), db.joinedload(Application.permission_type)).all()
    
    return render_template('account.html', user=user, applications=user_applications)

@app.route('/api/verify_password', methods=['POST'])
@login_required
def api_verify_password():
    """验证用户密码API"""
    password = request.json.get('password')
    user = User.query.get(session['user_id'])
    
    if user.check_password(password):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': '密码不正确'})

@app.route('/api/notifications')
@login_required
def api_notifications():
    """获取当前用户通知API"""
    user = User.query.get(session['user_id'])
    if user.is_admin():
        unread_count = Notification.query.filter_by(admin_id=session['user_id'], is_read=False).count()
        return jsonify({'unread_count': unread_count})
    return jsonify({'unread_count': 0})

if __name__ == '__main__':
    create_tables()
    app.run(debug=True, host='0.0.0.0', port=8080)