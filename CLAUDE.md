# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive Flask-based server management system (服务器管理系统) for monitoring Linux servers and managing user access permissions with automated server-side user provisioning. The application provides real-time server monitoring, batch-based permission request system, admin approval workflows, automatic user creation and permission configuration on target servers, and comprehensive account management features.

**Latest Updates (v3.2 - Advanced Permission Management & Enhanced UX):**
- 🆕 **Enhanced User Deletion**: Three-option deletion modal with complete server account management
  - **Delete User Only**: Removes user records while preserving server accounts
  - **Complete Deletion**: Revokes all permissions and deletes server accounts across all systems
  - Multi-step confirmation with detailed impact preview and server account information
- 🆕 **Individual Permission Revocation**: Granular permission management with server-side cleanup
  - Permission display as individual rows with dedicated delete buttons in admin interface
  - Automatic server-side permission revocation and Linux group removal
  - Real-time permission status updates and comprehensive audit trail
- 🆕 **Streamlined Application Process**: Simplified permission request workflow
  - Hidden "普通用户" permission card with automatic default SSH access provisioning
  - Optional permission selection - users can proceed without selections for basic access
  - Updated UI text and guidance: "基本SSH功能" → "默认功能" with clear explanatory text
- 🆕 **Enhanced Server Operations**: Complete user account lifecycle management
  - Automatic bash shell configuration (`/bin/bash`) for all new user accounts
  - Comprehensive user deletion across multiple servers with detailed logging and error handling
  - Individual server account management with targeted deletion and cleanup options
- 🆕 **Advanced Modal Interfaces**: Multi-step confirmation dialogs for critical operations
  - Server account impact preview before user deletion with detailed permission breakdown
  - Permission-specific confirmation dialogs with server and user information
  - Enhanced error handling, user feedback mechanisms, and operation status reporting

**Previous Updates (v3.1 - Enhanced Dashboard & Interface):**
- Enhanced User Dashboard with comprehensive metrics display and server access visualization
- Advanced Admin Review Interface with responsive card-based layout and modal system
- Security & UX Enhancements including password toggle and improved responsive design

**Previous Updates (v3.0 - Batch Application System):**
- 🆕 **Batch Application System**: Complete redesign of permission request workflow
  - Users can apply for multiple permissions in a single batch
  - Administrators review and approve entire batches instead of individual permissions
  - Each batch contains multiple permission requests with individual approval status
- 🆕 **Enhanced User Experience**: 
  - Applications displayed by batch (申请批次) rather than individual permissions
  - Color-coded permission status: green (approved), red (rejected), gray (pending)
  - Users can cancel entire pending application batches
- 🆕 **Improved Admin Interface**:
  - Batch review system with per-permission approval/rejection
  - Bulk permission management in single modal
  - Statistics now show application batches instead of individual permissions
- 🆕 **Database Schema Updates**:
  - Added `ApplicationBatch` model for grouping related permission requests
  - Enhanced `Application` model with batch relationships
  - Improved data consistency and referential integrity

**Previous Updates (v2.0):**
- Added account management interface for users and administrators
- Implemented password change functionality with security validation
- Added server password viewing with user authentication
- Enhanced admin user management with password reset capabilities
- Fixed page layout issues (removed sidebar layout, implemented centered design)
- Unified button styling with Claude orange theme
- Improved security with password verification APIs

## Development Commands

### Running the Application
```bash
python app.py
```
The application runs on http://localhost:8080

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Database Operations
- Database is automatically created on first run via `create_tables()` in app.py
- Uses SQLite with automatic schema creation
- Database file: `instance/database.db`
- Supports automatic migrations for schema updates

### Logging and Operations
- Application logs: Console output for Flask application
- Operation logs: `logs/server_operations.log` for all server operations
- Error logs: `logs/server_operations_error.log` for operation failures
- Automatic log rotation and cleanup after 30 days

## Architecture Overview

### Core Components

