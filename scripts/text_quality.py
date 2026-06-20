"""Heuristics for filtering comment-like text vs page chrome / news."""
import re
from typing import Iterable

BOILERPLATE_MARKERS = (
    '东方财富 扫一扫下载APP',
    '版权所有:东方财富网',
    'SINA Corporation',
    '扫码下载雪球App',
    '沪ICP备05006054号',
    '信息网络传播视听节目许可证',
    '新浪财经意见反馈留言板',
    'Copyright © 1996',
    '天天基金网微博',
    '东方财富网微博',
    '违法和不良信息举报',
    '关于我们',
    '可持续发展',
    '广告服务',
    '诚聘英才',
    '法律声明',
    '隐私保护',
)

GUBA_NAV_TOKENS = (
    '股吧首页 >',
    '返回',
    '帖子正文',
    '分享到：',
)

MOJIBAKE_RE = re.compile(r'[ÃÂæåèéêëìíîïðñòóôõöùúûüýÿ]{4,}')


def strip_boilerplate(text: str, *, max_len: int = 800) -> str:
    """Remove eastmoney/guba page chrome and keep user comment text."""
    if not text or not str(text).strip():
        return ''
    s = re.sub(r'\s+', ' ', str(text)).strip()
    if not s:
        return ''

    cut_at = len(s)
    for marker in BOILERPLATE_MARKERS:
        idx = s.find(marker)
        if idx >= 0:
            cut_at = min(cut_at, idx)
    s = s[:cut_at].strip()

    for token in GUBA_NAV_TOKENS:
        while token in s:
            s = s.split(token, 1)[-1].strip(' >|')

    # breadcrumb tail after last "吧 >"
    if '吧 >' in s:
        s = s.rsplit('吧 >', 1)[-1].strip()

    if is_boilerplate(s):
        return ''
    if len(s) > max_len:
        return s[:max_len]
    return s


def is_boilerplate(text: str) -> bool:
    if not text or not str(text).strip():
        return True
    s = str(text).strip()
    if any(m in s for m in BOILERPLATE_MARKERS):
        return True
    if s.count('东方财富') >= 2 and len(s) > 200:
        return True
    return False


def is_mojibake(text: str) -> bool:
    if not text:
        return False
    s = str(text)
    if MOJIBAKE_RE.search(s):
        return True
    # common UTF-8 read as latin1 pattern
    return 'Ã' in s or 'Â' in s or 'å' in s[:80]


def is_log_metadata(text: str) -> bool:
    if not text:
        return True
    s = str(text).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', s):
        return True
    if 'stub://' in s:
        return True
    if 'realstock/company' in s and len(s) < 300:
        return True
    if s.startswith('http') and len(s) < 200:
        return True
    return False


NEWS_TITLE_CUES = (
    '公告', '发布', '券商', '涨超', '概念涨', '涨1.', '涨0.', 'ETF', '基金', '医院', '品牌',
    '持股比例', '一季度', '营业收入', '回购股份', '摩根大通', '主力资金净流入',
    '指数期货', '标普', '纳斯达克', '道指', '恒生', '转跌', '转涨', '收涨', '收跌',
    '元/股', '收盘', '涨停', '跌停', '签约', '获批', '据悉', '报道', '财联社',
)


def is_user_comment(text: str, platform: str = '', url: str = '') -> bool:
    """True when text looks like discussable opinion, not syndicated news."""
    if not text or len(str(text).strip()) < 8:
        return False
    if is_log_metadata(text):
        return False
    if is_news_article(text, platform=platform, url=url):
        return False
    if is_news_headline(text, platform=platform):
        return False
    s = str(text).strip()
    macro_cues = (
        '指数期货', '标普500', '纳斯达克', '道指', '恒生指数', '主力净流入', '北向资金',
    )
    if len(s) < 100 and any(c in s for c in macro_cues):
        return False
    if re.match(r'^[^：:]{2,24}[：:][^。！？]{4,60}$', s):
        opinion_markers = (
            '认为', '看好', '看空', '建议', '我觉得', '分析', '预测', '担心',
            '期待', '加仓', '减仓', '持有', '买入', '卖出', '金叉', '死叉',
        )
        if not any(m in s for m in opinion_markers):
            return False
    return True


def is_news_headline(text: str, platform: str = '') -> bool:
    if not text:
        return False
    s = str(text).strip()
    if platform == 'sina_finance':
        return True
    if len(s) > 120:
        return True
    short_news = (
        '指数期货', '标普', '纳斯达克', '道指', '收涨', '收跌', '收盘', '元/股', '涨停', '跌停',
    )
    if any(c in s for c in short_news):
        return True
    return sum(1 for c in NEWS_TITLE_CUES if c in s) >= 1


def is_stock_or_search_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    u = url.lower()
    patterns = (
        'xueqiu.com/s/',
        'realstock/company',
        's.weibo.com/weibo?q=',
        '/company/sh',
        '/company/sz',
    )
    return any(p in u for p in patterns)


def is_news_article(text: str, platform: str = '', url: str = '') -> bool:
    if not text:
        return False
    s = str(text)
    if platform == 'sina_finance' and len(s) > 400:
        return True
    if 'finance.sina.com.cn' in str(url) and len(s) > 400:
        return True
    news_cues = ('记者', '本报讯', '公告显示', '证券时报记者', '财联社', '中新社')
    if len(s) > 600 and sum(1 for c in news_cues if c in s) >= 2:
        return True
    return False


def pick_comment_text(text: str, title: str = '', content: str = '', summary: str = '') -> str:
    """Prefer the shortest non-boilerplate field that looks like a user comment."""
    candidates: Iterable[str] = (
        str(title or '').strip(),
        str(text or '').strip(),
        str(content or '').strip(),
        str(summary or '').strip(),
    )
    clean = [
        strip_boilerplate(c) or c
        for c in candidates
        if c and not is_mojibake(c)
    ]
    clean = [c for c in clean if c and not is_boilerplate(c)]
    if not clean:
        for c in candidates:
            stripped = strip_boilerplate(str(c))
            if stripped:
                return stripped
        return str(title or text or '').strip()
    clean.sort(key=len)
    return clean[0]


def quality_issues(text: str, title: str = '', platform: str = '', url: str = '') -> list[str]:
    issues: list[str] = []
    body = pick_comment_text(text, title=title)
    if is_stock_or_search_url(url):
        issues.append('stock_or_search_url')
    if is_boilerplate(str(text)) and is_boilerplate(str(title)):
        issues.append('boilerplate')
    elif is_boilerplate(str(text)) and body:
        issues.append('text_boilerplate_use_title')
    if is_mojibake(str(text)) and is_mojibake(str(title)):
        issues.append('mojibake')
    if is_news_article(body or str(text), platform=platform, url=url):
        issues.append('news_article')
    if is_news_headline(body, platform=platform):
        issues.append('news_headline')
    if not body or len(body.strip()) < 4:
        issues.append('too_short')
    if len(body) > 1500:
        issues.append('too_long')
    return issues
