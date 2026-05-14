---
name: personal-daily-digest
description: 生成面向算法工程师的个人科技情报日报。从 AI、算法、科技媒体、GitHub 和 RSS 源聚合内容，完成排序、分层总结、消息推送与快手文档归档。以下场景唤醒：用户说「生成日报」「今天有什么值得看」「跑一次科技日报」「看看 AI 和科技快讯」「给我今天的情报」「daily digest」时触发。以下场景不唤醒：用户只是想查询单个仓库发布、查询某篇固定文章、查天气、查班车、订会议室、查食堂等非日报场景。
---

# personal-daily-digest — AI 日报

## 目标

为大模型算法工程师生成 AI 日报（标题格式：`YYYY-MM-DD AI 日报`），重点覆盖 arxiv 论文、AI 行业动态、科技快讯与宏观信号。

## 用户画像

- 角色：**大模型算法工程师**
- 核心关注：AI / 算法 / 推荐 / 搜索 / 广告 / 生成式推荐 / 用户反馈 / 推理优化 / 大模型动态
- 次级关注：科技行业快讯、大厂产品与平台动态
- 补充关注：影响科技行业的宏观新闻、国际事件、监管与产业信号
- 阅读偏好：不强控条数，排序合理、分层清晰即可

## 运行时安全约束

⚠️ 自修复熔断：脚本执行失败后最多重试 2 次，超过后停止并输出明确失败信息。
⚠️ agent-browser 降级：仅在 API 直接调用失败且无替代时降级，最多 1 次。

## 执行流程

```
Step 1  → 加载源池配置
Step 2  → 加载去重注册表（dedup_registry.json），过滤掉 48h 内已入选条目
Step 3  → 抓取各源候选内容
Step 4  → 与去重注册表比对，剔除已推送条目
Step 5  → arxiv 机构信息补全（/html/ 接口）
Step 6  → 关键词过滤 + 按用户画像评分排序
Step 7  → 按模板分层生成日报
Step 8  → 写入快手 Docs
Step 9  → 发送 KIM 卡片消息摘要
Step 10 → 将本次入选条目追加进去重注册表
Step 11 → 本地归档
```

---

## 增量去重机制

### 去重注册表

文件位置：`<workspace>/daily-digest/dedup_registry.json`

结构：

```json
{
  "items": {
    "arxiv:2605.11447": "2026-05-13T12:00:00+08:00",
    "url:https://openai.com/index/deployco": "2026-05-11T09:00:00+08:00",
    "github:huggingface/transformers:v5.8.1": "2026-05-13T11:00:00+08:00"
  },
  "last_cleanup": "2026-05-13T12:00:00+08:00"
}
```

### Key 生成规则

| 来源类型 | Key 格式 | 示例 |
|---|---|---|
| arxiv 论文 | `arxiv:{arxiv_id}` | `arxiv:2605.11447` |
| URL 条目（新闻/快讯） | `url:{normalized_url}` | `url:https://openai.com/index/deployco` |
| GitHub Release | `github:{repo}:{tag}` | `github:huggingface/transformers:v5.8.1` |

URL 规范化：去掉 `?utm_source=rss&...` 等 tracking 参数，去掉 `#comments`，统一 scheme 为 `https://`。

### 执行逻辑

1. **生成日报前**：读取 `dedup_registry.json`（不存在则创建空文件）
2. **候选池过滤**：对每个候选条目生成 key，如果 key 在注册表中且入选时间距今 ≤ 48h，则跳过
3. **过期清理**：入选时间超过 48h 的条目在每次运行时自动清理（48h 窗口比 24h 多一倍，防止跨天边界漏掉）
4. **生成日报后**：将本次所有入选条目的 key + 当前时间追加写入注册表
5. **写入时合并**：先读取现有注册表，追加新条目，清理过期条目，然后一次性写回（不要先读再写导致竞争）

### 示例

如果昨天日报已入选 `arxiv:2605.11447`，今天 RSS 中该论文仍出现 → 命中去重 → 跳过。
如果某 OpenAI Blog 条目 2 天前入选，今天仍在 RSS → 超过 48h → 不去重 → 可再次入选（但通常不会，因为 RSS 本身有时效性）。

## ⚠️ 硬性规则（不可违反）

### 规则一：标题必须叫「AI 日报」

日报标题格式：`YYYY-MM-DD AI 日报`，不得使用「科技情报日报」「个人科技情报流」等旧名称。

### 规则二：论文机构优先级大于作者名