1. **app.py**: Main Flask application with all routes and business logic
   - Authentication system with session-based login
   - Role-based access control (user/admin)
   - Server monitoring dashboard
   - Permission request/approval workflow
   - Automated server operations integration
   - 🆕 **Enhanced User Management APIs**: `/api/delete_user_enhanced`, `/api/revoke_user_permission`
   - 🆕 **Server Account Management**: User deletion with server account cleanup options

2. **models.py**: SQLAlchemy database models
   - User: Authentication, role management, and student information
   - Server: SSH connection details for monitored servers
   - Application: Permission requests from users with audit trail
   - ServerMetric: Time-series monitoring data
   - PermissionType: Configurable permission categories
   - Notification: Admin notifications for new requests

3. **server_monitor.py**: SSH-based server monitoring
   - Uses paramiko for SSH connections
   - Collects CPU, memory, disk usage via shell commands
   - Stores metrics in database with timestamps
   - Real-time server status detection

4. **server_operations.py**: 🆕 Automated server user management
   - ServerUserManager class for SSH-based user operations
   - Automatic Linux user creation and password generation
   - Permission configuration based on request type
   - Security features: input validation, command injection prevention
   - Integration with operation logging system
   - 🆕 **Enhanced User Deletion**: `delete_user_from_servers()`, `delete_user_account_only()`
   - 🆕 **Bash Shell Configuration**: All users created with `/bin/bash` as default shell
   - 🆕 **Comprehensive Cleanup**: Permission revocation with group removal across servers

5. **operation_log.py**: 🆕 Comprehensive operation logging system
   - OperationLogger class for structured logging
   - Detailed audit trail for all server operations
   - Separate error logging and operation success tracking
   - Log rotation and archival management
   - 🆕 **User Deletion Logging**: `log_user_deletion()` method for account removal audit trail
   - 🆕 **Permission Revocation Logging**: Individual permission deletion tracking

6. **config.py**: Application configuration
   - SSH timeout settings
   - Monitor refresh intervals
   - Database configuration
   - Security settings

### Key Features

- **Real-time Monitoring**: Collects server metrics every 30 seconds via SSH
- **Permission Management**: 5 predefined permission types (普通用户, 管理员权限, Docker权限, 数据库权限, 自定义权限)
- **Approval Workflow**: Users request → Admins review → Approve/Reject → Automatic server configuration
- **Notification System**: Real-time alerts for admins on new requests
- **🆕 Automated User Provisioning**: Automatic Linux user creation on target servers
- **🆕 Permission Configuration**: Automatic group assignments based on permission type
- **🆕 Security Hardening**: Input validation, command injection prevention, secure SSH operations
- **🆕 Comprehensive Logging**: Detailed operation audit trail and error tracking
- **🆕 User Experience**: One-click SSH connection info copy, password visibility toggle
- **🆕 Account Management**: User password changes, server password viewing with authentication
- **🆕 Admin Password Management**: Reset user passwords with validation and security checks
- **🆕 Unified UI Design**: Claude orange theme with centered layout and responsive design
- **🆕 Enhanced User Deletion**: Multi-option deletion system with server account management
- **🆕 Individual Permission Management**: Granular permission revocation with server-side cleanup
- **🆕 Streamlined Application Flow**: Simplified permission request with default access options

### Authentication & Authorization

- Default admin: username=`admin`, password=`admin123`
- Session-based authentication stored in Flask sessions
- Two decorators: `@login_required` and `@admin_required`
- Role-based UI rendering (admin vs user views)

### Database Schema

Key relationships:
- Users have many Applications
- Servers have many Applications and ServerMetrics
- Applications link User + Server + PermissionType
- Notifications alert Admins about Applications

### Frontend Technology

- Bootstrap 5 for UI styling with custom Claude-themed components
- Chart.js for monitoring data visualization and historical trends
- jQuery for AJAX requests and dynamic updates
- Jinja2 HTML templates in `templates/` directory
- Custom CSS styling in `static/css/claude-style.css`
- Interactive JavaScript features: password toggle, connection info copy, real-time notifications
- **🆕 Responsive Design**: Centered layout with max-width constraints, mobile-friendly
- **🆕 Account Management UI**: Password change forms, server info display, validation feedback
- **🆕 Admin Management Tools**: Password reset modals, form validation, user-friendly alerts

