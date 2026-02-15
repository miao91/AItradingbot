# Claude Code 重启后快速参考

## 🚀 快速恢复工作

### 1. 确认 GLM-5 已集成

GLM-5 已完全集成到项目中，无需额外操作。

**验证集成**:
```bash
python test_glm5.py
```

**配置 API Key** (如果还没有):
```bash
# 在 .env 文件中添加
ZHIPU_API_KEY=your_api_key_here
```

### 2. 服务端口说明

**⚠️ 重要**: 端口 8000 有旧服务残留

**临时方案**: 使用端口 8001
```bash
# 启动新服务在端口 8001
python -m uvicorn core.api.app:app --host 0.0.0.0 --port 8001 --reload
```

**API 访问**:
- Swagger UI: http://localhost:8001/docs
- 汇率 API: http://localhost:8001/api/v1/external/forex/USDCNH

### 3. 当前项目状态

#### ✅ 已完成
1. GLM-5 模型完全集成
2. 汇率预警系统 (FunHub)
3. 双层感知 UI 布局
4. 路由前缀修复

#### 🔄 进行中
- Task #19: 五维评估模型 (PENDING)
- Task #16: 全球情报研读 (PENDING)
- Task #17: AI 思维链展示 (PENDING)

#### ⚠️ 阻塞问题
- 端口 8000 被旧服务占用
- 需要手动终止 PID 24700, 7428

### 4. 下一步优先级

**高优先级**:
1. 实现全球情报研读模块 (Task #16)
2. 实现五维评估模型 (Task #19)
3. 集成 AI 思维链展示 (Task #17)

**中优先级**:
4. Tushare 实时快讯流 (Task #15)
5. 计算透明化弹窗 (Task #18)

### 5. 关键文件位置

```
# GLM-5 相关
shared/llm/clients.py              # GLM5Client 类
decision/ai_matrix/glm5/client.py  # GLM-5 决策客户端
decision/engine/valuation_tool.py  # 估值引擎 (支持 GLM-5)

# 汇率系统
core/api/v1/external.py            # 汇率 API 端点
docs/showcase/index.html           # 前端汇率显示

# 配置
.env                               # API Keys 配置
docs/GLM5_INTEGRATION.md           # GLM-5 详细文档
docs/PROJECT_STATUS.md             # 完整项目状态
```

### 6. 测试命令速查

```bash
# GLM-5 测试
python test_glm5.py

# 汇率 API 测试
curl http://localhost:8001/api/v1/external/forex/USDCNH

# 查看所有 API 路由
curl http://localhost:8001/openapi.json | python -m json.tool

# 启动所有服务
python run_all.py
```

### 7. 环境变量检查清单

确保 `.env` 包含：
```bash
ZHIPU_API_KEY=your_zhipu_api_key
FUNHUB_API_KEY=d5po719r01qthn8n1m90
TAVILY_API_KEY=your_tavily_api_key
KIMI_API_KEY=your_kimi_api_key
EXECUTION_MODE=manual
```

### 8. 常见问题

**Q: GLM-5 调用失败 (401 错误)**
A: 检查 `.env` 中的 `ZHIPU_API_KEY` 是否正确

**Q: 端口 8000 无法启动**
A: 旧服务残留，使用端口 8001 代替

**Q: 汇率数据不更新**
A: 检查 `FUNHUB_API_KEY` 和网络连接

### 9. 文档导航

- **项目总览**: docs/PROJECT_STATUS.md
- **GLM-5 集成**: docs/GLM5_INTEGRATION.md
- **API 文档**: http://localhost:8001/docs
- **前端控制面板**: docs/showcase/index.html

---

## 📝 继续工作建议

重启 Claude Code 后，建议按以下顺序继续：

1. **首先**: 运行 `python test_glm5.py` 验证环境
2. **然后**: 选择一个高优先级任务开始
3. **参考**: docs/PROJECT_STATUS.md 中的详细任务描述

---

**祝工作顺利！** 🚀
