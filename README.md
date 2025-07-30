# Server Management System (服务器管理系统)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A comprehensive Flask-based server management system for monitoring Linux servers and managing user access permissions with automated server-side user provisioning.

## 🌟 Key Features

### Core Functionality
- **Real-time Server Monitoring**: SSH-based monitoring with CPU, memory, disk usage metrics
- **Batch Permission Management**: Apply for multiple server permissions in organized batches
- **Automated User Provisioning**: Automatic Linux user creation and permission configuration
- **Role-based Access Control**: Admin and user roles with secure interface restrictions
- **Comprehensive Audit Trail**: Detailed logging of all server operations and user actions

### Enhanced User Experience (v3.1)
- **Personal Dashboard**: Enhanced metrics display with server access visualization
- **Connection Management**: One-click SSH command copying with secure credential viewing
- **Responsive Design**: Mobile-friendly interface with centered layout
- **Real-time Status**: Live server connection monitoring with visual indicators

### Advanced Admin Features
- **Batch Review System**: Process entire permission batches with individual approval controls
- **Modal-based Interface**: Detailed review modals with comprehensive permission management
- **User Administration**: Password reset capabilities, application history tracking
- **Automated Operations**: Server-side user creation and group configuration

## ✨ 功能特性

### 🔍 核心功能
- 🖥️ **服务器监控**: 实时监控CPU、内存、磁盘使用情况
- 📊 **图表展示**: 使用Chart.js展示监控数据和历史趋势  
- 👥 **用户管理**: 支持普通用户和管理员角色
- 📋 **权限申请**: 用户可申请不同类型的服务器权限
- ✅ **审核流程**: 管理员可审核通过或拒绝申请
- 🔔 **通知提醒**: 管理员收到新申请的实时通知
- 🤖 **自动化配置**: 权限批准后自动在服务器上创建用户和配置权限
- 📋 **操作日志**: 详细记录所有服务器操作和权限变更
- 🔐 **账户管理**: 用户密码修改、服务器密码查看和管理功能
- 🎨 **统一界面**: Claude风格的橙色主题，完全居中的响应式设计

### 🔐 权限类型与自动化配置
- **普通用户**: 基本SSH访问权限，自动创建Linux用户
- **管理员权限**: sudo权限和系统管理，自动添加到sudo组
- **Docker权限**: Docker容器管理权限，自动添加到docker组
- **数据库权限**: 数据库访问和管理权限，自动添加到database组  
- **自定义权限**: 其他特殊权限需求，可配置特定组权限

### 🛡️ 安全特性
- 输入验证和SQL注入防护
- 命令注入防护和安全命令检查
- 用户名和组名合法性验证
- SSH连接安全验证和超时控制
- 操作审计日志记录

## 🛠️ 技术栈
- **后端**: Python + Flask + SQLAlchemy + SQLite
- **前端**: HTML + Bootstrap 5 + Chart.js + jQuery
- **SSH操作**: paramiko (SSH连接和命令执行)
- **认证**: Session-based认证
- **安全**: shlex命令参数转义，正则表达式验证
- **日志**: Python logging模块，自定义操作日志系统

## 安装部署

### 1. 环境要求
- Python 3.7+
- pip

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 运行应用
```bash
python app.py
```

应用将在 http://localhost:8080 启动

### 4. 默认登录
- 用户名: admin
- 密码: admin123

## 📖 使用指南

### 👨‍💼 管理员操作流程
1. **添加服务器**: 在"管理 → 服务器管理"中添加要监控的服务器
2. **配置权限**: 系统预设了5种权限类型，可根据需要调整
3. **审核申请**: 在"管理 → 审核申请"中处理用户的权限申请
4. **自动化配置**: 批准申请后系统自动在目标服务器创建用户和配置权限
5. **监控查看**: 在控制台实时查看所有服务器状态
6. **权限撤销**: 可以撤销已批准的权限，自动移除服务器端权限

### 👤 普通用户操作流程
1. **注册账户**: 填写学号、实验室等信息注册账户
2. **查看服务器**: 在控制台查看可用服务器的监控状态
3. **申请权限**: 点击"申请权限"选择服务器和权限类型
4. **跟踪申请**: 在"我的申请"中查看申请状态和审核结果
5. **获取访问**: 权限批准后获得SSH连接信息和自动生成的密码
6. **一键连接**: 使用一键复制功能快速获取SSH连接命令
7. **🆕 账户管理**: 通过"账户信息"修改密码、查看服务器连接信息

