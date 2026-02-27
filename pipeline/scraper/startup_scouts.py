"""Startup scout scrapers — HN Who's Hiring, YC Directory, ProductHunt.

Target: Early-stage startups (<1 year, <10 people, bootstrapped/seed)
that need developers but don't have formal HR teams or job postings.

All use safe, public APIs with no anti-scraping concerns.
"""

import contextlib
import json
import os
import re
import time
from datetime import date, datetime

import httpx

from core.logger import logger
from core.models import ProfileConfig
from scraper.registry import scraper
from scraper.utils import build_skill_set, check_relevance, strip_html

# ─── HN Who's Hiring ────────────────────────────────────────────────────────

@scraper("hn_hiring", group="startup_scout")
async def scrape_hn_hiring(profile: ProfileConfig, limit: int = 50) -> list[dict]:
    """Scrape HN 'Who is Hiring?' threads via Algolia API (official, free, no auth).

    Monthly threads where companies post hiring comments.
    Each top-level comment = one company actively hiring.
    """
    aggregator_cfg = profile.aggregators.get("hn_hiring")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("HN Hiring: disabled in config, skipping.")
        return []

    all_skills = build_skill_set(profile)
    headers = {"User-Agent": "JobApplicationBot/1.0"}

    # Find "Who is Hiring?" story posts from the last 12 months
    twelve_months_ago = int(time.time()) - (365 * 24 * 60 * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Find the monthly thread stories
        try:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "query": '"Who is Hiring"',
                    "tags": "story,ask_hn",
                    "numericFilters": f"created_at_i>{twelve_months_ago}",
                    "hitsPerPage": 12,
                },
                headers=headers,
            )
            resp.raise_for_status()
            stories = resp.json().get("hits", [])
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            logger.error(f"HN Hiring: failed to fetch story list: {e}")
            return []

        # Filter to actual "Who is Hiring" threads (not "Who wants to be hired")
        hiring_stories = [
            s for s in stories
            if "who is hiring" in s.get("title", "").lower()
            and "hired" not in s.get("title", "").lower()
        ]

        if not hiring_stories:
            logger.info("HN Hiring: no 'Who is Hiring' threads found in last 12 months")
            return []

        logger.info(f"HN Hiring: found {len(hiring_stories)} threads, fetching comments...")

        # Step 2: Fetch comments from each thread (most recent first)
        all_comments = []
        for story in hiring_stories[:6]:  # Last 6 months max
            story_id = story.get("objectID")
            if not story_id:
                continue

            try:
                resp = await client.get(
                    "https://hn.algolia.com/api/v1/search",
                    params={
                        "tags": f"comment,story_{story_id}",
                        "hitsPerPage": 200,
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                comments = resp.json().get("hits", [])
                # Only top-level comments (parent_id == story_id)
                top_level = [
                    c for c in comments
                    if str(c.get("parent_id")) == str(story_id)
                ]
                all_comments.extend(top_level)
                logger.info(f"HN Hiring: story {story_id} → {len(top_level)} top-level comments")
            except (httpx.HTTPError, json.JSONDecodeError) as e:
                logger.error(f"HN Hiring: failed to fetch comments for story {story_id}: {e}")

    # Step 3: Parse and normalize
    jobs = []
    seen_companies = set()

    for comment in all_comments:
        parsed = _parse_hn_comment(comment)
        if not parsed:
            continue

        company_key = parsed["company"].lower().strip()
        if company_key in seen_companies:
            continue
        seen_companies.add(company_key)

        # Relevance check
        if not check_relevance(parsed.get("title", ""), parsed["description"], all_skills):
            continue

        jobs.append(parsed)
        if len(jobs) >= limit:
            break

    logger.info(f"HN Hiring: {len(jobs)} relevant startups (from {len(all_comments)} comments)")
    return jobs


def _parse_hn_comment(comment: dict) -> dict | None:
    """Parse an HN hiring comment into a normalized job dict.

    HN hiring comments typically follow:
    Company Name | Location | Role | Remote | URL
    <description>
    """
    text_html = comment.get("comment_text", "")
    if not text_html or len(text_html) < 100:
        return None

    text_plain = strip_html(text_html)

    # Extract first line (usually has company | location | role format)
    lines = text_plain.split("\n", 1) if "\n" in text_plain else [text_plain[:200], text_plain]
    first_line = lines[0].strip() if lines else ""

    # Parse pipe-delimited first line (some use · or — or – instead of |)
    # Normalize common separators to |
    normalized_first = first_line
    for sep in ["·", "—", "–", " - "]:
        normalized_first = normalized_first.replace(sep, "|")
    parts = [p.strip() for p in normalized_first.split("|")]
    company = parts[0] if parts else "Unknown"

    # Clean company name
    company = re.sub(r'https?://\S+', '', company).strip()  # Remove URLs
    company = re.sub(r'^#\s*', '', company).strip()          # Remove leading #
    # If company name looks like a sentence (has "is hiring", "looking for"), truncate
    for marker in [" is hiring", " is looking", " are looking", " are hiring"]:
        if marker in company.lower():
            company = company[:company.lower().index(marker)].strip()
            break
    company = company[:60]  # Truncate overly long names

    if not company or len(company) < 2:
        return None

    # Extract location from parts
    location = ""
    is_remote = False
    for part in parts[1:]:
        part_lower = part.lower()
        if any(kw in part_lower for kw in ["remote", "worldwide", "anywhere", "global"]):
            is_remote = True
        if not location and any(kw in part_lower for kw in ["remote", "sf", "nyc", "london", "berlin", "india",
                                                              "us", "eu", "uk", "bengaluru", "bangalore"]):
            location = part.strip()

    if not location:
        location = "Remote" if is_remote else "Unknown"

    # Extract URLs from comment
    urls = re.findall(r'https?://[^\s<>"]+', text_html)
    company_url = ""
    skip_domains = ["ycombinator.com", "news.ycombinator", "lever.co",
                    "greenhouse.io", "linkedin.com", "jobs.lever.co"]
    for url in urls:
        # Only use company website URLs (not job boards or HN links)
        if not any(skip in url for skip in skip_domains):
            company_url = url
            break

    # Parse date
    created_at = comment.get("created_at_i")
    post_date = None
    if created_at:
        with contextlib.suppress(ValueError, TypeError, OSError):
            post_date = datetime.fromtimestamp(int(created_at)).date()

    # Build a title from parts
    role_parts = [p.strip() for p in parts if any(kw in p.lower() for kw in
                  ["engineer", "developer", "hire", "hiring", "looking", "python",
                   "react", "full-stack", "backend", "frontend", "ai", "ml"])]
    title = role_parts[0] if role_parts else f"Hiring at {company}"

    return {
        "title": title[:200],
        "company": company,
        "location": location,
        "source": "hn_hiring",
        "discovered_via": "hn_hiring",
        "description": text_plain[:5000],
        "job_url": company_url or f"https://news.ycombinator.com/item?id={comment.get('objectID', '')}",
        "date_posted": post_date,
        "is_remote": is_remote,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        # Startup profile metadata
        "hn_thread_date": post_date,
    }


# ─── YC Directory ────────────────────────────────────────────────────────────

@scraper("yc_directory", group="startup_scout")
async def scrape_yc_directory(profile: ProfileConfig, limit: int = 50) -> list[dict]:
    """Scrape YC company directory — public data, no auth.

    Fetches companies from recent batches (last ~1.5 years) with small teams.
    """
    aggregator_cfg = profile.aggregators.get("yc_directory")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("YC Directory: disabled in config, skipping.")
        return []

    all_skills = build_skill_set(profile)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    # Recent batches (last ~1.5 years)
    current_year = date.today().year
    batches = []
    for year in range(current_year, current_year - 2, -1):
        batches.extend([f"W{str(year)[2:]}", f"S{str(year)[2:]}"])

    jobs = []
    seen_slugs = set()

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for batch in batches:
            try:
                # YC's public companies endpoint
                resp = await client.get(
                    "https://www.ycombinator.com/companies",
                    params={
                        "batch": batch,
                        "team_size": "1-10",
                        "status": "Active",
                    },
                    headers=headers,
                )
                resp.raise_for_status()

                # Try to extract JSON data from the page
                companies = _extract_yc_companies(resp.text, batch)

                for comp in companies:
                    slug = comp.get("slug", comp.get("name", "").lower().replace(" ", "-"))
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)

                    description = f"{comp.get('one_liner', '')}\n\n{comp.get('long_description', '')}".strip()

                    # Relevance check
                    if not check_relevance(comp.get("name", ""), description, all_skills):
                        continue

                    batch_date = _batch_to_date(batch)
                    website = comp.get("website", "")
                    yc_url = f"https://www.ycombinator.com/companies/{slug}"

                    jobs.append({
                        "title": f"Developer at {comp.get('name', 'Unknown')} ({batch})",
                        "company": comp.get("name", "Unknown"),
                        "location": comp.get("location", "Remote"),
                        "source": "yc_directory",
                        "discovered_via": "yc_directory",
                        "description": description[:5000],
                        "job_url": website or yc_url,
                        "date_posted": batch_date,
                        "is_remote": "remote" in description.lower() or comp.get("team_size", 99) <= 5,
                        "salary_min": None,
                        "salary_max": None,
                        "salary_currency": None,
                        # Startup profile metadata
                        "yc_batch": batch,
                        "yc_url": yc_url,
                        "founding_date": batch_date,
                        "team_size": comp.get("team_size"),
                        "one_liner": comp.get("one_liner", ""),
                    })

                    if len(jobs) >= limit:
                        break

                logger.info(f"YC Directory: batch {batch} → {len(companies)} companies found")

            except (httpx.HTTPError, json.JSONDecodeError) as e:
                logger.error(f"YC Directory: failed for batch {batch}: {e}")

            if len(jobs) >= limit:
                break

    logger.info(f"YC Directory: {len(jobs)} relevant startups")
    return jobs


def _extract_yc_companies(html_text: str, batch: str) -> list[dict]:
    """Extract company data from YC companies page.

    YC embeds company data as JSON in a Next.js data script tag.
    Falls back to basic HTML parsing if JSON extraction fails.
    """
    companies = []

    # Try to find JSON data in Next.js script tags
    json_patterns = [
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r'"companies"\s*:\s*(\[.*?\])\s*[,}]',
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, html_text, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                # Navigate Next.js data structure
                if isinstance(data, dict):
                    props = data.get("props", {}).get("pageProps", {})
                    company_list = props.get("companies", props.get("results", []))
                    if company_list:
                        return company_list
                elif isinstance(data, list):
                    return data
            except (json.JSONDecodeError, TypeError):
                continue

    # Fallback: parse company cards from HTML
    card_pattern = r'<a[^>]*href="/companies/([^"]+)"[^>]*>.*?<span[^>]*>([^<]+)</span>'
    cards = re.findall(card_pattern, html_text, re.DOTALL)

    for slug, name in cards:
        name = strip_html(name).strip()
        if name and len(name) > 1:
            companies.append({
                "name": name,
                "slug": slug,
                "one_liner": "",
                "long_description": "",
                "website": "",
                "location": "Remote",
                "team_size": 5,
            })

    return companies


def _batch_to_date(batch: str) -> date:
    """Convert YC batch string to approximate date. W25→2025-01-15, S24→2024-06-15."""
    try:
        season = batch[0]
        year = 2000 + int(batch[1:])
        month = 1 if season == "W" else 6
        return date(year, month, 15)
    except (ValueError, IndexError):
        return date.today()


# ─── ProductHunt ─────────────────────────────────────────────────────────────

@scraper("producthunt", group="startup_scout", needs_key="PRODUCTHUNT_API_TOKEN")
async def scrape_producthunt(profile: ProfileConfig, limit: int = 30) -> list[dict]:
    """Scrape ProductHunt — GraphQL API with free API token.

    Fetches recently launched products. Maker names are included (great for email finding).
    Requires PRODUCTHUNT_API_TOKEN env var.
    """
    aggregator_cfg = profile.aggregators.get("producthunt")
    if aggregator_cfg and not aggregator_cfg.enabled:
        logger.info("ProductHunt: disabled in config, skipping.")
        return []

    api_token = os.getenv("PRODUCTHUNT_API_TOKEN", "")
    if not api_token:
        logger.info("ProductHunt: PRODUCTHUNT_API_TOKEN not set, skipping.")
        return []

    all_skills = build_skill_set(profile)

    query = """
    query {
        posts(order: NEWEST, first: 50) {
            edges {
                node {
                    name
                    tagline
                    description
                    url
                    website
                    createdAt
                    votesCount
                    makers {
                        name
                        headline
                    }
                    topics {
                        edges {
                            node { name }
                        }
                    }
                }
            }
        }
    }
    """

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                "https://api.producthunt.com/v2/api/graphql",
                json={"query": query},
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            logger.error(f"ProductHunt API failed: {e}")
            return []

    posts = data.get("data", {}).get("posts", {}).get("edges", [])

    jobs = []
    for edge in posts:
        node = edge.get("node", {})
        name = node.get("name", "")
        tagline = node.get("tagline", "")
        description = node.get("description", "")
        website = node.get("website", "")
        ph_url = node.get("url", "")
        created_at = node.get("createdAt", "")

        # Get maker info
        makers = node.get("makers", [])
        maker_info = ""
        if makers:
            maker_names = [m.get("name", "") for m in makers if m.get("name")]
            maker_headlines = [m.get("headline", "") for m in makers if m.get("headline")]
            if maker_names:
                maker_info = f"Makers: {', '.join(maker_names)}"
            if maker_headlines:
                maker_info += f" | {'; '.join(maker_headlines[:2])}"

        # Get topics
        topics = [
            t["node"]["name"]
            for t in node.get("topics", {}).get("edges", [])
            if t.get("node", {}).get("name")
        ]

        full_description = f"{tagline}\n\n{description}"
        if maker_info:
            full_description += f"\n\n{maker_info}"
        if topics:
            full_description += f"\n\nTopics: {', '.join(topics)}"

        # Relevance: check if tech-related
        tech_topics = {"developer tools", "artificial intelligence", "tech", "saas",
                       "productivity", "api", "open source", "web app", "no-code"}
        is_tech = bool(set(t.lower() for t in topics) & tech_topics)

        if not is_tech and not check_relevance(name, full_description, all_skills):
            continue

        # Parse date
        post_date = None
        if created_at:
            with contextlib.suppress(ValueError, AttributeError):
                post_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()

        # Build structured maker data
        ph_maker_data = [
            {"name": m.get("name", ""), "headline": m.get("headline", "")}
            for m in makers if m.get("name")
        ]

        jobs.append({
            "title": f"Product: {name} — {tagline[:100]}",
            "company": name,
            "location": "Remote",
            "source": "producthunt",
            "discovered_via": "producthunt",
            "description": full_description[:5000],
            "job_url": website or ph_url,
            "date_posted": post_date,
            "is_remote": True,
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
            # Startup profile metadata
            "ph_url": ph_url,
            "ph_launch_date": post_date,
            "ph_votes_count": node.get("votesCount", 0),
            "ph_maker_data": ph_maker_data,
            "topics": topics,
        })

        if len(jobs) >= limit:
            break

    logger.info(f"ProductHunt: {len(jobs)} relevant products (from {len(posts)} total)")
    return jobs