每篇 arxiv 论文的信息行格式：

```
🏛️ 机构｜作者1, 作者2 et al.
```

- **机构排在第一位，用 🏛️ 标记**
- 机构信息必须从 `arxiv/html/` 接口获取（见规则三）
- 多机构用 `&` 连接（如：香港城市大学 & 清华大学）
- 抓不到机构时写「机构待确认」，**不得省略或留空**

### 规则三：arxiv 机构信息获取方式

arxiv 论文的机构信息有三种获取路径，可靠性排序：

| 方式 | 可靠性 | 说明 |
|---|---|---|
| arxiv RSS | ❌ 不可用 | 只有作者姓名，不含机构 |
| arxiv abs 页面 + readability | ❌ 不可用 | readability 会过滤掉 author affiliation DOM 结构 |
| **arxiv `/html/` 接口** | ✅ **唯一正确方式** | 返回论文 HTML 全文，机构在 author block 中完整可用 |

**⚠️ `fetch_arxiv.py` 已内置机构补全逻辑（`fetch_affiliations()` 函数）：**
- 排序后自动对 Top 15 论文逐篇抓 `https://arxiv.org/html/{id}v1`
- 用 `web_fetch` 抓取，串行 + 2s 间隔，防止 429 rate limit
- 从返回文本中提取 `affiliations` 列表和 `authors` 字段中的机构字符串
- AI **不需要** 再自己逐篇调用 `web_fetch` 补全机构，直接使用脚本输出的 `affiliations` 字段即可
- 若 `affiliations` 为空但 `authors` 中包含机构文本，AI 应从 `authors` 字段中手动提取机构信息，不得写「机构待确认」

**备用注意事项：**
- arxiv API 的 `<arxiv:affiliation>` 字段是**可选的**（大多数作者不填），不能依赖它作为主链路
- arxiv API 有严格 rate limit（3 req/s，易触发 429），**禁止逐篇循环调用 API**
- 若脚本补全时某篇 `/html/` 页面超时或 429，跳过该篇，AI 在生成日报时从 `authors` 字段提取机构

### 规则四：论文摘要用「工程意义」三行格式（算法工程师视角）

**不要翻译 abstract**，而是站在算法工程师的角度说清楚三件事，每行一句：

```
- ❓ 工程问题：现有方案在工业落地/实际系统中的哪个具体痛点（不是学术背景）
- 🔧 核心方法：用什么技术手段解决，一句话，点到本质（结构/训练策略/数据/优化目标）
- 💡 对你的价值：这个工作对推荐/大模型/搜索/用户反馈工程有什么直接参考价值
```

示例（正确）：
```
- ❓ 工程问题：生成式推荐模型在 item ID 稀疏场景下泛化差，冷启动命中率低
- 🔧 核心方法：用语义 token 替代 ID，结合 contrastive 对齐 item 语义空间
- 💡 对你的价值：直接可用于快手冷启动推荐，语义 token 方案可替代现有 ID embedding
```

示例（错误，禁止）：
```
- ❓ 问题：现有检索增强方法在多跳推理上表现不佳
- 🔧 方法：提出了一种新的检索框架
- ✅ 结果：在 HotpotQA 上提升了 3 个点
```

禁止写纯结果数字但无工程结论，禁止重复描述同一内容。

### 规则五：科技快讯必须全量覆盖所有已抓取源

抓取到的每个源（36Kr、极客公园、The Verge、爱范儿等）的所有相关条目都必须出现在日报中，**不得因"懒"省略条目**。

如果某个源当天没有相关条目，在元信息中说明即可，但不能只用了 1 条就把其余丢弃。

### 规则六：链接必须可点击

- 日报 Markdown 中所有链接统一使用 `[描述文字](URL)` 格式，禁止裸链接
- KIM 卡片消息中使用 `kimMd` 格式，链接写为 `[标题](URL)`
- 快手 Docs 链接同理

### 规则七：增量去重，48h 内已推送条目不得重复

- 每次生成日报前必须加载 `dedup_registry.json`，对候选池中的每个条目生成 key 进行比对
- 48h 内已入选的条目直接跳过，不进入排序和输出
- 日报生成后必须将本次所有入选条目追加进注册表
- 注册表自动清理超过 48h 的过期条目

---

## 默认源池

详见 `<skill_directory>/reference/default-sources.md`。