### 🔄 自动化权限配置流程
1. 管理员批准申请
2. 系统SSH连接到目标服务器
3. 检查用户是否存在，不存在则自动创建
4. 生成安全随机密码
5. 根据权限类型自动配置：
   - 普通用户：创建基本用户账户
   - 管理员权限：添加到sudo组
   - Docker权限：添加到docker组
   - 数据库权限：添加到database组
6. 记录详细操作日志
7. 在用户界面显示连接信息

### 监控功能
- **实时数据**: 每30秒自动更新监控数据
- **历史图表**: 点击服务器详情查看6小时历史趋势
- **状态指示**: 在线(绿色)、离线(红色)、未知(灰色)

## 📁 项目结构
```
server-manage/
├── app.py                  # Flask主应用，路由和业务逻辑
├── models.py               # SQLAlchemy数据库模型
├── server_monitor.py       # 服务器监控逻辑
├── server_operations.py    # 🆕 服务器用户管理和权限配置
├── operation_log.py        # 🆕 操作日志记录系统
├── config.py               # 应用配置
├── requirements.txt        # Python依赖包
├── CLAUDE.md               # AI助手项目指导文档
├── README.md               # 项目说明文档
├── instance/
│   └── database.db         # SQLite数据库(运行后生成)
├── logs/                   # 🆕 操作日志目录(运行后生成)
│   ├── server_operations.log       # 操作日志
│   └── server_operations_error.log # 错误日志
├── templates/              # Jinja2 HTML模板
│   ├── base.html           # 基础模板
│   ├── login.html          # 登录页面
│   ├── dashboard.html      # 管理员控制台
│   ├── user_dashboard.html # 🆕 用户控制台
│   ├── account.html        # 🆕 账户信息管理页面
│   ├── apply.html          # 权限申请页面
│   ├── my_applications.html # 我的申请
│   ├── admin_review.html   # 管理员审核页面
│   ├── admin_servers.html  # 服务器管理
│   └── admin_users.html    # 用户管理
└── static/                 # 静态资源文件
    ├── css/
    │   └── claude-style.css # 🆕 自定义样式
    └── js/                 # JavaScript文件
```

## 🗄️ 数据库表结构
- **users**: 用户信息、认证和角色管理
- **servers**: 服务器SSH连接配置信息
- **permission_types**: 权限类型定义和描述
- **applications**: 用户权限申请记录和审核状态
- **server_metrics**: 服务器监控数据时序存储
- **notifications**: 管理员通知和消息队列

### 核心数据关系
- 用户(User) → 多个申请(Application)
- 服务器(Server) → 多个申请(Application) + 多个监控数据(ServerMetric)
- 申请(Application) 关联 用户(User) + 服务器(Server) + 权限类型(PermissionType)
- 通知(Notification) 提醒管理员关于申请(Application)

## 配置说明

### SSH连接配置
在添加服务器时需要提供：
- 服务器名称（显示名称）
- 主机地址（IP或域名）
- SSH端口（默认22）
- 用户名
- 密码（目前仅支持密码认证）

### 监控数据收集
系统通过SSH连接执行以下命令收集监控数据：
- CPU使用率: `top -bn1` 或 `/proc/stat`
- 内存使用率: `free`
- 磁盘使用率: `df -h /`
- 系统负载: `uptime`

## 🔒 安全注意事项

### ⚠️ 已知安全隐患
1. **🔴 高风险 - 服务器密码明文存储**: Server表中的password字段以明文形式存储，需要实施加密存储
2. **🟡 中风险 - 缺少CSRF防护**: 表单缺少CSRF token验证，建议添加flask-wtf的CSRFProtect
3. **🟡 中风险 - XSS风险**: 表单输入需要HTML转义防护

### 基础安全
1. **修改默认密码**: 部署后立即修改admin默认密码
2. **SSH连接安全**: 目标服务器建议配置SSH密钥认证
3. **HTTPS加密**: 生产环境建议配置HTTPS和SSL证书
4. **防火墙配置**: 限制应用访问来源IP和端口
5. **定期备份**: 定期备份数据库文件和操作日志

### 应用内安全机制
- ✅ **输入验证**: 用户名、组名格式验证
- ✅ **命令注入防护**: shlex参数转义和危险命令检测
- ✅ **SQL注入防护**: SQLAlchemy ORM防护
- ✅ **会话安全**: Flask session认证和超时
- ✅ **权限控制**: 角色基础访问控制(RBAC)
- ✅ **操作审计**: 详细的操作日志记录

