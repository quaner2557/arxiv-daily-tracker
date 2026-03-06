#!/usr/bin/env python3
"""
arXiv Daily Tracker - 基于 paperBotV2 的实现
使用 AI 粗排 + 精排筛选高质量论文
"""

import os
import re
import json
import time
import logging
import requests
import feedparser
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path

from openai import OpenAI
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_random_exponential
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ Prompt 模板（完全复用 paperBotV2）============

PRERANK_PROMPT = """
# Role
You are a highly experienced Research Engineer specializing in Large Language Models (LLMs) and Large-Scale Recommendation Systems, with deep knowledge of the search, recommendation, and advertising domains.

# My Current Focus

- **Core Domain Advances:** Core advances within RecSys, Search, or Ads itself, even if they do not involve LLMs.
- **Enabling LLM Tech:** Trends and Foundational progress in the core LLM which must have potential applications in RecSys, Search or Ads.
- **Enabling Transformer Tech:** Advances in Transformer architecture (e.g., efficiency, new attention mechanisms, MoE, etc.).
- **Direct LLM Applications:** Novel ideas and direct applications of LLM technology for RecSys, Search or Ads.
- **VLM Analogy for Heterogeneous Data:** Ideas inspired by **Vision-Language Models** that treat heterogeneous data (like context features and user sequences) as distinct modalities for unified modeling. 

# Irrelevant Topics
- Fingerprint, Federated learning, Security, Privacy, Fairness, Ethics, or other non-technical topics
- Medical, Biology, Chemistry, Physics or other domain-specific applications
- Neural Architectures Search (NAS) or general AutoML
- Purely theoretical papers without clear practical implications
- Hallucination, Evaluation benchmarks, or other purely NLP-centric topics
- Purely Vision, 3D Vision, Graphic or Speech papers without clear relevance to RecSys/Search/Ads
- Ads creative generation, auction, bidding or other Non-Ranking Ads topics 
- AIGC, Content generation, Summarization, or other purely LLM-centric topics
- Reinforcement Learning (RL) papers without clear relevance to RecSys/Search/Ads

# Goal
Screen new papers based on my focus. **DO NOT include irrelevant topics**.

# Task
Based ONLY on the paper's title, provide a quick evaluation.
1. **Academic Translation**: Translate the title into professional Chinese, prioritizing accurate technical terms and faithful meaning.
2. **Relevance Score (1-10)**: How relevant is it to **My Current Focus**?
3. **Reasoning**: A 2-3 sentence explanation for your score. **For "Enabling Tech" papers, you MUST explain their potential application in RecSys/Search/Ads.**

# Input Paper
- **Title**: {title}

# Output Format
Provide your analysis strictly in the following JSON format.
{{
  "translation": "...",
  "relevance_score": <integer>,
  "reasoning": "..."
}}
"""

