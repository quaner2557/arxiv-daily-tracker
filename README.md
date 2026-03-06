# arXiv Daily Tracker

基于 [paperBotV2](https://github.com/Doragd/Algorithm-Practice-in-Industry/tree/main/paperBotV2) 的论文汇总，不再调用 LLM API，直接抓取已筛选的高质量论文。

## 工作原理

1. **抓取数据**：每天从 paperBotV2 的 GitHub 仓库抓取已粗排+精排的论文数据
2. **飞书推送**：使用 paperBotV2 的飞书卡片模板推送消息
3. **本地存档**：将 HTML 网页存档到自己的 GitHub 仓库

## 数据来源

- **原始数据**: [Doragd/Algorithm-Practice-in-Industry/paperBotV2](https://github.com/Doragd/Algorithm-Practice-in-Industry/tree/main/paperBotV2)
- **数据格式**: JSON（包含论文标题、翻译、评分、总结等）
- **更新频率**: 每天自动抓取

## 配置

### 必需配置（GitHub Secrets）

| Secret | 说明 |
|--------|------|
| `FEISHU_URL` | 飞书机器人 Webhook 地址 |

### 可选配置

无需其他配置，程序会自动抓取 paperBotV2 的数据。

## 输出

运行后会生成以下文件到 `output/` 目录：

- `YYYYMMDD.html` - HTML 格式存档（可直接在浏览器打开）
- `YYYYMMDD.md` - Markdown 格式（便于阅读）
- `YYYYMMDD.json` - JSON 格式数据

## 与原版区别

| 功能 | 原版 | 本版本 |
|------|------|--------|
| LLM API 调用 | ✅ 需要 | ❌ 不需要 |
| 数据来源 | arXiv API | paperBotV2 已筛选数据 |
| 费用 | 有（API 调用费） | 无 |
| 飞书模板 | paperBotV2 模板 | paperBotV2 模板 |

## 感谢

- [paperBotV2](https://github.com/Doragd/Algorithm-Practice-in-Industry/tree/main/paperBotV2) - 提供论文筛选和飞书模板
