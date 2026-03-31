# 📚 MAC-ADG 文档导航索引

**最后更新**: 2026年3月10日  
**文档版本**: 1.0 (完整版)

---

## 快速导航

### 🎯 我需要...

#### 了解系统全貌
→ 阅读 **[ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md)**
- 全局架构图 (ASCII画)
- 7层分解（配置→数据库→代理→编排→工具→前端）
- 数据流向完整演示
- 推荐时间: 20-30分钟

#### 日常开发参考
→ 阅读 **[DEVELOPER_QUICK_GUIDE.md](DEVELOPER_QUICK_GUIDE.md)**
- "我想要..."快速导航 (14个常见场景)
- 常用命令和代码片段
- 常见问题排查
- 推荐时间: 5-10分钟 (查阅式)

#### 查询API接口
→ 阅读 **[INTERFACE_REFERENCE.md](INTERFACE_REFERENCE.md)**
- Agent类标准接口
- Orchestrator方法签名
- 数据库模型CRUD
- 工具函数参考
- 推荐时间: 2-5分钟 (速查式)

#### 代码审查总结
→ 阅读 **[CODE_REVIEW_REPORT.md](CODE_REVIEW_REPORT.md)**
- 系统评分 (4.3/5)
- 优势与警告
- 生产就绪清单
- 改进建议优先级
- 推荐时间: 15-20分钟

#### 了解当前进度
→ 查看 **[COMPLETION_REPORT.md](COMPLETION_REPORT.md)** (原有)

#### 快速验证环境
→ 运行 `python quick_verify.py`

---

## 文档全景

```
MAC-ADG 项目文档
│
├─ 🏗️  架构与设计
│  ├─ ARCHITECTURE_MAP.md           📋 (650行) ⭐⭐⭐ 必读
│  ├─ INTERFACE_REFERENCE.md        📋 (400行) ⭐⭐⭐ 必查
│  └─ CODE_REVIEW_REPORT.md         📋 (350行) ⭐⭐ 推荐
│
├─ 👨‍💻 开发指南
│  ├─ DEVELOPER_QUICK_GUIDE.md      📋 (550行) ⭐⭐⭐ 常用
│  ├─ QUICKSTART.md                 📋 (原有) ⭐⭐ 入门
│  └─ TESTING_GUIDE.md              📋 (原有) ⭐ 测试
│
├─ 📊 项目管理
│  ├─ PROJECT_STATUS.md             📋 (原有) 
│  ├─ DEVELOPMENT_ROADMAP.md        📋 (原有)
│  ├─ COMPLETION_REPORT.md          📋 (原有)
│  └─ AI_ASSISTANT_GUIDE.md         📋 (原有)
│
└─ 💾 源代码文件
   ├─ config.py                     🐍 全局配置
   ├─ main.py                       🐍 Streamlit入口
   ├─ database/
   │  ├─ models.py                  🐍 数据模型
   │  └─ connection.py              🐍 DB连接
   ├─ backend/
   │  ├─ orchestrator.py            🐍 流程编排
   │  ├─ agents/
   │  │  ├─ scout_agent.py          🐍 元数据获取
   │  │  ├─ vision_agent.py         🐍 浏览器+截图
   │  │  └─ judge_agent.py          🐍 身份匹配
   │  └─ utils/
   │     ├─ pdf_loader.py           🐍 文件管理
   │     └─ excel_parser.py         🐍 Excel解析
   ├─ frontend/
   │  ├─ components.py              🐍 UI组件库
   │  └─ pages/
   └─ pages/
      ├─ 1_Data_Management.py       🐍 数据管理
      ├─ 2_Smart_Extraction.py      🐍 ⭐ 主工作页面
      └─ 3_Analytics_Reports.py     🐍 报表分析
```

---

## 文档使用地图

### 按用户角色

#### 🔵 系统架构师
1. 阅读 ARCHITECTURE_MAP.md (全景了解)
2. 查看 CODE_REVIEW_REPORT.md (设计评价)
3. 参考 INTERFACE_REFERENCE.md (接口规范)

#### 🟢 后端开发者
1. 快速阅读 ARCHITECTURE_MAP.md 的"代理层"部分
2. 主要参考 DEVELOPER_QUICK_GUIDE.md
3. 常查 INTERFACE_REFERENCE.md 的"Agent接口"部分
4. 调用代码时查看相应.py文件的docstring

#### 🟠 前端开发者
1. 快速阅读 ARCHITECTURE_MAP.md 的"前端层"部分
2. 主要参考 DEVELOPER_QUICK_GUIDE.md 的"Streamlit调用"部分
3. 查看 INTERFACE_REFERENCE.md 的"Streamlit UI接口"部分