FINERANK_PROMPT = """
# Role
You are a highly experienced Research Engineer specializing in Large Language Models (LLMs) and Large-Scale Recommendation Systems, with deep knowledge of the search, recommendation, and advertising domains.

# My Current Focus

- **Core Domain Advances:** Core advances within RecSys, Search, or Ads itself, even if they do not involve LLMs.
- **Enabling LLM Tech:** Trends and Foundational progress in the core LLM which must have potential applications in RecSys, Search or Ads.
- **Enabling Transformer Tech:** Advances in Transformer architecture (e.g., efficiency, new attention mechanisms, MoE, etc.).
- **Direct LLM Applications:** Novel ideas and direct applications of LLM technology for RecSys, Search or Ads.
- **VLM Analogy for Heterogeneous Data:** Ideas inspired by **Vision-Language Models** that treat heterogeneous data (like context features and user sequences) as distinct modalities for unified modeling. 

# Goal
Perform a detailed analysis of the provided paper based on its title and abstract. Identify its core contributions and relevance to my focus areas.

# Task
Based on the paper's **Title** and **Abstract**, provide a comprehensive analysis.
1.  **Relevance Score (1-10)**: Re-evaluate the relevance score (1-10) based on the detailed information in the abstract.
2.  **Reasoning**: A 1-2 sentence explanation for your score in Chinese, direct and compact, no filter phrases.
3.  **Summary**: Generate a 1-2 sentence, ultra-high-density Chinese summary focusing solely on the paper's core idea, to judge if its "idea" is interesting. The summary must precisely distill and answer these two questions:
    1.  **Topic:** What core problem is the paper studying or solving?
    2.  **Core Idea:** What is its core method, key idea, or main analytical conclusion?
    **STRICTLY IGNORE EXPERIMENTAL RESULTS:** Do not include any information about performance, SOTA, dataset metrics, or numerical improvements.
    **FOCUS ON THE "IDEA":** Your sole purpose is to clearly convey the paper's "core idea," not its "experimental achievements."

# Input Paper
- **Title**: {title}
- **Abstract**: {summary}

# Output Format
Provide your analysis strictly in the following JSON format.
{{
  "rerank_relevance_score": <integer>,
  "rerank_reasoning": "...",
  "summary": "..."
}}
"""


@dataclass
class Paper:
    """论文数据结构"""
    arxiv_id: str
    title: str
    authors: str
    categories: str
    pub_date: str
    url: str
    ori_summary: str
    
    # AI 分析结果
    translation: str = ""
    relevance_score: int = 0
    reasoning: str = ""
    rerank_relevance_score: int = 0
    rerank_reasoning: str = ""
    summary: str = ""
    
    # 状态标记
    is_filtered: bool = False
    is_fine_ranked: bool = False


