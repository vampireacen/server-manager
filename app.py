from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from sqlalchemy.orm import joinedload
from models import db, User, Server, Application, ApplicationBatch, PermissionType, ServerMetric, Notification
from server_monitor import collect_all_servers_metrics, get_server_latest_metrics, get_server_metrics_history
from username_generator import generate_username_for_user, validate_username_format
from config import Config
from datetime import datetime
import json
import logging

# 配置日志
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# 初始化数据库
db.init_app(app)

def migrate_database():
    """数据库迁移"""
    with app.app_context():
        # 检查是否需要添加字段到users表
        try:
            # 获取users表的列信息
            result = db.session.execute(db.text("PRAGMA table_info(users)")).fetchall()
            columns = [row[1] for row in result]  # 第二个元素是列名
            
            # 检查并添加name字段
            if 'name' not in columns:
                print("正在添加name字段到users表...")
                db.session.execute(db.text("ALTER TABLE users ADD COLUMN name VARCHAR(100)"))
                # 为现有用户设置默认姓名（使用用户名）
                db.session.execute(db.text("UPDATE users SET name = username WHERE name IS NULL OR name = ''"))
                db.session.commit()
                print("name字段添加成功")
            
            # 检查并添加identity_type字段
            if 'identity_type' not in columns:
                print("正在添加identity_type字段到users表...")
                db.session.execute(db.text("ALTER TABLE users ADD COLUMN identity_type VARCHAR(50)"))
                db.session.commit()
                print("identity_type字段添加成功")
                
            # 检查并添加其他可能缺失的字段
            missing_fields = []
            expected_fields = ['laboratory', 'supervisor', 'contact']
            for field in expected_fields:
                if field not in columns:
                    missing_fields.append(field)
            
            if missing_fields:
                for field in missing_fields:
                    print(f"正在添加{field}字段到users表...")
                    db.session.execute(db.text(f"ALTER TABLE users ADD COLUMN {field} VARCHAR(100)"))
                db.session.commit()
                print(f"成功添加字段: {', '.join(missing_fields)}")
                
        except Exception as e:
            print(f"数据库迁移过程中出现错误: {e}")
            db.session.rollback()
        
        # 检查并添加servers表的新字段
        try:
            result = db.session.execute(db.text("PRAGMA table_info(servers)")).fetchall()
            server_columns = [row[1] for row in result]
            
            server_missing_fields = []
            server_expected_fields = {
                'auth_type': 'VARCHAR(20) DEFAULT "password"',
                'key_path': 'VARCHAR(500)',
                'user_selectable': 'BOOLEAN DEFAULT 1',
                'hostname': 'VARCHAR(100)',
                'system_version': 'VARCHAR(100)',
                'kernel_version': 'VARCHAR(100)',
                'system_arch': 'VARCHAR(50)'
            }
            
            for field, field_type in server_expected_fields.items():
                if field not in server_columns:
                    server_missing_fields.append((field, field_type))
            
            if server_missing_fields:
                for field, field_type in server_missing_fields:
                    print(f"正在添加{field}字段到servers表...")
                    db.session.execute(db.text(f"ALTER TABLE servers ADD COLUMN {field} {field_type}"))
                db.session.commit()
                print(f"成功添加服务器字段: {', '.join([f[0] for f in server_missing_fields])}")
                
        except Exception as e:
            print(f"服务器表迁移错误: {e}")
            db.session.rollback()
        
        # 检查并添加applications表的新字段
        try:
            result = db.session.execute(db.text("PRAGMA table_info(applications)")).fetchall()
            app_columns = [row[1] for row in result]
            
            # 检查并添加server_username字段
            if 'server_username' not in app_columns:
                print("正在添加server_username字段到applications表...")
                db.session.execute(db.text("ALTER TABLE applications ADD COLUMN server_username VARCHAR(50)"))
                db.session.commit()
                print("server_username字段添加成功")
            
            # 检查并添加nodekey字段
            if 'nodekey' not in app_columns:
                print("正在添加nodekey字段到applications表...")
                db.session.execute(db.text("ALTER TABLE applications ADD COLUMN nodekey VARCHAR(200)"))
                db.session.commit()
                print("nodekey字段添加成功")
                
        except Exception as e:
            print(f"applications表迁移错误: {e}")
            db.session.rollback()

def create_tables():
    """创建数据库表"""
    with app.app_context():
        # 首先进行数据库迁移
        migrate_database()
        
        # 创建所有表
        db.create_all()
        
        # 创建默认管理员用户
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', name='系统管理员', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
        else:
            # 如果管理员存在但没有姓名，添加姓名
            if not admin.name:
                admin.name = '系统管理员'
        
        # 创建默认超级管理员用户
        super_admin = User.query.filter_by(username='superadmin').first()
        if not super_admin:
            super_admin = User(username='superadmin', name='超级管理员', role='super_admin')
            super_admin.set_password('superadmin123')
            db.session.add(super_admin)
        else:
            # 如果超级管理员存在但没有姓名，添加姓名
            if not super_admin.name:
                super_admin.name = '超级管理员'
        
        # 创建默认权限类型
        permission_types = [
            {'name': '普通用户', 'description': '基本SSH访问权限', 'requires_reason': False},
            {'name': '管理员权限', 'description': 'sudo权限和系统管理', 'requires_reason': True},
            {'name': 'Docker权限', 'description': 'Docker容器管理权限', 'requires_reason': True},
            {'name': '数据库权限', 'description': '数据库访问和管理权限', 'requires_reason': True},
            {'name': 'Tailscale权限', 'description': '由于 Tailscale nodekey 具有时效性，需与管理员确认时间后再进行申请', 'requires_reason': True},
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

def super_admin_required(f):
    """超级管理员权限验证装饰器"""
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_super_admin():
            flash('需要超级管理员权限', 'error')
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
            session['name'] = getattr(user, 'name', None) or user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    name = request.form.get('name', '')  # 使用get方法避免KeyError
    password = request.form['password']
    student_id = request.form['student_id']
    identity_type = request.form.get('identity_type', '')  # 身份类别
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
        name=name if name else username,  # 如果没有提供姓名，使用用户名作为默认值
        student_id=student_id,
        identity_type=identity_type,  # 身份类别
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
        # 统计待处理的申请批次数量，而不是单个权限数量
        pending_applications = ApplicationBatch.query.filter_by(status='pending').count()
        
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
        
        # 按服务器分组权限
        server_permissions = {}
        for app in approved_applications:
            server_id = app.server.id
            if server_id not in server_permissions:
                server_permissions[server_id] = {
                    'server': app.server,
                    'permissions': [],
                    'user_password': None,  # 用户密码，从admin_comment中提取
                    'server_username': None  # 实际的服务器用户名
                }
            server_permissions[server_id]['permissions'].append(app)
            
            # 设置服务器用户名（使用第一个找到的server_username，如果没有则使用系统用户名）
            if server_permissions[server_id]['server_username'] is None:
                if app.server_username:
                    server_permissions[server_id]['server_username'] = app.server_username
                else:
                    # 如果没有设置server_username，尝试生成或使用系统用户名
                    from username_generator import generate_username_for_user
                    generated_username, _ = generate_username_for_user(user.name or user.username, server_id)
                    server_permissions[server_id]['server_username'] = generated_username or user.username
            
            # 提取用户密码（只需要提取一次）
            if server_permissions[server_id]['user_password'] is None and app.admin_comment:
                import re
                password_match = re.search(r'\[系统生成\] 用户密码: (.+)', app.admin_comment)
                if password_match:
                    server_permissions[server_id]['user_password'] = password_match.group(1)
        
        # 最近的申请批次状态
        recent_batches = ApplicationBatch.query.filter_by(
            user_id=session['user_id']
        ).options(
            db.joinedload(ApplicationBatch.server)
        ).order_by(ApplicationBatch.created_at.desc()).limit(5).all()
        
        # 可申请的服务器（仅显示管理员设置为可选择的服务器）
        available_servers = Server.query.filter_by(user_selectable=True).all()
        
        return render_template('user_dashboard.html', 
                             user=user,
                             approved_applications=approved_applications,
                             server_permissions=server_permissions,
                             recent_batches=recent_batches,
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

@app.route('/api/test_connection/<int:server_id>')
@admin_required
def api_test_connection(server_id):
    """测试服务器连接API - 仅测试连接"""
    server = Server.query.get_or_404(server_id)
    
    try:
        from server_monitor import ServerMonitor
        monitor = ServerMonitor(server)
        
        # 尝试连接服务器
        if monitor.connect():
            message = f'连接到服务器 {server.name} 成功'
            monitor.disconnect()
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': f'无法连接到服务器 {server.name}，请检查网络连接和SSH配置'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'连接测试异常: {str(e)}'
        })

