# GitHub Actions 部署

## 1. Fork 仓库

点击右上角的 "Fork" 按钮，将仓库复制到你的 GitHub 账号下。

## 2. 配置 Secrets

进入你的 Fork 仓库 -> Settings -> Secrets and variables -> Actions

### 添加 Secrets（加密数据）：

| Secret 名称 | 说明 | 示例 |
|------------|------|------|
| `OPENAI_API_KEY` | AI 服务的 API Key | sk-xxx... |
| `OPENAI_BASE_URL` | （可选）API 基础 URL | https://api.deepseek.com/v1 |
| `FEISHU_WEBHOOK` | （可选）飞书机器人 Webhook | https://open.feishu.cn/... |

### 添加 Variables（非加密数据）：

进入 Settings -> Secrets and variables -> Actions -> Variables

| Variable 名称 | 说明 | 默认值 |
|--------------|------|--------|
| `MODEL_NAME` | AI 模型名称 | deepseek-chat |

## 3. 自定义配置

编辑 `config.yaml` 文件，修改：

- **companies**: 你想关注的公司列表
- **keywords**: 研究方向关键词
- **categories**: arXiv 分类

提交更改：
```bash
git add config.yaml
git commit -m "Update subscription config"
git push
```

## 4. 启用 GitHub Actions

进入 Actions 标签页，点击 "I understand my workflows, go ahead and enable them"。

## 5. 测试运行

进入 Actions -> arXiv Daily Tracker -> Run workflow，点击运行测试。

## 6. 查看结果

- 运行完成后，结果会自动提交到 `output/` 目录
- 可以在 Actions 的 Artifacts 中下载结果
- 如果配置了飞书 Webhook，会收到推送通知

## 定时运行

工作流默认每天北京时间 9:00 自动运行，如需修改，编辑 `.github/workflows/arxiv-tracker.yml` 中的 cron 表达式：

```yaml
on:
  schedule:
    - cron: '0 1 * * *'  # UTC 1:00 = 北京时间 9:00
```

## 费用说明

- **GitHub Actions**: 免费版每月 2000 分钟，足够使用
- **AI 总结**: 取决于你的 API 提供商，DeepSeek 约 0.2 元/天