class ArxivTracker:
    """arXiv 论文追踪器 - 基于 paperBotV2 实现"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
        self.model = os.getenv("MODEL_NAME", "deepseek-chat")
        
        # 配置参数
        self.target_categories = [cat.strip() for cat in os.getenv("TARGET_CATEGORYS", "cs.IR,cs.CL,cs.AI").split(",")]
        self.max_papers = int(os.getenv("MAX_PAPERS", "100"))
        self.rough_score_threshold = int(os.getenv("ROUGH_SCORE_THRESHOLD", "4"))
        self.return_papers = int(os.getenv("RETURN_PAPERS", "20"))
        self.feishu_urls = [url.strip() for url in os.getenv("FEISHU_URL", "").split(",") if url.strip()]
        
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
    
    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(5))
    def call_llm_api(self, prompt_content: str) -> Optional[Dict]:
        """调用 LLM API 并返回 JSON 结果"""
        if not self.client:
            logger.error("LLM 客户端未初始化")
            return None
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt_content}],
                response_format={'type': 'json_object'}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"调用 API 失败: {e}")
            raise
    
    def fetch_daily_papers(self, category: str) -> Dict[str, Paper]:
        """获取指定分类的当天论文"""
        base_url = 'http://export.arxiv.org/api/query?'
        
        # 计算日期范围
        today_utc = datetime.now(timezone.utc)
        start_of_day = today_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_utc = start_of_day - timedelta(days=1)
        
        search_query = f'cat:{category} AND submittedDate:[{yesterday_utc.strftime("%Y%m%d%H%M%S")} TO {today_utc.strftime("%Y%m%d%H%M%S")}]'
        
        query_params = {
            'search_query': search_query,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending',
            'start': 0,
            'max_results': self.max_papers
        }
        
        try:
            response = requests.get(base_url, params=query_params, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return {}
        
        feed = feedparser.parse(response.content)
        papers = {}
        
        logger.info(f"分类 '{category}' 中找到 {len(feed.entries)} 篇论文")
        
        for entry in feed.entries:
            title = re.sub(r'\s+', ' ', entry.title.replace('\n', ' ').strip())
            arxiv_id = entry.id.split('/abs/')[-1]
            authors = ', '.join(author.name for author in entry.authors)
            summary = re.sub(r'\s+', ' ', entry.summary.replace('\n', ' ').strip())
            published = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d %H:%M:%S')
            categories = ', '.join(tag.term for tag in entry.tags)
            url = f"https://www.alphaxiv.org/abs/{arxiv_id}"
            
            papers[arxiv_id] = Paper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                categories=categories,
                pub_date=published,
                url=url,
                ori_summary=summary
            )
        
        return papers
    
    def rough_analyze_paper(self, paper: Paper) -> Optional[Paper]:
        """粗排：基于标题分析"""
        prompt = PRERANK_PROMPT.format(title=paper.title)
        result = self.call_llm_api(prompt)
        
        if result:
            paper.translation = result.get('translation', '')
            paper.relevance_score = result.get('relevance_score', 0)
            paper.reasoning = result.get('reasoning', '')
            return paper
        return None
    
    def rough_rank_papers(self, papers: Dict[str, Paper]) -> List[Paper]:
        """并发粗排"""
        analyzed = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_paper = {
                executor.submit(self.rough_analyze_paper, paper): paper 
                for paper in papers.values()
            }
            
            logger.info(f"开始粗排 {len(papers)} 篇论文...")
            
            for future in tqdm(as_completed(future_to_paper), total=len(papers), desc="粗排进度"):
                try:
                    result = future.result()
                    if result:
                        analyzed.append(result)
                except Exception as e:
                    logger.warning(f"分析失败: {e}")
        
        # 按分数排序
        analyzed.sort(key=lambda p: p.relevance_score, reverse=True)
        
        # 打印预览
        logger.info("\n--- 粗排结果预览 ---")
        for p in analyzed[:10]:
            logger.info(f"[{p.relevance_score}/10] {p.translation}")
        
        # 过滤低分
        filtered = [p for p in analyzed if p.relevance_score >= self.rough_score_threshold]
        logger.info(f"\n粗排: {len(analyzed)} 篇 -> 过滤后 {len(filtered)} 篇 (阈值: {self.rough_score_threshold})")
        
        return filtered
    
    def fine_analyze_paper(self, paper: Paper) -> Optional[Paper]:
        """精排：基于标题+摘要分析"""
        prompt = FINERANK_PROMPT.format(title=paper.title, summary=paper.ori_summary)
        result = self.call_llm_api(prompt)
        
        if result:
            paper.rerank_relevance_score = result.get('rerank_relevance_score', 0)
            paper.rerank_reasoning = result.get('rerank_reasoning', '')
            paper.summary = result.get('summary', '')
            paper.is_fine_ranked = True
            return paper
        return None
    
    def fine_rank_papers(self, papers: List[Paper]) -> List[Paper]:
        """并发精排"""
        # 只精排前 N 篇
        papers_to_rank = papers[:self.return_papers]
        
        analyzed = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_paper = {
                executor.submit(self.fine_analyze_paper, paper): paper 
                for paper in papers_to_rank
            }
            
            logger.info(f"开始精排 {len(papers_to_rank)} 篇论文...")
            
            for future in tqdm(as_completed(future_to_paper), total=len(papers_to_rank), desc="精排进度"):
                try:
                    result = future.result()
                    if result:
                        analyzed.append(result)
                except Exception as e:
                    logger.warning(f"精排失败: {e}")
        
        # 按精排分数排序
        analyzed.sort(key=lambda p: p.rerank_relevance_score, reverse=True)
        
        logger.info(f"\n精排完成: {len(analyzed)} 篇")
        return analyzed
    
    def save_results(self, all_papers: Dict[str, Paper], final_papers: List[Paper]):
        """保存结果到 JSON 和 Markdown"""
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        date_str = datetime.now().strftime('%Y%m%d')
        
        # 保存所有论文的 JSON
        all_data = {p.arxiv_id: asdict(p) for p in all_papers.values()}
        with open(output_dir / f"{date_str}.json", 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        # 保存精排结果的 Markdown
        md_content = self.generate_markdown(final_papers)
        with open(output_dir / f"{date_str}.md", 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"结果已保存到 output/{date_str}.json 和 output/{date_str}.md")
    
    def generate_markdown(self, papers: List[Paper]) -> str:
        """生成 Markdown 报告"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        md = f"""# arXiv 论文日报 - {date_str}

