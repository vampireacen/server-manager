# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive Flask-based server management system (服务器管理系统) for monitoring Linux servers and managing user access permissions with automated server-side user provisioning. The application provides real-time server monitoring, batch-based permission request system, admin approval workflows, automatic user creation and permission configuration on target servers, and comprehensive account management features.

**Development Guidelines**

- 始终使用中文回答

**Latest Updates (v3.3 - Super Admin Role & UI Enhancements):**
- 🆕 **Super Administrator Role System**: Complete three-tier role management system
  - **Super Admin**: Full system control with user role management capabilities
  - **Admin**: All management functions except role modification
  - **User**: Basic application and account management functions
  - Role-based UI rendering with proper permission controls
- 🆕 **Enhanced Role Management**: Advanced user role management interface
  - Only super admins can promote/demote user roles
  - Role-specific deletion permissions (admins can only delete regular users)
  - Comprehensive role management modal with three-tier selection
- 🆕 **Server Username Display Fix**: Corrected server account name display
  - Fixed user interface to show actual server usernames instead of system usernames
  - Proper server account name handling in admin management interface
  - Consistent display of modified server usernames across all user interfaces
- 🆕 **UI & Navigation Improvements**: Enhanced user experience
  - Correct role badges in navigation (Super Admin, Admin, User)
  - Fixed admin review interface to hide application IDs in confirmation modals
  - Improved permission display with reviewer information for admins

[... rest of the existing content remains unchanged ...]