@app.route('/api/retrieve_server_info/<int:server_id>')
@admin_required
def api_retrieve_server_info(server_id):
    """检索并填充服务器的系统信息和硬件配置"""
    try:
        server = Server.query.get_or_404(server_id)
        
        # 检查哪些字段为空
        system_fields_to_check = ['hostname', 'system_version', 'kernel_version', 'system_arch']
        hardware_fields_to_check = ['cpu_model', 'cpu_count', 'memory_model', 'memory_count', 
                                  'gpu_model', 'gpu_count', 'ssd_model', 'ssd_count']
        
        empty_system_fields = [field for field in system_fields_to_check 
                              if not getattr(server, field)]
        empty_hardware_fields = [field for field in hardware_fields_to_check 
                               if not getattr(server, field)]
        
        if not empty_system_fields and not empty_hardware_fields:
            return jsonify({
                'success': True,
                'message': '所有配置信息和系统信息都已完整，无需检索',
                'updated_info': {}
            })
        
        # 连接服务器并获取信息
        from server_monitor import ServerMonitor
        monitor = ServerMonitor(server)
        
        if monitor.connect():
            message = '连接成功'
            updated_info = {}
            
            try:
                # 获取完整信息
                print(f"🚀 [INFO] 开始检索服务器 {server.name} 的完整信息...")
                complete_info = monitor.get_complete_info()
                print(f"🚀 [INFO] 检索到的完整信息: {complete_info}")
                
                # 只更新空字段
                system_updated = []
                hardware_updated = []
                
                for field in empty_system_fields:
                    if complete_info.get(field):
                        setattr(server, field, complete_info[field])
                        updated_info[field] = complete_info[field]
                        if field == 'hostname':
                            system_updated.append(f'主机名: {complete_info[field]}')
                        elif field == 'system_version':
                            system_updated.append(f'系统版本: {complete_info[field]}')
                        elif field == 'kernel_version':
                            system_updated.append(f'内核版本: {complete_info[field]}')
                        elif field == 'system_arch':
                            system_updated.append(f'系统架构: {complete_info[field]}')
                
                for field in empty_hardware_fields:
                    if complete_info.get(field):
                        setattr(server, field, complete_info[field])
                        updated_info[field] = complete_info[field]
                        if field == 'cpu_model':
                            cpu_info = complete_info[field]
                            if complete_info.get('cpu_count'):
                                cpu_info += f' x{complete_info["cpu_count"]}'
                            hardware_updated.append(f'CPU: {cpu_info}')
                        elif field == 'memory_model':
                            memory_info = complete_info[field]
                            if complete_info.get('memory_count'):
                                memory_info = f'{complete_info["memory_count"]}GB {memory_info}'
                            hardware_updated.append(f'内存: {memory_info}')
                        elif field == 'gpu_model':
                            gpu_info = complete_info[field]
                            if complete_info.get('gpu_count'):
                                gpu_info += f' x{complete_info["gpu_count"]}'
                            hardware_updated.append(f'GPU: {gpu_info}')
                        elif field == 'ssd_model':
                            storage_info = complete_info[field]
                            hardware_updated.append(f'存储: {storage_info}')
                
                # 提交数据库更新
                if updated_info:
                    db.session.commit()
                    
                    if system_updated:
                        message += f'\n\n系统信息已检索：\n' + '\n'.join(system_updated)
                    if hardware_updated:
                        message += f'\n\n硬件配置已检测：\n' + '\n'.join(hardware_updated)
                else:
                    message += '\n注意：未能检索到有效的配置信息'
                        
            except Exception as e:
                print(f'检索服务器信息失败: {e}')
                message += f'\n注意：检索服务器信息失败: {str(e)}'
            
            monitor.disconnect()
            return jsonify({
                'success': True,
                'message': message,
                'updated_info': updated_info
            })
        else:
            return jsonify({
                'success': False,
                'error': f'无法连接到服务器 {server.name}，请检查网络连接和SSH配置'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'信息检索异常: {str(e)}'
        })

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
        
        # 检查是否已有该服务器的待处理申请批次
        existing_batch = ApplicationBatch.query.filter_by(
            user_id=session['user_id'],
            server_id=server_id,
            status='pending'
        ).first()
        
        if existing_batch:
            server = Server.query.get(server_id)
            flash(f'您已有一个针对服务器 {server.name} 的待处理申请，请等待审核或撤销后重新申请', 'warning')
            return redirect(url_for('apply'))
        
        # 创建申请批次
        batch = ApplicationBatch(
            user_id=session['user_id'],
            server_id=server_id,
            reason=reason
        )
        db.session.add(batch)
        db.session.flush()  # 获取batch ID
        
        # 为每个权限类型创建单独的申请
        created_applications = []
        for permission_type_id in permission_type_ids:
            application = Application(
                batch_id=batch.id,
                user_id=session['user_id'],
                server_id=server_id,
                permission_type_id=permission_type_id
            )
            
            # 如果是 Tailscale 权限，添加 nodekey
            permission_type = PermissionType.query.get(permission_type_id)
            if permission_type and permission_type.name == 'Tailscale权限':
                nodekey = request.form.get('nodekey', '')
                if not nodekey:
                    flash('Tailscale权限需要提供nodekey', 'error')
                    return redirect(url_for('apply'))
                application.nodekey = nodekey
            
            db.session.add(application)
            created_applications.append(application)
        
        db.session.flush()  # 获取application IDs
        
        # 创建管理员通知（一个批次一个通知）
        server = Server.query.get(server_id)
        user = User.query.get(session['user_id'])
        permission_names = []
        for permission_type_id in permission_type_ids:
            permission_type = PermissionType.query.get(permission_type_id)
            permission_names.append(permission_type.name)
        
        permission_list = '、'.join(permission_names)
        message = f"用户 {user.username} 申请服务器 {server.name} 的权限：{permission_list}"
        
        # 给所有管理员发送通知
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            notification = Notification(
                admin_id=admin.id,
                message=message,
                application_id=created_applications[0].id  # 关联到批次中的第一个申请
            )
            db.session.add(notification)
        
        db.session.commit()
        flash(f'已成功提交申请批次（包含 {len(permission_type_ids)} 个权限），请等待管理员审核', 'success')
        return redirect(url_for('my_applications'))
    
    servers = Server.query.filter_by(user_selectable=True).all()
    permission_types = PermissionType.query.all()
    
    return render_template('apply.html', servers=servers, permission_types=permission_types)

