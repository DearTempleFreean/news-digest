"""
Global News Digest - Daily Email Newsletter
"""

import feedparser
import smtplib
import ssl
import os
import re
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import time

# 1. SOURCES 주소 정상화 (반드시 XML 형태의 RSS 주소여야 합니다)
SOURCES = {
    "🇺🇸 New York Times":      "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "🇺🇸 NYT Business":        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "🇺🇸 NYT Technology":      "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "🇺🇸 Washington Post":     "https://feeds.washingtonpost.com/rss/world",
    "🇺🇸 CNN World":           "http://rss.cnn.com/rss/edition_world.rss",
    "🇺🇸 CNN Business":        "http://rss.cnn.com/rss/money_news_international.rss",
    "🇺🇸 Fox News World":      "https://moxie.foxnews.com/google-publisher/world.xml",
    "🇺🇸 Wall Street Journal": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "🇺🇸 WSJ Markets":         "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "🇺🇸 Financial Times":     "https://www.ft.com/rss/home",
    "🇺🇸 AP News":             "https://feeds.apnews.com/apf-topnews",
    "🇬🇧 The Times (UK)":      "https://www.thetimes.co.uk/feed/",
    "🇬🇧 Reuters World":       "https://feeds.reuters.com/reuters/worldNews",
    "🇬🇧 Reuters Business":    "https://feeds.reuters.com/reuters/businessNews",
    "🌐 EIN Presswire":        "https://www.einnews.com/rss/newsfeed-full",
    "🇯🇵 Asahi Shimbun":       "https://www.asahi.com/rss/asahi/newsheadlines.rdf",
    "🇨🇳 Global Times":        "https://www.globaltimes.cn/rss/outbrain.xml",
    "🇯🇴 Jordan Times":        "https://jordantimes.com/rss/all",
    "🇫🇷 Le Monde":            "https://www.lemonde.fr/rss/une.xml",
    "🇫🇷 Le Figaro":           "https://www.lefigaro.fr/rss/figaro_actualites.xml",
    "🇩🇪 Der Spiegel":         "https://www.spiegel.de/international/index.rss",
    "🇩🇪 Die Welt":            "https://www.welt.de/feeds/section/wirtschaft.rss",
    "이코노미스트":            "https://naver.com",  # 네이버 제공 이코노미스트 RSS로 수정
    "매일경제":                "https://naver.com",  # 네이버 제공 매일경제 전체 RSS로 수정
}

# 2. 키워드 고도화 (금융, 경제, IT, AI 분야만 명시하고 한국어 키워드 대폭 추가)
KEYWORDS = {
    "💹 경제/금융": [
        "economy", "economic", "finance", "financial", "market", "stock", "bond",
        "inflation", "recession", "gdp", "trade", "investment", "bank", "currency",
        "interest rate", "fed", "ecb", "imf", "wto", "export", "import",
        "wirtschaft", "markt", "économie", "経済", "金融", "经济",
        "금리", "부채", "주식", "채권", "환율", "증시", "코스피", "코스닥", "나스닥", "물가", 
        "인플레이션", "경기침체", "수출", "수입", "투자", "금융", "은행", "재정", "세금"
    ],
    "💻 기술/IT": [
        "technology", "tech", "ai", "artificial intelligence", "chip", "semiconductor",
        "software", "hardware", "cyber", "digital", "physical ai", "startup", "silicon valley",
        "apple", "google", "microsoft", "meta", "amazon", "nvidia", "openai",
        "coreweave", "palantir technology", "nuscale power", "intel",
        "technologie", "テクノロジー", "科技",
        "인공지능", "반도체", "칩", "소프트웨어", "하드웨어", "사이버", "디지털", "스타트업", 
        "실리콘밸리", "엔비디아", "빅테크", "클라우드", "로봇", "플랫폼", "애플", "마이크로소프트"
    ],
}

MAX_ITEMS_PER_SOURCE = 3