#### 🔴 QA/测试人员
1. 阅读 CODE_REVIEW_REPORT.md 了解已知问题
2. 参考 TESTING_GUIDE.md 运行测试
3. 查看 DEVELOPER_QUICK_GUIDE.md 的"常见问题排查"部分

#### 🟣 新评审员
1. 优先读 CODE_REVIEW_REPORT.md (快速了解状态)
2. 深入读 ARCHITECTURE_MAP.md (全面理解)
3. 使用 INTERFACE_REFERENCE.md (验证实现)

---

## 文档关键章节速查

### ARCHITECTURE_MAP.md
| 章节 | 行数 | 用途 |
|------|------|------|
| 全局架构 | 15-40 | 系统全景 |
| Config配置层 | 70-100 | 配置管理 |
| 数据库层 | 100-250 | DB设计 |
| Scout Agent | 250-320 | 元数据获取 |
| Vision Agent | 320-380 | 浏览器自动化 |
| Judge Agent | 380-440 | 身份匹配 |
| Orchestrator | 440-490 | 流程编排 |
| 实现约束清单 | 550-650 | 规范约定 |

### DEVELOPER_QUICK_GUIDE.md
| 章节 | 行数 | 用途 |
|------|------|------|
| 快速导航 | 15-120 | 常见任务答案 |
| 常用命令 | 120-160 | 终端命令 |
| 状态参考 | 160-220 | 状态转移 |
| 问题排查 | 220-350 | 5个Q&A |
| 性能优化 | 350-400 | 优化建议 |
| 代码片段库 | 400-500 | copy-paste代码 |

### INTERFACE_REFERENCE.md
| 章节 | 行数 | 用途 |
|------|------|------|
| Agent接口 | 15-150 | Scout/Vision/Judge |
| Orchestrator | 150-200 | 编排器方法 |
| 数据库模型 | 200-300 | Faculty/Paper/Author CRUD |
| 工具函数 | 300-350 | pdf_loader/excel_parser |
| Streamlit UI | 350-380 | 文件上传/调用 |
| 诊断与错误 | 380-450 | 问题排查 |

### CODE_REVIEW_REPORT.md
| 章节 | 行数 | 用途 |
|------|------|------|
| 执行摘要 | 15-50 | 快速评分 |
| 架构评查 | 50-120 | 设计优缺点 |
| 模块评查 | 120-250 | 逐层评价 |
| 关键发现 | 300-350 | 优势/警告/问题 |
| 生产清单 | 350-400 | 发布前检查 |
| 改进优先级 | 400-450 | P0/P1/P2排序 |

---

## 按场景快速查询

### 场景1: "我要添加新的Agent行为"
1. **设计参考**: ARCHITECTURE_MAP.md → "代理层" (选择相似的代理参考)
2. **接口规范**: INTERFACE_REFERENCE.md → "Agent类标准接口"
3. **集成位置**: ARCHITECTURE_MAP.md → "编排层" (修改Orchestrator)
4. **代码样板**: DEVELOPER_QUICK_GUIDE.md → "如何添加新的Agent类型"

### 场景2: "性能太慢，哪里能优化"
1. **瓶颈分析**: CODE_REVIEW_REPORT.md → "性能评查" (4/5=改进空间大)
2. **优化建议**: DEVELOPER_QUICK_GUIDE.md → "性能优化建议"
3. **实现参考**: DEVELOPER_QUICK_GUIDE.md → "快速优化"

### 场景3: "某个功能有bug怎么调试"
1. **问题排查**: DEVELOPER_QUICK_GUIDE.md → "常见问题排查" (Q&A)
2. **接口查证**: INTERFACE_REFERENCE.md → "边界检查清单"
3. **测试验证**: terminal运行 `python test_*.py`

### 场景4: "代码审查发现问题，怎么修复"
1. **优先级确认**: CODE_REVIEW_REPORT.md → "改进建议优先级"
2. **实现指南**: ARCHITECTURE_MAP.md → 相应模块部分 + CODE_REVIEW_REPORT.md → "具体改进建议"

### 场景5: "新成员入职，从哪开始学"
1. **快速入门** (5分钟): QUICKSTART.md
2. **架构全景** (30分钟): ARCHITECTURE_MAP.md 前200行
3. **开发参考** (日常用): DEVELOPER_QUICK_GUIDE.md (收藏)
4. **深入学习** (需要时): 其他文档 + 源代码

### 场景6: "要发版前，系统状态如何"
1. **整体评分**: CODE_REVIEW_REPORT.md → "执行摘要" (4.3/5)
2. **生产清单**: CODE_REVIEW_REPORT.md → "生产就绪清单"
3. **已知问题**: CODE_REVIEW_REPORT.md → "关键发现"

