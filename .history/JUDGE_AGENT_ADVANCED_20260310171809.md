# 🎯 Judge Agent 进阶设计方案

## 问题分析

你遇到的问题是**身份融合的核心难点**：

### 1️⃣ 问题类型

#### 问题 A: 名字歧义（一人多名）
```
同一个教师：
  - 中文: 刘泽平
  - 英文简写: Z.P. Liu
  - 英文全名: Zeping Liu  ← 拼音顺序问题
  - 英文全名: Liu, Zeping ← 姓名顺序问题
  - 网红名: Lewis Liu ← 非学名
```

#### 问题 B: 单位歧义（同一单位多名）
```
四川大学物理学院:
  - 中文: 四川大学物理学院
  - 英文: School of Physics, Sichuan University
  - 缩写: SPU
  - 附属医院: 四川大学华西医院 → Huaxi Hospital, Sichuan University
  - 实验室: 四川大学物理学院磁学实验室 → Laboratory of Magnetism, SU
```

#### 问题 C: 同名同单位（生物学意义上的歧义）
```
四川大学物理学院有2个王力：
  - 论文A: 王力 + 发表年份2020 + 第3作者
  - 论文B: 王力 + 发表年份2021 + 第1作者
  → 需要用 { 名字 + 单位 + 发表年份 + 作者排名 } 四维特征区分
```

---

## 解决方案框架

### 架构：三层递进式身份融合

```
输入: 论文作者信息 {name, affiliation, date, rank}
  ↓
┌─────────────────────────────────────┐
│ L1: 快速过滤  (Simple Match)        │  ← 现有代码
│ 99% 情况在这里就能匹配              │
│ 耗时: <10ms/论文                    │
└─────────────────────────────────────┘
  ↓ (如果匹配失败或多个候选)
┌─────────────────────────────────────┐
│ L2: 置信度评分  (Multi-Dimension)   │  ← 新增
│ 用 { 名字 + 单位 + 年份 + 合作者 }  │
│ 计算匹配得分，给出排序候选         │
│ 耗时: <50ms/论文                    │
└─────────────────────────────────────┘
  ↓ (如果L2得分不清定<0.7)
┌─────────────────────────────────────┐
│ L3: AI 辅助决策  (LLM Fusion)       │  ← 新增
│ 调用DeepSeek/GPT询问：              │
│ "这个{name,affiliation,year}        │
│  最可能匹配我们数据库的哪个教师？"  │
│ 耗时: ~1s/论文 (API调用)            │
└─────────────────────────────────────┘
  ↓
输出: matched_faculty_id (或NULL if 不确定)
```

---

## 具体实现方案

### L1: 快速过滤（保持现有逻辑）

**目的**: 处理 99% 的简单匹配情况

```python
# 现有代码中的字符串匹配部分保持不变
# 只需要改进一点: 引入 Levenshtein 距离

def _quick_match(self, paper_author_name: str, faculty) -> float:
    """
    快速匹配，返回置信度 [0, 1]
    
    策略:
    1. 精确匹配 → 返回 1.0
    2. 包含匹配（只要名字出现在文本中）→ 返回 0.95
    3. 模糊匹配（考虑缩写和顺序调换）→ 返回 0.7-0.9
    4. 无匹配 → 返回 0.0
    """
    from difflib import SequenceMatcher
    
    # 准备所有待检查的名字变体
    candidates = []
    if faculty.name_zh:
        candidates.append(faculty.name_zh)
    
    if faculty.name_en_list:
        try:
            candidates.extend(json.loads(faculty.name_en_list))
        except:
            pass
    
    # 计算最高得分
    best_score = 0.0
    for variant in candidates:
        if not variant:
            continue
            
        # 精确匹配
        if variant.lower() == paper_author_name.lower():
            return 1.0
        
        # 包含匹配（子字符串）
        if variant.lower() in paper_author_name.lower():
            return 0.95
        
        # 模糊匹配（Levenshtein距离）
        similarity = SequenceMatcher(None, 
                                   variant.lower(), 
                                   paper_author_name.lower()).ratio()
        if similarity > 0.8:  # 80%相似度为阈值
            best_score = max(best_score, similarity)
    
    return best_score
```

---

### L2: 置信度评分（新增核心）

**目的**: 用多维度特征排序候选

