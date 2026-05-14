# 默认信息源配置（v1.2）

## 设计原则

围绕大模型算法工程师的核心关注点，分四类来源：
- **arxiv 学术论文**（核心，不可漏）
- 算法 / AI 行业动态
- 科技媒体快讯
- 宏观科技信号

## 可用性状态（2026-05-13 验证）

| 源 | URL | 状态 |
|---|---|---|
| OpenAI Blog RSS | https://openai.com/news/rss.xml | ✅ 200 |
| Anthropic News（页面）| https://www.anthropic.com/news | ✅ 200（无 RSS，用页面抓取）|
| Anthropic RSS | https://www.anthropic.com/news/rss.xml | ❌ 404 |
| Google Blog RSS | https://blog.google/rss/ | ❌ 连接失败 |
| HuggingFace Blog RSS | https://huggingface.co/blog/feed.xml | ❌ 连接失败 |
| HuggingFace Blog（页面）| https://huggingface.co/blog | 备用 |
| 爱范儿 RSS | https://www.ifanr.com/feed | ✅ 200 |
| 36Kr RSS | https://36kr.com/feed | ✅ 200 |
| 极客公园 RSS | https://www.geekpark.net/rss | ✅ 200 |
| The Verge AI RSS | https://www.theverge.com/rss/ai-artificial-intelligence/index.xml | ✅ 200 |
| MIT News AI RSS | https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml | ✅ 200 |
| arxiv RSS (cs.IR) | https://export.arxiv.org/rss/cs.IR | ✅ 200 |
| arxiv RSS (cs.LG) | https://export.arxiv.org/rss/cs.LG | ⛔ 已移除（误匹配严重，相关论文交叉投稿到 cs.IR/cs.AI）|
| arxiv RSS (cs.AI) | https://export.arxiv.org/rss/cs.AI | 待测 |
| arxiv API | https://export.arxiv.org/api/query | ⚠️ 429（rate limit，谨慎调用）|
| Reuters Tech/World | https://www.reuters.com/technology/ | ❌ 连接失败 |
| GitHub API | https://api.github.com/repos/... | ✅ 200 |

---

## A. arxiv 论文（核心专题，每日必抓）

用户画像：**大模型算法工程师**，以下领域不可漏。

### 关键词过滤策略

抓取 arxiv RSS 后，按以下关键词进行相关性过滤（大小写不敏感，命中任一即入选候选）：

**大模型 / 预训练 / 推理优化：**
`large language model`, `LLM`, `foundation model`, `instruction tuning`, `RLHF`, `alignment`,
`inference`, `KV cache`, `speculative decoding`, `quantization`, `fine-tuning`, `LoRA`,
`chain-of-thought`, `reasoning`, `transformer`, `attention`, `mixture of experts`, `MoE`

**推荐系统 / 生成式推荐：**
`recommendation`, `recommender`, `generative recommendation`, `sequential recommendation`,
`collaborative filtering`, `user modeling`, `item representation`, `retrieval-augmented`,
`RAG`, `knowledge graph`, `click-through rate`, `CTR`, `ranking`, `re-ranking`

**用户反馈 / 偏好学习：**
`user feedback`, `user preference`, `implicit feedback`, `explicit feedback`,
`reward model`, `preference learning`, `human feedback`, `online learning`

**搜索 / 广告：**
`information retrieval`, `dense retrieval`, `bi-encoder`, `cross-encoder`, `query`,
`ads`, `sponsored search`, `conversion rate`, `CVR`

### RSS 源配置

**只抓 cs.IR 和 cs.AI，不抓 cs.LG。** cs.LG 每天数百条且误匹配严重，相关论文几乎都交叉投稿到 cs.IR 或 cs.AI。

```json
[
  {
    "name": "arxiv cs.IR (Information Retrieval)",
    "url": "https://export.arxiv.org/rss/cs.IR",
    "note": "覆盖推荐、搜索、检索，全量保留不过滤"
  },
  {
    "name": "arxiv cs.AI (Artificial Intelligence)",
    "url": "https://export.arxiv.org/rss/cs.AI",
    "note": "关键词过滤后取高分论文，覆盖 AI 方法、对齐、RLHF"
  }
]
```