@app.route('/my_applications')
@login_required
def my_applications():
    """用户查看自己的申请批次"""
    # 获取用户的申请批次
    batches_query = ApplicationBatch.query.filter_by(user_id=session['user_id']).options(
        db.joinedload(ApplicationBatch.server),
        db.joinedload(ApplicationBatch.user)
    ).order_by(ApplicationBatch.created_at.desc()).all()
    
    # 转换为字典格式以便JSON序列化
    batches_json = []
    for batch in batches_query:
        # 获取批次中的所有申请
        applications = Application.query.filter_by(batch_id=batch.id).options(
            db.joinedload(Application.permission_type),
            db.joinedload(Application.reviewer)
        ).all()
        
        # 构造权限列表
        permissions = []
        for app in applications:
            perm_dict = {
                'id': app.id,
                'permission_type': {
                    'id': app.permission_type.id,
                    'name': app.permission_type.name,
                    'description': app.permission_type.description
                },
                'status': app.status,
                'reviewed_at': app.reviewed_at.isoformat() if app.reviewed_at else None,
                'admin_comment': app.admin_comment
            }
            
            if app.reviewer:
                perm_dict['reviewer'] = {
                    'id': app.reviewer.id,
                    'username': app.reviewer.username
                }
            else:
                perm_dict['reviewer'] = None
                
            permissions.append(perm_dict)
        
        batch_dict = {
            'id': batch.id,
            'user': {
                'id': batch.user.id,
                'username': batch.user.username
            },
            'server': {
                'id': batch.server.id,
                'name': batch.server.name,
                'host': batch.server.host,
                'port': batch.server.port
            },
            'reason': batch.reason,
            'status': batch.get_status_summary(),
            'can_be_cancelled': batch.can_be_cancelled(),
            'created_at': batch.created_at.isoformat() if batch.created_at else None,
            'permissions': permissions
        }
        
        batches_json.append(batch_dict)
    
    return render_template('my_applications.html', batches=batches_query, batches_json=batches_json)

@app.route('/api/cancel_application_batch/<int:batch_id>', methods=['POST'])
@login_required
def cancel_application_batch(batch_id):
    """用户撤销申请批次"""
    batch = ApplicationBatch.query.get_or_404(batch_id)
    
    # 检查是否是当前用户的申请
    if batch.user_id != session['user_id']:
        return jsonify({'success': False, 'message': '无权限操作此申请'}), 403
    
    # 检查是否可以撤销
    if not batch.can_be_cancelled():
        return jsonify({'success': False, 'message': '此申请无法撤销，可能已被审核'}), 400
    
    try:
        # 更新批次状态为已撤销
        batch.status = 'cancelled'
        
        # 更新批次中所有申请的状态
        Application.query.filter_by(batch_id=batch_id).update({'status': 'cancelled'})
        
        # 删除相关的通知（可选）
        Notification.query.filter(
            Notification.application_id.in_(
                db.session.query(Application.id).filter_by(batch_id=batch_id)
            )
        ).delete(synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '申请已成功撤销'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'撤销失败: {str(e)}'}), 500

@app.route('/admin/review')
@admin_required
def admin_review():
    """管理员审核页面 - 按批次显示"""
    status_filter = request.args.get('status', 'pending')
    
    # 获取所有批次，然后基于状态摘要过滤
    all_batches = ApplicationBatch.query.options(
        db.joinedload(ApplicationBatch.server),
        db.joinedload(ApplicationBatch.user)
    ).order_by(ApplicationBatch.created_at.desc()).all()
    
    # 根据状态过滤批次（使用get_status_summary方法）
    if status_filter == 'pending':
        batches = [batch for batch in all_batches if batch.get_status_summary() == 'pending']
    elif status_filter == 'processing':
        batches = [batch for batch in all_batches if batch.get_status_summary() == 'processing']  
    elif status_filter == 'completed':
        batches = [batch for batch in all_batches if batch.get_status_summary() == 'completed']
    elif status_filter == 'cancelled':
        batches = [batch for batch in all_batches if batch.get_status_summary() == 'cancelled']
    else:  # all
        batches = all_batches
    
    
    # 转换为字典格式以便JSON序列化
    batches_json = []
    for batch in batches:
        # 获取批次中的所有申请
        applications = Application.query.filter_by(batch_id=batch.id).options(
            db.joinedload(Application.permission_type),
            db.joinedload(Application.reviewer)
        ).all()
        
        # 构造权限列表
        permissions = []
        for app in applications:
            perm_dict = {
                'id': app.id,
                'permission_type': {
                    'id': app.permission_type.id,
                    'name': app.permission_type.name,
                    'description': app.permission_type.description,
                    'requires_reason': app.permission_type.requires_reason
                },
                'status': app.status,
                'reviewed_at': app.reviewed_at.isoformat() if app.reviewed_at else None,
                'admin_comment': app.admin_comment
            }
            
            if app.reviewer:
                perm_dict['reviewer'] = {
                    'id': app.reviewer.id,
                    'username': app.reviewer.username
                }
            else:
                perm_dict['reviewer'] = None
                
            permissions.append(perm_dict)
        
        batch_dict = {
            'id': batch.id,
            'user': {
                'id': batch.user.id,
                'username': batch.user.username
            },
            'server': {
                'id': batch.server.id,
                'name': batch.server.name,
                'host': batch.server.host,
                'port': batch.server.port
            },
            'reason': batch.reason,
            'status': batch.get_status_summary(),
            'created_at': batch.created_at.isoformat() if batch.created_at else None,
            'permissions': permissions,
            'permissions_count': len(permissions),
            'permissions_preview': [p['permission_type']['name'] for p in permissions[:2]]
        }
        
        batches_json.append(batch_dict)
    
    # 标记通知为已读
    Notification.query.filter_by(admin_id=session['user_id'], is_read=False).update({'is_read': True})
    db.session.commit()
    
    return render_template('admin_review.html', 
                         batches=batches, 
                         all_batches=all_batches,
                         batches_json=batches_json, 
                         status_filter=status_filter)

