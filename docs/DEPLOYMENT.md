# Deployment Guide

This guide provides comprehensive instructions for deploying the Server Management System in various environments.

## 🎯 Deployment Overview

The Server Management System supports multiple deployment scenarios:
- **Development**: Local development with SQLite
- **Production**: Production deployment with PostgreSQL/MySQL
- **Docker**: Containerized deployment
- **Cloud**: Cloud platform deployment (AWS, Azure, GCP)

## 🛠️ Pre-Deployment Checklist

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+ recommended), macOS, or Windows
- **Python**: 3.8 or higher
- **Memory**: Minimum 2GB RAM (4GB+ recommended for production)
- **Storage**: Minimum 10GB available disk space
- **Network**: Outbound SSH access to target servers

### Security Requirements
- **Firewall**: Configure firewall rules for web application access
- **SSL/TLS**: SSL certificate for HTTPS (production environments)
- **SSH Keys**: SSH key pairs for secure server connections (recommended)
- **Database Security**: Secure database credentials and access controls

## 🖥️ Development Deployment

### Local Development Setup

1. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/server-manage.git
   cd server-manage
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   ```bash
   export FLASK_ENV=development
   export FLASK_DEBUG=1
   export SECRET_KEY="your-development-secret-key"
   ```

5. **Initialize Database**
   ```bash
   python -c "from app import create_tables; create_tables()"
   ```

6. **Run Application**
   ```bash
   python app.py
   ```

7. **Access Application**
   - URL: `http://localhost:8080`
   - Default credentials: admin / admin123

### Development Configuration

Create a `.env` file for environment variables:
```env
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=your-development-secret-key-here
DATABASE_URL=sqlite:///instance/database.db
SSH_TIMEOUT=30
MONITOR_INTERVAL=30
```

## 🏢 Production Deployment

### Server Preparation

1. **Update System**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install Python and Dependencies**
   ```bash
   sudo apt install python3 python3-pip python3-venv nginx supervisor -y
   ```

3. **Create Application User**
   ```bash
   sudo useradd -m -s /bin/bash servermanager
   sudo usermod -aG sudo servermanager
   ```

### Application Setup

1. **Deploy Application Code**
   ```bash
   sudo -u servermanager git clone https://github.com/yourusername/server-manage.git /home/servermanager/server-manage
   cd /home/servermanager/server-manage
   ```

2. **Create Virtual Environment**
   ```bash
   sudo -u servermanager python3 -m venv venv
   sudo -u servermanager ./venv/bin/pip install -r requirements.txt
   ```

3. **Production Configuration**
   ```bash
   sudo -u servermanager tee /home/servermanager/server-manage/.env << EOF
   FLASK_ENV=production
   SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
   DATABASE_URL=postgresql://username:password@localhost/servermanager
   SSH_TIMEOUT=60
   MONITOR_INTERVAL=30
   ALLOWED_HOSTS=your-domain.com
   EOF
   ```

### Database Configuration

#### PostgreSQL Setup
1. **Install PostgreSQL**
   ```bash
   sudo apt install postgresql postgresql-contrib -y
   ```

2. **Create Database and User**
   ```bash
   sudo -u postgres createdb servermanager
   sudo -u postgres createuser --interactive servermanager
   sudo -u postgres psql -c "ALTER USER servermanager WITH PASSWORD 'secure-password';"
   sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE servermanager TO servermanager;"
   ```

3. **Update Requirements**
   ```bash
   echo "psycopg2-binary==2.9.5" >> requirements.txt
   sudo -u servermanager ./venv/bin/pip install psycopg2-binary
   ```

#### MySQL Setup (Alternative)
1. **Install MySQL**
   ```bash
   sudo apt install mysql-server -y
   ```

2. **Create Database and User**
   ```sql
   mysql -u root -p
   CREATE DATABASE servermanager;
   CREATE USER 'servermanager'@'localhost' IDENTIFIED BY 'secure-password';
   GRANT ALL PRIVILEGES ON servermanager.* TO 'servermanager'@'localhost';
   FLUSH PRIVILEGES;
   EXIT;
   ```

### Web Server Configuration