def fetch_feed(name, url):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            html_content = response.read()
            feed = feedparser.parse(html_content)
            
        items = []
        for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            summary = re.sub(r"<[^>]+>", "", summary)
            summary = summary[:200] + "…" if len(summary) > 200 else summary
            
            pub_date = ""
            is_recent = True
            
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    pub_date = dt.strftime("%Y-%m-%d %H:%M UTC")

                    now_utc = datetime.now(timezone.utc)
                    age_hours = (now_utc - dt).total_seconds() / 3600
                    if age_hours > 24:
                        is_recent = False
                except Exception:
                    pass
                    
            if title and link and is_recent:
                items.append({"title": title, "link": link, "summary": summary, "date": pub_date})
        return items
    except Exception as e:
        print(f"  ⚠️  {name} 수집 중 에러 발생: {e}")
        return []

# 3. 카테고리 매칭 로직 수정 (원하는 키워드가 아예 없는 경우 None을 반환하여 탈락시킴)
def categorize(title, summary):
    text = (title + " " + summary).lower()
    for cat, kws in KEYWORDS.items():
        if any(kw in text for kw in kws):
            return cat
    return None  # 금융, 경제, IT, AI 분야가 아니면 None 반환

def collect_all_news():
    all_articles = {}
    total = 0
    for name, url in SOURCES.items():
        print(f"  📰 {name} 수집 중...")
        items = fetch_feed(name, url)
        if items:
            all_articles[name] = items
            total += len(items)
        time.sleep(0.5)
    print(f"\n  ✅ 총 {total}개 기사 1차 수집 완료")
    return all_articles

# 4. HTML 빌드 함수 수정 (정형화된 카테고리만 통과시키고, 빈 섹션은 아예 만들지 않음)
def build_html(articles):
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    date_str = now_kst.strftime("%Y년 %m월 %d일 (%A)")
    cat_map = {}
    
    # 기사 분류 및 필터링 적용
    for source, items in articles.items():
        for item in items:
            cat = categorize(item["title"], item["summary"])
            if cat is not None:  # 중요: 카테고리가 지정된(필터링 통과한) 기사만 담음
                cat_map.setdefault(cat, []).append((source, item))

    cat_order = ["💹 경제/금융", "💻 기술/IT"]
    sections_html = ""
    total_filtered_articles = sum(len(v) for v in cat_map.values())

    for cat in cat_order:
        if cat not in cat_map:
            continue
        items = cat_map[cat]
        articles_html = ""
        for source, item in items:
            articles_html += f"""
            <div style="border-left:3px solid #2563eb;margin:12px 0;padding:10px 14px;background:#f8fafc;border-radius:0 6px 6px 0;">
              <div style="font-size:11px;color:#64748b;margin-bottom:4px;">
                {source}{f' <span style="color:#94a3b8;">· {item["date"]}</span>' if item["date"] else ""}
              </div>
              <a href="{item['link']}" style="font-size:15px;font-weight:600;color:#1e293b;text-decoration:none;line-height:1.4;display:block;margin-bottom:5px;">
                {item['title']}
              </a>
              {f'<div style="font-size:13px;color:#475569;line-height:1.6;">{item["summary"]}</div>' if item["summary"] else ""}
            </div>"""

        sections_html += f"""
        <div style="margin-bottom:32px;">
          <h2 style="font-size:18px;font-weight:700;color:#1e293b;margin:0 0 12px 0;
                     padding:8px 14px;background:linear-gradient(135deg,#dbeafe,#ede9fe);
                     border-radius:6px;display:inline-block;">{cat}
            <span style="font-size:13px;font-weight:400;color:#64748b;margin-left:8px;">{len(items)}건</span>
          </h2>
          {articles_html}
        </div>"""

    # 최종 메일 본문 구성 (통과된 뉴스 통계 출력)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>글로벌 뉴스 다이제스트 - {date_str}</title></head>
<body style="margin:0;padding:20px;background-color:#f1f5f9;font-family:sans-serif;">
<div style="max-width:600px;margin:0 auto;background:#ffffff;padding:24px;border-radius:12px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);">
  <h1 style="font-size:22px;color:#0f172a;margin-top:0;">🌐 Global News Digest</h1>
  <p style="font-size:14px;color:#475569;">선택하신 전문 분야 핵심 뉴스 브리핑 ({date_str})</p>
  <hr style="border:0;border-top:1px solid #e2e8f0;margin:20px 0;">
  {sections_html if total_filtered_articles > 0 else '<p style="color:#64748b;font-size:14px;">최근 24시간 동안 필터링 조건에 부합하는 새로운 뉴스가 없습니다.</p>'}
</div>
</body>
</html>"""
