# arXiv Daily Tracker

每天自动获取 arXiv 最新论文，支持按公司/机构名称和研究方向关键词筛选。

## 功能特点

- 🔍 **多维度筛选**：支持按公司名称（如 Google, Meta, OpenAI）和研究方向（如 recommendation, search, retrieval）筛选
- 🤖 **AI 总结**：使用大模型自动总结论文摘要
- 📧 **多种推送方式**：支持飞书/钉钉/邮件推送
- ⏰ **定时执行**：GitHub Actions 每天自动运行
- 💾 **本地运行**：也支持本地手动运行

## 快速开始

### 1. 配置环境变量

复制 `.env.example` 为 `.env` 并填写：

```bash
# AI 配置（用于总结论文）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1  # 或其他兼容 OpenAI API 的服务
MODEL_NAME=deepseek-chat

# 推送配置（可选）
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

### 2. 配置订阅规则

编辑 `config.yaml`：

```yaml
# 订阅配置
subscriptions:
  # 按公司/机构筛选
  companies:
    - Google
    - Meta
    - OpenAI
    - Microsoft
    - Amazon
    - Netflix
    - Spotify
    - ByteDance
    - Alibaba
    - Tencent
  
  # 按研究方向关键词筛选
  keywords:
    - recommendation
    - search
    - retrieval
    - ranking
    - matching
    - candidate generation
  
  # arXiv 分类
  categories:
    - cs.IR  # 信息检索
    - cs.LG  # 机器学习
    - cs.AI  # 人工智能
    - cs.CL  # 计算语言学
    - cs.DB  # 数据库

# 输出配置
output:
  format: markdown  # markdown 或 json
  max_papers_per_day: 50  # 每天最多推送论文数
  
# 总结配置
summary:
  language: zh  # zh 或 en
  max_length: 500  # 总结最大长度
```

### 3. 运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行爬虫
python main.py
```

## GitHub Actions 自动运行

1. Fork 本仓库
2. 设置 Secrets（Settings -> Secrets and variables -> Actions）：
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`（可选）
3. 设置 Variables：
   - `MODEL_NAME`（默认 deepseek-chat）
   - `FEISHU_WEBHOOK`（可选，用于飞书推送）
4. 启用 GitHub Actions

工作流默认每天北京时间早 9 点运行。

## 输出示例

程序会生成 Markdown 文件，包含：
- 论文标题和链接
- 作者和机构
- AI 生成的中文总结
- 匹配的关键词

## License

MIT