```python
def _calculate_confidence(
    self, 
    paper_author: dict,      # {name, affiliation, rank, date}
    faculty,                 # Faculty ORM object
    match_score_l1: float    # L1返回的分数
) -> float:
    """
    多维度置信度评分
    
    维度1: 名字匹配度 (40%) → match_score_l1
    维度2: 单位匹配度 (35%) → _affiliation_match()
    维度3: 发表年份 (15%)  → _year_recency()
    维度4: 合作者信号 (10%) → _coauthor_signal()
    
    返回: [0, 1] 的最终置信度
    """
    
    score =  0.4 * match_score_l1
    score += 0.35 * self._affiliation_match(paper_author.get('affiliation'), faculty)
    score += 0.15 * self._year_recency(paper_author.get('pub_year'), faculty)
    score += 0.1 * self._coauthor_signal(paper_author.get('coauthors'), faculty)
    
    return min(1.0, score)
```

#### L2-1: 单位匹配（最复杂）

```python
def _affiliation_match(self, paper_affiliation: str, faculty) -> float:
    """
    单位匹配，返回 [0, 1]
    
    逻辑:
    - 精确匹配 (如"四川大学物理学院") → 1.0
    - 主单位匹配 (如"四川大学") → 0.9
    - 学院/实验室匹配 (如"物理学院") → 0.8
    - 有相关关键词 (如"四川") → 0.6
    - 无关 → 0.0
    """
    
    if not paper_affiliation or not faculty.department:
        return 0.5  # 无信息时中立
    
    paper_aff = paper_affiliation.lower()
    faculty_dept = faculty.department.lower()  # 教师的主单位
    
    # 方案1: 精确匹配
    if paper_aff == faculty_dept:
        return 1.0
    
    # 方案2: 包含匹配（主单位是否在论文单位中）
    if faculty_dept in paper_aff:
        return 0.9
    
    # 方案3: 建立单位同义词库，处理中英混合
    synonyms = self._get_affiliation_synonyms(faculty_dept)
    for synonym in synonyms:
        if synonym in paper_aff:
            return 0.85
    
    # 方案4: 关键词匹配（四川大学、华西医院等）
    keywords = self._extract_keywords(faculty_dept)
    matched_keywords = sum(1 for kw in keywords if kw in paper_aff)
    if matched_keywords > 0:
        return 0.5 + 0.2 * min(matched_keywords / len(keywords), 1.0)
    
    return 0.0

def _get_affiliation_synonyms(self, department: str) -> list:
    """
    单位同义词库（中英对照）
    
    这个应该从数据库配置表加载，而不是硬编码
    """
    synonym_map = {
        "四川大学物理学院": [
            "School of Physics, Sichuan University",
            "Sichuan University School of Physics",
            "SGU Physics",
            "物理系",
        ],
        "四川大学华西医院": [
            "Huaxi Hospital, Sichuan University",
            "West China Hospital",
            "West China Medical School",
        ],
        # ... 更多同义词
    }
    
    return synonym_map.get(department, [])

def _extract_keywords(self, department: str) -> list:
    """
    从部门名称提取关键词
    """
    import re
    # 移除括号、特殊字符，按层级提取
    keywords = re.findall(r'[\u4e00-\u9fff]+|[A-Za-z]+', department)
    return keywords
```

#### L2-2: 发表年份（消除歧义）

```python
def _year_recency(self, pub_year: int, faculty) -> float:
    """
    以发表年份过滤同名者
    
    逻辑:
    - 如果教师从未发表过: 返回 0.5（不确定）
    - 如果论文年份在教师的发表期间: 返回 1.0
    - 如果论文年份在教师入职前: 返回 0.0（不可能）
    - 如果教师已退休但论文较新: 返回 0.3（可能，但低可信度）
    """
    
    # 检查教师的发表年份范围（从现有论文推断）
    # 假设从数据库中计算出的教师活跃期间: [first_pub, last_pub]
    db = next(get_db())
    papers = db.query(Paper).join(PaperAuthor).filter(
        PaperAuthor.matched_faculty_id == faculty.id
    ).all()
    
    if not papers:
        return 0.5  # 教师无发表记录，不确定
    
    years = [p.publish_date.year for p in papers if p.publish_date]
    if not years:
        return 0.5
    
    earliest = min(years)
    latest = max(years)
    
    if not pub_year:
        return 0.5  # 论文日期未知
    
    # 判断论文年份是否在教师的活跃期间
    if earliest <= pub_year <= latest:
        return 1.0
    elif pub_year > latest:
        # 论文比教师最后一篇还新
        # 可能是因为教师继续发表，也可能是同名者
        return max(0.0, 0.7 - (pub_year - latest) * 0.05)
    elif pub_year < earliest:
        # 论文比教师最早的还旧
        return 0.0  # 不可能，这个教师当时还没出现
    
    return 0.5
```

#### L2-3: 合作者信号（增强可靠性）

