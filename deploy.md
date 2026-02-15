# AI TradeBot - 部署手册

## 目录

1. [系统要求](#系统要求)
2. [本地开发环境部署](#本地开发环境部署)
3. [生产环境部署](#生产环境部署)
4. [网站集成配置](#网站集成配置)
5. [PM2 进程管理](#pm2-进程管理)
6. [Nginx 反向代理配置](#nginx-反向代理配置)
7. [HTTPS 证书配置](#https-证书配置)
8. [故障排查](#故障排查)

---

## 系统要求

### 硬件要求
- CPU: 2核心及以上
- 内存: 2GB 及以上
- 硬盘: 10GB 及以上

### 软件要求
- 操作系统: Linux (推荐 Ubuntu 20.04+ 或 CentOS 7+)
- Python: 3.10+
- Node.js: 16+ (可选，用于前端集成)

---

## 本地开发环境部署

### 1. 克隆项目

```bash
git clone <your-repo-url> AItradebot
cd AItradebot
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
# venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
nano .env  # 编辑配置
```

必需配置:
```bash
DATABASE_URL=sqlite:///data/database/aitradebot.db
EXECUTION_MODE=manual
```

可选配置:
```bash
KIMI_API_KEY=sk-xxxx
ZHIPUAI_API_KEY=xxxx
MINIMAX_API_KEY=xxxx
TAVILY_API_KEY=tvly-xxxx
TUSHARE_TOKEN=xxxx
```

### 5. 初始化数据库

```bash
python scripts/init_db.py init
```

### 6. 启动服务

```bash
# 方法一：使用一键启动脚本
python run_all.py

# 方法二：分别启动
# 终端1
python -m uvicorn core.api.app:app --reload --port 8000

# 终端2
streamlit run ui/app.py --server.port 8501
```

### 7. 验证服务

访问以下地址验证：

- API 文档: http://localhost:8000/docs
- 公共接口: http://localhost:8000/api/v1/public/active_events
- 作战中心: http://localhost:8501

---

## 生产环境部署

### 方案 A: 传统 VPS 部署

#### 1. 服务器购买推荐

- 阿里云: ECS 共享实例 s6 (2核4GB)
- 腾讯云: 轻量应用服务器 2核4GB
- AWS: EC2 t3.medium (2核4GB)

#### 2. 系统初始化 (Ubuntu)

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 3.10
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip -y

# 安装必要的系统依赖
sudo apt install git nginx sqlite3 -y

# 安装 Node.js (可选，用于前端集成)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo E="
NODESOURCE_KEY=ECCDF47E6A3AF8BC9D5841CBE0F39D4B8929292 \
NODE_MAJOR=18 && \
sudo echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_18.x" \
    | sudo tee /etc/apt/sources.list.d/nodesource.list
sudo apt install nodejs -y
```

#### 3. 部署代码

```bash
# 创建项目目录
sudo mkdir -p /opt/aitradebot
sudo chown $USER:$USER /opt/aitradebot

# 克隆或上传代码
cd /opt/aitradebot
git clone <your-repo-url> .  # 注意最后的点
# 或使用 scp/rsync 上传本地代码

# 创建虚拟环境
python3.10 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装生产依赖
pip install gunicorn python-dotenv
```

#### 4. 配置环境

```bash
nano .env
```

生产环境配置:
```bash
DATABASE_URL=sqlite:///data/database/aitradebot.db
EXECUTION_MODE=manual  # 生产环境建议使用 manual

# AI API 密钥
KIMI_API_KEY=xxxx
ZHIPUAI_API_KEY=xxxx
MINIMAX_API_KEY=xxxx
TAVILY_API_KEY=xxxx
TUSHARE_TOKEN=xxxx
```

#### 5. 配置 CORS (重要!)

编辑 `core/api/app.py`，确保包含你的域名:

```python
allowed_origins = [
    "https://www.myrwaai.com",
    "https://myrwaai.com",
]
```

#### 6. 测试启动

```bash
# 测试 API
python -m uvicorn core.api.app:app --host 0.0.0.0 --port 8000

# 访问 http://your-server-ip:8000/docs 测试
```

---

## 网站集成配置

### 方式一：直接嵌入 HTML

将 `docs/web_widget.js` 中的 JavaScript 代码复制到你的网站。

**步骤：**

1. 下载 `ai-tradebot-widget.js` 并上传到网站服务器
2. 在 HTML 中引入:

```html
<!DOCTYPE html>
<html>
<head>
    <title>我的交易网站</title>
    <script src="/path/to/ai-tradebot-widget.js"></script>
</head>
<body>
    <h1>AI 交易动态</h1>
    <div id="ai-tradebot-wall"></div>
</body>
</html>
```

3. 修改 widget 中的 API 地址:

```javascript
const CONFIG = {
    API_BASE_URL: 'https://your-api-server.com',  // 修改为你的服务器地址
    ...
};
```

### 方式二：API 调用

如果你使用 JavaScript 框架（React/Vue），可以直接调用 API：

```javascript
// 获取活跃事件
async function fetchAITradeEvents() {
    const response = await fetch('https://your-api-server.com/api/v1/public/active_events');
    const data = await response.json();

    // 渲染数据到页面
    renderEvents(data.events);
}

// 定时刷新 (每30秒)
setInterval(fetchAITradeEvents, 30000);
```

---

## PM2 进程管理

PM2 是 Node.js 进程管理器，非常适合保持 Python 服务永久运行。

### 1. 安装 PM2

```bash
npm install -g pm2
```

### 2. 创建 PM2 配置文件

创建 `ecosystem.config.json`:

```json
{
  "apps": [
    {
      "name": "ai-tradebot-api",
      "script": "python -m uvicorn core.api.app:app --host 0.0.0.0 --port 8000",
      "cwd": "/opt/aitradebot",
      "interpreter": "/opt/aitradebot/venv/bin/python3.10",
      "instances": 1,
      "exec_mode": "fork",
      "env": {
        "DATABASE_URL": "sqlite:///data/database/aitradebot.db",
        "EXECUTION_MODE": "manual"
      },
      "error_file": "logs/api-error.log",
      "out_file": "logs/api-out.log",
      "log_date_format": "YYYY-MM-DD HH:mm:ss",
      "merge_logs": true,
      "autorestart": true,
      "max_restarts": 10,
      "restart_delay": 10000
    },
    {
      "name": "ai-tradebot-ui",
      "script": "streamlit run ui/app.py --server.port 8501",
      "cwd": "/opt/aitradebot",
      "interpreter": "/opt/aitradebot/venv/bin/python3.10",
      "instances": 1,
      "exec_mode": "fork",
      "env": {
        "PYTHONPATH": "/opt/aitradebot"
      },
      "error_file": "logs/ui-error.log",
      "out_file": "logs/ui-out.log",
      "log_date_format": "YYYY-MM-DD HH:mm:ss",
      "merge_logs": true,
      "autorestart": true,
      "max_restarts": 5,
      "restart_delay": 10000
    }
  ]
}
```

### 3. 创建启动脚本

创建 `start.sh`:

```bash
#!/bin/bash
cd /opt/aitradebot
source venv/bin/activate

# 启动服务
pm2 restart ecosystem.config.json
pm2 save
pm2 startup
```

```bash
chmod +x start.sh
```

### 4. PM2 常用命令

```bash
# 启动所有服务
pm2 start ecosystem.config.json

# 停止所有服务
pm2 stop ecosystem.config.json

# 重启所有服务
pm2 restart ecosystem.config.json

# 查看状态
pm2 status

# 查看日志
pm2 logs ai-tradebot-api
pm2 logs ai-tradebot-ui

# 开机自启动
pm2 startup
pm2 save
```

### 5. 监控和告警

```bash
# 监控
pm2 monit

# 安装监控面板 (可选)
pm2 install pm2-logrotate
```

---

## Nginx 反向代理配置

### 1. 安装 Nginx

```bash
sudo apt install nginx -y
```

### 2. 创建配置文件

创建 `/etc/nginx/sites-available/aitradebot`:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 修改为你的域名

    # API 服务
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持 (如果需要)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 静态文件缓存 (可选)
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        proxy_pass http://127.0.0.1:8000;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 3. 启用配置

```bash
sudo ln -s /etc/nginx/sites-available/aitradebot /etc/nginx/sites-enabled/
sudo nginx -t  # 测试配置
sudo systemctl restart nginx
```

---

## HTTPS 证书配置

### 使用 Let's Encrypt (免费)

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx -y

# 获取证书
sudo certbot --nginx -d your-domain.com

# Certbot 会自动修改 Nginx 配置并重启服务
```

### 配置自动续期

```bash
# 测试续期
sudo certbot renew --dry-run

# Certbot 会自动添加 cron 任务进行自动续期
sudo systemctl status certbot.timer
```

---

## 完整部署清单

### 部署前检查

- [ ] 服务器已购买并可访问
- [ ] 域名已解析到服务器 IP
- [ ] Python 3.10+ 已安装
- [ ] Git 已安装
- [ ] .env 配置文件已创建

### 部署步骤

1. **系统准备**
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3.10 python3.10-venv python3-pip git nginx sqlite3
   ```

2. **项目部署**
   ```bash
   cd /opt
   sudo git clone <repo> AItradebot
   cd AItradebot
   python3.10 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **配置环境**
   ```bash
   cp .env.example .env
   nano .env  # 编辑配置
   python scripts/init_db.py init
   ```

4. **配置 PM2**
   ```bash
   npm install -g pm2
   pm2 start ecosystem.config.json
   pm2 save
   pm2 startup
   ```

5. **配置 Nginx**
   ```bash
   sudo nano /etc/nginx/sites-available/aitradebot
   sudo ln -s /etc/nginx/sites-available/aitradebot /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

6. **配置 HTTPS**
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

7. **验证部署**
   - 访问 https://your-domain.com/api/v1/public/active_events
   - 访问 https://your-domain.com/docs
   - 检查数据是否正常返回

---

## 监控和维护

### 日志查看

```bash
# PM2 日志
pm2 logs ai-tradebot-api --lines 100
pm2 logs ai-tradebot-ui --lines 100

# 应用日志
tail -f logs/api-out.log
tail -f logs/api-error.log
```

### 数据库备份

```bash
# 创建备份脚本
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp data/database/aitradebot.db backups/aitradebot_$DATE.db
# 保留最近 30 天的备份
find backups/ -name "aitradebot_*.db" -mtime +30 -delete
EOF

chmod +x backup.sh

# 添加到 crontab
crontab -e
# 每天凌晨 3 点备份
0 3 * * * /opt/aitradebot/backup.sh
```

### 更新部署

```bash
cd /opt/aitradebot
git pull
source venv/bin/activate
pip install -r requirements.txt

# 重启服务
pm2 restart ecosystem.config.json
```

---

## 安全加固

### 1. 防火墙配置

```bash
# 只开放必要端口
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

### 2. 禁止 root 远程登录

```bash
sudo nano /etc/ssh/sshd_config
# 设置:
# PermitRootLogin no
sudo systemctl restart sshd
```

### 3. 配置 fail2ban

```bash
sudo apt install fail2ban -y
```

---

## 故障排查

### 问题 1: API 返回 404

**原因**: URL 路径不正确

**解决**:
- 检查 URL 是否为 `/api/v1/public/active_events`
- 确认 FastAPI 正在运行
- 检查 Nginx 配置

### 问题 2: CORS 错误

**原因**: 域名未在允许列表中

**解决**:
- 编辑 `core/api/app.py` 中的 `allowed_origins`
- 添加你的域名到列表
- 重启 FastAPI 服务

### 问题 3: 数据无法更新

**原因**: 数据库文件权限问题

**解决**:
```bash
sudo chown -R $USER:$USER /opt/aitradebot/data
sudo chmod -R 755 /opt/aitradebot/data
```

### 问题 4: 服务自动重启

**原因**: 内存不足或应用崩溃

**解决**:
- 检查 PM2 日志: `pm2 logs ai-tradebot-api --lines 50`
- 检查系统内存: `free -h`
- 增加服务器内存或优化代码

### 问题 5: 证书续期失败

**解决**:
```bash
sudo certbot renew --force-renewal
```

---

## 性能优化

### 1. 数据库优化

```sql
-- 定期 VACUUM (清理数据库)
VACUUM;

-- 重建索引 (偶尔执行)
REINDEX;
```

### 2. 日志轮转

```bash
# 配置 logrotate
sudo nano /etc/logrotate.d/aitradebot

/opt/aitradebot/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
    }
}
```

---

## 联系支持

如有问题，请查看：

- API 文档: `http://your-domain.com/docs`
- GitHub Issues: `<your-repo>/issues`
- 日志文件: `/opt/aitradebot/logs/`

---

## 更新日志

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0.0 | 2024-02-11 | 初始版本，支持手动确认模式 + 网站集成 |

---

**部署完成后，请访问 https://www.myrwaai.com 查看 AI 交易实时展示墙效果。**
