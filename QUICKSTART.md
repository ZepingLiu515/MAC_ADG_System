# 🚀 快速开始指南

## 📝 系统现状

**整体完成度**: 69% (25/36 个功能)

### ✅ 已完成
- ✅ 数据库设计与初始化 (100%)
- ✅ Scout Agent (100%) - 元数据获取、URL构建
- ✅ Vision Agent (67%) - 浏览器截图、视觉分析
- ✅ Judge Agent (57%) - 基础身份匹配、标记识别
- ✅ Orchestrator (67%) - 流程编排、批量处理
- ✅ 前端 UI (57%) - Streamlit 页面框架

### ⏳ 待实现 (Critical Path)
- ⏳ **3.3.6** - DeepSeek-VL 视觉识别（优先）
- ⏳ **3.4.6** - LLM 驱动的匹配（优先）
- ⏳ **3.4.5** - 模糊匹配算法 (Levenshtein)
- ⏳ **3.6.5, 3.6.6** - PDF 预览、审核面板

---

## 🏃 你可以立即做什么

### 1️⃣ 验证环境 (5 分钟)

```bash
# 进入项目目录
cd MAC_ADG_System

# 运行环境检查
python quick_verify.py
```

**预期输出**:
```
✅ Python 版本: 3.9.x
✅ streamlit
✅ sqlalchemy
✅ pandas
✅ requests
✅ fitz
✅ config.py 加载成功
✅ 数据库连接成功，找到 3 张表
```

---

### 2️⃣ 初始化数据库 (30 秒)

```bash
python force_init_db.py
```

**预期输出**:
```
--- Force Initializing Database ---
Dropped old tables.
[INFO] Database initialized at: .../data/mac_adg.db
✅ SUCCESS: Database tables created successfully!
```

---

### 3️⃣ 运行单元测试 (10 分钟)

#### ✅ Scout Agent 测试
```bash
python test_scout.py
```
**验证**: 能否从 Crossref 获取元数据和下载 PDF

#### ✅ Vision Agent 测试
```bash
python test_vision.py
```
**验证**: 能否从 PDF 提取文本和生成图片快照

#### ✅ Judge Agent 测试
```bash
python test_judge.py
```
**验证**: 能否匹配教师身份并写入数据库

#### ✅ Orchestrator 集成测试
```bash
python test_orchestrator.py
```
**验证**: 能否运行完整的 Scout→Vision→Judge 流水线

#### ✅ 端到端测试
```bash
python test_complete_pipeline.py
```
**验证**: 完整流程从 DOI 到数据库写入

---

### 4️⃣ 启动 Streamlit UI (2 分钟)

```bash
streamlit run main.py
```

**浏览器自动打开**: http://localhost:8501

**可以做的操作**:
- 📂 上传教师名单
- 🤖 批量提取 DOI
- 📊 查看统计报表

---

## 🎯 下一步开发优先级

### 🔴 Phase 4: LLM 集成 (最关键)

这两个功能是系统的核心难点，**必须**依赖 DeepSeek API：

#### **4.1 Vision Agent 增强** - DeepSeek-VL 集成
- **功能**: 从 PDF 图片中智能识别作者列表和特殊标记
- **文件**: `backend/agents/vision_agent.py`
- **优先级**: 🔴 **P0** (高度优先)
- **预估工作量**: 2-3 小时