> 基于 AI 粗排+精排筛选的高质量论文

## 今日精选 ({len(papers)} 篇)

"""
        
        for i, p in enumerate(papers, 1):
            stars = "⭐️" * p.rerank_relevance_score if p.rerank_relevance_score else "N/A"
            md += f"""### {i}. {p.translation}

**原文标题**: [{p.title}]({p.url})

**作者**: {p.authors}

**评分**: {stars} ({p.rerank_relevance_score}/10)

**分类**: {p.categories}

**核心总结**:
{p.summary}

**评分理由**:
{p.rerank_reasoning}

---

"""
        
        return md
    
    def send_to_feishu(self, papers: List[Paper]):
        """发送飞书卡片消息"""
        if not self.feishu_urls or not papers:
            logger.info("未配置飞书推送，跳过")
            return
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        # 构建卡片数据（复用 paperBotV2 的模板格式）
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
        
        for p in papers:
            score = p.rerank_relevance_score
            score_formatted = "⭐️" * score + f" <text_tag color='blue'>{score}分</text_tag>" if score else "N/A"
            
            card_data['data']['template_variable']['loop'].append({
                "paper": f"[{p.title}]({p.url})",
                "translation": p.translation or "N/A",
                "score": score_formatted,
                "summary": p.summary or "N/A"
            })
        
        card = json.dumps(card_data)
        body = json.dumps({"msg_type": "interactive", "card": card})
        headers = {"Content-Type": "application/json"}
        
        for url in self.feishu_urls:
            try:
                ret = requests.post(url=url, data=body, headers=headers, timeout=10)
                logger.info(f"飞书推送状态: {ret.status_code}")
            except Exception as e:
                logger.error(f"飞书推送失败: {e}")
    
    def run(self):
        """运行完整流程"""
        logger.info("=" * 60)
        logger.info("开始运行 arXiv Daily Tracker")
        logger.info(f"目标分类: {self.target_categories}")
        logger.info("=" * 60)
        
        # 1. 获取所有分类的论文
        all_papers = {}
        for category in self.target_categories:
            papers = self.fetch_daily_papers(category)
            all_papers.update(papers)
            time.sleep(3)  # 避免请求过快
        
        logger.info(f"\n共获取 {len(all_papers)} 篇论文")
        
        if not all_papers:
            logger.info("没有新论文，结束")
            return
        
        # 2. 粗排
        filtered_papers = self.rough_rank_papers(all_papers)
        
        # 更新状态
        for p in filtered_papers:
            all_papers[p.arxiv_id].is_filtered = True
        
        if not filtered_papers:
            logger.info("粗排后没有符合条件的论文")
            return
        
        # 3. 精排
        final_papers = self.fine_rank_papers(filtered_papers)
        
        # 更新状态
        for p in final_papers:
            all_papers[p.arxiv_id].rerank_relevance_score = p.rerank_relevance_score
            all_papers[p.arxiv_id].rerank_reasoning = p.rerank_reasoning
            all_papers[p.arxiv_id].summary = p.summary
            all_papers[p.arxiv_id].is_fine_ranked = True
        
        # 4. 保存结果
        self.save_results(all_papers, final_papers)
        
        # 5. 发送飞书通知
        self.send_to_feishu(final_papers)
        
        logger.info("=" * 60)
        logger.info(f"完成！共处理 {len(final_papers)} 篇高质量论文")
        logger.info("=" * 60)


def main():
    tracker = ArxivTracker()
    tracker.run()


if __name__ == '__main__':
    main()