### 服务器端安全要求
- 目标服务器需要独立的管理用户账户
- 建议使用专用管理用户而非root用户
- 定期审查和清理不活跃的用户账户
- 监控异常登录和权限使用情况

## 🔧 故障排除

### 常见问题
1. **SSH连接失败**: 
   - 检查服务器地址、端口、用户名密码是否正确
   - 确认目标服务器SSH服务运行正常
   - 检查网络连通性和防火墙设置

2. **监控数据为空**: 
   - 确保SSH用户有执行监控命令的权限
   - 检查目标服务器是否安装了必要的命令工具
   - 查看logs/server_operations_error.log了解具体错误

3. **自动权限配置失败**:
   - 检查SSH用户是否有sudo权限
   - 确认目标服务器支持所需的用户管理命令
   - 查看操作日志确认具体失败原因

4. **页面无法访问**: 
   - 检查Flask应用是否正常启动
   - 确认端口8080没有被其他程序占用
   - 检查防火墙设置和端口开放情况

### 📋 日志系统
- **应用日志**: 控制台输出Flask应用运行日志
- **操作日志**: `logs/server_operations.log` 记录所有服务器操作
- **错误日志**: `logs/server_operations_error.log` 记录操作错误
- **日志轮转**: 超过30天的日志会自动归档

### 🔍 调试技巧
- 启用Flask调试模式查看详细错误信息
- 使用浏览器开发者工具检查前端错误
- 检查数据库连接和表结构是否正确
- 手动测试SSH连接验证凭据正确性

## 🚀 Installation & Quick Start

### Prerequisites
- Python 3.8 or higher
- SSH access to target Linux servers
- Standard Linux command utilities on target servers

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/server-manage.git
   cd server-manage
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Access the system**
   - Open your browser to `http://localhost:8080`
   - Login with default credentials:
     - Username: `admin`
     - Password: `admin123`
   - **⚠️ Change default password immediately after first login**

## 📊 System Architecture

### Backend Components
- **Flask Application** (`app.py`): Main application with routes and business logic
- **Database Models** (`models.py`): SQLAlchemy ORM models with batch application support
- **Server Monitor** (`server_monitor.py`): SSH-based monitoring with real-time metrics
- **Server Operations** (`server_operations.py`): Automated user management and permission configuration
- **Operation Logging** (`operation_log.py`): Comprehensive audit trail system

### Database Schema
```
User -> ApplicationBatch -> Applications -> Server
     -> Notifications           -> PermissionType
Server -> ServerMetrics
```

### Key Relationships
- Users create ApplicationBatches containing multiple permission Applications
- Each Application links User + Server + PermissionType
- Administrators receive Notifications for new ApplicationBatches
- Servers store real-time ServerMetrics data

## 🔧 Configuration

### Server Setup
Add servers through the admin interface with the following details:
- **Name**: Display name for identification
- **Host**: IP address or hostname
- **Port**: SSH port (default: 22)
- **Username**: SSH username with sudo privileges
- **Password**: SSH password (encrypted storage recommended)

### Permission Types
The system includes 5 predefined permission categories:
1. **普通用户** (Regular User): Basic SSH access with user account creation
2. **管理员权限** (Admin Rights): sudo group membership for system administration
3. **Docker权限** (Docker Access): docker group membership for container management
4. **数据库权限** (Database Access): database group membership for DB operations
5. **自定义权限** (Custom Rights): Flexible permissions requiring manual configuration

## 📖 Usage Guide

### For End Users

#### Requesting Permissions
1. Navigate to "申请权限" (Apply for Permissions)
2. Select target server and multiple permission types
3. Submit batch application with reason
4. Monitor status in "我的申请" (My Applications)

#### Accessing Servers
1. View approved servers in personal dashboard
2. Use password visibility toggle to view credentials securely
3. Copy SSH connection command with one click
4. Connect using: `ssh username@host -p port`

#### Account Management
- Access "账户信息" to change password
- View all server connections and credentials
- Secure password verification for sensitive operations

### For Administrators

#### Reviewing Applications
1. Access "审核申请" to view pending batches
2. Use filter buttons to view different status categories
3. Click on batch cards to open detailed review modal
4. Approve/reject individual permissions with comments
5. Automatic server configuration on approval

#### Managing Infrastructure
- **Server Management**: Add, edit, monitor server configurations
- **User Administration**: Manage users, reset passwords, view histories
- **Real-time Monitoring**: Dashboard with live server metrics
- **Notification System**: Instant alerts for new requests