@app.route('/admin/review_batch/<int:batch_id>', methods=['POST'])
@admin_required
def admin_review_batch(batch_id):
    """管理员批次审核申请"""
    batch = ApplicationBatch.query.get_or_404(batch_id)
    
    # 获取批次中的所有申请
    applications = Application.query.filter_by(batch_id=batch_id).all()
    
    # 获取自定义服务器用户名（如果提供）
    server_username = request.form.get('server_username', '').strip()
    
    # 处理每个权限的审核结果
    approved_applications = []
    
    for app in applications:
        action = request.form.get(f'action_{app.id}')
        admin_comment = request.form.get(f'comment_{app.id}', '')
        
        if action in ['approved', 'rejected']:
            # 更新申请状态
            app.status = action
            app.reviewed_by = session['user_id']
            app.reviewed_at = datetime.utcnow()
            app.admin_comment = admin_comment
            
            # 收集批准的申请，后续批量处理
            if action == 'approved':
                # 设定自定义服务器用户名（如果提供）
                if server_username:
                    app.server_username = server_username
                approved_applications.append(app)
    
    # 批量配置所有批准的权限
    if approved_applications:
        try:
            from server_operations import configure_user_permissions_batch, configure_tailscale_permission
            
            # 批量配置用户权限
            results = configure_user_permissions_batch(approved_applications)
            
            # 处理配置结果
            for app, success, message in results:
                timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                if success:
                    # 在管理员评论中记录自动化操作
                    auto_comment = f"\n[{timestamp}] 系统自动配置: {message}"
                    app.admin_comment = (app.admin_comment or '') + auto_comment
                    
                    # 如果是 Tailscale 权限，需要额外处理
                    if app.permission_type.name == "Tailscale权限":
                        try:
                            tailscale_success, tailscale_message = configure_tailscale_permission(app)
                            tailscale_timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                            if tailscale_success:
                                tailscale_comment = f"\n[{tailscale_timestamp}] Tailscale配置成功: {tailscale_message}"
                                app.admin_comment += tailscale_comment
                                logger.info(f"Tailscale权限配置成功 - 用户: {app.user.username}, 消息: {tailscale_message}")
                            else:
                                tailscale_comment = f"\n[{tailscale_timestamp}] Tailscale配置失败: {tailscale_message}"
                                app.admin_comment += tailscale_comment
                                logger.error(f"Tailscale权限配置失败 - 用户: {app.user.username}, 错误: {tailscale_message}")
                        except Exception as e:
                            tailscale_timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                            tailscale_comment = f"\n[{tailscale_timestamp}] Tailscale配置异常: {str(e)}"
                            app.admin_comment += tailscale_comment
                            logger.error(f"Tailscale权限配置异常 - 用户: {app.user.username}, 异常: {str(e)}")
                else:
                    # 在管理员评论中记录错误信息
                    error_comment = f"\n[{timestamp}] 自动配置失败: {message}，需要手动处理"
                    app.admin_comment = (app.admin_comment or '') + error_comment
                        
        except ImportError:
            pass  # 自动化模块未就绪
        except Exception as e:
            # 记录异常信息
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            for app in approved_applications:
                error_comment = f"\n[{timestamp}] 配置异常: {str(e)}"
                app.admin_comment = (app.admin_comment or '') + error_comment
    
    # 更新批次状态
    # 检查批次中所有申请是否都已被审核
    all_applications_in_batch = Application.query.filter_by(batch_id=batch_id).all()
    pending_applications = [app for app in all_applications_in_batch if app.status == 'pending']
    
    if len(pending_applications) == 0:
        # 所有申请都已审核完成，批次状态设为已完成
        batch.status = 'completed'
    else:
        # 还有未审核的申请，批次状态设为处理中
        batch.status = 'processing'
    
    # 提交数据库更改
    db.session.commit()
    
    flash('批次审核已提交', 'success')
    return redirect(url_for('admin_review'))