### Security Architecture

- **Input Validation**: Username and group name format validation using regex
- **Command Injection Prevention**: `shlex.quote()` for safe parameter passing
- **Dangerous Command Detection**: Pattern matching to prevent harmful commands
- **SSH Security**: Connection timeout, authentication validation, secure parameter handling
- **Session Management**: Flask session-based authentication with role-based access control
- **Audit Logging**: Comprehensive operation logging for security monitoring

## Default Login Credentials

- Username: `admin`
- Password: `admin123`
- Change these immediately after deployment

## Server Requirements

### SSH Monitoring Requirements
Servers being monitored must:
- Allow SSH password authentication (or key-based authentication)
- Have standard Linux commands: `top`, `free`, `df`, `uptime`
- SSH user must have permission to execute monitoring commands

### Automated User Management Requirements
For automatic user provisioning to work:
- SSH user must have `sudo` privileges
- Target servers must support standard Linux user management commands: `useradd`, `usermod`, `chpasswd`, `gpasswd`
- Required system groups should exist or be creatable: `sudo`, `docker`, `database`
- SSH user should have permission to create users and modify group memberships

### Network and Security Requirements
- Reliable network connectivity between management system and target servers
- SSH service running on target servers (default port 22 or custom port)
- Firewall rules allowing SSH connections from management system
- Sufficient disk space for user home directories and logs

## 🆕 Routes and APIs (Latest Version)

### Core Application Routes
- **`/dashboard`**: Main user/admin dashboard with role-based views
  - User view: Personal server access, application status, metrics
  - Admin view: System overview, pending applications, server monitoring
- **`/apply`**: Batch application system for multiple permission requests
- **`/my_applications`**: User application history with batch management
- **`/admin/review`**: Admin batch review interface with approval workflow

### Account Management Routes
- **`/account` (GET/POST)**: Account information page for users
  - GET: Display user info, password change form, server connections
  - POST: Handle password changes with validation (action=change_password)
  - Requires: @login_required decorator
  - Features: Server password viewing with user authentication

### Admin Management Routes
- **`/admin/servers`**: Server configuration and management
- **`/admin/users`**: User management with password reset capabilities
- **`/admin/review_batch/<int:batch_id>`**: Batch approval processing
- **`/admin/revoke_permission/<int:app_id>`**: Permission revocation
- **🆕 `/api/delete_user_enhanced` (POST)**: Enhanced user deletion with multiple options
  - Supports `user_only` and `delete_all` deletion modes
  - Provides detailed server account impact information
  - Handles ApplicationBatch cleanup and foreign key constraints
- **🆕 `/api/revoke_user_permission` (POST)**: Individual permission revocation
  - Revokes specific permissions with server-side cleanup
  - Updates permission status and maintains audit trail

### API Endpoints
- **`/api/verify_password` (POST)**: Verify user password for secure operations
  - Request: `{"password": "user_password"}`
  - Response: `{"success": true/false, "message": "error_message"}`
- **`/api/cancel_application_batch/<int:batch_id>`**: User batch cancellation
- **`/api/notifications`**: Real-time notification system for admins
- **`/api/server_metrics/<int:server_id>`**: Real-time server monitoring data
- **`/api/server_metrics_history/<int:server_id>`**: Historical metrics

### Updated Templates
- **`user_dashboard.html`**: Enhanced user dashboard with metrics and server access
- **`admin_review.html`**: Batch-based admin review interface
- **`account.html`**: Account management interface
- **🆕 `admin_users.html`**: Enhanced user management with advanced deletion and permission controls
  - Individual permission rows with delete buttons
  - Three-option user deletion modal with impact preview
  - Real-time permission status updates and server account information
