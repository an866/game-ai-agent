"""游戏检索聚合 —— RAWG 优先，Steam / 联网兜底（UI 面板共用）

中文名在 RAWG 上常匹配到无关结果（空洞骑士→星空骑士），因此：
1. 常见中英别名表
2. 按名称相似度挑种子，而不是盲目取第一条
3. 联网兜底时过滤「盘点/Best games like」类文章标题
"""

import re
from loguru import logger

# 常见中文名 → 英文名（RAWG/Steam 主用英文）
# 注意：长 key 放前面匹配；「空洞骑士」不应带出 Silksong
EN_ALIASES: dict[str, list[str]] = {
    "空洞骑士：丝之歌": ["Hollow Knight Silksong"],
    "空洞骑士丝之歌": ["Hollow Knight Silksong"],
    "丝之歌": ["Hollow Knight Silksong", "Silksong"],
    "空洞骑士": ["Hollow Knight"],
    "艾尔登法环": ["Elden Ring"],
    "黑神话悟空": ["Black Myth: Wukong"],
    "黑神话": ["Black Myth: Wukong"],
    "原神": ["Genshin Impact"],
    "鸣潮": ["Wuthering Waves"],
    "只狼": ["Sekiro Shadows Die Twice"],
    "巫师3": ["The Witcher 3: Wild Hunt"],
    "赛博朋克2077": ["Cyberpunk 2077"],
    "荒野大镖客2": ["Red Dead Redemption 2"],
    "王国之泪": ["Tears of the Kingdom"],
    "塞尔达": ["The Legend of Zelda"],
    "怪物猎人": ["Monster Hunter"],
    "生化危机": ["Resident Evil"],
    "最终幻想": ["Final Fantasy"],
    "黑暗之魂": ["Dark Souls"],
    "血源诅咒": ["Bloodborne"],
    "死亡搁浅": ["Death Stranding"],
    "霍格沃茨之遗": ["Hogwarts Legacy"],
    "博德之门3": ["Baldur's Gate 3"],
    "博德之门": ["Baldur's Gate"],
    "哈迪斯": ["Hades"],
    "星空": ["Starfield"],
    "明日方舟终末地": ["Arknights: Endfield"],
    "绝区零": ["Zenless Zone Zero"],
    "崩坏星穹铁道": ["Honkai: Star Rail"],
    "我的世界": ["Minecraft"],
    "泰拉瑞亚": ["Terraria"],
    "星露谷物语": ["Stardew Valley"],
}

# 文章标题噪声（不是游戏名）
_ARTICLE_NOISE = re.compile(
    r"(best games|games like|similar|盘点|推荐|值得一玩|top\s*\d+|"
    r"list of|guide|review|评测|攻略|if you|you should|you loved|"
    r"after finishing|play after|games to play)",
    re.I,
)

# 别名匹配最小分：低于此分不采信 RAWG 第一条
MIN_SEED_SCORE = 40.0


