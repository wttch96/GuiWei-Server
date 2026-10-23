"""按描述文本查找相似物品。

拍照识图会先把图片转成名称、描述、分类和标签，这里再用混合文本相似度
（中文二元组余弦 + 名称相似度 + 分类/标签加成）在已有物品中匹配。
不依赖外部向量服务，离线即可运行。
"""
import re
from collections import Counter
from difflib import SequenceMatcher

from sqlalchemy.orm import joinedload, selectinload

from app.models import Item

DEFAULT_LIMIT = 6
MAX_LIMIT = 20
MIN_SCORE = 0.3

_CJK_RE = re.compile(r"[一-鿿]+")
_WORD_RE = re.compile(r"[a-z0-9]+")
_COMPACT_RE = re.compile(r"[^一-鿿a-z0-9]+")

# 识图描述里常见的泛化词，避免只因“物品 / 收纳 / 可以”等词而误判相似。
_STOP_TERMS = frozenset(
    {
        "物品", "收纳", "整理", "适合", "可以", "用于", "使用", "一个", "这个",
        "那个", "以及", "或者", "并且", "的话", "我们", "你们", "他们", "非常",
        "比较", "推荐", "建议", "颜色", "外观", "材质", "尺寸", "大小", "数量",
        "如果", "需要", "进行", "属于", "主要", "其他", "其它", "就是", "因为",
        "所以", "但是", "而且", "还是", "已经", "可能", "一般", "通常", "例如",
        "比如", "等等", "放在", "存放", "位置", "地方", "家中", "家里", "家庭",
        "日常", "常见", "用于", "用来", "具有", "带有", "表面", "整体", "部分",
    }
)


def _normalize(text) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _compact(text) -> str:
    return _COMPACT_RE.sub("", _normalize(text))


def _tokens(text) -> list[str]:
    """中文按二元组切分，英文/数字按单词切分。"""
    text = _normalize(text)
    tokens: list[str] = []
    for word in _WORD_RE.findall(text):
        if len(word) >= 2 and word not in _STOP_TERMS:
            tokens.append(word)
    for run in _CJK_RE.findall(text):
        if len(run) < 2:
            continue
        # 较短的整体词（通常是名称）额外保留，增强精确匹配
        if len(run) <= 6 and run not in _STOP_TERMS:
            tokens.append(run)
        for index in range(len(run) - 1):
            bigram = run[index : index + 2]
            if bigram not in _STOP_TERMS:
                tokens.append(bigram)
    return tokens


def _vector(sources: list[tuple[str, float]]) -> Counter:
    vector: Counter = Counter()
    for text, weight in sources:
        for token in _tokens(text):
            vector[token] += weight
    return vector


def _cosine(left: Counter, right: Counter) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    if not common:
        return 0.0
    dot = sum(left[token] * right[token] for token in common)
    left_norm = sum(value * value for value in left.values()) ** 0.5
    right_norm = sum(value * value for value in right.values()) ** 0.5
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _names(values) -> list[str]:
    result: list[str] = []
    for value in values or []:
        name = value.get("name") if isinstance(value, dict) else value
        name = _normalize(name)
        if name and name not in result:
            result.append(name)
    return result


def _query_sources(suggestion: dict) -> tuple[list[tuple[str, float]], dict]:
    name = _normalize(suggestion.get("name"))
    description = _normalize(suggestion.get("description"))
    category = _normalize(suggestion.get("category"))
    tags = _names(suggestion.get("tags"))
    raw_text = _normalize(suggestion.get("raw_text"))
    sources = [
        (name, 3.0),
        (category, 1.5),
        (" ".join(tags), 2.0),
        (description, 1.0),
        (raw_text, 0.5),
    ]
    return sources, {
        "name": name,
        "description": description,
        "category": category,
        "tags": set(tags),
    }


def _candidate_sources(item: Item) -> tuple[list[tuple[str, float]], dict]:
    category = item.category.name if item.category else ""
    tags = [tag.name for tag in item.tags]
    sources = [
        (item.name, 3.0),
        (category, 1.5),
        (" ".join(tags), 2.0),
        (item.description or "", 1.0),
        (item.ai_summary or "", 1.0),
    ]
    return sources, {
        "name": _normalize(item.name),
        "description": _normalize(item.description),
        "category": _normalize(category),
        "tags": {_normalize(tag) for tag in tags if tag},
    }


def _score(query: dict, candidate: dict, cosine: float) -> tuple[float, list[str]]:
    query_name = query["name"]
    candidate_name = candidate["name"]
    compact_query = _compact(query_name)
    compact_candidate = _compact(candidate_name)

    name_sim = 0.0
    if compact_query and compact_candidate:
        name_sim = SequenceMatcher(None, compact_query, compact_candidate).ratio()

    shared_tags = query["tags"] & candidate["tags"]
    tag_union = query["tags"] | candidate["tags"]
    tag_sim = len(shared_tags) / len(tag_union) if tag_union else 0.0
    category_match = 1.0 if query["category"] and query["category"] == candidate["category"] else 0.0

    score = 0.55 * cosine + 0.25 * name_sim + 0.10 * tag_sim + 0.10 * category_match

    reasons: list[str] = []
    if compact_query and compact_query == compact_candidate:
        reasons.append("名称相同")
    elif name_sim >= 0.55 or (
        compact_query
        and compact_candidate
        and (compact_query in compact_candidate or compact_candidate in compact_query)
    ):
        reasons.append("名称相近")
    if category_match:
        reasons.append(f"同分类 · {query['category']}")
    if shared_tags:
        reasons.append("共同标签：" + "、".join(sorted(shared_tags)[:3]))
    if cosine >= 0.35:
        reasons.append("描述相似")
    elif not reasons:
        reasons.append("文本相近")

    return min(1.0, score), reasons


def find_similar_items(
    suggestion: dict,
    limit: int = DEFAULT_LIMIT,
    exclude_item_id: int | None = None,
) -> list[dict]:
    """返回与识图结果最相似的物品，带 similarity（0-1）与匹配原因。"""
    if not isinstance(suggestion, dict):
        return []
    try:
        limit = max(1, min(MAX_LIMIT, int(limit)))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    query_sources, query = _query_sources(suggestion)
    query_vector = _vector(query_sources)
    if not query_vector:
        return []

    db_query = Item.query.options(
        joinedload(Item.category),
        joinedload(Item.room),
        joinedload(Item.container),
        selectinload(Item.tags),
        selectinload(Item.photos),
    )
    if exclude_item_id:
        db_query = db_query.filter(Item.id != int(exclude_item_id))

    scored: list[tuple[float, list[str], Item]] = []
    for item in db_query.all():
        candidate_sources, candidate = _candidate_sources(item)
        cosine = _cosine(query_vector, _vector(candidate_sources))
        score, reasons = _score(query, candidate, cosine)
        if score >= MIN_SCORE:
            scored.append((score, reasons, item))

    scored.sort(key=lambda row: (-row[0], -row[2].id))
    payload: list[dict] = []
    for score, reasons, item in scored[:limit]:
        data = item.to_dict()
        data["similarity"] = round(score, 4)
        data["match_reasons"] = reasons
        payload.append(data)
    return payload