### 机构信息获取方式

arxiv RSS 只有作者姓名，不含机构。机构信息必须单独抓取。

**唯一正确方式：使用 `/html/` 接口**

```
https://arxiv.org/html/{arxiv_id}v1
```

⚠️ **`fetch_arxiv.py` 已内置机构补全逻辑（`fetch_affiliations()` 函数），AI 不需要再自己逐篇调用 `web_fetch` 补全机构。**

脚本自动执行的流程：
1. 排序后自动对 Top 15 论文逐篇抓 `https://arxiv.org/html/{id}v1`
2. 串行 + 2s 间隔，防止 429 rate limit
3. 从返回文本中提取 `affiliations` 列表和 `authors` 字段中的机构字符串
4. 若 `affiliations` 为空但 `authors` 中包含机构文本，AI 应从 `authors` 字段手动提取，不得写「机构待确认」

三种方式对比：

| 方式 | 可靠性 | 说明 |
|---|---|---|
| arxiv RSS | ❌ | 只有作者名，无机构 |
| arxiv abs 页面（readability） | ❌ | readability 会过滤掉 affiliation DOM |
| arxiv Atom API (`<arxiv:affiliation>`) | ⚠️ 可选字段 | 大多数作者不填，不可作为主链路 |
| **arxiv `/html/` 接口** | ✅ **唯一可靠** | 脚本已内置，自动补全 Top 15 |

---

## B. 算法 / AI 行业动态源

### RSS / Blog

```json
[
  {
    "name": "OpenAI Blog",
    "url": "https://openai.com/news/rss.xml",
    "status": "✅"
  },
  {
    "name": "Anthropic News（页面）",
    "url": "https://www.anthropic.com/news",
    "method": "page_fetch",
    "status": "✅",
    "note": "无 RSS，直接抓页面列表"
  },
  {
    "name": "The Verge AI",
    "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "status": "✅",
    "note": "英文科技媒体，AI 报道覆盖全面"
  },
  {
    "name": "MIT News AI",
    "url": "https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml",
    "status": "✅",
    "note": "学界研究动态，可作为 arxiv 补充"
  }
]
```

### GitHub 仓库（只看 Release，不看 commit）

```json
[
  "huggingface/transformers",
  "vllm-project/vllm",
  "sgl-project/sglang",
  "pytorch/pytorch"
]
```

说明：
- `openai/openai-python` 是 SDK，相关性低于 OpenAI Blog，降优先级
- `langchain-ai/langchain` 和 `mlflow/mlflow` 与大模型算法关联弱，移除

---

## C. 科技媒体快讯源

```json
[
  {
    "name": "爱范儿",
    "url": "https://www.ifanr.com/feed",
    "status": "✅"
  },
  {
    "name": "36Kr",
    "url": "https://36kr.com/feed",
    "status": "✅"
  },
  {
    "name": "极客公园",
    "url": "https://www.geekpark.net/rss",
    "status": "✅"
  }
]
```

---

## D. 宏观科技信号源

Reuters 已连接失败，暂时用 The Verge AI 中的产业报道替代覆盖。后续若有可用 RSS 再补充。

---

## 日报分层结构更新

在原有结构基础上增加「arxiv 论文精选」专区：

```
1. 今日重点（S/A 级）
2. arxiv 论文精选（大模型 / 推荐 / 搜索 / 用户反馈）← 新增，核心专题
3. 算法与 AI 动态
4. 科技快讯
5. 宏观科技信号
6. 我的观察
7. 元信息
```

## 输出策略

- arxiv 专区：cs.IR 全收 + cs.AI 关键词过滤后打分排序，合并取 Top 10
- 强排序，不强控条数
- 链接统一使用 `[标题](链接)` 可点击格式
