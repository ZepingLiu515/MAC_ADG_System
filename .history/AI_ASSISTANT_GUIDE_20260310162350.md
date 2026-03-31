# 🤖 AI 辅助开发指南 - 功能逐项完成清单

## 使用方法

此文档用于指导您与 AI 进行迭代式开发。每个功能都有：
- **描述**: 功能的具体需求
- **验收标准**: 如何确认功能完成
- **测试命令**: 如何测试该功能
- **代码位置**: 需要修改的文件
- **预估时间**: 完成该功能需要的时间

---

## 📋 功能开发清单

### 🔴 Critical: 必须完成的核心功能

---

#### ✨ **功能 1: Vision Agent - 自适应图片切片**

**优先级**: 🔴 P0  
**状态**: ⏳ 待实现  
**预估时间**: 1 小时

**描述**:
现在 Vision Agent 只返回整个网页截图。应该实现自适应切片：
- 从浏览器截图中识别作者区域（通常在页面上半部分）
- 将该区域裁剪成独立的图片
- 返回裁剪后的图片供 Vision LLM 使用

**验收标准**:
```python
vision_agent = VisionAgent()
result = vision_agent.process(doi)
# result 应包含:
# - result['text']: 网页文本 ✓
# - result['image_path']: 完整截图 ✓
# - result['author_slice']: 作者区域图片 (新增!)
# - result['author_slice_coords']: 坐标 (x1, y1, x2, y2)
```

**测试命令**:
```bash
# 编写测试脚本 test_vision_slicing.py
python test_vision_slicing.py
# 预期: 成功生成 author_slice 图片
```

**代码位置**:
- 修改: `backend/agents/vision_agent.py`
- 新增方法:
  - `_extract_author_region(pix)`: 裁剪作者区域
  - `_get_region_coordinates(page)`: 获取区域坐标

**实现步骤**:
1. 在 `_capture_webpage` 中添加自适应切片逻辑
2. 使用 PIL/Pillow 的 `crop()` 方法
3. 返回 author_slice 路径和坐标

---

#### ✨ **功能 2: Vision Agent - DeepSeek-VL 集成**

**优先级**: 🔴 P0  
**状态**: ⏳ 待实现  
**预估时间**: 2 小时

**描述**:
现在 Vision Agent 只提取原始文本。应该集成 DeepSeek-VL 大模型识别作者名：
- 调用 DeepSeek-VL API 识别图片中的作者列表
- 识别 * (通讯) 和 # (共同一作) 标记
- 返回结构化的作者列表

**验收标准**:
```python
vision_agent = VisionAgent()
result = vision_agent.process(doi)
# result 应包含:
# - result['text']: 网页文本 (现有)
# - result['image_path']: 截图 (现有)
# - result['authors']: [
#     {
#       'name': 'Zeping Liu',
#       'is_corresponding': True,  # 识别 *
#       'is_co_first': False,      # 识别 #
#       'position': 1
#     },
#     ...
#   ]
```

**测试命令**:
```bash
python -c "
from backend.agents.vision_agent import VisionAgent
va = VisionAgent()
result = va.process('data/pdf_cache/...')
print('Authors:', result.get('authors'))
"
```

**代码位置**:
- 修改: `backend/agents/vision_agent.py`
- 新增方法: `_call_deepseek_vlm(image_path) -> list`
- 修改 `_process_pdf()` 返回结构

**实现步骤**:
1. 读取 `.env` 中的 `DEEPSEEK_API_KEY`
2. 实现 API 调用函数
3. 设计合适的 Prompt
4. 解析返回的 JSON
5. 与现有文本提取集成

**关键 Prompt**:
```
请仔细识别图片中的作者列表。每个作者的名字旁边可能有以下标记：
- * 星号表示通讯作者 (corresponding author)
- # 井号表示共同一作 (co-first author)

请返回 JSON 格式:
{
  "authors": [
    {"name": "Author Name", "is_corresponding": bool, "is_co_first": bool, "position": int}
  ],
  "confidence": 0.95
}
```

---