@app.route('/admin/review_application/<int:app_id>', methods=['POST'])
@admin_required
def admin_review_application(app_id):
    """管理员审核单个申请 - 兼容旧版本"""
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
                from server_operations import configure_user_permissions, configure_tailscale_permission
                
                # 尝试自动配置用户权限
                success, message = configure_user_permissions(application)
                
                if success:
                    # 权限配置成功
                    flash(f'申请已批准，服务器权限配置成功: {message}', 'success')
                    
                    # 在管理员评论中记录自动化操作
                    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    auto_comment = f"\n[{timestamp}] 系统自动配置: {message}"
                    application.admin_comment = (application.admin_comment or '') + auto_comment
                    
                    # 如果是 Tailscale 权限，需要额外处理
                    if application.permission_type.name == "Tailscale权限":
                        try:
                            tailscale_success, tailscale_message = configure_tailscale_permission(application)
                            tailscale_timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                            if tailscale_success:
                                tailscale_comment = f"\n[{tailscale_timestamp}] Tailscale配置成功: {tailscale_message}"
                                application.admin_comment += tailscale_comment
                                flash(f'Tailscale权限配置成功: {tailscale_message}', 'success')
                            else:
                                tailscale_comment = f"\n[{tailscale_timestamp}] Tailscale配置失败: {tailscale_message}"
                                application.admin_comment += tailscale_comment
                                flash(f'Tailscale权限配置失败: {tailscale_message}', 'warning')
                        except Exception as e:
                            tailscale_timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                            tailscale_comment = f"\n[{tailscale_timestamp}] Tailscale配置异常: {str(e)}"
                            application.admin_comment += tailscale_comment
                            flash(f'Tailscale权限配置异常: {str(e)}', 'error')
                    
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
            auth_type = request.form.get('auth_type', 'password')
            server = Server(
                name=request.form['name'],
                host=request.form['host'],
                port=int(request.form.get('port', 22)),
                username=request.form['username'],
                auth_type=auth_type
            )
            
            if auth_type == 'password':
                server.password = request.form.get('password', '')
            else:
                server.key_path = request.form.get('key_path', '')
            
            # 添加位置信息
            server.location = request.form.get('location', '')
            server.datacenter = request.form.get('datacenter', '')
            server.rack = request.form.get('rack', '')
            server.rack_position = request.form.get('rack_position', '')
            
            # 设置用户可选择属性
            server.user_selectable = 'user_selectable' in request.form
            
            # 添加配置信息
            server.cpu_model = request.form.get('cpu_model', '')
            server.cpu_count = int(request.form['cpu_count']) if request.form.get('cpu_count') else None
            server.gpu_model = request.form.get('gpu_model', '')
            server.gpu_count = int(request.form['gpu_count']) if request.form.get('gpu_count') else None
            server.memory_model = request.form.get('memory_model', '')
            server.memory_count = int(request.form['memory_count']) if request.form.get('memory_count') else None
            server.ssd_model = request.form.get('ssd_model', '')
            server.ssd_count = int(request.form['ssd_count']) if request.form.get('ssd_count') else None
            
            # 添加系统信息
            server.hostname = request.form.get('hostname', '')
            server.system_version = request.form.get('system_version', '')
            server.kernel_version = request.form.get('kernel_version', '')
            server.system_arch = request.form.get('system_arch', '')
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
            
            # 更新认证类型
            auth_type = request.form.get('auth_type', 'password')
            server.auth_type = auth_type
            
            if auth_type == 'password':
                # 只有提供了新密码才更新密码
                new_password = request.form.get('password', '').strip()
                if new_password:
                    server.password = new_password
                server.key_path = ''
            else:
                # 密钥认证
                new_key_path = request.form.get('key_path', '').strip()
                if new_key_path:
                    server.key_path = new_key_path
                server.password = ''
            
            # 更新位置信息
            server.location = request.form.get('location', '')
            server.datacenter = request.form.get('datacenter', '')
            server.rack = request.form.get('rack', '')
            server.rack_position = request.form.get('rack_position', '')
            
            # 更新用户可选择属性
            server.user_selectable = 'user_selectable' in request.form
            
            # 更新配置信息
            server.cpu_model = request.form.get('cpu_model', '')
            server.cpu_count = int(request.form['cpu_count']) if request.form.get('cpu_count') else None
            server.gpu_model = request.form.get('gpu_model', '')
            server.gpu_count = int(request.form['gpu_count']) if request.form.get('gpu_count') else None
            server.memory_model = request.form.get('memory_model', '')
            server.memory_count = int(request.form['memory_count']) if request.form.get('memory_count') else None
            server.ssd_model = request.form.get('ssd_model', '')
            server.ssd_count = int(request.form['ssd_count']) if request.form.get('ssd_count') else None
            
            # 更新系统信息
            server.hostname = request.form.get('hostname', '')
            server.system_version = request.form.get('system_version', '')
            server.kernel_version = request.form.get('kernel_version', '')
            server.system_arch = request.form.get('system_arch', '')
                
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
            # 切换用户角色 - 只有超级管理员可以执行此操作
            current_user = User.query.get(session['user_id'])
            if not current_user.can_manage_roles():
                flash('只有超级管理员可以修改用户角色', 'error')
            else:
                user_id = request.form['user_id']
                new_role = request.form['role']
                user = User.query.get_or_404(user_id)
                
                if user.id == session['user_id']:
                    flash('不能修改自己的角色', 'error')
                else:
                    user.role = new_role
                    db.session.commit()
                    
                    role_name = {"admin": "管理员", "super_admin": "超级管理员", "user": "普通用户"}.get(new_role, new_role)
                    flash(f'用户 {user.username} 角色已更新为 {role_name}', 'success')
                
        elif action == 'delete':
            # 删除用户
            user_id = request.form['user_id']
            user = User.query.get_or_404(user_id)
            
            if user.id == session['user_id']:
                flash('不能删除自己的账户', 'error')
            else:
                # 删除相关的申请记录
                Application.query.filter_by(user_id=user_id).delete()
                # 删除相关的申请批次记录
                ApplicationBatch.query.filter_by(user_id=user_id).delete()
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
    
    # 获取当前用户信息以便在模板中进行权限判断
    current_user = User.query.get(session['user_id'])
    
    return render_template('admin_users.html', 
                         users=users, 
                         user_applications_count=user_applications_count,
                         current_user=current_user)

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

@app.route('/api/user_server_accounts/<int:user_id>')
@admin_required
def api_user_server_accounts(user_id):
    """获取用户在各服务器的账户信息API"""
    user = User.query.get_or_404(user_id)
    
    # 获取用户已批准的申请
    approved_applications = Application.query.filter_by(
        user_id=user_id, 
        status='approved'
    ).options(db.joinedload(Application.server), db.joinedload(Application.permission_type)).all()
    
    # 按服务器分组权限
    server_accounts = {}
    for app in approved_applications:
        server_id = app.server.id
        if server_id not in server_accounts:
            # 确定实际的服务器用户名
            actual_server_username = user.username  # 默认使用系统用户名
            if app.server_username:
                actual_server_username = app.server_username
            else:
                # 如果没有设置server_username，尝试生成
                from username_generator import generate_username_for_user
                generated_username, _ = generate_username_for_user(user.name or user.username, server_id)
                if generated_username:
                    actual_server_username = generated_username
            
            server_accounts[server_id] = {
                'server_id': server_id,
                'server_name': app.server.name,
                'server_host': app.server.host,
                'server_port': app.server.port,
                'server_status': app.server.status,
                'username': actual_server_username,  # 使用实际的服务器用户名
                'user_password': None,
                'permissions': []
            }
        
        server_accounts[server_id]['permissions'].append({
            'application_id': app.id,
            'type': app.permission_type.name,
            'status': '已配置' if app.admin_comment and '系统自动配置' in app.admin_comment else '需手动配置',
            'reviewed_at': app.reviewed_at.strftime('%Y-%m-%d %H:%M') if app.reviewed_at else '--'
        })
        
        # 提取用户密码
        if server_accounts[server_id]['user_password'] is None and app.admin_comment:
            import re
            password_match = re.search(r'\[系统生成\] 用户密码: (.+)', app.admin_comment)
            if password_match:
                server_accounts[server_id]['user_password'] = password_match.group(1)
    
    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'name': user.name,  # 添加name字段以正确显示用户姓名
            'role': user.role,
            'student_id': user.student_id,
            'laboratory': user.laboratory,
            'supervisor': user.supervisor,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M')
        },
        'server_accounts': list(server_accounts.values())
    })

@app.route('/api/update_user_server_password', methods=['POST'])
@admin_required
def api_update_user_server_password():
    """更新用户在特定服务器的密码API"""
    user_id = request.json.get('user_id')
    server_id = request.json.get('server_id')
    new_password = request.json.get('new_password')
    
    if not all([user_id, server_id, new_password]):
        return jsonify({'success': False, 'message': '参数不完整'}), 400
    
    user = User.query.get(user_id)
    server = Server.query.get(server_id)
    
    if not user or not server:
        return jsonify({'success': False, 'message': '用户或服务器不存在'}), 404
    
    # 查找该用户在该服务器的第一个已批准申请来更新密码
    application = Application.query.filter_by(
        user_id=user_id,
        server_id=server_id,
        status='approved'
    ).first()
    
    if not application:
        return jsonify({'success': False, 'message': '未找到相关权限申请'}), 404
    
    try:
        # 使用server_operations模块更新服务器上的密码
        from server_operations import ServerUserManager
        
        manager = ServerUserManager(server)
        if not manager.connect():
            return jsonify({'success': False, 'message': '无法连接到服务器'}), 500
        
        try:
            # 更新服务器上的用户密码
            import shlex
            safe_username = shlex.quote(user.username)
            safe_password = shlex.quote(new_password)
            success, output = manager.execute_command(
                f"sh -c \"echo {safe_username}:{safe_password} | chpasswd\"", 
                require_sudo=True
            )
            
            if not success:
                return jsonify({'success': False, 'message': f'更新服务器密码失败: {output}'}), 500
                
            # 更新数据库中的admin_comment
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            password_info = f"[系统生成] 用户密码: {new_password}"
            
            # 如果已经有密码信息，替换它；否则添加
            import re
            if application.admin_comment:
                # 替换现有密码信息
                new_comment = re.sub(r'\[系统生成\] 用户密码: .+', password_info, application.admin_comment)
                if new_comment == application.admin_comment:  # 如果没有找到匹配项，就添加
                    application.admin_comment += f"\n[{timestamp}] 管理员更新密码: {password_info}"
                else:
                    application.admin_comment = new_comment + f"\n[{timestamp}] 管理员更新密码"
            else:
                application.admin_comment = f"[{timestamp}] 管理员更新密码: {password_info}"
            
            db.session.commit()
            
            return jsonify({'success': True, 'message': '密码更新成功'})
            
        finally:
            manager.disconnect()
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新密码时发生异常: {str(e)}'}), 500

