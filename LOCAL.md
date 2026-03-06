# 本地运行

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

1. 复制环境变量文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的 API Key：
```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-chat
```

3. （可选）配置飞书推送：
```
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

4. 根据需要编辑 `config.yaml` 调整公司和关键词

## 运行

```bash
# 获取今天的论文
python main.py

# 获取最近 3 天的论文
python main.py --days 3

# 跳过 AI 总结（测试用）
python main.py --skip-summary
```

## 输出

结果会保存在 `output/` 目录：
- `YYYY-MM-DD.md` - Markdown 格式报告
- `YYYY-MM-DD.json` - JSON 格式数据