```python
def _coauthor_signal(self, paper_coauthors: list, faculty) -> float:
    """
    检查论文的其他合作者是否也在我们的数据库中
    
    逻辑:
    - 如果论文的其他作者也是我们学校的教师，匹配可靠性大幅提升
    - 否则返回中立值
    """
    
    if not paper_coauthors:
        return 0.5
    
    db = next(get_db())
    matched_coauthors = 0
    
    for coauthor_name in paper_coauthors:
        # 查询是否有其他Faculty的名字匹配这个合作者
        other_faculty = db.query(Faculty).filter(
            Faculty.id != faculty.id
        ).all()
        
        for other in other_faculty:
            # 用L1简单匹配检查
            if self._quick_match(coauthor_name, other) > 0.8:
                matched_coauthors += 1
                break
    
    # 如果有来自我们学校的合作者，可信度大幅提升
    signal = 0.5 + 0.5 * min(matched_coauthors / max(1, len(paper_coauthors)), 1.0)
    return signal
```

---

### L3: AI 辅助决策（不清定时触发）

**目的**: 当 L2 置信度不足（<0.7）时，调用 LLM 进行模糊决策

```python
def _llm_fusion(
    self,
    paper_author: dict,
    candidates: list  # [(faculty, confidence_l2), ...]
) -> Faculty:
    """
    调用LLM 进行身份融合
    
    输入: 论文作者信息 + 候选教师列表（按L2置信度排序）
    输出: 最终匹配的教师 ID
    
    何时触发: 当最高候选的置信度 < 0.7 时触发
    """
    
    import os
    from openai import OpenAI  # 或使用 requests 调用 DeepSeek API
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("[Judge-L3] No API key, skipping LLM fusion")
        return None
    
    # 构建提示词
    paper_info = f"""
    论文作者信息:
    - 姓名: {paper_author.get('name')}
    - 单位: {paper_author.get('affiliation')}
    - 发表年份: {paper_author.get('pub_year')}
    - 作者排名: {paper_author.get('rank')}
    - 共同作者: {', '.join(paper_author.get('coauthors', []))}
    """
    
    candidates_info = "\n".join([
        f"选项{i+1}: {faculty.name_zh} (单位: {faculty.department}, 可靠性: {conf:.2%})"
        for i, (faculty, conf) in enumerate(candidates[:3])  # 只给前3个候选
    ])
    
    prompt = f"""
你是一个学术身份识别专家。我需要你帮我精准匹配一个论文作者到我们大学的教师数据库。

{paper_info}

我们数据库中的候选教师（按可靠性排序）:
{candidates_info}

请分析并回答：
1. 这个论文作者最可能匹配以上哪个教师？请给出你的理由。
2. 你的置信度是多少？(0-100%)
3. 如果所有候选都不可靠，请说"无法确定"。

返回格式（JSON）:
{{
    "matched_index": 1,  // 0表示第一个选项，-1表示无法确定
    "confidence": 0.85,
    "reasoning": "..."
}}
    """
    
    try:
        # 调用 DeepSeek API（假设你已配置）
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # 降低温度，保证稳定性
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        
        matched_index = result.get("matched_index", -1)
        if matched_index >= 0 and matched_index < len(candidates):
            return candidates[matched_index][0]
        else:
            return None
    
    except Exception as e:
        print(f"[Judge-L3] LLM error: {e}")
        return None
```

---

## 新的 Judge Agent 架构

