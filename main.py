#!/usr/bin/env python3
"""
arXiv Daily Tracker - 每天获取指定公司和研究方向的最新论文
"""

import os
import re
import json
import yaml
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path

import arxiv
import feedparser
import requests
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """论文数据结构"""
    arxiv_id: str
    title: str
    authors: List[str]
    abstract: str
    published: datetime
    primary_category: str
    categories: List[str]
    pdf_url: str
    arxiv_url: str
    
    # 匹配信息
    matched_companies: List[str] = None
    matched_keywords: List[str] = None
    summary: str = None
    
    def __post_init__(self):
        if self.matched_companies is None:
            self.matched_companies = []
        if self.matched_keywords is None:
            self.matched_keywords = []


class ArxivTracker:
    """arXiv 论文追踪器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.client = self._init_openai_client()
        
        # 编译正则表达式以提高性能
        self.company_patterns = self._compile_patterns(self.config['subscriptions']['companies'])
        self.keyword_patterns = self._compile_patterns(self.config['subscriptions']['keywords'])
    
    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _init_openai_client(self) -> Optional[OpenAI]:
        """初始化 OpenAI 客户端"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("未设置 OPENAI_API_KEY，将跳过 AI 总结")
            return None
        
        base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
        return OpenAI(api_key=api_key, base_url=base_url)
    
    def _compile_patterns(self, patterns: List[str]) -> List[re.Pattern]:
        """编译正则表达式模式"""
        compiled = []
        for pattern in patterns:
            # 使用单词边界匹配，不区分大小写
            escaped = re.escape(pattern)
            compiled.append(re.compile(r'\b' + escaped + r'\b', re.IGNORECASE))
        return compiled
    
    def _match_patterns(self, text: str, patterns: List[re.Pattern]) -> List[str]:
        """在文本中匹配模式"""
        matches = set()
        for pattern in patterns:
            for match in pattern.finditer(text):
                matches.add(match.group().lower())
        return list(matches)
    
    def fetch_papers(self, days_back: int = 1) -> List[Paper]:
        """
        获取指定天数内的 arXiv 论文
        
        Args:
            days_back: 获取最近几天的论文（默认1天）
        """
        papers = []
        categories = self.config['subscriptions']['categories']
        
        # 计算日期范围（使用 UTC 时区）
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"开始获取 {start_date.date()} 到 {end_date.date()} 的论文...")
        logger.info(f"目标分类: {categories}")
        
        for category in categories:
            try:
                logger.info(f"正在获取分类 {category} 的论文...")
                
                # 使用 arxiv 库搜索
                search = arxiv.Search(
                    query=f"cat:{category}",
                    max_results=self.config['output']['max_papers_per_day'],
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending,
                )
                
                for result in search.results():
                    # 只获取指定日期范围内的论文
                    if result.published < start_date:
                        break
                    
                    paper = Paper(
                        arxiv_id=result.entry_id.split('/')[-1],
                        title=result.title,
                        authors=[str(a) for a in result.authors],
                        abstract=result.summary,
                        published=result.published,
                        primary_category=result.primary_category,
                        categories=result.categories,
                        pdf_url=result.pdf_url,
                        arxiv_url=result.entry_id
                    )
                    papers.append(paper)
                    
            except Exception as e:
                logger.error(f"获取分类 {category} 时出错: {e}")
                continue
        
        logger.info(f"共获取 {len(papers)} 篇论文")
        return papers
    
    def filter_papers(self, papers: List[Paper]) -> List[Paper]:
        """
        根据公司和关键词筛选论文
        """
        filtered = []
        
        for paper in papers:
            # 构建搜索文本
            search_text = f"{paper.title} {paper.abstract} {' '.join(paper.authors)}"
            
            # 匹配公司
            matched_companies = self._match_patterns(search_text, self.company_patterns)
            
            # 匹配关键词
            matched_keywords = self._match_patterns(search_text, self.keyword_patterns)
            
            # 如果匹配到公司或关键词，则保留
            if matched_companies or matched_keywords:
                paper.matched_companies = matched_companies
                paper.matched_keywords = matched_keywords
                filtered.append(paper)
        
        logger.info(f"筛选后剩余 {len(filtered)} 篇相关论文")
        return filtered
    
    def summarize_paper(self, paper: Paper) -> str:
        """
        使用 AI 总结论文
        """
        if not self.client:
            return ""
        
        try:
            lang = self.config['summary']['language']
            max_length = self.config['summary']['max_length']
            
            if lang == 'zh':
                prompt = f"""请用中文总结以下学术论文的核心内容，限制在 {max_length} 字以内：

标题：{paper.title}

摘要：{paper.abstract}

请总结：
1. 研究问题和动机
2. 主要方法/贡献
3. 实验结果或关键发现

用简洁的 bullet points 格式输出。"""
            else:
                prompt = f"""Please summarize the following academic paper in {max_length} characters or less:

Title: {paper.title}

Abstract: {paper.abstract}

Summarize:
1. Research problem and motivation
2. Main method/contribution
3. Key findings or results

Use concise bullet points."""
            
            response = self.client.chat.completions.create(
                model=os.getenv('MODEL_NAME', 'deepseek-chat'),
                messages=[
                    {"role": "system", "content": "You are an expert in computer science research, specializing in information retrieval and recommendation systems."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config['summary']['temperature'],
                max_tokens=800
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"总结论文 {paper.arxiv_id} 时出错: {e}")
            return ""
    
    def generate_markdown(self, papers: List[Paper], date: datetime = None) -> str:
        """
        生成 Markdown 格式的报告
        """
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime("%Y-%m-%d")
        
        md = f"""# arXiv 论文日报 - {date_str}

> 自动追踪推荐系统和搜索方向的最新研究

## 筛选条件

- **关注公司**: {', '.join(self.config['subscriptions']['companies'][:10])}...
- **研究方向**: {', '.join(self.config['subscriptions']['keywords'][:10])}...

## 今日发现 ({len(papers)} 篇)

"""
        
        for i, paper in enumerate(papers, 1):
            md += f"""### {i}. {paper.title}

**作者**: {', '.join(paper.authors[:5])}{'...' if len(paper.authors) > 5 else ''}

**arXiv**: [{paper.arxiv_id}]({paper.arxiv_url}) | [PDF]({paper.pdf_url})

**分类**: {paper.primary_category}

**匹配标签**:
"""
            if paper.matched_companies:
                md += f"- 🏢 公司: {', '.join(paper.matched_companies)}\n"
            if paper.matched_keywords:
                md += f"- 🔑 关键词: {', '.join(paper.matched_keywords)}\n"
            
            md += f"\n**AI 总结**:\n\n{paper.summary or '暂无总结'}\n\n---\n\n"
        
        return md
    
    def save_results(self, papers: List[Paper], date: datetime = None):
        """
        保存结果到文件
        """
        if date is None:
            date = datetime.now()
        
        output_dir = Path(self.config['output']['directory'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        date_str = date.strftime("%Y-%m-%d")
        
        # 保存 Markdown
        if self.config['output']['format'] == 'markdown':
            md_content = self.generate_markdown(papers, date)
            md_path = output_dir / f"{date_str}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            logger.info(f"Markdown 报告已保存: {md_path}")
        
        # 保存 JSON
        json_path = output_dir / f"{date_str}.json"
        papers_data = [asdict(p) for p in papers]
        # 转换 datetime 为字符串
        for p in papers_data:
            p['published'] = p['published'].isoformat()
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(papers_data, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON 数据已保存: {json_path}")
    
    def send_notification(self, papers: List[Paper]):
        """
        发送通知（飞书等）
        """
        # 飞书推送
        webhook = os.getenv('FEISHU_WEBHOOK')
        if webhook and papers:
            try:
                date_str = datetime.now().strftime("%Y-%m-%d")
                
                # 构建飞书卡片消息
                content = f"今日发现 {len(papers)} 篇相关论文\n\n"
                for i, paper in enumerate(papers[:5], 1):  # 只显示前5篇
                    content += f"{i}. {paper.title}\n"
                    if paper.matched_companies:
                        content += f"   公司: {', '.join(paper.matched_companies)}\n"
                    content += f"   {paper.arxiv_url}\n\n"
                
                message = {
                    "msg_type": "text",
                    "content": {
                        "text": f"📚 arXiv 论文日报 ({date_str})\n\n{content}"
                    }
                }
                
                response = requests.post(webhook, json=message, timeout=10)
                if response.status_code == 200:
                    logger.info("飞书通知发送成功")
                else:
                    logger.error(f"飞书通知发送失败: {response.text}")
                    
            except Exception as e:
                logger.error(f"发送飞书通知时出错: {e}")
    
    def run(self, days_back: int = 1, skip_summary: bool = False):
        """
        运行完整流程
        
        Args:
            days_back: 获取最近几天的论文
            skip_summary: 是否跳过 AI 总结（用于测试）
        """
        logger.info("=" * 50)
        logger.info("开始运行 arXiv Daily Tracker")
        logger.info("=" * 50)
        
        # 1. 获取论文
        papers = self.fetch_papers(days_back)
        
        if not papers:
            logger.info("未找到新论文")
            return
        
        # 2. 筛选论文
        filtered_papers = self.filter_papers(papers)
        
        if not filtered_papers:
            logger.info("没有匹配到相关论文")
            return
        
        # 3. AI 总结
        if not skip_summary and self.client:
            logger.info("开始 AI 总结...")
            for i, paper in enumerate(filtered_papers):
                logger.info(f"总结论文 {i+1}/{len(filtered_papers)}: {paper.arxiv_id}")
                paper.summary = self.summarize_paper(paper)
        
        # 4. 保存结果
        self.save_results(filtered_papers)
        
        # 5. 发送通知
        self.send_notification(filtered_papers)
        
        logger.info("=" * 50)
        logger.info(f"运行完成！共处理 {len(filtered_papers)} 篇相关论文")
        logger.info("=" * 50)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='arXiv Daily Tracker')
    parser.add_argument('--days', type=int, default=1, help='获取最近几天的论文 (默认: 1)')
    parser.add_argument('--skip-summary', action='store_true', help='跳过 AI 总结')
    parser.add_argument('--config', type=str, default='config.yaml', help='配置文件路径')
    
    args = parser.parse_args()
    
    tracker = ArxivTracker(config_path=args.config)
    tracker.run(days_back=args.days, skip_summary=args.skip_summary)


if __name__ == '__main__':
    main()
