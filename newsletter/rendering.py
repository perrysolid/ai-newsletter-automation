"""Design phase tools: HTML / Markdown / JSON rendering of the newsletter.

Visual language: editorial print aesthetic — warm paper, ink black, vermilion
accent, Georgia serif display with Courier mono labels. All layout is
table-based with inline styles so it renders in every email client.
"""

import json
import logging
from collections import Counter
from datetime import datetime
from html import escape
from typing import Dict

from .server import mcp

logger = logging.getLogger(__name__)

# ---- Design tokens ----
INK = "#191512"          # near-black ink
PAPER = "#FBF7ED"        # warm paper
PAGE = "#EFE8D8"         # page background
ACCENT = "#C43D12"       # vermilion
MUTED = "#867B66"        # faded ink
BODY_TXT = "#453E31"     # body copy
RULE = "#D8CDB4"         # hairline rule
SERIF = "Georgia, 'Times New Roman', serif"
MONO = "'Courier New', Courier, monospace"


# ---- Building blocks ----

def _eyebrow(text, color=ACCENT):
    return (f'<div style="font-family:{MONO};font-size:11px;font-weight:bold;'
            f'letter-spacing:3px;color:{color};padding-bottom:10px;">{text}</div>')


def _section_band(label, count_label=""):
    right = (f'<td align="right" style="font-family:{MONO};font-size:10px;'
             f'letter-spacing:2px;color:{PAPER};opacity:0.7;padding:11px 40px 11px 0;">{count_label}</td>') if count_label else ''
    return (f'<tr><td style="background-color:{INK};">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="font-family:{MONO};font-size:11px;font-weight:bold;letter-spacing:3px;'
            f'color:{PAPER};padding:11px 0 11px 40px;">{label}</td>{right}'
            f'</tr></table></td></tr>')


def _dotted_rule(pad="0 40px"):
    return (f'<tr><td style="padding:{pad};">'
            f'<div style="border-top:1px dashed {RULE};font-size:0;line-height:0;">&nbsp;</div></td></tr>')


def _mono_link(href, label):
    return (f'<a href="{escape(href, quote=True)}" target="_blank" style="font-family:{MONO};'
            f'font-size:12px;font-weight:bold;letter-spacing:1px;color:{ACCENT};'
            f'text-decoration:none;border-bottom:2px solid {ACCENT};padding-bottom:1px;">{label}</a>')


def _tag_chip(text):
    return (f'<span style="font-family:{MONO};font-size:10px;letter-spacing:1px;color:{INK};'
            f'border:1px solid {INK};padding:2px 7px;margin-right:6px;white-space:nowrap;">{escape(text)}</span>')


def _compact_num(n):
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _bar_row(label, value, max_value, display, color=INK):
    pct = int(round((value / max_value) * 100)) if max_value else 0
    pct = min(max(pct, 4), 100)
    rest = 100 - pct
    return (f'<tr>'
            f'<td width="150" valign="middle" style="font-family:{MONO};font-size:10px;letter-spacing:1px;'
            f'color:{INK};padding:5px 10px 5px 0;white-space:nowrap;">{escape(label)}</td>'
            f'<td valign="middle" style="padding:5px 0;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="{pct}%" style="background-color:{color};font-size:8px;line-height:13px;">&nbsp;</td>'
            f'<td width="{rest}%" style="background-color:{PAGE};font-size:8px;line-height:13px;">&nbsp;</td>'
            f'</tr></table></td>'
            f'<td width="64" align="right" valign="middle" style="font-family:{MONO};font-size:10px;'
            f'color:{MUTED};padding:5px 0 5px 10px;white-space:nowrap;">{display}</td></tr>')


def _figure_box(caption, rows_html):
    return (f'<tr><td style="padding:24px 40px 4px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {INK};">'
            f'<tr><td style="border-bottom:1px solid {INK};background-color:{PAGE};font-family:{MONO};'
            f'font-size:10px;font-weight:bold;letter-spacing:2px;color:{INK};padding:8px 14px;">{caption}</td></tr>'
            f'<tr><td style="padding:12px 14px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>'
            f'</td></tr></table></td></tr>')


# ---- Page sections ----