@app.route('/api/reset_user_password', methods=['POST'])
@admin_required
def api_reset_user_password():
    """重置用户登录密码API"""
    user_id = request.json.get('user_id')
    new_password = request.json.get('new_password')
    
    if not all([user_id, new_password]):
        return jsonify({'success': False, 'message': '参数不完整'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    try:
        # 更新用户密码
        user.set_password(new_password)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '用户密码重置成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'重置密码时发生异常: {str(e)}'}), 500

@app.route('/api/user_profile/<int:user_id>')
@admin_required
def api_user_profile(user_id):
    """获取用户详细信息API"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    user_data = {
        'id': user.id,
        'username': user.username,
        'name': user.name or '',
        'student_id': user.student_id or '',
        'identity_type': user.identity_type or '',
        'laboratory': user.laboratory or '',
        'supervisor': user.supervisor or '',
        'contact': user.contact or '',
        'role': user.role,
        'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else ''
    }
    
    return jsonify({'success': True, 'user': user_data})

@app.route('/api/admin_edit_user_profile', methods=['POST'])
@admin_required
def api_admin_edit_user_profile():
    """管理员编辑用户信息API"""
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'message': '缺少用户ID'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    # 获取更新字段
    username = data.get('username', '').strip()
    name = data.get('name', '').strip()
    student_id = data.get('student_id', '').strip()
    identity_type = data.get('identity_type', '').strip()
    laboratory = data.get('laboratory', '').strip()
    supervisor = data.get('supervisor', '').strip()
    contact = data.get('contact', '').strip()
    role = data.get('role', 'user')
    
    # 验证必填字段
    if not all([username, name, student_id, identity_type, laboratory, supervisor]):
        return jsonify({'success': False, 'message': '请填写所有必填字段'}), 400
    
    try:
        # 检查用户名是否已被其他用户使用
        existing_username = User.query.filter(
            User.username == username,
            User.id != user.id
        ).first()
        if existing_username:
            return jsonify({'success': False, 'message': '该用户名已被其他用户使用'}), 400
        
        # 检查学号是否已被其他用户使用
        existing_student = User.query.filter(
            User.student_id == student_id,
            User.id != user.id
        ).first()
        if existing_student:
            return jsonify({'success': False, 'message': '该学号已被其他用户使用'}), 400
        
        # 更新用户信息
        user.username = username
        user.name = name
        user.student_id = student_id
        user.identity_type = identity_type
        user.laboratory = laboratory
        user.supervisor = supervisor
        user.contact = contact
        user.role = role
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '用户信息更新成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新用户信息时发生异常: {str(e)}'}), 500

@app.route('/api/reset_server_password', methods=['POST'])
@admin_required
def api_reset_server_password():
    """重置用户在服务器上的密码API"""
    user_id = request.json.get('user_id')
    server_id = request.json.get('server_id')
    auto_generate = request.json.get('auto_generate', True)
    custom_password = request.json.get('new_password')
    
    if not all([user_id, server_id]):
        return jsonify({'success': False, 'message': '参数不完整'}), 400
    
    user = User.query.get(user_id)
    server = Server.query.get(server_id)
    
    if not user or not server:
        return jsonify({'success': False, 'message': '用户或服务器不存在'}), 404
    
    # 查找该用户在该服务器的第一个已批准申请
    application = Application.query.filter_by(
        user_id=user_id,
        server_id=server_id,
        status='approved'
    ).first()
    
    if not application:
        return jsonify({'success': False, 'message': '未找到相关权限申请'}), 404
    
    try:
        # 使用server_operations模块重置服务器上的密码
        from server_operations import ServerUserManager
        
        manager = ServerUserManager(server)
        if not manager.connect():
            return jsonify({'success': False, 'message': '无法连接到服务器'}), 500
        
        try:
            # 生成或使用自定义密码
            if auto_generate:
                new_password = manager.generate_password()
            else:
                new_password = custom_password
                if not new_password:
                    return jsonify({'success': False, 'message': '自定义密码不能为空'}), 400
            
            # 更新服务器上的用户密码
            import shlex
            safe_username = shlex.quote(user.username)
            safe_password = shlex.quote(new_password)
            success, output = manager.execute_command(
                f"sh -c \"echo {safe_username}:{safe_password} | chpasswd\"", 
                require_sudo=True
            )
            
            if not success:
                return jsonify({'success': False, 'message': f'更新服务器密码失败: {output}'}), 500
                
            # 更新数据库中的admin_comment
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            password_info = f"[系统生成] 用户密码: {new_password}"
            
            # 如果已经有密码信息，替换它；否则添加
            import re
            if application.admin_comment:
                # 替换现有密码信息
                new_comment = re.sub(r'\[系统生成\] 用户密码: .+', password_info, application.admin_comment)
                if new_comment == application.admin_comment:  # 如果没有找到匹配项，就添加
                    application.admin_comment += f"\n[{timestamp}] 管理员重置密码: {password_info}"
                else:
                    application.admin_comment = new_comment + f"\n[{timestamp}] 管理员重置密码"
            else:
                application.admin_comment = f"[{timestamp}] 管理员重置密码: {password_info}"
            
            db.session.commit()
            
            # 返回新密码（如果是自动生成的话）
            result = {'success': True, 'message': '服务器密码重置成功'}
            if auto_generate:
                result['new_password'] = new_password
            
            return jsonify(result)
            
        finally:
            manager.disconnect()
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'重置密码时发生异常: {str(e)}'}), 500

@app.route('/api/revoke_user_permission', methods=['POST'])
@admin_required
def api_revoke_user_permission():
    """撤销用户权限API"""
    try:
        data = request.get_json()
        application_id = data.get('application_id')
        
        if not application_id:
            return jsonify({'success': False, 'message': '缺少申请ID参数'}), 400
        
        # 获取申请记录
        application = Application.query.get(application_id)
        if not application:
            return jsonify({'success': False, 'message': '申请记录不存在'}), 404
        
        if application.status != 'approved':
            return jsonify({'success': False, 'message': '只能撤销已批准的权限'}), 400
        
        # 调用服务器操作撤销权限
        from server_operations import revoke_user_permissions
        success, message = revoke_user_permissions(application)
        
        if success:
            # 更新申请状态
            application.status = 'revoked'
            application.reviewed_at = datetime.utcnow()
            application.reviewed_by = session['user_id']
            
            # 添加管理员备注
            current_comment = application.admin_comment or ""
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            revoke_comment = f"[{timestamp}] 管理员撤销权限: {message}"
            application.admin_comment = f"{current_comment}\n{revoke_comment}".strip()
            
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': f'{application.permission_type.name} 权限已成功撤销'
            })
        else:
            return jsonify({'success': False, 'message': f'撤销权限失败: {message}'}), 500
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"撤销用户权限API异常: {e}")
        return jsonify({'success': False, 'message': f'撤销权限时发生异常: {str(e)}'}), 500

@app.route('/api/delete_user_enhanced', methods=['POST'])
@admin_required
def api_delete_user_enhanced():
    """增强的用户删除API，支持两种删除模式"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        mode = data.get('mode')
        
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID参数'}), 400
        
        if mode not in ['user_only', 'server_only', 'delete_all']:
            return jsonify({'success': False, 'message': '无效的删除模式'}), 400
        
        # 获取用户记录
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        
        # 检查是否试图删除自己
        if user.id == session['user_id']:
            return jsonify({'success': False, 'message': '不能删除自己的账户'}), 400
        
        username = user.username
        logger.info(f"管理员请求删除用户 {username}，模式: {mode}")
        
        # 根据删除模式执行相应操作
        if mode == 'delete_all':
            # 完全删除：撤销服务器权限和删除用户记录
            from server_operations import delete_user_from_servers
            
            # 先从服务器删除用户账户和权限
            server_success, server_message = delete_user_from_servers(user)
            
            if not server_success:
                logger.warning(f"服务器删除部分失败: {server_message}")
                # 即使服务器删除失败，仍然继续删除数据库记录
            
            # 删除数据库中的相关记录
            Application.query.filter_by(user_id=user_id).delete()
            ApplicationBatch.query.filter_by(user_id=user_id).delete()
            Notification.query.filter_by(admin_id=user_id).delete()
            
            db.session.delete(user)
            db.session.commit()
            
            if server_success:
                message = f'用户 {username} 及其服务器账户已完全删除'
            else:
                message = f'用户 {username} 数据库记录已删除，但服务器操作部分失败: {server_message}'
            
            logger.info(f"完全删除用户完成: {message}")
            return jsonify({'success': True, 'message': message})
            
        elif mode == 'server_only':
            # 仅删除服务器账户，保留系统记录
            from server_operations import delete_user_from_servers
            
            # 从服务器删除用户账户和权限
            server_success, server_message = delete_user_from_servers(user)
            
            if server_success:
                message = f'用户 {username} 的所有服务器账户已删除（系统记录保留）'
                logger.info(f"仅删除服务器账户完成: {message}")
                return jsonify({'success': True, 'message': message})
            else:
                logger.warning(f"服务器账户删除失败: {server_message}")
                return jsonify({'success': False, 'message': f'删除服务器账户失败: {server_message}'}), 500
                
        else:  # mode == 'user_only'
            # 仅删除用户记录，不影响服务器账户
            Application.query.filter_by(user_id=user_id).delete()
            ApplicationBatch.query.filter_by(user_id=user_id).delete()
            Notification.query.filter_by(admin_id=user_id).delete()
            
            db.session.delete(user)
            db.session.commit()
            
            message = f'用户 {username} 的系统记录已删除（服务器账户保留）'
            logger.info(f"仅删除用户记录完成: {message}")
            return jsonify({'success': True, 'message': message})
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"增强删除用户API异常: {e}")
        return jsonify({'success': False, 'message': f'删除用户时发生异常: {str(e)}'}), 500

@app.route('/tailscale_tutorial')
@login_required
def tailscale_tutorial():
    """Tailscale教程页面"""
    return render_template('tailscale_tutorial.html')

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
        
        elif action == 'edit_profile':
            # 编辑用户信息
            name = request.form.get('name', '').strip()
            student_id = request.form.get('student_id', '').strip()
            identity_type = request.form.get('identity_type', '').strip()
            laboratory = request.form.get('laboratory', '').strip()
            supervisor = request.form.get('supervisor', '').strip()
            contact = request.form.get('contact', '').strip()
            
            # 验证必填字段
            if not all([name, student_id, identity_type, laboratory, supervisor]):
                flash('请填写所有必填字段', 'error')
                return redirect(url_for('account'))
            
            # 检查学号是否被其他用户使用
            existing_student = User.query.filter(
                User.student_id == student_id,
                User.id != user.id
            ).first()
            if existing_student:
                flash('该学号已被其他用户使用', 'error')
                return redirect(url_for('account'))
            
            # 更新用户信息
            user.name = name
            user.student_id = student_id
            user.identity_type = identity_type
            user.laboratory = laboratory
            user.supervisor = supervisor
            user.contact = contact
            
            try:
                db.session.commit()
                # 更新session中的姓名
                session['name'] = name
                flash('个人信息更新成功', 'success')
            except Exception as e:
                db.session.rollback()
                flash('更新失败，请重试', 'error')
            
            return redirect(url_for('account'))
    
    # 获取用户的服务器权限信息（仅显示已批准的申请）
    user_applications = Application.query.filter_by(
        user_id=session['user_id'], 
        status='approved'
    ).options(db.joinedload(Application.server), db.joinedload(Application.permission_type)).all()
    
    # 按服务器分组权限
    server_permissions = {}
    for app in user_applications:
        server_id = app.server.id
        if server_id not in server_permissions:
            server_permissions[server_id] = {
                'server': app.server,
                'permissions': [],
                'user_password': None,  # 用户密码，从admin_comment中提取
                'server_username': None  # 实际的服务器用户名
            }
        server_permissions[server_id]['permissions'].append(app)
        
        # 设置服务器用户名（使用第一个找到的server_username，如果没有则使用系统用户名）
        if server_permissions[server_id]['server_username'] is None:
            if app.server_username:
                server_permissions[server_id]['server_username'] = app.server_username
            else:
                # 如果没有设置server_username，尝试生成或使用系统用户名
                from username_generator import generate_username_for_user
                generated_username, _ = generate_username_for_user(user.name or user.username, server_id)
                server_permissions[server_id]['server_username'] = generated_username or user.username
        
        # 提取用户密码（只需要提取一次）
        if server_permissions[server_id]['user_password'] is None and app.admin_comment:
            import re
            password_match = re.search(r'\[系统生成\] 用户密码: (.+)', app.admin_comment)
            if password_match:
                server_permissions[server_id]['user_password'] = password_match.group(1)
    
    return render_template('account.html', user=user, applications=user_applications, server_permissions=server_permissions)

@app.route('/api/verify_password', methods=['POST'])
@login_required
def api_verify_password():
    """验证用户密码API - 支持临时认证缓存"""
    password = request.json.get('password')
    user = User.query.get(session['user_id'])
    
    if user.check_password(password):
        # 验证成功，设置临时认证缓存，有效期15分钟
        from datetime import datetime, timedelta
        session['password_verified_at'] = datetime.now().isoformat()
        session['password_verified_until'] = (datetime.now() + timedelta(minutes=15)).isoformat()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': '密码不正确'})

@app.route('/api/check_password_verification', methods=['GET'])
@login_required
def api_check_password_verification():
    """检查密码验证缓存状态API"""
    from datetime import datetime
    
    # 检查是否有有效的密码验证缓存
    if 'password_verified_until' in session:
        try:
            verified_until = datetime.fromisoformat(session['password_verified_until'])
            if datetime.now() < verified_until:
                # 缓存仍然有效
                remaining_minutes = int((verified_until - datetime.now()).total_seconds() / 60)
                return jsonify({
                    'verified': True, 
                    'remaining_minutes': remaining_minutes
                })
        except ValueError:
            # 如果日期格式有问题，清除缓存
            session.pop('password_verified_at', None)
            session.pop('password_verified_until', None)
    
    return jsonify({'verified': False})

@app.route('/api/notifications')
@login_required
def api_notifications():
    """获取当前用户通知API"""
    user = User.query.get(session['user_id'])
    if user.is_admin():
        unread_count = Notification.query.filter_by(admin_id=session['user_id'], is_read=False).count()
        return jsonify({'unread_count': unread_count})
    return jsonify({'unread_count': 0})

@app.route('/api/generate_username', methods=['POST'])
@login_required
@admin_required
def api_generate_username():
    """为用户生成服务器账户名 API"""
    try:
        data = request.get_json()
        chinese_name = data.get('chinese_name', '').strip()
        server_id = data.get('server_id')
        
        if not chinese_name:
            return jsonify({
                'success': False, 
                'message': '请提供中文姓名'
            })
        
        if not server_id:
            return jsonify({
                'success': False, 
                'message': '请提供服务器ID'
            })
        
        # 检查服务器是否存在
        server = Server.query.get(server_id)
        if not server:
            return jsonify({
                'success': False, 
                'message': '服务器不存在'
            })
        
        # 生成用户名
        username, message = generate_username_for_user(chinese_name, server_id)
        
        if username:
            return jsonify({
                'success': True,
                'username': username,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            })
            
    except Exception as e:
        logger.error(f"生成用户名 API 错误: {e}")
        return jsonify({
            'success': False,
            'message': f'生成用户名失败: {str(e)}'
        })

@app.route('/api/validate_username', methods=['POST'])
@login_required
@admin_required
def api_validate_username():
    """验证用户名格式 API"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        server_id = data.get('server_id')
        
        if not username:
            return jsonify({
                'success': False,
                'message': '请提供用户名'
            })
        
        # 验证格式
        if not validate_username_format(username):
            return jsonify({
                'success': False,
                'message': '用户名不符合Linux命名规范（3-32位，字母开头，只能包含字母数字下划线连字符）'
            })
        
        # 检查在服务器上是否已存在
        if server_id:
            existing_apps = Application.query.filter_by(
                server_id=server_id,
                server_username=username,
                status='approved'
            ).first()
            
            if existing_apps:
                return jsonify({
                    'success': False,
                    'message': f'用户名 {username} 在该服务器上已存在'
                })
        
        return jsonify({
            'success': True,
            'message': '用户名可用'
        })
        
    except Exception as e:
        logger.error(f"验证用户名 API 错误: {e}")
        return jsonify({
            'success': False,
            'message': f'验证失败: {str(e)}'
        })

@app.route('/api/check_server_username', methods=['POST'])
@login_required
@admin_required
def api_check_server_username():
    """检查服务器上用户名是否存在 API"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        server_id = data.get('server_id')
        
        if not username or not server_id:
            return jsonify({
                'success': False,
                'message': '请提供用户名和服务器ID'
            })
        
        # 获取服务器
        server = Server.query.get(server_id)
        if not server:
            return jsonify({
                'success': False,
                'message': '服务器不存在'
            })
        
        # SSH连接检查用户名是否存在
        from server_operations import ServerUserManager
        manager = ServerUserManager(server)
        
        try:
            if manager.connect():
                exists = manager.user_exists(username)
                manager.disconnect()
                
                return jsonify({
                    'success': True,
                    'exists': exists,
                    'message': f'用户名 {username} {"已存在" if exists else "可用"}'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '无法连接到服务器进行检查'
                })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'检查用户名时出错: {str(e)}'
            })
            
    except Exception as e:
        logger.error(f"检查服务器用户名 API 错误: {e}")
        return jsonify({
            'success': False,
            'message': f'检查失败: {str(e)}'
        })