#### ✨ **功能 3: Judge Agent - Levenshtein 模糊匹配**

**优先级**: 🔴 P0  
**状态**: ⏳ 待实现  
**预估时间**: 1.5 小时

**描述**:
现在 Judge Agent 只支持完全字符串匹配。应该添加模糊匹配来处理：
- "Z.P. Liu" vs "Zeping Liu"
- "Liu Zeping" vs "Zeping Liu" (名字顺序)
- 拼写错误容错

**验收标准**:
```python
judge = JudgeAgent()
# 能匹配以下情况
assert judge._fuzzy_match("Z.P. Liu", "Zeping Liu", threshold=0.7)
assert judge._fuzzy_match("Xiaoming Wang", "X.M. Wang", threshold=0.7)
assert judge._fuzzy_match("John Smith", "Jon Smith", threshold=0.6)
```

**测试命令**:
```bash
python -c "
from backend.agents.judge_agent import JudgeAgent
j = JudgeAgent()
test_cases = [
    ('Z.P. Liu', 'Zeping Liu'),
    ('Xiaoming Wang', 'X.M. Wang'),
    ('John Smith', 'Jon Smith'),
]
for a, b in test_cases:
    result = j._fuzzy_match(a, b, 0.7)
    print(f'{a} <-> {b}: {result}')
"
```

**代码位置**:
- 修改: `backend/agents/judge_agent.py`
- 新增方法: `_fuzzy_match(name1, name2, threshold) -> bool`
- 在 `adjudicate()` 中调用此方法

**实现步骤**:
1. 安装 `difflib` (标准库)
2. 实现 `_fuzzy_match()` 方法
3. 在现有字符串匹配逻辑后调用
4. 设置合适的阈值 (0.7-0.8)

**代码参考**:
```python
from difflib import SequenceMatcher

def _fuzzy_match(self, name1: str, name2: str, threshold: float = 0.7) -> bool:
    """检查两个名字是否足够相似"""
    # 清理：去除空格和标点
    clean1 = name1.lower().replace(" ", "").replace(".", "")
    clean2 = name2.lower().replace(" ", "").replace(".", "")
    
    # 计算相似度
    similarity = SequenceMatcher(None, clean1, clean2).ratio()
    return similarity >= threshold
```

---

#### ✨ **功能 4: Judge Agent - DeepSeek LLM 集成**

**优先级**: 🔴 P0  
**状态**: ⏳ 待实现  
**预估时间**: 2 小时

**描述**:
当模糊匹配和字符串匹配都不确定时，应该调用 LLM 进行推理：
- 输入：论文作者名 + 教师名单
- LLM 判断是否为同一人
- 生成推理链 (Chain of Thought)
- 返回置信度

**验收标准**:
```python
judge = JudgeAgent()
result = judge._llm_match({
    'paper_author': 'Z.P. Liu from Stanford',
    'faculty': 'Zeping Liu from 计算机学院'
})
# result 应包含:
# {
#   'is_match': True/False,
#   'confidence': 0.85,
#   'reasoning': '...'
# }
```

**测试命令**:
```bash
python test_judge_llm.py
```

**代码位置**:
- 修改: `backend/agents/judge_agent.py`
- 新增方法: `_llm_match(paper_author_info, faculty_info) -> dict`
- 在 `adjudicate()` 中作为最后手段调用

**实现步骤**:
1. 使用标准 `requests` 库调用 DeepSeek API
2. 设计 Prompt 让 LLM 进行推理
3. 解析返回结果
4. 返回是否匹配 + 置信度

**关键 Prompt**:
```
你是一个学术文献处理专家。请判断以下两个名字是否代表同一个人：

论文中的作者: {paper_author_name}
论文作者单位: {paper_affiliation}

基准名单中的教师: {faculty_name}
教师单位: {faculty_department}

请考虑以下因素：
1. 名字的拼音相似性
2. 英文缩写习惯 (例: Z.P. Liu vs Zeping Liu)
3. 单位翻译差异
4. 发表时间是否合理

请用以下 JSON 格式回答:
{
  "is_match": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "你的分析"
}
```