def _render_head_and_masthead(issue_date, preheader):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <title>Khabar AI</title>
</head>
<body style="margin:0;padding:0;background-color:{PAGE};">
    <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{PAGE};">
    <tr><td align="center" style="padding:32px 12px;">
    <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:640px;max-width:100%;background-color:{PAPER};border:1px solid {INK};">

        <!-- Masthead -->
        <tr><td style="border-bottom:6px double {INK};padding:38px 40px 26px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
                <td style="font-family:{MONO};font-size:11px;font-weight:bold;letter-spacing:4px;color:{ACCENT};">&#9632; THE WEEKLY AI DISPATCH</td>
                <td align="right" style="font-family:{MONO};font-size:11px;letter-spacing:2px;color:{MUTED};">FREE EDITION</td>
            </tr></table>
            <div style="font-family:{SERIF};font-size:56px;font-weight:bold;line-height:1.0;color:{INK};padding:16px 0 14px;">Khabar <span style="color:{ACCENT};">AI</span></div>
            <div style="border-top:1px solid {INK};padding-top:9px;font-family:{MONO};font-size:11px;letter-spacing:2px;color:{INK};">
                {issue_date.upper()}
            </div>
        </td></tr>
"""


def _render_stat_strip(papers, repos, all_categories):
    total_stars = sum(int(r.get('stars', 0) or 0) for r in repos)
    stats = []
    if papers:
        stats.append((str(len(papers)), "NEW PAPERS"))
    if repos:
        stats.append((str(len(repos)), "HOT REPOS"))
    if total_stars:
        stats.append((_compact_num(total_stars), "STARS EARNED"))
    if all_categories:
        stats.append((str(len(all_categories)), "FIELDS"))
    if not stats:
        return ""
    cells = ""
    for j, (num, label) in enumerate(stats):
        border = f"border-left:1px solid {RULE};" if j else ""
        cells += (f'<td width="{100 // len(stats)}%" align="center" style="{border}padding:16px 6px;">'
                  f'<div style="font-family:{SERIF};font-size:32px;font-weight:bold;color:{INK};line-height:1;">{num}</div>'
                  f'<div style="font-family:{MONO};font-size:9px;font-weight:bold;letter-spacing:2px;color:{ACCENT};padding-top:7px;">{label}</div></td>')
    return f"""
        <tr><td style="border-bottom:1px solid {INK};">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table>
        </td></tr>
"""


def _render_big_story(big_story):
    if not big_story.get("title"):
        return ""
    story_title = escape(big_story.get("title", ""))
    story_text = escape(big_story.get("content", ""))
    drop_cap = ""
    if story_text:
        drop_cap = (f'<span style="float:left;font-family:{SERIF};font-size:56px;line-height:44px;'
                    f'font-weight:bold;color:{ACCENT};padding:5px 10px 0 0;">{story_text[0]}</span>')
        story_text = story_text[1:]
    source_link = ""
    if big_story.get("source"):
        source_link = f'<div style="padding-top:16px;">{_mono_link(big_story["source"], "CONTINUE READING &#8599;")}</div>'
    return f"""
        <tr><td style="padding:30px 40px 32px;">
            {_eyebrow("&#9733; THE BIG STORY")}
            <div style="font-family:{SERIF};font-size:29px;font-weight:bold;line-height:1.15;color:{INK};padding-bottom:14px;">{story_title}</div>
            <div style="font-family:{SERIF};font-size:15px;line-height:1.7;color:{BODY_TXT};">{drop_cap}{story_text}</div>
            {source_link}
        </td></tr>