```python
class JudgeAgent:
    """改进版 Judge Agent"""
    
    def adjudicate(self, scout_data, vision_data):
        """
        新流程:
        1. 提取论文作者信息 (从Vision返回的结果)
        2. 对每个论文作者，执行 L1→L2→L3 递进式匹配
        3. 保存到数据库
        """
        
        doi = scout_data.get("doi")
        title = scout_data.get("title")
        journal = scout_data.get("journal")
        pub_date = scout_data.get("publish_date")
        pub_year = pub_date.year if pub_date else None
        
        db: Session = next(get_db())
        
        try:
            # 从Vision返回中提取作者列表
            # 假设Vision返回: {text, image_path, authors: [{name, affiliation, rank, is_corresponding, is_co_first}]}
            vision_authors = vision_data.get("authors", [])
            
            if not vision_authors:
                # 如果Vision没有识别到作者（因为没有接入VLM），降级到文本提取
                vision_authors = self._extract_authors_from_text(vision_data.get("text", ""))
            
            # 为每个论文作者找到最匹配的教师
            matched_count = 0
            for paper_author_info in vision_authors:
                paper_author_name = paper_author_info.get("name")
                paper_author_aff = paper_author_info.get("affiliation", "")
                paper_author_rank = paper_author_info.get("position", 999)
                is_corresponding = paper_author_info.get("is_corresponding", False)
                is_co_first = paper_author_info.get("is_co_first", False)
                
                # ===== L1: 快速过滤 =====
                candidates_l1 = []
                all_faculty = db.query(Faculty).all()
                
                for faculty in all_faculty:
                    score_l1 = self._quick_match(paper_author_name, faculty)
                    if score_l1 > 0.6:  # L1阈值: 0.6
                        candidates_l1.append((faculty, score_l1))
                
                if not candidates_l1:
                    print(f"[Judge] 作者 '{paper_author_name}' 在L1未找到")
                    continue
                
                # ===== L2: 置信度评分 =====
                candidates_l2 = []
                paper_author_dict = {
                    "name": paper_author_name,
                    "affiliation": paper_author_aff,
                    "pub_year": pub_year,
                    "rank": paper_author_rank,
                    "coauthors": [a["name"] for a in vision_authors if a["name"] != paper_author_name]
                }
                
                for faculty, score_l1 in candidates_l1:
                    score_l2 = self._calculate_confidence(paper_author_dict, faculty, score_l1)
                    candidates_l2.append((faculty, score_l2))
                
                # 按L2置信度排序
                candidates_l2.sort(key=lambda x: x[1], reverse=True)
                
                # 判断是否需要L3
                best_faculty, best_score = candidates_l2[0]
                
                if best_score < 0.7 and len(candidates_l2) > 1:
                    # ===== L3: AI 融合 =====
                    print(f"[Judge] 触发L3 (最高置信度: {best_score:.2%})")
                    best_faculty = self._llm_fusion(paper_author_dict, candidates_l2) or best_faculty
                
                # ===== 保存到数据库 =====
                existing_link = db.query(PaperAuthor).filter(
                    PaperAuthor.paper_doi == doi,
                    PaperAuthor.matched_faculty_id == best_faculty.id
                ).first()
                
                if not existing_link:
                    author_record = PaperAuthor(
                        paper_doi=doi,
                        rank=paper_author_rank,
                        raw_name=paper_author_name,
                        matched_faculty_id=best_faculty.id,
                        is_corresponding=is_corresponding,
                        is_co_first=is_co_first,
                        confidence_score=best_score  # 新增：保存置信度
                    )
                    db.add(author_record)
                    matched_count += 1
            
            # 保存论文记录
            existing_paper = db.query(Paper).filter(Paper.doi == doi).first()
            if not existing_paper:
                paper = Paper(
                    doi=doi,
                    title=title,
                    journal=journal,
                    publish_date=pub_date,
                    pdf_path=scout_data.get("pdf_path") or scout_data.get("html_path"),
                    status="COMPLETED"
                )
                db.add(paper)
            
            db.commit()
            print(f"[Judge] 完成审判, 匹配了 {matched_count} 个教师")
            return True
        
        except Exception as e:
            db.rollback()
            print(f"[Judge] 错误: {e}")
            return False
        finally:
            db.close()
```

---

## 数据库改进

需要在 `PaperAuthor` 表中添加新字段：

```python
# database/models.py 中的 PaperAuthor 类

class PaperAuthor(Base):
    __tablename__ = "paper_author"
    
    # ... 现有字段 ...
    
    # 新增字段（支持分层匹配）
    confidence_score = Column(Float, default=0.5)  # 最终置信度 [0, 1]
    matched_level = Column(String, default="L1")   # 匹配级别: "L1", "L2", "L3"
    match_signals = Column(JSON, nullable=True)    # 调试用: {name_score, aff_score, year_score, coauthor_score}
```

---

## 总结与建议

| 问题 | 解决方案 | 何时触发 |
|------|--------|--------|
| 名字多格式 | L1: Levenshtein + 模糊匹配 | 总是 |
| 单位多格式 | L2: 同义词库 + 关键词匹配 | L1候选>1 |
| 同名同单位 | L2: 发表年份 + 合作者信号 | L1候选>1 |
| 中英单位差异 | L2: 建立中英对照库 | 单位匹配时 |
| 终极歧义 | L3: 调用LLM | L2置信度<0.7 |

---

## 部署建议

### 阶段1（当前 - P1）
- ✅ 实现 L1 快速过滤
- ✅ 改进 Levenshtein 距离计算
- ⏳ 建立基础单位同义词库（手动维护 JSON 文件）

### 阶段2（P2）
- ⏳ 实现 L2 多维度评分
- ⏳ 对接 Vision Agent 返回的结构化作者信息
- ⏳ 建立中英单位对照表

### 阶段3（P2.5）
- ⏳ 调用 DeepSeek API 实现 L3
- ⏳ 设计 LLM prompt 并测试

### 阶段4（P3）
- ⏳ 性能优化：缓存单位同义词库
- ⏳ 监控：记录每个匹配的置信度分布
- ⏳ 人工审核：定期审核 L3 决策的准确性