**实现步骤**:
1. 添加图片切片函数 (定位作者栏)
2. 调用 DeepSeek-VL 识别作者名和标记 (* #)
3. 返回结构化的作者列表

#### **4.2 Judge Agent 增强** - LLM 模糊匹配
- **功能**: 处理"Z.P. Liu" vs "Zeping Liu"这样的模糊匹配
- **文件**: `backend/agents/judge_agent.py`
- **优先级**: 🔴 **P0** (高度优先)
- **预估工作量**: 2-3 小时

**实现步骤**:
1. 集成 Levenshtein 距离算法
2. 实现 LLM Prompt 用于疑难匹配
3. 实现贝叶斯冲突消解逻辑

---

### 🟡 Phase 5: 前端优化 (次优先)

#### **5.1 PDF 预览组件**
- **功能**: 在前端展示 Vision Agent 生成的图片快照
- **文件**: `frontend/pages/2_Smart_Extraction.py`
- **优先级**: 🟡 **P1**
- **预估工作量**: 1-2 小时

#### **5.2 手动审核面板**
- **功能**: 允许用户修改疑难匹配结果
- **文件**: 新建 `frontend/pages/4_Manual_Review.py`
- **优先级**: 🟡 **P1**
- **预估工作量**: 2-3 小时

---

### 🟢 Phase 6: 优化 & 扩展 (可选)

- 异步处理大批量 DOI (500+)
- 断点续传和故障恢复
- 性能监控和日志系统
- 缓存优化 (Redis)

---

## 💡 关键代码模板

### 如何集成 DeepSeek API (Vision Agent)

```python
# 在 backend/agents/vision_agent.py 中添加

def _call_deepseek_vlm(self, image_path: str) -> dict:
    """调用 DeepSeek-VL 识别作者信息"""
    import base64
    import requests
    import os
    
    # 读取图片
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": "deepseek-vl-7b-chat",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_data}"}
                    },
                    {
                        "type": "text",
                        "text": """请识别图片中的作者列表。
                                  注意：名字右上角的 * 代表通讯作者，# 代表共同一作。
                                  返回 JSON 格式: {"authors": [{"name": "...", "is_corresponding": bool, "is_co_first": bool}, ...]}"""
                    }
                ]
            }
        ]
    }
    
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        text = result["choices"][0]["message"]["content"]
        # 解析 JSON 返回
        return json.loads(text)
    else:
        raise Exception(f"DeepSeek API 错误: {response.status_code}")
```

### 如何集成模糊匹配 (Judge Agent)

```python
# 在 backend/agents/judge_agent.py 中添加

from difflib import SequenceMatcher

def _fuzzy_match(self, name1: str, name2: str, threshold: float = 0.7) -> bool:
    """模糊匹配函数"""
    # 移除空格和特殊字符
    clean1 = name1.lower().replace(" ", "").replace(".", "")
    clean2 = name2.lower().replace(" ", "").replace(".", "")
    
    similarity = SequenceMatcher(None, clean1, clean2).ratio()
    return similarity >= threshold
```

---

## 📊 测试检查清单

```markdown
## 快速测试清单

- [ ] python quick_verify.py → 所有检查通过
- [ ] python force_init_db.py → 数据库创建成功
- [ ] python test_scout.py → ✅ Scout Agent 通过
- [ ] python test_vision.py → ✅ Vision Agent 通过  
- [ ] python test_judge.py → ✅ Judge Agent 通过
- [ ] python test_orchestrator.py → ✅ Orchestrator 通过
- [ ] python test_complete_pipeline.py → ✅ 端到端通过
- [ ] streamlit run main.py → UI 成功启动
  - [ ] 教师名单页面可以上传
  - [ ] 智能提取页面可以运行
  - [ ] 统计报表页面显示数据
```

---

## 🔧 故障排除

### 问题: "无法解析导入 streamlit"
**解决**: 
```bash
pip install streamlit
```

### 问题: "数据库连接失败"
**解决**:
```bash
python force_init_db.py
```

### 问题: "网页截图失败 / 403 / 风控拦截"
**说明**: 当前主流程是 WebDriver 截图 → Vision 解析，不依赖 PDF 下载。

**解决**:
- 尝试使用系统 Chrome：`$env:PLAYWRIGHT_CHANNEL="chrome"`
- 开启可视化调试：`$env:PLAYWRIGHT_HEADLESS="0"`
- 若仍 403：这通常是网络出口/IP 信誉问题，需要更换合规出口或使用允许的代理（见开发手册）

### 问题: "DeepSeek API 返回 401"
**解决**: 
```bash
# 检查 API Key
type .env
# 或新建 .env 文件并设置正确的 Key
```

### 问题: "还没导入教师/单位库，测试时论文被跳过"
**说明**: 现在 Judge 在检测到 `Faculty` 表为空时，会进入“测试模式”：不再直接跳过论文，而是把作者落库并把论文标记为 `NEEDS_REVIEW`，方便你验证主链路（作者/单位/通讯/共一）。

**建议配置**（用于“先匹配单位再看作者姓名”）：
```bash
$env:SCHOOL_AFFILIATION_KEYWORDS="四川大学,Sichuan University,West China"
```

---

## 📞 获得帮助

### 常见问题查看
- 查看 [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) 了解详细的测试方法
- 查看 [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) 了解整体规划
- 查看 [docs/MAC_ADG_DEVELOPER_HANDBOOK.md](docs/MAC_ADG_DEVELOPER_HANDBOOK.md) 了解最新架构与运行参数

### 调试技巧
```bash
# 启用详细输出
$env:PYTHONUNBUFFERED="1"

# 查看数据库内容
python -c "
from database.connection import SessionLocal
from database.models import Paper, Faculty
db = SessionLocal()
print(f'Papers: {db.query(Paper).count()}')
print(f'Faculty: {db.query(Faculty).count()}')
"
```

---

## 📈 预期时间表

| 任务 | 时间 | 优先级 |
|-----|------|--------|
| 环境验证 | 5 分钟 | P0 |
| 数据库初始化 | 1 分钟 | P0 |
| 单元测试 | 15-20 分钟 | P0 |
| Streamlit UI 测试 | 10 分钟 | P0 |
| DeepSeek 集成 (Vision) | 2-3 小时 | P0 |
| DeepSeek 集成 (Judge) | 2-3 小时 | P0 |
| 模糊匹配算法 | 1-2 小时 | P1 |
| 前端优化 (PDF 预览、审核) | 3-4 小时 | P1 |
| **总估计** | **12-16 小时** | - |

---

## ✨ 下一步

👉 **立即开始**:
```bash
python quick_verify.py
python force_init_db.py
python test_complete_pipeline.py
streamlit run main.py
```

👉 **想要完全功能**，需要集成 DeepSeek API：
- 获取 API Key: https://platform.deepseek.com/
- 在 `.env` 文件中配置
- 按照上面的代码模板在 Vision 和 Judge Agent 中集成

祝您开发顺利！ 🎉