def expand_queries(query: str) -> list[str]:
    """用户输入 → 优先查询序列（原名 + 别名）。

    只做「key 出现在用户输入里」的包含匹配，不用反向包含——
    否则「空洞骑士」会命中「空洞骑士：丝之歌」的别名。
    """
    q = (query or "").strip()
    if not q:
        return []
    out = [q]
    for key, aliases in sorted(EN_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if key == q or key in q:
            for a in aliases:
                if a not in out:
                    out.append(a)
    return out


def _name_score(candidate: str, want: str) -> float:
    """简单名称相关度：包含/相等加分，无关词扣分"""
    c = (candidate or "").lower()
    w = (want or "").lower()
    if not c or not w:
        return 0.0
    if c == w:
        return 100.0
    if w in c or c in w:
        return 80.0
    c_toks = set(re.findall(r"[a-z0-9]+", c))
    w_toks = set(re.findall(r"[a-z0-9]+", w))
    if not w_toks:
        return 0.0
    overlap = len(c_toks & w_toks) / len(w_toks)
    return overlap * 50.0


def _pick_best_rawg(results: list[dict], want: str) -> tuple[dict | None, float]:
    if not results:
        return None, 0.0
    scored = sorted(
        results,
        key=lambda r: _name_score(str(r.get("name") or ""), want),
        reverse=True,
    )
    best = scored[0]
    score = _name_score(str(best.get("name") or ""), want)
    return best, score


def _steam_item_to_card(item: dict) -> dict:
    return {
        "id": item.get("appid"),
        "name": item.get("name", ""),
        "slug": None,
        "rating": None,
        "released": None,
        "genres": [],
        "platforms": ["Steam"],
        "background_image": None,
        "metacritic": None,
        "source": "steam",
    }


async def _rawg_search(query: str, *, platforms: str | None = None,
                       genres: str | None = None) -> list[dict]:
    from src.tools.rawg import RAWGGameSearchTool
    results = await RAWGGameSearchTool()._arun(query, platforms=platforms, genres=genres)
    for r in results or []:
        r.setdefault("source", "rawg")
    return results or []


async def search_games(query: str, *, platforms: str | None = None,
                       genres: str | None = None) -> list[dict]:
    """搜索游戏卡片数据。多别名择优；RAWG 失败时回退 Steam。"""
    best_list: list[dict] = []
    best_score = -1.0
    for q in expand_queries(query):
        try:
            results = await _rawg_search(q, platforms=platforms, genres=genres)
            if not results:
                continue
            ordered = sorted(
                results,
                key=lambda r: _name_score(str(r.get("name") or ""), q),
                reverse=True,
            )
            top_score = _name_score(str(ordered[0].get("name") or ""), q)
            # 用户原始 query 也参与评分（中英都算）
            top_score = max(
                top_score,
                _name_score(str(ordered[0].get("name") or ""), query),
            )
            if top_score > best_score:
                best_score = top_score
                best_list = ordered
            if top_score >= MIN_SEED_SCORE:
                return ordered
        except Exception as exc:
            logger.warning(f"RAWG 搜索失败 [{q}]: {exc}")

    if best_list:
        return best_list

    try:
        from src.tools.steam_api import SteamSearchTool
        for q in expand_queries(query):
            steam = await SteamSearchTool()._arun(q)
            if steam:
                return [_steam_item_to_card(s) for s in steam[:10]]
    except Exception as exc:
        logger.warning(f"Steam 搜索也失败: {exc}")

    return []


def _is_article_title(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return True
    if _ARTICLE_NOISE.search(t):
        return True
    # 常见站点尾巴 / 过长标题（更像文章而非游戏名）
    if len(t) > 48:
        return True
    if re.search(r"\b(GamerSky|Gaming\.net|IGN|PCGamer|3DM|游民|游侠|篝火)\b", t, re.I):
        return True
    if re.search(r"[：:]\s*\d+\s*款|盘点|十佳|榜单", t):
        return True
    return False


# RAWG 类型名 → slug（用于 /games?genres=）
_GENRE_SLUGS = {
    "action": "action",
    "adventure": "adventure",
    "indie": "indie",
    "platformer": "platformer",
    "rpg": "role-playing-games-rpg",
    "shooter": "shooter",
    "strategy": "strategy",
    "simulation": "simulation",
    "puzzle": "puzzle",
    "racing": "racing",
    "sports": "sports",
    "casual": "casual",
    "fighting": "fighting",
    "arcade": "arcade",
    "educational": "educational",
    "family": "family",
    "board-games": "board-games",
    "card": "card",
    "massively-multiplayer": "massively-multiplayer",
}


# 热门游戏精选相似（suggested 401 时的高质量兜底）
CURATED_SIMILAR: dict[str, list[str]] = {
    "hollow knight": [
        "Ori and the Blind Forest", "Dead Cells", "Celeste",
        "Blasphemous", "Salt and Sanctuary", "Ori and the Will of the Wisps",
    ],
    "elden ring": [
        "Dark Souls III", "Bloodborne", "Sekiro: Shadows Die Twice",
        "Lies of P", "Nioh 2", "Remnant: From the Ashes",
    ],
    "genshin impact": [
        "Honkai: Star Rail", "Wuthering Waves", "Zenless Zone Zero",
        "The Legend of Zelda: Breath of the Wild",
    ],
    "hades": [
        "Hades II", "Dead Cells", "Slay the Spire", "Curse of the Dead Gods",
        "Risk of Rain 2",
    ],
    "stardew valley": [
        "My Time at Portia", "Spiritfarer", "Coral Island", "Sun Haven",
    ],
    "minecraft": [
        "Terraria", "Core Keeper", "Valheim", "Don't Starve Together",
    ],
    "sekiro: shadows die twice": [
        "Sekiro", "Elden Ring", "Dark Souls III", "Bloodborne", "Lies of P",
    ],
    "sekiro": [
        "Sekiro: Shadows Die Twice", "Elden Ring", "Dark Souls III", "Bloodborne",
    ],
}


async def _curated_similar(seed_name: str, genre_pref: list[str] | None) -> list[dict]:
    """按精选名单搜 RAWG，回填评分/封面。"""
    key = (seed_name or "").strip().lower()
    names = CURATED_SIMILAR.get(key)
    if not names:
        # 宽松包含匹配
        for k, v in CURATED_SIMILAR.items():
            if k in key or key in k:
                names = v
                break
    if not names:
        return []
    from src.tools.rawg import RAWGGameSearchTool
    out = []
    for name in names[:5]:
        try:
            results = await RAWGGameSearchTool()._arun(name)
            best, score = _pick_best_rawg(results or [], name)
            if best and score >= 60:
                best = dict(best)
                best.setdefault("source", "rawg")
                if genre_pref:
                    best["_match_score"] = len(set(genre_pref) & set(best.get("genres") or []))
                out.append(best)
        except Exception as exc:
            logger.warning(f"精选相似回填失败 [{name}]: {exc}")
    if genre_pref:
        out.sort(key=lambda x: x.get("_match_score", 0), reverse=True)
    return out


async def _similar_by_genre(seed_id: int, seed_name: str, genre_pref: list[str] | None) -> list[dict]:
    """suggested 401 时：精选名单优先，其次按 genres 列表接口。"""
    curated = await _curated_similar(seed_name, genre_pref)
    if curated:
        logger.info(f"使用精选相似 {len(curated)} 条 seed={seed_name}")
        return curated

    from src.tools.rawg import RAWGGameDetailTool, _rawg_get
    detail = await RAWGGameDetailTool()._arun(seed_id)
    genres = [g for g in (detail or {}).get("genres") or [] if g]
    slugs = []
    for g in genres:
        slug = _GENRE_SLUGS.get(g.lower())
        if slug and slug not in slugs:
            slugs.append(slug)
    slugs.sort(key=lambda s: 0 if s in ("platformer", "indie", "puzzle") else 1)
    if not slugs:
        return []
    genre_param = ",".join(slugs[:2])
    logger.info(f"同类型 genres 过滤: {genre_param} (seed genres={genres})")
    try:
        data = await _rawg_get("games", {
            "genres": genre_param,
            "ordering": "-rating",
            "page_size": 12,
        })
    except Exception as exc:
        logger.warning(f"genres 列表失败: {exc}")
        return []
    seed_l = (seed_name or "").lower()
    out = []
    for game in (data or {}).get("results") or []:
        name = str(game.get("name") or "")
        if not name or name.lower() == seed_l:
            continue
        rating = game.get("rating") or 0
        if rating and float(rating) < 3.5:
            continue
        card = {
            "id": game.get("id"),
            "name": name,
            "slug": game.get("slug"),
            "rating": rating,
            "released": game.get("released"),
            "genres": [g["name"] for g in game.get("genres") or []],
            "platforms": [p["platform"]["name"] for p in game.get("platforms") or []],
            "background_image": game.get("background_image"),
            "metacritic": game.get("metacritic"),
            "source": "rawg",
        }
        if genre_pref:
            card["_match_score"] = len(set(genre_pref) & set(card["genres"]))
        out.append(card)
        if len(out) >= 5:
            break
    if genre_pref:
        out.sort(key=lambda x: x.get("_match_score", 0), reverse=True)
    return out


async def recommend_games(seed_query: str, *, genre_pref: list[str] | None = None) -> tuple[list[dict], str | None]:
    """相似游戏推荐。返回 (cards, seed_name)。"""
    seed_name = None
    queries = expand_queries(seed_query) or [seed_query]
    suggested_401 = False

    for q in queries:
        try:
            from src.tools.rawg import RAWGGameSearchTool, RAWGGameRecommendationsTool
            results = await RAWGGameSearchTool()._arun(q)
            best, score = _pick_best_rawg(results or [], q)
            if not best or score < MIN_SEED_SCORE:
                logger.info(f"跳过低置信种子 [{q}] {best.get('name') if best else None} score={score}")
                continue
            try:
                recs = await RAWGGameRecommendationsTool()._arun(best["id"])
            except Exception as rec_exc:
                if "401" in str(rec_exc):
                    suggested_401 = True
                    logger.info(f"suggested 401，尝试同类型检索 seed={best.get('name')}")
                    recs = await _similar_by_genre(best["id"], best.get("name") or "", genre_pref)
                else:
                    raise
            if not recs:
                continue
            seed_name = best["name"]
            for rec in recs:
                rec.setdefault("source", "rawg")
            if genre_pref and "_match_score" not in (recs[0] or {}):
                for rec in recs:
                    rec["_match_score"] = len(set(genre_pref) & set(rec.get("genres", [])))
                recs.sort(key=lambda r: r.get("_match_score", 0), reverse=True)
            return recs, seed_name
        except Exception as exc:
            logger.warning(f"RAWG 推荐失败 [{q}]: {exc}")

    # Steam 定位后再试 RAWG（仅当 suggested 尚未确认 401，避免重复打墙）
    if not suggested_401:
        try:
            from src.tools.steam_api import SteamSearchTool
            from src.tools.rawg import RAWGGameSearchTool, RAWGGameRecommendationsTool
            for q in queries:
                steam = await SteamSearchTool()._arun(q)
                if not steam:
                    continue
                en_name = steam[0].get("name") or q
                results = await RAWGGameSearchTool()._arun(en_name)
                best, score = _pick_best_rawg(results or [], en_name)
                if best and score >= MIN_SEED_SCORE:
                    try:
                        recs = await RAWGGameRecommendationsTool()._arun(best["id"])
                    except Exception as rec_exc:
                        if "401" in str(rec_exc):
                            suggested_401 = True
                            recs = await _similar_by_genre(best["id"], best.get("name") or "", genre_pref)
                        else:
                            raise
                    if recs:
                        for rec in recs:
                            rec.setdefault("source", "rawg")
                        return recs, best["name"]
        except Exception as exc:
            logger.warning(f"Steam→RAWG 推荐失败: {exc}")

    # 联网兜底：过滤文章站标题
    recs = []
    try:
        from src.tools.web_search import search_web
        en = next((x for x in reversed(queries) if re.search(r"[A-Za-z]", x)), seed_query)
        hits = await search_web(f"{en} similar metroidvania games", max_results=8)
        seen = set()
        for i, h in enumerate(hits[:8]):
            title = (h.get("title") or "").strip()
            if not title or _is_article_title(title):
                continue
            short = re.split(r"\s+[·|–—]\s+|\s+-\s+", title)[0].strip()[:60]
            if not short or _is_article_title(short):
                continue
            key = short.lower()
            if key in seen:
                continue
            seen.add(key)
            recs.append({
                "id": f"web-{i}",
                "name": short,
                "rating": None,
                "released": None,
                "genres": [],
                "background_image": None,
                "snippet": (h.get("snippet") or "")[:140],
                "source": "web",
            })
            if len(recs) >= 5:
                break
    except Exception as exc:
        logger.warning(f"联网推荐也失败: {exc}")

    return recs, seed_name or seed_query