## 🔒 Security Features

### Authentication & Authorization
- Session-based authentication with role-based access control
- Secure password hashing with industry-standard algorithms
- Protected API endpoints with authentication validation
- Session timeout management

### Data Protection
- Input validation and sanitization for all forms
- Command injection prevention with `shlex.quote()`
- SQL injection protection via SQLAlchemy ORM
- Secure credential storage (encryption recommended)

### Server Security
- SSH connection timeouts and error handling
- Automated user creation with secure password generation
- Group-based permission management
- Comprehensive audit logging for all operations

### Known Security Considerations
1. **Server Password Storage**: Currently stored in plain text (encryption recommended)
2. **CSRF Protection**: Missing CSRF tokens (flask-wtf CSRFProtect recommended)
3. **XSS Prevention**: HTML escaping needed for user inputs

## 🔍 Monitoring & Troubleshooting

### System Monitoring
- Real-time metrics collection every 30 seconds
- Historical data visualization with Chart.js
- Server status indicators (online/offline/unknown)
- Automated error detection and logging

### Log Management
- **Application Logs**: Console output for Flask application
- **Operation Logs**: `logs/server_operations.log` for all server operations
- **Error Logs**: `logs/server_operations_error.log` for failures
- **Automatic Rotation**: 30-day log retention with archival

### Common Issues & Solutions

1. **SSH Connection Failures**
   - Verify server credentials and network connectivity
   - Check SSH service status and firewall rules
   - Review error logs for specific connection issues

2. **Permission Configuration Errors**
   - Ensure SSH user has sudo privileges
   - Verify target server compatibility
   - Check group existence and permissions

3. **Database Issues**
   - Verify SQLite file permissions
   - Check available disk space
   - Review schema migration logs

## 🚀 Deployment

### Production Setup
1. Configure environment variables for production
2. Set up reverse proxy (nginx/Apache)
3. Configure SSL certificates
4. Set up database backups
5. Configure log rotation

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "app.py"]
```

## 🔄 Version History

### Version 3.1 (Current) - Enhanced Dashboard & Interface
- Enhanced user dashboard with comprehensive metrics
- Advanced admin review interface with batch processing
- Improved security and UX enhancements
- Responsive design for mobile devices

### Version 3.0 - Batch Application System
- Complete redesign of permission request workflow
- Batch-based application system with individual approvals
- Enhanced admin interface with bulk management
- Database schema improvements

### Version 2.0 - Account Management
- User account management interface
- Password change functionality with validation
- Server credential viewing with authentication
- Admin user management enhancements

## 🛠️ Development & Extension

The system uses a modular design that supports flexible extensions:

### Feature Extensions
- **Permission Types**: Add new permission definitions in `models.py`
- **Monitoring Metrics**: Extend `server_monitor.py` for additional data collection
- **Authentication**: Integrate LDAP, AD, or OAuth2 authentication systems
- **Notifications**: Add email, SMS, or webhook notification channels
- **API Integration**: Provide RESTful APIs for third-party systems

### Security Enhancements
- **SSH Key Authentication**: Support SSH public key authentication
- **Multi-Factor Authentication**: Integrate TOTP or SMS verification
- **Fine-grained Permissions**: Implement more detailed access control
- **Enhanced Auditing**: Add user behavior analysis and anomaly detection

### Performance Optimizations
- **Database Migration**: Move to PostgreSQL or MySQL for better performance
- **Caching System**: Integrate Redis for monitoring data caching
- **Async Processing**: Use Celery for time-consuming SSH operations
- **Load Balancing**: Support multi-instance deployment

### Development Guidelines
1. Follow existing code structure and naming conventions
2. Add appropriate test cases for new functionality
3. Provide migration scripts for database changes
4. Update CLAUDE.md documentation for AI assistant guidance

## 🤝 Contributing

We welcome contributions to improve this project!

### How to Contribute
1. Fork the repository to your GitHub account
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Setup
1. Clone your fork and set up the development environment
2. Install dependencies: `pip install -r requirements.txt`
3. Run tests to ensure everything works
4. Make your changes and test thoroughly
5. Update documentation as needed

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Flask framework and its ecosystem
- Bootstrap for responsive UI components
- Chart.js for data visualization
- Paramiko for SSH connectivity
- SQLAlchemy for database ORM

## 📞 Support

For support and questions:
- Create an issue in the repository
- Review the documentation in `CLAUDE.md`
- Check the troubleshooting guide in this README

---

**Built with ❤️ for efficient server management**