"""


def _render_papers(papers, all_categories):
    if not papers:
        return ""
    html = _section_band("SECTION 01 &middot; LATEST RESEARCH", f"{len(papers[:5])} PAPERS")

    # FIG. 01 — papers by field
    if all_categories:
        top_cats = all_categories.most_common(5)
        max_count = top_cats[0][1]
        rows = "".join(
            _bar_row(cat, count, max_count, f"{count} PAPER{'S' if count != 1 else ''}",
                     color=ACCENT if k == 0 else INK)
            for k, (cat, count) in enumerate(top_cats)
        )
        html += _figure_box("FIG. 01 &mdash; THIS WEEK&rsquo;S PAPERS BY FIELD", rows)

    for i, paper in enumerate(papers[:5], 1):
        p_title = escape(paper.get('title', 'Untitled'))
        p_url = escape(paper.get('url', '#'), quote=True)
        authors = escape(', '.join(paper.get('authors', ['Unknown'])))
        published = escape(paper.get('published', ''))
        summary = escape(paper.get('summary', 'No summary available'))
        chips = ''.join(_tag_chip(c) for c in paper.get('categories', [])[:3])
        pdf_link = f' &nbsp;&nbsp; {_mono_link(paper["pdf_url"], "PDF &#8595;")}' if paper.get('pdf_url') else ''
        if i > 1:
            html += _dotted_rule()
        html += f"""
        <tr><td style="padding:26px 40px 26px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
                <td width="58" valign="top" style="font-family:{SERIF};font-style:italic;font-size:38px;font-weight:bold;color:{ACCENT};line-height:1;">{i:02d}</td>
                <td valign="top">
                    <a href="{p_url}" target="_blank" style="font-family:{SERIF};font-size:19px;font-weight:bold;line-height:1.25;color:{INK};text-decoration:none;">{p_title}</a>
                    <div style="font-family:{MONO};font-size:11px;letter-spacing:1px;color:{MUTED};padding:8px 0 10px;">{authors} &nbsp;&middot;&nbsp; {published}</div>
                    <div style="font-family:{SERIF};font-size:14px;line-height:1.65;color:{BODY_TXT};padding-bottom:12px;">{summary}</div>
                    <div style="padding-bottom:14px;">{chips}</div>
                    <div>{_mono_link(paper.get('url', '#'), "READ PAPER &#8599;")}{pdf_link}</div>
                </td>
            </tr></table>
        </td></tr>
"""
    return html


def _render_repos(repos):
    if not repos:
        return ""
    html = _section_band("SECTION 02 &middot; TRENDING CODE", f"{len(repos[:5])} REPOS")

    # FIG. 02 — stars comparison
    shown = repos[:5]
    max_stars = max(int(r.get('stars', 0) or 0) for r in shown) or 1
    rows = "".join(
        _bar_row((r.get('name') or '?')[:16].upper(), int(r.get('stars', 0) or 0), max_stars,
                 f"&#9733; {_compact_num(r.get('stars', 0))}",
                 color=ACCENT if k == 0 else INK)
        for k, r in enumerate(shown)
    )
    html += _figure_box("FIG. 02 &mdash; REPOSITORY STARS, THIS WEEK", rows)

    for i, repo in enumerate(shown, 1):
        full_name = repo.get('full_name', repo.get('name', ''))
        r_url = escape(repo.get('url', '#'), quote=True)
        r_name = escape(repo.get('name', 'Unnamed Repo'))
        r_desc = escape(repo.get('description') or 'No description available')
        og_image = escape(f"https://opengraph.githubassets.com/1/{full_name}", quote=True)
        chips = ''.join(_tag_chip(t) for t in repo.get('topics', [])[:3])
        if i > 1:
            html += _dotted_rule()
        html += f"""
        <tr><td style="padding:26px 40px 26px;">
            <a href="{r_url}" target="_blank" style="text-decoration:none;">
                <img src="{og_image}" width="558" alt="{escape(full_name)} &mdash; GitHub repository" style="display:block;width:100%;height:auto;border:1px solid {INK};" />
            </a>
            <div style="padding-top:14px;">
                <a href="{r_url}" target="_blank" style="font-family:{SERIF};font-size:18px;font-weight:bold;color:{INK};text-decoration:none;">{r_name}</a>
            </div>
            <div style="font-family:{MONO};font-size:11px;letter-spacing:1px;color:{MUTED};padding:6px 0 8px;">&#9733; {repo.get('stars', 0):,} &nbsp;&middot;&nbsp; &#8916; {repo.get('forks', 0):,} FORKS &nbsp;&middot;&nbsp; {escape(str(repo.get('language', 'N/A'))).upper()}</div>
            <div style="font-family:{SERIF};font-size:14px;line-height:1.6;color:{BODY_TXT};padding-bottom:12px;">{r_desc}</div>
            <div style="padding-bottom:2px;">{chips}</div>
        </td></tr>
