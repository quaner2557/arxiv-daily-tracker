# arXiv Daily Tracker

基于 [paperBotV2](https://github.com/Doragd/Algorithm-Practice-in-Industry/tree/main/paperBotV2) 实现，使用 AI 粗排+精排筛选高质量论文。

## 核心特点

- 🤖 **AI 粗排**：基于标题快速筛选，给出 1-10 分相关性评分
- 🎯 **AI 精排**：基于标题+摘要深度分析，生成中文总结
- ⭐ **评分展示**：飞书卡片带星级评分（⭐️ x 分数）
- 📝 **标题翻译**：自动生成专业中文标题翻译
- 🏷️ **智能分类**：自动识别 RecSys/Search/Ads 相关论文

## 工作流程

```
获取论文 → 粗排（标题评分）→ 精排（摘要总结）→ 生成报告 → 飞书推送
   ↓
  100篇      筛选≥4分           取前20篇
```

## 配置

### 环境变量

复制 `.env.example` 为 `.env`：

```bash
# AI 配置（必填）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-chat

# arXiv 配置（可选）
TARGET_CATEGORYS=cs.IR,cs.CL,cs.AI,cs.LG,cs.DB
MAX_PAPERS=100
ROUGH_SCORE_THRESHOLD=4
RETURN_PAPERS=20

# 飞书推送（可选，支持多个URL用逗号分隔）
FEISHU_URL=https://open.feishu.cn/...
```

### GitHub Actions 配置

在仓库 Settings 中配置：

**Secrets:**
- `OPENAI_API_KEY` - AI API Key
- `OPENAI_BASE_URL` - API 基础 URL（可选）
- `FEISHU_URL` - 飞书 Webhook（可选）

**Variables:**
- `MODEL_NAME` - 模型名称（默认 deepseek-chat）
- `TARGET_CATEGORYS` - arXiv 分类（默认 cs.IR,cs.CL,cs.AI）
- `MAX_PAPERS` - 每分类最大获取数（默认 100）
- `ROUGH_SCORE_THRESHOLD` - 粗排分数阈值（默认 4）
- `RETURN_PAPERS` - 最终推送数量（默认 20）

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

## 输出示例

### Markdown 报告
```markdown
# arXiv 论文日报 - 2024-01-15

## 今日精选 (15 篇)

### 1. 基于大语言模型的推荐系统综述

**原文标题**: [A Survey on Large Language Models for Recommendation](...)

**作者**: John Doe, et al.

**评分**: ⭐️⭐️⭐️⭐️⭐️⭐️⭐️⭐️ (8/10)

**核心总结**:
该论文系统综述了LLM在推荐系统中的应用，提出了新的分类体系。核心贡献是建立了LLM4Rec的统一框架，并指出了未来研究方向。

**评分理由**:
直接相关，全面梳理了LLM与RecSys的结合点，对工业界有重要参考价值。
```

### 飞书卡片
- 带星级评分的论文列表
- 中文标题翻译
- 一句话核心总结
- 点击标题跳转论文

## 筛选标准

### 关注领域
- RecSys、Search、Ads 核心进展
- LLM 基础技术（有应用潜力）
- Transformer 架构改进
- VLM 异构数据建模思想

### 排除领域
- 隐私/安全/伦理等非技术话题
- 医学/生物/化学等垂直应用
- NAS/AutoML
- 纯理论无实践
- 纯 NLP/CV 无相关性

## License

MIT
