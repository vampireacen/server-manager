from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    servers = Server.query.all()
    
    # 获取当前用户
    user = User.query.get(session['user_id'])
    
    # 如果是管理员，获取待处理申请数量
    pending_applications = 0
    if user.is_admin():
        pending_applications = Application.query.filter_by(status='pending').count()
    
    return render_template('dashboard.html', 
                         servers=servers, 
                         user=user,
                         pending_applications=pending_applications)

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
        permission_type_id = request.form['permission_type_id']
        reason = request.form.get('reason', '')
        
        # 检查是否已有待处理的申请
        existing = Application.query.filter_by(
            user_id=session['user_id'],
            server_id=server_id,
            status='pending'
        ).first()
        
        if existing:
            flash('您已有一个待处理的申请，请等待审核', 'warning')
            return redirect(url_for('apply'))
        
        # 创建新申请
        application = Application(
            user_id=session['user_id'],
            server_id=server_id,
            permission_type_id=permission_type_id,
            reason=reason
        )
        
        db.session.add(application)
        
        # 创建管理员通知
        server = Server.query.get(server_id)
        permission_type = PermissionType.query.get(permission_type_id)
        user = User.query.get(session['user_id'])
        
        message = f"用户 {user.username} 申请服务器 {server.name} 的 {permission_type.name}"
        
        # 给所有管理员发送通知
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            notification = Notification(
                admin_id=admin.id,
                message=message,
                application_id=application.id
            )
            db.session.add(notification)
        
        db.session.commit()
        flash('申请已提交，请等待管理员审核', 'success')
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
        application.status = action
        application.reviewed_by = session['user_id']
        application.reviewed_at = datetime.utcnow()
        application.admin_comment = admin_comment
        
        db.session.commit()
        flash(f'申请已{action}', 'success')
    
    return redirect(url_for('admin_review'))

@app.route('/admin/servers', methods=['GET', 'POST'])
@admin_required
def admin_servers():
    """管理员服务器管理页面"""
    if request.method == 'POST':
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
        return redirect(url_for('admin_servers'))
    
    servers = Server.query.all()
    return render_template('admin_servers.html', servers=servers)

@app.route('/admin/users')
@admin_required
def admin_users():
    """管理员用户管理页面"""
    users = User.query.all()
    return render_template('admin_users.html', users=users)

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