"""
    return html


def _render_products(products):
    if not products:
        return ""
    html = _section_band("SECTION 03 &middot; FRESH TOOLS", f"{len(products[:3])} LAUNCHES")

    # FIG. 03 — upvotes comparison
    shown_products = products[:3]
    max_votes = max(int(p.get('votes', 0) or 0) for p in shown_products) or 1
    rows = "".join(
        _bar_row((p.get('name') or '?')[:16].upper(), int(p.get('votes', 0) or 0), max_votes,
                 f"&#9650; {_compact_num(p.get('votes', 0))}",
                 color=ACCENT if k == 0 else INK)
        for k, p in enumerate(shown_products)
    )
    html += _figure_box("FIG. 03 &mdash; LAUNCH UPVOTES", rows)

    for i, product in enumerate(shown_products, 1):
        if i > 1:
            html += _dotted_rule()
        html += f"""
        <tr><td style="padding:26px 40px 26px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
                <td valign="top">
                    <a href="{escape(product.get('url', '#'), quote=True)}" target="_blank" style="font-family:{SERIF};font-size:19px;font-weight:bold;color:{INK};text-decoration:none;">{escape(product.get('name', 'Unnamed Product'))}</a>
                    <div style="font-family:{SERIF};font-style:italic;font-size:14px;color:{BODY_TXT};padding:6px 0 8px;">{escape(product.get('tagline', ''))}</div>
                </td>
                <td width="90" align="right" valign="top">
                    <span style="font-family:{MONO};font-size:12px;font-weight:bold;background-color:{INK};color:{PAPER};padding:5px 9px;white-space:nowrap;">&#9650; {product.get('votes', 0):,}</span>
                </td>
            </tr></table>
            <div style="font-family:{SERIF};font-size:14px;line-height:1.6;color:{BODY_TXT};padding-bottom:12px;">{escape((product.get('description') or '')[:200])}</div>
            <div>{_mono_link(product.get('url', '#'), "CHECK IT OUT &#8599;")}</div>
        </td></tr>
"""
    return html


def _render_tweets(tweets):
    if not tweets:
        return ""
    html = _section_band("SECTION 04 &middot; HEARD ONLINE", f"{len(tweets[:3])} POSTS")
    for i, tweet in enumerate(tweets[:3], 1):
        if i > 1:
            html += _dotted_rule()
        html += f"""
        <tr><td style="padding:26px 40px 26px;">
            <div style="font-family:{SERIF};font-size:52px;line-height:0.5;color:{ACCENT};padding-top:10px;">&ldquo;</div>
            <div style="font-family:{SERIF};font-style:italic;font-size:17px;line-height:1.55;color:{INK};padding:4px 0 12px;">{escape(tweet.get('text', ''))}</div>
            <div style="font-family:{MONO};font-size:11px;letter-spacing:1px;color:{MUTED};padding-bottom:12px;">&mdash; {escape(tweet.get('author_name', 'Unknown'))} {escape(tweet.get('author', ''))} &nbsp;&middot;&nbsp; &#10084; {tweet.get('likes', 0):,} &nbsp;&middot;&nbsp; &#8635; {tweet.get('retweets', 0):,}</div>
            <div>{_mono_link(tweet.get('url', '#'), "VIEW POST &#8599;")}</div>
        </td></tr>
"""
    return html


def _render_footer():
    return f"""
        <tr><td style="background-color:{INK};padding:30px 40px;">
            <div style="font-family:{MONO};font-size:11px;font-weight:bold;letter-spacing:3px;color:{PAPER};padding-bottom:10px;">THANKS FOR READING</div>
            <div style="font-family:{SERIF};font-style:italic;font-size:16px;color:{PAPER};padding-bottom:16px;">Stay curious, keep learning.</div>
            <div style="border-top:1px solid {MUTED};padding-top:14px;font-family:{MONO};font-size:10px;letter-spacing:1px;color:#A79C87;line-height:1.7;">
                KHABAR AI &mdash; YOUR WEEKLY SIGNAL IN THE NOISE<br>
                You&rsquo;re receiving this because you subscribed to Khabar AI.
            </div>
        </td></tr>

    </table>
    </td></tr>
    </table>