- **🆕 `apply.html`**: Streamlined application process with simplified workflow
  - Hidden "普通用户" permission card for cleaner interface
  - Updated guidance text and explanatory information
  - Optional permission selection with automatic default access
- **`base.html`**: Updated navigation with responsive design

## Automated Operations Workflow

### Permission Grant Process
1. Admin approves user application in web interface
2. System calls `configure_user_permissions()` from `server_operations.py`
3. SSH connection established to target server
4. User existence check performed
5. If user doesn't exist:
   - Generate secure random password (16 characters)
   - Create Linux user with home directory
   - Set generated password
6. Configure permissions based on type:
   - **🆕 默认权限**: Basic shell access with bash shell (`/bin/bash`), no additional groups
   - **管理员权限**: Add to `sudo` group for system administration
   - **Docker权限**: Add to `docker` group (create if not exists)
   - **数据库权限**: Add to `database` group (create if not exists)
   - **自定义权限**: Basic access with manual configuration option
7. Log all operations to `logs/server_operations.log`
8. Store generated password in application admin comment
9. Update application status and display result to admin

### Permission Revoke Process
1. Admin clicks revoke permission for approved application
2. System calls `revoke_user_permissions()` from `server_operations.py`
3. SSH connection established to target server
4. Remove user from relevant groups based on permission type
5. Application status updated to 'revoked'
6. Operation logged for audit trail

### 🆕 Enhanced User Deletion Process (v3.2)
1. **User Deletion Options**:
   - **User Records Only**: Removes user from database while preserving server accounts
   - **Complete Deletion**: Revokes all permissions and deletes server accounts
2. **Multi-Server Processing**: Handles user accounts across multiple servers systematically
3. **Permission Revocation**: Automatically removes users from all relevant groups before deletion
4. **Comprehensive Logging**: Detailed audit trail for all deletion operations and results
5. **Error Handling**: Graceful handling of individual server failures with partial success reporting

### 🆕 Individual Permission Management (v3.2)
1. **Granular Control**: Admin can revoke individual permissions without affecting others
2. **Server-Side Cleanup**: Automatic removal from Linux groups and permission cleanup
3. **Real-Time Updates**: Permission status updates immediately in the interface
4. **Audit Trail**: Complete logging of permission changes with timestamps and details

## Development Guidelines

### Code Organization
- Follow existing module structure and naming conventions
- Place server operation logic in `server_operations.py`
- Use `operation_log.py` for all audit logging
- Database operations should use SQLAlchemy ORM
- Template changes should maintain Bootstrap 5 compatibility

### Security Considerations
- Always validate user input before SSH operations
- Use `shlex.quote()` for command parameter escaping
- Implement proper error handling for SSH operations
- Log security-relevant events for monitoring
- Never expose passwords in plain text logs

### ⚠️ Known Security Issues (v2.0)
1. **🔴 High Risk - Server Password Storage**: Server passwords stored in plain text in database
   - Location: `models.py:37` - `password = db.Column(db.String(200))`
   - Impact: SSH passwords visible to anyone with database access
   - Recommendation: Implement symmetric encryption (AES) for server passwords

2. **🟡 Medium Risk - CSRF Protection**: Missing CSRF tokens on forms
   - Impact: Vulnerable to cross-site request forgery attacks
   - Recommendation: Add `flask-wtf` CSRFProtect

3. **🟡 Medium Risk - XSS Prevention**: Form inputs not HTML-escaped
   - Impact: Potential script injection through user inputs
   - Recommendation: Use `{{ variable|e }}` in templates or `escape()` in backend

### Testing and Debugging
- Test SSH operations manually before automation
- Use development mode for detailed error messages
- Check operation logs for troubleshooting
- Verify user creation and permissions on target servers
- Test edge cases: network failures, permission denied, etc.

### Error Handling
- Graceful handling of SSH connection failures
- Clear error messages for administrators
- Automatic retry mechanisms where appropriate
- Fallback to manual configuration when automation fails
- Comprehensive logging of all error conditions