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

PAGE_CHROME_MARKERS = (
    '公司概况',
    '公司简介',
    '公司高管',
    '股权信息',
    '股本结构',
    '十大股东',
    '十大流通股东',
    '基金持股',
    '深股通',
    '可融资',
    '可卖空',
    '首页 公司概况',
    '扫码下载雪球',
    '点击展开查看完整评论',
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
    '期货', '指数', '美股', '道指', '纳指', '标普',
)


def is_news_headline(text: str, platform: str = '') -> bool:
    if not text:
        return False
    s = str(text).strip()
    if platform == 'sina_finance':
        return True
    if len(s) > 120:
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


def is_page_chrome(text: str, platform: str = "") -> bool:
    """Stock profile / nav pages scraped as text, not real opinions."""
    if not text or not str(text).strip():
        return True
    s = re.sub(r'\s+', ' ', str(text)).strip()
    hits = sum(1 for m in PAGE_CHROME_MARKERS if m in s)
    if hits >= 2:
        return True
    if platform == 'xueqiu' and hits >= 1 and len(s) > 80:
        return True
    if re.search(r'¥\d+\.\d+\s*[+-]\d', s) and '深股通' in s:
        return True
    return False


def is_user_comment(
    text: str, platform: str = "", url: str = "", title: str = ""
) -> bool:
    """True when text looks like a user opinion rather than news or page chrome."""
    body = pick_comment_text(text, title=title)
    if not body or len(body.strip()) < 4:
        return False
    if is_boilerplate(body):
        return False
    if is_stock_or_search_url(url):
        return False
    if is_news_article(body, platform=platform, url=url):
        return False
    if is_news_headline(body, platform=platform):
        return False
    if is_spam_or_promo(body):
        return False
    if is_low_value_opinion(body):
        return False
    return True


# Ultra-short fluff / greeting that carries no usable opinion signal.
LOW_VALUE_EXACT = frozenset(
    {
        "顶",
        "路过",
        "沙发",
        "板凳",
        "马克",
        "签到",
        "打卡",
        "加油",
        "早",
        "晚",
        "好",
        "嗯",
        "哦",
        "哈",
        "呵呵",
        "哈哈",
        "嘿嘿",
        "周末愉快",
        "早上好",
        "晚上好",
        "挺好",
        "不错",
        "来了",
        "围观",
        "关注",
        "收藏",
        "同问",
        "求指教",
        "啥情况",
        "怎么了",
        "看不懂",
        "无语",
        "醉了",
        "服了",
        "牛",
        "牛逼",
        "牛B",
        "垃圾",
        "辣鸡",
        "呵呵呵",
    }
)

SPAM_MARKERS = (
    "加微信",
    "加V",
    "加v",
    "加薇",
    "私信领",
    "私聊",
    "荐股",
    "带单",
    "跟单",
    "QQ群",
    "qq群",
    "免费推荐",
    "内部消息",
    "稳赚",
    "必涨",
    "拉群",
    "扫码进群",
    "开户送",
    "代操",
    "老师带",
    "免费指标",
    "加我",
)

OPINION_CUES = (
    "买",
    "卖",
    "仓",
    "涨",
    "跌",
    "空",
    "多",
    "看",
    "套",
    "割",
    "抄",
    "底",
    "顶",
    "反弹",
    "突破",
    "支撑",
    "压力",
    "估值",
    "分红",
    "业绩",
    "回购",
    "利好",
    "利空",
    "风险",
    "机会",
    "持有",
    "清仓",
    "加仓",
    "减仓",
    "止损",
    "止盈",
    "机构",
    "主力",
    "资金",
    "情绪",
    "走势",
    "行情",
    "破位",
    "反转",
    "横盘",
    "震荡",
)


def cjk_len(text: str) -> int:
    return sum(1 for ch in str(text or "") if "\u4e00" <= ch <= "\u9fff")


def is_spam_or_promo(text: str) -> bool:
    s = str(text or "")
    if not s:
        return False
    if any(m in s for m in SPAM_MARKERS):
        return True
    # contact handles / phone-like bait
    if re.search(r"(?:微信|vx|VX|v信)\s*[:：]?\s*[a-zA-Z0-9_\-]{4,}", s):
        return True
    if re.search(r"1[3-9]\d{9}", s) and ("加" in s or "联系" in s or "私" in s):
        return True
    return False


def is_low_value_opinion(text: str) -> bool:
    """True for fluff / ultra-short / non-opinion noise that wastes LLM budget."""
    s = re.sub(r"\s+", "", str(text or "")).strip()
    if not s:
        return True
    # strip common punctuation for exact match
    core = re.sub(r"[，。！？、；：,.!?;:…·~\-_/\\\|（）()【】\[\]「」\"'“”‘’]", "", s)
    if core in LOW_VALUE_EXACT:
        return True
    if cjk_len(s) < 8 and len(s) < 12:
        return True
    # repeated single char / laugh spam: 哈哈哈哈 / 啊啊啊啊
    if re.fullmatch(r"(.)\1{3,}", core):
        return True
    if re.fullmatch(r"(哈|呵|嘿|啊|哦|嗯|咦){3,}", core):
        return True
    # mostly digits / prices / symbols, almost no Chinese
    if cjk_len(s) < 4 and re.search(r"\d", s):
        return True
    # very short and no opinion cue
    if cjk_len(s) < 12 and not any(c in s for c in OPINION_CUES):
        return True
    return False


def is_precise_opinion(
    text: str,
    *,
    platform: str = "",
    url: str = "",
    title: str = "",
    min_cjk: int = 8,
) -> bool:
    """Strict gate for crawl / rescoring: keep only usable retail opinions."""
    body = pick_comment_text(text, title=title) or str(title or text or "").strip()
    if not body:
        return False
    if is_boilerplate(body) or is_page_chrome(body, platform=platform):
        return False
    if is_mojibake(body) or is_log_metadata(body):
        return False
    if is_stock_or_search_url(url):
        return False
    if is_news_article(body, platform=platform, url=url):
        return False
    if is_news_headline(body, platform=platform):
        return False
    if is_spam_or_promo(body):
        return False
    if is_low_value_opinion(body):
        return False
    if cjk_len(body) < min_cjk and len(body) < max(12, min_cjk + 2):
        return False
    return True


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
    if is_page_chrome(body or str(text), platform=platform):
        issues.append('page_chrome')
    if is_news_article(body or str(text), platform=platform, url=url):
        issues.append('news_article')
    if is_news_headline(body, platform=platform):
        issues.append('news_headline')
    if is_spam_or_promo(body or str(title) or str(text)):
        issues.append('spam_promo')
    if is_low_value_opinion(body or str(title) or str(text)):
        issues.append('low_value')
    if not body or len(body.strip()) < 4:
        issues.append('too_short')
    elif cjk_len(body) < 8 and len(body) < 12:
        issues.append('too_short_cjk')
    if len(body) > 1500:
        issues.append('too_long')
    return issues