---

### 🟡 High Priority: 重要的增强功能

---

#### ✨ **功能 5: Judge Agent - 贝叶斯冲突消解**

**优先级**: 🟡 P1  
**状态**: ⏳ 待实现  
**预估时间**: 2 小时

**描述**:
当存在多个数据源 (API 元数据 vs Vision 提取) 有矛盾时，应该用贝叶斯推理消解冲突：

示例冲突：
- Crossref API 没有识别出通讯作者
- Vision Agent 从 PDF 看到了 * 标记

应该：
- 评估每个数据源的可信度
- 采用可信度更高的结果
- 生成推理链供用户审核

**验收标准**:
```python
judge = JudgeAgent()
conflict = {
    'api_data': {'is_corresponding': False},
    'vision_data': {'is_corresponding': True, 'marker': '*'}
}
result = judge._resolve_conflict(conflict)
# result 应该是:
# {
#   'resolved_value': True,
#   'source': 'vision',
#   'confidence': 0.95,
#   'reasoning_chain': [...]
# }
```

**测试命令**:
```bash
python test_judge_conflict_resolution.py
```

**代码位置**:
- 修改: `backend/agents/judge_agent.py`
- 新增方法: `_resolve_conflict(conflict_dict) -> dict`

**实现思路**:
```
P(correct | vision_marker) > P(correct | api_only)
所以当两者矛盾时，优先采用 vision 的结果
```

---

#### ✨ **功能 6: 前端 - PDF 预览组件**

**优先级**: 🟡 P1  
**状态**: ⏳ 待实现  
**预估时间**: 1.5 小时

**描述**:
在智能提取页面，为每篇论文显示：
- Vision Agent 生成的首页图片
- 标注出识别的作者区域
- 点击可查看完整 PDF

**验收标准**:
```
在 /pages/2_Smart_Extraction.py 页面：
- 结果表格有 "PDF 预览" 列
- 点击可显示图片
- 图片旁有下载 PDF 的链接
```

**测试命令**:
```bash
streamlit run main.py
# 侧边栏选择 Smart Extraction
# 上传包含 DOI 的 Excel
# 检查结果表格是否有预览
```

**代码位置**:
- 修改: `pages/2_Smart_Extraction.py`
- 使用: `frontend/components.py` 中的 `pdf_preview()`

**实现步骤**:
1. 在结果表格中添加图片列
2. 使用 `st.image()` 显示图片
3. 添加下载链接

---

#### ✨ **功能 7: 前端 - 手动审核面板**

**优先级**: 🟡 P1  
**状态**: ⏳ 待实现  
**预估时间**: 3 小时

**描述**:
为疑难匹配（模糊度高的匹配）创建审核界面：
- 显示 Judge Agent 的推理过程
- 允许用户手动修改匹配结果
- 保存用户的修正到数据库

**验收标准**:
```
新建页面: /pages/4_Manual_Review.py
- 显示所有 confidence < 0.8 的记录
- 每条记录显示：
  * 论文信息
  * 论文中的作者名
  * 匹配到的教师
  * 运算过程
  * [修改] 按钮
- 可以改正错误的匹配
```

**测试命令**:
```bash
streamlit run main.py
# 侧边栏选择 Manual Review
# 检查是否显示待审核记录
```

**代码位置**:
- 新建: `pages/4_Manual_Review.py`
- 修改: `database/models.py` 添加 confidence 字段
- 修改: `database/models.py` 添加 is_reviewed 字段

---

### 🟢 Nice to Have: 优化功能

---

#### ✨ **功能 8: 异步处理**

**优先级**: 🟢 P2  
**状态**: ⏳ 待实现  
**预估时间**: 3 小时

**描述**:
当处理 500+ DOI 时，应该支持异步并行处理而不是串行：
- 使用 `asyncio` 或 `concurrent.futures`
- 限制并发数（避免 API 限流）
- 显示实时进度

