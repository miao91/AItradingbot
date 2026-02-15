# AI TradeBot 展示页面部署指南

本页面是一个独立的静态HTML页面，可以部署到任何静态网站托管服务。

## 📍 文件位置

```
docs/showcase/index.html
```

## 🚀 部署方式

### 方式一：GitHub Pages（推荐，免费）

1. **将项目推送到GitHub**
   ```bash
   git init
   git add docs/showcase/index.html
   git commit -m "Add showcase page"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/aitradebot.git
   git push -u origin main
   ```

2. **启用GitHub Pages**
   - 进入仓库的 Settings → Pages
   - Source 选择: Deploy from a branch
   - Branch 选择: main
   - Folder 选择: /docs
   - 点击 Save

3. **访问页面**
   ```
   https://YOUR_USERNAME.github.io/aitradebot/
   ```

### 方式二：Vercel（推荐，快速）

1. **安装Vercel CLI**
   ```bash
   npm install -g vercel
   ```

2. **部署**
   ```bash
   cd docs/showcase
   vercel
   ```

3. **完成**
   - Vercel会给你一个 `.vercel.app` 域名
   - 可以在Vercel控制台添加自定义域名

### 方式三：Netlify（拖拽部署）

1. 访问 [Netlify Drop](https://app.netlify.com/drop)
2. 将 `docs/showcase/` 文件夹拖入页面
3. 等待部署完成

### 方式四：直接本地预览

```bash
# 使用Python启动简单服务器
cd docs/showcase
python -m http.server 8080

# 访问 http://localhost:8080
```

## 🔗 链接到 myrwa.ai

### 选项1: 等待RWA交易功能上线

myrwa.ai 的"RWA交易"功能即将上线，届时可以：
- 将AI TradeBot作为交易工具提交到平台
- 在平台的项目展示区展示

### 选项2: 独立页面 + 平台链接

1. 将展示页面部署到上述任一平台
2. 在myrwa.ai候补名单中说明你的项目
3. 提供部署后的页面链接

### 选项3: 嵌入iframe

如果myrwa.ai支持iframe嵌入，可以使用：

```html
<iframe
  src="https://your-deployed-url.com"
  width="100%"
  height="800"
  frameborder="0">
</iframe>
```

## 🎨 自定义页面

你可以修改 `index.html` 中的以下内容：

### 更改GitHub链接
搜索并替换：
```html
<a href="https://github.com">GitHub</a>
```
改为你的实际仓库地址

### 更改联系方式
在footer部分修改：
```html
<a href="#">联系我们</a>
```

### 添加实际截图
在页面中添加：
```html
<div class="screenshot-section">
  <img src="your-screenshot.png" alt="AI TradeBot Dashboard">
</div>
```

## 📊 添加分析统计

### Google Analytics

在 `</head>` 前添加：
```html
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

## 🔐 自定义域名

### 在Vercel上设置
1. 进入项目设置 → Domains
2. 添加你的域名
3. 按提示配置DNS记录

### 在Netlify上设置
1. 进入 Domain settings
2. Add custom domain
3. 配置DNS

## 📱 预览

页面特性：
- ✅ 完全响应式设计
- ✅ 移动端友好
- ✅ 无需构建，纯HTML
- ✅ 加载速度快
- ✅ SEO友好

## 🎯 下一步

1. 部署展示页面
2. 将链接添加到：
   - GitHub README
   - myrwa.ai 候补申请
   - 社交媒体简介

3. 持续更新页面内容，展示项目进展

---

**需要帮助？** 请查看：
- [GitHub Pages文档](https://docs.github.com/pages)
- [Vercel文档](https://vercel.com/docs)
- [Netlify文档](https://docs.netlify.com/)