</body>
</html>
"""


# ---- Tools ----

@mcp.tool()
def generate_html_newsletter(draft_content: Dict, template: str = "default") -> Dict:
    """
    Convert newsletter draft into HTML with design specifications.

    Args:
        draft_content: Newsletter draft content dictionary
        template: Template style to use (default, modern, minimal)

    Returns:
        Complete HTML newsletter ready for distribution
    """
    try:
        metadata = draft_content.get("metadata", {})
        sections = draft_content.get("sections", {})

        issue_date = escape(str(metadata.get('date', datetime.now().strftime("%B %d, %Y"))))

        papers = sections.get("top_papers", [])
        repos = sections.get("github_repos", [])
        products = sections.get("ai_products", [])
        tweets = sections.get("tweets", [])
        big_story = sections.get("big_story", {})

        all_categories = Counter()
        for p in papers:
            for c in p.get('categories', []):
                all_categories[c] += 1

        # Preview text shown next to the subject line in inboxes
        preview_bits = []
        if big_story.get("title"):
            preview_bits.append(big_story["title"])
        if papers:
            preview_bits.append(f"{len(papers)} new papers")
        if repos:
            preview_bits.append(f"{len(repos)} trending repos")
        preheader = escape(" · ".join(preview_bits) or "This week in AI")

        html = _render_head_and_masthead(issue_date, preheader)
        html += _render_stat_strip(papers, repos, all_categories)
        html += _render_big_story(big_story)
        html += _render_papers(papers, all_categories)
        html += _render_repos(repos)
        html += _render_products(products)
        html += _render_tweets(tweets)
        html += _render_footer()

        logger.info(f"Generated HTML newsletter ({len(html)} bytes)")

        return {
            "status": "success",
            "html": html,
            "size": len(html),
            "template": template
        }

    except Exception as e:
        logger.error(f"Failed to generate HTML: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


@mcp.tool()
def export_newsletter(content: Dict, format: str = "html") -> Dict:
    """
    Export newsletter in multiple formats (HTML, Markdown, JSON).

    Args:
        content: Newsletter content
        format: Output format (html, markdown, json)

    Returns:
        Exported content in requested format
    """
    try:
        if format == "markdown":
            # Convert to markdown
            md = convert_to_markdown(content)
            return {
                "status": "success",
                "content": md,
                "format": "markdown",
                "size": len(md)
            }
        elif format == "json":
            json_content = json.dumps(content, indent=2)
            return {
                "status": "success",
                "content": json_content,
                "format": "json",
                "size": len(json_content)
            }
        else:
            # HTML is default
            return generate_html_newsletter(content)

    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


def convert_to_markdown(content: Dict) -> str:
    """Helper function to convert newsletter content to Markdown"""
    metadata = content.get("metadata", {})
    sections = content.get("sections", {})

    md = f"""# {metadata.get('title', 'Newsletter')}
{metadata.get('date', '')}

---

"""

    # Big story
    big_story = sections.get("big_story", {})
    if big_story.get("title"):
        md += f"""## 🌟 This Week's Big Story

### {big_story['title']}

{big_story.get('content', '')}

{f"[Read More]({big_story['source']})" if big_story.get('source') else ''}

---

"""

    # Papers
    if sections.get("top_papers"):
        md += "## 📄 Top AI Research Papers\n\n"
        for i, paper in enumerate(sections["top_papers"][:5], 1):
            md += f"""### {i}. {paper.get('title', 'Untitled')}

**Authors:** {', '.join(paper.get('authors', ['Unknown']))}

{paper.get('summary', '')}

[Read Paper]({paper.get('url', '#')})

---

"""

    # Repos
    if sections.get("github_repos"):
        md += "## 💻 Trending GitHub Repositories\n\n"
        for repo in sections["github_repos"][:5]:
            md += f"""### ⭐ {repo.get('name', 'Unnamed')}

{repo.get('description', '')}

**Stats:** {repo.get('stars', 0):,} stars | {repo.get('forks', 0):,} forks | Language: {repo.get('language', 'N/A')}

[View Repository]({repo.get('url', '#')})

---

"""

    # Products
    if sections.get("ai_products"):
        md += "## 🛠️ New AI Products & Tools\n\n"
        for product in sections["ai_products"][:3]:
            md += f"""### {product.get('name', 'Unnamed')}

**{product.get('tagline', '')}**

{product.get('description', '')}

👍 {product.get('votes', 0):,} upvotes | [Check it out]({product.get('url', '#')})

---

"""

    md += "\n**Thanks for reading! 🙌**\n\n*Khabar AI — your weekly signal in the noise*\n"

    return md