**验收标准**:
```
处理 100 个 DOI：
- 串行耗时: ~50 秒
- 并行耗时 (workers=5): ~12 秒
```

**代码位置**:
- 修改: `backend/orchestrator.py`

---

#### ✨ **功能 9: 断点续传**

**优先级**: 🟢 P2  
**状态**: ⏳ 待实现  
**预估时间**: 2 小时

**描述**:
当处理大批量时，应支持中途中断后继续：
- 记录处理进度到数据库
- 崩溃重启后从断点继续
- 避免重复处理

**验收标准**:
```
处理 100 个 DOI，在第 50 个时中断：
- 重启后继续从 51 开始
- 不重新处理 1-50
```

**代码位置**:
- 修改: `backend/orchestrator.py`
- 修改: `database/models.py` 添加 process_status

---

## 📊 进度追踪表

| 功能 | 优先级 | 状态 | 完成百分比 | 估计完成日期 |
|-----|--------|------|----------|-----------|
| 1. Vision - 自适应切片 | 🔴 P0 | ⏳ | 0% | - |
| 2. Vision - DeepSeek-VL | 🔴 P0 | ⏳ | 0% | - |
| 3. Judge - Levenshtein | 🔴 P0 | ⏳ | 0% | - |
| 4. Judge - DeepSeek LLM | 🔴 P0 | ⏳ | 0% | - |
| 5. Judge - 贝叶斯推理 | 🟡 P1 | ⏳ | 0% | - |
| 6. 前端 - PDF 预览 | 🟡 P1 | ⏳ | 0% | - |
| 7. 前端 - 审核面板 | 🟡 P1 | ⏳ | 0% | - |
| 8. 异步处理 | 🟢 P2 | ⏳ | 0% | - |
| 9. 断点续传 | 🟢 P2 | ⏳ | 0% | - |

---

## 🚀 如何与 AI 协作

### 对话模板

当您请求 AI 帮助实现某个功能时：

```
你好，我需要完成 MAC-ADG 项目中的功能。

请完成：Vision Agent - 自适应图片切片

要求：
1. 修改 backend/agents/vision_agent.py
2. 新增方法用于识别和裁剪作者region
3. 修改 _process_pdf() 返回 author_slice 路径和坐标

验收标准：
- test_vision_slicing.py 通过
- 生成的图片可在 data/visual_slices/author_* 看到

请直接修改代码，不要只提建议。
```

### AI 会为您做：
1. ✅ 直接修改代码文件
2. ✅ 添加需要的函数和逻辑
3. ✅ 创建相应的测试脚本
4. ✅ 确保与现有代码集成

---

## 📞 常见问题

### Q: 应该按什么顺序实现?
**A**: 按优先级顺序：
1. 功能 1-4 (P0) - 核心能力，1 周内完成
2. 功能 5-7 (P1) - 增强能力，下周完成
3. 功能 8-9 (P2) - 优化能力，可选

### Q: 需要 DeepSeek API Key 吗?
**A**: 
- 功能 1, 3 不需要 (纯本地)
- 功能 2, 4, 5 需要 API Key (可免费试用)

### Q: 每个功能测试需要多久?
**A**: 5-10 分钟，按测试命令执行即可

---

## ✅ 完成清单

使用此清单跟踪进度（可复制到项目中）：

```markdown
# 🎯 MAC-ADG 开发进度

- [ ] 功能 1：Vision - 自适应切片
  - [ ] 代码实现
  - [ ] 单元测试通过
  - [ ] 集成测试通过
  
- [ ] 功能 2：Vision - DeepSeek-VL
  - [ ] 获取 API Key
  - [ ] 代码实现
  - [ ] 单元测试通过
  
- [ ] 功能 3：Judge - Levenshtein
  - [ ] 代码实现
  - [ ] 单元测试通过
  
- [ ] 功能 4：Judge - DeepSeek LLM
  - [ ] 代码实现
  - [ ] 单元测试通过
  - [ ] 集成测试通过（完整流程测试）
  
- [ ] 功能 5-9：高级功能
  ...
```

---

祝您开发顺利！ 🚀