#### Nginx Configuration
1. **Create Nginx Configuration**
   ```bash
   sudo tee /etc/nginx/sites-available/servermanager << EOF
   server {
       listen 80;
       server_name your-domain.com www.your-domain.com;
       
       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_set_header Host \$host;
           proxy_set_header X-Real-IP \$remote_addr;
           proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto \$scheme;
           proxy_connect_timeout 60s;
           proxy_send_timeout 60s;
           proxy_read_timeout 60s;
       }
   }
   EOF
   ```

2. **Enable Site**
   ```bash
   sudo ln -s /etc/nginx/sites-available/servermanager /etc/nginx/sites-enabled/
   sudo nginx -t  # Test configuration
   sudo systemctl reload nginx
   ```

#### SSL Configuration with Let's Encrypt
1. **Install Certbot**
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   ```

2. **Obtain SSL Certificate**
   ```bash
   sudo certbot --nginx -d your-domain.com -d www.your-domain.com
   ```

3. **Auto-renewal Setup**
   ```bash
   sudo crontab -e
   # Add: 0 12 * * * /usr/bin/certbot renew --quiet
   ```

### Process Management

#### Supervisor Configuration
1. **Create Supervisor Configuration**
   ```bash
   sudo tee /etc/supervisor/conf.d/servermanager.conf << EOF
   [program:servermanager]
   command=/home/servermanager/server-manage/venv/bin/python app.py
   directory=/home/servermanager/server-manage
   user=servermanager
   autostart=true
   autorestart=true
   redirect_stderr=true
   stdout_logfile=/var/log/servermanager.log
   environment=FLASK_ENV=production
   EOF
   ```

2. **Start Services**
   ```bash
   sudo supervisorctl reread
   sudo supervisorctl update
   sudo supervisorctl start servermanager
   ```

## 🐳 Docker Deployment

### Docker Configuration

1. **Create Dockerfile**
   ```dockerfile
   FROM python:3.9-slim

   # Set working directory
   WORKDIR /app

   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       openssh-client \
       && rm -rf /var/lib/apt/lists/*

   # Copy requirements and install Python dependencies
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   # Copy application code
   COPY . .

   # Create non-root user
   RUN useradd -m -u 1000 servermanager && chown -R servermanager:servermanager /app
   USER servermanager

   # Expose port
   EXPOSE 8080

   # Health check
   HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
       CMD curl -f http://localhost:8080/ || exit 1

   # Start application
   CMD ["python", "app.py"]
   ```

2. **Create Docker Compose**
   ```yaml
   version: '3.8'

   services:
     web:
       build: .
       ports:
         - "8080:8080"
       environment:
         - FLASK_ENV=production
         - SECRET_KEY=${SECRET_KEY}
         - DATABASE_URL=postgresql://servermanager:${DB_PASSWORD}@db:5432/servermanager
       depends_on:
         - db
       volumes:
         - ./logs:/app/logs
         - ./instance:/app/instance
       restart: unless-stopped

     db:
       image: postgres:13
       environment:
         - POSTGRES_DB=servermanager
         - POSTGRES_USER=servermanager
         - POSTGRES_PASSWORD=${DB_PASSWORD}
       volumes:
         - postgres_data:/var/lib/postgresql/data
       restart: unless-stopped

     nginx:
       image: nginx:alpine
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - ./nginx.conf:/etc/nginx/nginx.conf
         - ./ssl:/etc/nginx/ssl
       depends_on:
         - web
       restart: unless-stopped

   volumes:
     postgres_data:
   ```

3. **Environment File**
   ```bash
   tee .env << EOF
   SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
   DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
   EOF
   ```

4. **Deploy with Docker Compose**
   ```bash
   docker-compose up -d
   ```

## ☁️ Cloud Deployment

### AWS Deployment

#### EC2 Instance Setup
1. **Launch EC2 Instance**
   - Instance type: t3.medium (minimum)
   - OS: Ubuntu 20.04 LTS
   - Security group: Allow HTTP (80), HTTPS (443), SSH (22)

2. **Connect and Setup**
   ```bash
   ssh -i your-key.pem ubuntu@your-ec2-instance
   # Follow production deployment steps
   ```

#### RDS Database Setup
1. **Create RDS Instance**
   ```bash
   aws rds create-db-instance \
       --db-instance-identifier servermanager-db \
       --db-instance-class db.t3.micro \
       --engine postgres \
       --master-username servermanager \
       --master-user-password your-secure-password \
       --allocated-storage 20 \
       --vpc-security-group-ids sg-xxxxxxxxx
   ```

2. **Update Database URL**
   ```env
   DATABASE_URL=postgresql://servermanager:password@your-rds-endpoint:5432/servermanager
   ```

### Azure Deployment

#### App Service Deployment
1. **Create Resource Group**
   ```bash
   az group create --name servermanager-rg --location eastus
   ```

2. **Create App Service Plan**
   ```bash
   az appservice plan create \
       --name servermanager-plan \
       --resource-group servermanager-rg \
       --sku B1 \
       --is-linux
   ```

3. **Deploy Web App**
   ```bash
   az webapp create \
       --resource-group servermanager-rg \
       --plan servermanager-plan \
       --name servermanager-app \
       --runtime "PYTHON|3.9"
   ```

### Google Cloud Platform

#### App Engine Deployment
1. **Create app.yaml**
   ```yaml
   runtime: python39

   env_variables:
     FLASK_ENV: production
     SECRET_KEY: your-secret-key
     DATABASE_URL: your-database-url

   automatic_scaling:
     min_instances: 1
     max_instances: 10
   ```

2. **Deploy Application**
   ```bash
   gcloud app deploy
   ```

## 🔧 Post-Deployment Configuration

### Initial Setup
1. **Access Application**
   - Navigate to your domain/IP address
   - Login with default credentials (admin/admin123)
   - **Immediately change default password**

2. **Add First Server**
   - Go to "管理" → "服务器管理"
   - Add your first server for monitoring
   - Test SSH connection

3. **Configure Permissions**
   - Review default permission types
   - Customize as needed for your environment

### Monitoring Setup
1. **Log Monitoring**
   ```bash
   # Setup log rotation
   sudo tee /etc/logrotate.d/servermanager << EOF
   /var/log/servermanager.log {
       daily
       missingok
       rotate 30
       compress
       notifempty
       copytruncate
   }
   EOF
   ```

2. **System Monitoring**
   - Setup monitoring for CPU, memory, disk usage
   - Configure alerts for application failures
   - Monitor database performance

### Backup Configuration
1. **Database Backup**
   ```bash
   # Create backup script
   sudo tee /usr/local/bin/backup-servermanager.sh << 'EOF'
   #!/bin/bash
   DATE=$(date +%Y%m%d_%H%M%S)
   pg_dump servermanager > /backup/servermanager_$DATE.sql
   find /backup -name "servermanager_*.sql" -mtime +7 -delete
   EOF
   sudo chmod +x /usr/local/bin/backup-servermanager.sh
   
   # Schedule backup
   sudo crontab -e
   # Add: 0 2 * * * /usr/local/bin/backup-servermanager.sh
   ```

### Security Hardening
1. **Firewall Configuration**
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw --force enable
   ```

2. **SSH Security**
   ```bash
   # Disable password authentication
   sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
   sudo systemctl restart ssh
   ```

3. **Application Security**
   - Enable CSRF protection
   - Implement rate limiting
   - Configure secure headers
   - Setup intrusion detection

## 🔍 Troubleshooting

### Common Issues
1. **Application Won't Start**
   - Check supervisor logs: `sudo tail -f /var/log/servermanager.log`
   - Verify environment variables
   - Check database connectivity

2. **SSH Connection Failures**
   - Verify SSH keys and permissions
   - Check network connectivity
   - Review firewall rules

3. **Database Connection Issues**
   - Verify database credentials
   - Check database service status
   - Review connection string format

### Performance Optimization
1. **Database Optimization**
   - Create appropriate indexes
   - Configure connection pooling
   - Monitor query performance

2. **Application Tuning**
   - Adjust SSH timeout settings
   - Configure monitoring intervals
   - Optimize static file serving

## 📊 Monitoring and Maintenance

### Health Checks
- Application endpoint monitoring
- Database connectivity checks
- SSH server accessibility tests
- SSL certificate expiration monitoring

### Regular Maintenance
- Security updates and patches
- Database maintenance and optimization
- Log file cleanup and archival
- Performance monitoring and tuning

### Scaling Considerations
- Load balancer configuration
- Database scaling options
- Application server scaling
- Monitoring infrastructure scaling