---

## 文档更新策略

**维护频率**:
- 每月一次 (定期同步代码变化)
- 新功能发布时 (+1 周内更新)
- 紧急bug修复后 (即刻更新)

**更新规则**:
1. 代码改动 → 更新对应模块的INTERFACE_REFERENCE.md
2. 架构改动 → 更新ARCHITECTURE_MAP.md + CODE_REVIEW_REPORT.md
3. 新增功能 → 更新DEVELOPER_QUICK_GUIDE.md (代码片段库)
4. 性能优化 → 更新CODE_REVIEW_REPORT.md (性能指标)

---

## 文件对应关系

| 代码文件 | 主要文档参考 | 快速链接 |
|---------|-----------|--------|
| config.py | ARCHITECTURE_MAP.md 第70-100行 | [Config配置层](ARCHITECTURE_MAP.md#第1层配置层-configpy) |
| database/*.py | ARCHITECTURE_MAP.md 第100-250行 | [数据库层](ARCHITECTURE_MAP.md#第2层数据库层) |
| backend/agents/*.py | ARCHITECTURE_MAP.md 第250-440行 + INTERFACE_REFERENCE.md | [代理层](ARCHITECTURE_MAP.md#第3层代理层-backendagents) |
| backend/orchestrator.py | ARCHITECTURE_MAP.md 第440-490行 + INTERFACE_REFERENCE.md | [编排层](ARCHITECTURE_MAP.md#第4层编排层-backendorchestratorpy) |
| backend/utils/*.py | ARCHITECTURE_MAP.md 第490-550行 | [工具库](ARCHITECTURE_MAP.md#第5层工具库-backendutils) |
| pages/*.py | ARCHITECTURE_MAP.md 第550-600行 | [前端层](ARCHITECTURE_MAP.md#第6层前端层) |

---

## 文档质量保证

### ✅ 已验证项
- [x] 所有代码示例已在Python 3.8+ 中验证
- [x] 所有路径都是workspace-relative (不含绝对路径)
- [x] 所有API签名与源代码匹配
- [x] 所有命令行示例可直接复制运行
- [x] 所有链接都指向repo内有效文件

### 📝 维护日志
```
2026-03-10  v1.0  初版完成
  - ARCHITECTURE_MAP.md (650行)
  - DEVELOPER_QUICK_GUIDE.md (550行)
  - INTERFACE_REFERENCE.md (400行)
  - CODE_REVIEW_REPORT.md (350行)
  - 总计: 1950行文档
```

---

## 如何使用这个索引

### 方法1: 按任务查询
1. 找到你的任务描述 (在"快速导航"或"按场景"部分)
2. 点击推荐的文档链接
3. 查看对应章节

### 方法2: 按角色选择
1. 在"按用户角色"找到自己
2. 按推荐顺序阅读文档

### 方法3: 按速度选择
- ⚡ **5分钟**: 本索引 + CODE_REVIEW_REPORT.md 摘要
- ⏱️ **15分钟**: ARCHITECTURE_MAP.md 前200行
- ⏰ **1小时**: 完整阅读ARCHITECTURE_MAP.md
- 📚 **完整**: 全部4份文档

### 方法4: Ctrl+F快速搜索
1. 在对应文档中按 Ctrl+F
2. 搜索关键词 (如"Scout"、"Vision"、"匹配")
3. 跳转到相关章节

---

## 常见搜索词

| 搜索词 | 推荐文档 | 位置 |
|--------|---------|------|
| ScoutAgent | INTERFACE_REFERENCE.md | 清单1 |
| VisionAgent | INTERFACE_REFERENCE.md | 清单1 |
| JudgeAgent | INTERFACE_REFERENCE.md | 清单1 |
| Orchestrator | INTERFACE_REFERENCE.md | 清单2 |
| Faculty / Paper / Author | INTERFACE_REFERENCE.md | 清单3 |
| 数据流向 | ARCHITECTURE_MAP.md | 数据流向图 |
| 性能 | CODE_REVIEW_REPORT.md | 性能评查 |
| 生产就绪 | CODE_REVIEW_REPORT.md | 生产就绪清单 |
| 错误处理 | DEVELOPER_QUICK_GUIDE.md | 常见问题排查 |
| API签名 | INTERFACE_REFERENCE.md | (全文) |

---

## 版权与维护

**文档所有者**: MAC-ADG 项目技术团队  
**最后更新**: 2026年3月10日  
**维护状态**: ✅ 主动维护  
**建议反馈方式**: 在相关文档旁添加 `<!-- feedback: ... -->` 注释

---

**祝开发愉快！如有疑问，先查这份索引。** 🚀