核心源分类：
- **A. arxiv 论文**：cs.IR / cs.AI RSS（每日必抓，不抓 cs.LG）
- **B. AI 行业动态**：OpenAI Blog RSS、Anthropic News 页面、The Verge AI RSS、MIT News AI RSS、GitHub Releases
- **C. 科技媒体快讯**：爱范儿 RSS、36Kr RSS、极客公园 RSS
- **D. 宏观科技信号**：The Verge 产业报道替代 Reuters（Reuters 已连接失败）

---

## 排序原则

提高优先级：
- AI / 算法 / 模型 / 推荐 / 搜索 / 广告 / 生成式推荐 / 用户反馈
- 大厂 AI 动作与产品发布
- 有工业背景或 SIGIR/KDD/NeurIPS 等顶会接收标记的论文
- 科技行业快讯
- 会影响科技行业判断的宏观事件

降低优先级：
- 与算法工程方向弱相关的纯 infra 细节
- 纯系统底层长尾更新
- 仅技术上有趣但不够相关的发布

### arxiv 论文筛选规则

**只抓取 cs.IR 和 cs.AI 两个分类，不抓 cs.LG。** cs.LG 条数太多（每天数百条），关键词误匹配严重，且与推荐/检索/大模型相关的论文几乎全部交叉投稿到 cs.IR 或 cs.AI，不需要单独抓 cs.LG。

**cs.IR（信息检索）**：全部保留，不过滤。这是推荐/搜索/检索的主战场。

**cs.AI（人工智能）**：标题级匹配，命中以下关键词保留：
```
recommendation | retrieval | large language model | LLM | RLHF |
preference optimization | reward model | generative recommendation |
user behavior | user feedback | CTR | DPO | alignment | MoE |
inference efficiency | RAG | fine-tuning LLM
```

**最终取 Top 10 论文**，按领域相关性打分排序后取前 10 篇。

打分规则（标题命中加分）：
- `+3`：recommendation / retrieval / ranking / CTR / user behavior / user feedback / generative recommendation / collaborative filtering
- `+2`：LLM inference / RLHF / reward model / DPO / preference optimization / MoE / alignment
- `+1`：large language model / LLM（通用 LLM 研究）
- `-2`：medical / clinical / health / EHR / agriculture / traffic / seismic / satellite / protein / biology / chemistry

**兜底规则**：
- cs.IR 全收
- cs.AI 关键词过滤 + 打分排序
- 合并后取 Top 10，推荐/检索相关论文优先级始终最高

---

## 日报结构

```
1. 今日重点（S/A 级）
2. arxiv 论文精选（大模型 / 推荐 / 搜索 / 用户反馈，每日必出）
3. 算法与 AI 动态
4. 科技快讯（全量覆盖）
5. 宏观科技信号
6. 我的观察
7. 元信息
```

详细模板见 `<skill_directory>/reference/daily-template.md`。

---

## 输出要求

### 消息摘要（KIM kimMixCard）

⚠️ **KIM 卡片必须包含以下所有模块，不得省略任何一个：**

1. **今日重点** — 2-3 条，含机构 + ❓/🔧/💡 三行格式
2. **arxiv 论文精选列表** — 含机构 + 领域标签，逐篇列出
3. **算法与 AI 动态** — 按条列出（不得省略）
4. **科技快讯** — 按源分组，全量列出（不得省略）
5. **快手 Docs 完整日报链接** — 可点击 Markdown 格式

如果卡片内容超长，允许每条适当压缩摘要文字，但**模块本身不能删**。

⚠️ **KIM 卡片固定结尾模板（必须原样包含，只替换 {} 内的变量）：**

```
---
📄 完整日报：[{日期} AI 日报]({docs_url})
```

- `{日期}` 替换为 `YYYY-MM-DD`
- `{docs_url}` 替换为本次写入快手 Docs 后返回的文档 URL
- 这一行**必须出现在 KIM 卡片的最后**，不得省略、不得移到卡片中间
- 如果 Docs 写入失败，写「文档写入失败，请查看本地归档」，不得留空

### 快手 Docs

完整日报写入快手 Docs，使用 docs-shuttle skill 的 push 命令。Markdown 链接统一 `[标题](URL)` 格式。

---

## 本地归档

保存到 `<workspace>/daily-digest/archive/YYYY-MM-DD/`：
- `daily_report.md`
- `run_log.json`（可选）

---

## 参考文件

- 模板：`<skill_directory>/reference/daily-template.md`
- 默认源：`<skill_directory>/reference/default-sources.md`
- 路线图：`<skill_directory>/reference/roadmap.md`