@app.route('/api/generate_batch_usernames', methods=['POST'])
@login_required
@admin_required
def api_generate_batch_usernames():
    """为批次中的权限申请生成用户名 API"""
    try:
        data = request.get_json()
        batch_id = data.get('batch_id')
        
        if not batch_id:
            return jsonify({
                'success': False,
                'message': '请提供批次ID'
            })
        
        # 获取批次和权限申请
        batch = ApplicationBatch.query.get(batch_id)
        if not batch:
            return jsonify({
                'success': False,
                'message': '批次不存在'
            })
        
        applications = Application.query.filter_by(batch_id=batch_id).all()
        if not applications:
            return jsonify({
                'success': False,
                'message': '批次中没有权限申请'
            })
        
        # 为每个需要创建用户的申请生成用户名
        from username_generator import generate_username_for_user
        
        results = {}
        server = applications[0].server
        user = applications[0].user
        
        # 只为新用户生成用户名（检查是否已经有server_username）
        if not applications[0].server_username:
            # 使用用户的真实姓名生成用户名
            user_real_name = user.name or user.username
            username, message = generate_username_for_user(user_real_name, server.id)
            
            if username:
                results = {
                    'batch_id': batch_id,
                    'server_id': server.id,
                    'server_name': server.name,
                    'user_id': user.id,
                    'user_name': user.name or user.username,
                    'generated_username': username,
                    'message': message
                }
            else:
                return jsonify({
                    'success': False,
                    'message': f'生成用户名失败: {message}'
                })
        else:
            # 已有用户名，直接返回
            results = {
                'batch_id': batch_id,
                'server_id': server.id,
                'server_name': server.name,
                'user_id': user.id,
                'user_name': user.name or user.username,
                'generated_username': applications[0].server_username,
                'message': '使用现有用户名'
            }
        
        return jsonify({
            'success': True,
            'data': results
        })
        
    except Exception as e:
        logger.error(f"生成批次用户名 API 错误: {e}")
        return jsonify({
            'success': False,
            'message': f'生成用户名失败: {str(e)}'
        })

if __name__ == '__main__':
    create_tables()
    app.run(debug=True, host='0.0.0.0', port=8080)