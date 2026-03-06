#!/usr/bin/env python3
"""
arXiv Daily Tracker - 抓取 paperBotV2 的论文汇总
不再调用 LLM API，直接复用 paperBotV2 的结果
"""

import os
import re
import json
import time
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PaperBotV2Tracker:
    """抓取 paperBotV2 的论文汇总"""
    
    # paperBotV2 的 GitHub 仓库信息
    PAPERBOT_REPO = "Doragd/Algorithm-Practice-in-Industry"
    PAPERBOT_RAW_URL = "https://raw.githubusercontent.com/Doragd/Algorithm-Practice-in-Industry/main"
    PAPERBOT_GITHUB_URL = "https://github.com/Doragd/Algorithm-Practice-in-Industry/blob/main"
    
    def __init__(self):
        self.feishu_urls = [url.strip() for url in os.getenv("FEISHU_URL", "").split(",") if url.strip()]
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
    
    def get_today_date_str(self) -> str:
        """获取今天的日期字符串"""
        return datetime.now(timezone.utc).strftime('%Y%m%d')
    
    def fetch_paperbot_data(self, date_str: str = None) -> Optional[Dict]:
        """
        从 paperBotV2 获取指定日期的论文数据
        
        paperBotV2 的数据结构：
        - paperBotV2/arxiv_daily/data/YYYYMMDD.json
        - 包含所有论文的详细信息（已粗排+精排）
        """
        if date_str is None:
            date_str = self.get_today_date_str()
        
        # 尝试获取今天的数据
        urls_to_try = [
            f"{self.PAPERBOT_RAW_URL}/paperBotV2/arxiv_daily/data/{date_str}.json",
            f"{self.PAPERBOT_RAW_URL}/paperBotV2/arxiv_daily/data/{date_str}_arxiv.json",
        ]
        
        # 如果没找到今天的，尝试昨天（因为时区差异）
        yesterday = datetime.now(timezone.utc) - __import__('datetime').timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y%m%d')
        urls_to_try.extend([
            f"{self.PAPERBOT_RAW_URL}/paperBotV2/arxiv_daily/data/{yesterday_str}.json",
            f"{self.PAPERBOT_RAW_URL}/paperBotV2/arxiv_daily/data/{yesterday_str}_arxiv.json",
        ])
        
        for url in urls_to_try:
            try:
                logger.info(f"尝试获取: {url}")
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"成功获取 {len(data)} 篇论文")
                    return data
            except Exception as e:
                logger.warning(f"获取失败: {e}")
                continue
        
        logger.error("无法获取 paperBotV2 数据")
        return None
    
    def fetch_paperbot_html(self, date_str: str = None) -> Optional[str]:
        """
        获取 paperBotV2 生成的 HTML 页面内容
        """
        if date_str is None:
            date_str = self.get_today_date_str()
        
        urls_to_try = [
            f"{self.PAPERBOT_RAW_URL}/paperBotV2/output/{date_str}.html",
            f"{self.PAPERBOT_RAW_URL}/paperBotV2/output/{date_str}_arxiv.html",
        ]
        
        yesterday = datetime.now(timezone.utc) - __import__('datetime').timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y%m%d')
        urls_to_try.extend([
            f"{self.PAPERBOT_RAW_URL}/paperBotV2/output/{yesterday_str}.html",
            f"{self.PAPERBOT_RAW_URL}/paperBotV2/output/{yesterday_str}_arxiv.html",
        ])
        
        for url in urls_to_try:
            try:
                logger.info(f"尝试获取 HTML: {url}")
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    logger.info(f"成功获取 HTML")
                    return response.text
            except Exception as e:
                logger.warning(f"获取失败: {e}")
                continue
        
        return None
    
    def parse_papers(self, data: Dict) -> List[Dict]:
        """
        解析 paperBotV2 的数据格式
        
        paperBotV2 的数据格式：
        {
            "arxiv_id": {
                "title": "...",
                "translation": "...",
                "url": "...",
                "authors": "...",
                "categories": "...",
                "pub_date": "...",
                "ori_summary": "...",
                "summary": "...",
                "relevance_score": 8,
                "rerank_relevance_score": 9,
                "is_fine_ranked": true,
                ...
            }
        }
        """
        papers = []
        for arxiv_id, paper_info in data.items():
            # 只保留精排过的论文（高质量）
            if paper_info.get('is_fine_ranked', False):
                papers.append({
                    'arxiv_id': arxiv_id,
                    'title': paper_info.get('title', ''),
                    'translation': paper_info.get('translation', ''),
                    'url': paper_info.get('url', f"https://www.alphaxiv.org/abs/{arxiv_id}"),
                    'authors': paper_info.get('authors', ''),
                    'categories': paper_info.get('categories', ''),
                    'pub_date': paper_info.get('pub_date', ''),
                    'summary': paper_info.get('summary', ''),
                    'relevance_score': paper_info.get('relevance_score', 0),
                    'rerank_relevance_score': paper_info.get('rerank_relevance_score', 0),
                    'rerank_reasoning': paper_info.get('rerank_reasoning', ''),
                })
        
        # 按精排分数排序
        papers.sort(key=lambda p: p['rerank_relevance_score'], reverse=True)
        
        logger.info(f"解析到 {len(papers)} 篇精排论文")
        return papers
    
    def save_html_archive(self, html_content: str, date_str: str = None):
        """保存 HTML 存档到本地"""
        if date_str is None:
            date_str = self.get_today_date_str()
        
        # 保存原始 HTML
        html_path = self.output_dir / f"{date_str}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # 同时保存为 Markdown（便于阅读）
        md_content = self.convert_html_to_md(html_content)
        md_path = self.output_dir / f"{date_str}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"HTML 存档已保存: {html_path}")
        return html_path, md_path
    
    def convert_html_to_md(self, html_content: str) -> str:
        """简单转换 HTML 为 Markdown"""
        # 提取标题
        title_match = re.search(r'<title>(.*?)</title>', html_content, re.DOTALL)
        title = title_match.group(1) if title_match else "arXiv 论文日报"
        
        # 提取正文（简化处理）
        # 移除 script 和 style
        content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
        
        # 转换常见标签
        content = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n\n', content, flags=re.DOTALL)
        content = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n\n', content, flags=re.DOTALL)
        content = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n\n', content, flags=re.DOTALL)
        content = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', content, flags=re.DOTALL)
        content = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', content, flags=re.DOTALL)
        content = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', content, flags=re.DOTALL)
        
        # 移除其他标签
        content = re.sub(r'<[^>]+>', '', content)
        
        # 清理空白
        content = re.sub(r'\n\n\n+', '\n\n', content)
        
        return f"# {title}\n\n{content.strip()}"
    
    def send_to_feishu(self, papers: List[Dict]):
        """
        使用 paperBotV2 的飞书卡片模板格式推送
        
        模板 ID: AAqxH62u1uNko (paperBotV2 的模板)
        """
        if not self.feishu_urls or not papers:
            logger.info("未配置飞书推送，跳过")
            return
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        # 构建 paperBotV2 格式的卡片数据
        card_data = {
            "type": "template",
            "data": {
                "template_id": "AAqxH62u1uNko",
                "template_version_name": "1.0.8",
                "template_variable": {
                    "loop": [],
                    "date": date_str
                }
            }
        }
        
        for p in papers[:20]:  # 最多推送 20 篇
            score = p.get('rerank_relevance_score', 0)
            score_formatted = "⭐️" * score + f" <text_tag color='blue'>{score}分</text_tag>" if score else "N/A"
            
            card_data['data']['template_variable']['loop'].append({
                "paper": f"[{p['title']}]({p['url']})",
                "translation": p.get('translation', 'N/A'),
                "score": score_formatted,
                "summary": p.get('summary', 'N/A')
            })
        
        card = json.dumps(card_data)
        body = json.dumps({"msg_type": "interactive", "card": card})
        headers = {"Content-Type": "application/json"}
        
        for url in self.feishu_urls:
            try:
                ret = requests.post(url=url, data=body, headers=headers, timeout=10)
                logger.info(f"飞书推送状态: {ret.status_code}")
                if ret.status_code != 200:
                    logger.error(f"飞书推送失败: {ret.text}")
            except Exception as e:
                logger.error(f"飞书推送失败: {e}")
    
    def run(self):
        """运行完整流程"""
        logger.info("=" * 60)
        logger.info("开始抓取 paperBotV2 的论文汇总")
        logger.info("=" * 60)
        
        date_str = self.get_today_date_str()
        
        # 1. 获取论文数据
        data = self.fetch_paperbot_data(date_str)
        if not data:
            logger.error("无法获取论文数据，结束")
            return
        
        # 2. 解析论文
        papers = self.parse_papers(data)
        if not papers:
            logger.info("没有精排论文，结束")
            return
        
        # 3. 获取 HTML 存档
        html_content = self.fetch_paperbot_html(date_str)
        if html_content:
            self.save_html_archive(html_content, date_str)
        else:
            # 如果没有 HTML，生成一个简单的
            logger.warning("未找到 HTML，生成简单版本")
            html_content = self.generate_simple_html(papers, date_str)
            self.save_html_archive(html_content, date_str)
        
        # 4. 保存 JSON 数据
        json_path = self.output_dir / f"{date_str}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)
        
        # 5. 飞书推送
        self.send_to_feishu(papers)
        
        logger.info("=" * 60)
        logger.info(f"完成！共处理 {len(papers)} 篇论文")
        logger.info("=" * 60)
    
    def generate_simple_html(self, papers: List[Dict], date_str: str) -> str:
        """生成简单的 HTML 页面"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>arXiv 论文日报 - {date_str}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
        h1 {{ color: #333; border-bottom: 2px solid #007acc; padding-bottom: 10px; }}
        .paper {{ background: #f8f9fa; border-left: 4px solid #007acc; padding: 15px; margin: 15px 0; border-radius: 4px; }}
        .title {{ font-size: 18px; font-weight: bold; color: #007acc; margin-bottom: 8px; }}
        .translation {{ font-size: 16px; color: #333; margin-bottom: 8px; }}
        .meta {{ color: #666; font-size: 14px; margin-bottom: 8px; }}
        .score {{ color: #ff6b6b; font-weight: bold; }}
        .summary {{ color: #555; margin-top: 10px; }}
        a {{ color: #007acc; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>📚 arXiv 论文日报 - {date_str}</h1>
    <p>共 {len(papers)} 篇高质量论文（来自 paperBotV2）</p>
"""
        
        for i, p in enumerate(papers, 1):
            stars = "⭐️" * p.get('rerank_relevance_score', 0)
            html += f"""
    <div class="paper">
        <div class="title">{i}. <a href="{p['url']}">{p['title']}</a></div>
        <div class="translation">{p.get('translation', '')}</div>
        <div class="meta">
            <span class="score">{stars} ({p.get('rerank_relevance_score', 0)}/10)</span> | 
            作者: {p.get('authors', 'N/A')} | 
            分类: {p.get('categories', 'N/A')}
        </div>
        <div class="summary">{p.get('summary', '')}</div>
    </div>
"""
        
        html += """
</body>
</html>
"""
        return html


def main():
    tracker = PaperBotV2Tracker()
    tracker.run()


if __name__ == '__main__':
    main()
