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

# [설정] 깃허브 환경변수 연동
SMTP_SERVER = "://naver.com"
SMTP_PORT = 465
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")

SOURCES = {
    "🇺🇸 New York Times":      "https://nytimes.com",
    "🇺🇸 NYT Business":        "https://nytimes.com",
    "🇺🇸 NYT Technology":      "https://nytimes.com",
    "🇺🇸 Washington Post":     "https://washingtonpost.com",
    "🇺🇸 CNN World":           "http://cnn.com",
    "🇺🇸 CNN Business":        "http://cnn.com",
    "🇺🇸 Wall Street Journal": "https://dj.com",
    "🇺🇸 WSJ Markets":         "https://dj.com",
    "🇺🇸 Financial Times":     "https://ft.com",
    "🇬🇧 Reuters Business":    "https://reuters.com",
    "🇬🇧 Reuters World":       "https://feeds.reuters.com/reuters/worldNews",
    "🌐 EIN Presswire":        "https://www.einnews.com/rss/newsfeed-full",
    "🇯🇵 Asahi Shimbun":       "https://www.asahi.com/rss/asahi/newsheadlines.rdf",
    "🇨🇳 Global Times":        "https://www.globaltimes.cn/rss/outbrain.xml",
    "🇯🇴 Jordan Times":        "https://jordantimes.com/rss/all",
    "🇫🇷 Le Monde":            "https://www.lemonde.fr/rss/une.xml",
    "🇫🇷 Le Figaro":           "https://www.lefigaro.fr/rss/figaro_actualites.xml",
    "🇩🇪 Der Spiegel":         "https://www.spiegel.de/international/index.rss",
    "🇩🇪 Die Welt":            "https://www.welt.de/feeds/section/wirtschaft.rss",
    "이코노미스트":            "https://naver.com",
    "매일경제":                "https://naver.com",
}

# 키워드를 더욱 직관적이고 포괄적으로 튜닝 (매칭 확률 상승)
KEYWORDS = {
    "💹 경제/금융": [
        "economy", "economic", "finance", "financial", "market", "stock", "bond",
        "inflation", "recession", "gdp", "trade", "investment", "bank", "currency",
        "interest rate", "fed", "금리", "주식", "채권", "환율", "증시", "물가", "상승", "하락",
        "인플레이션", "금융", "펀드", "경제", "시장", "수출"
    ],
    "💻 기술/IT": [
        "technology", "tech", "ai", "artificial intelligence", "chip", "semiconductor",
        "software", "hardware", "nvidia", "openai", "apple", "google", "microsoft",
        "인공지능", "반도체", "칩", "소프트웨어", "빅테크", "기술", "it", "로봇", "드론", "과학"
    ],
}

MAX_ITEMS_PER_SOURCE = 3  # 검사 대상을 3개에서 5개로 늘려 누락 방지

def fetch_feed(name, url):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
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
                    
                    # 변경: 시차와 수집 공백을 감안하여 24시간에서 48시간으로 유연화
                    if age_hours > 48:
                        is_recent = False
                except Exception:
                    pass
            if title and link and is_recent:
                items.append({"title": title, "link": link, "summary": summary, "date": pub_date})
        return items
    except Exception as e:
        print(f"  ⚠️  {name} 에러: {e}")
        return []

def categorize(title, summary):
    text = (title + " " + summary).lower()
    for cat, kws in KEYWORDS.items():
        if any(kw in text for kw in kws):
            return cat
    return None

def build_html(articles):
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    date_str = now_kst.strftime("%Y년 %m월 %d일 (%A)")
    cat_map = {}
    
    for source, items in articles.items():
        for item in items:
            cat = categorize(item["title"], item["summary"])
            if cat is not None:
                cat_map.setdefault(cat, []).append((source, item))

    cat_order = ["💹 경제/금융", "💻 기술/IT"]
    sections_html = ""
    total_articles = sum(len(v) for v in cat_map.values())

    for cat in cat_order:
        if cat not in cat_map:
            continue
        items = cat_map[cat]
        articles_html = ""
        for source, item in items:
            articles_html += f"""
            <div style="border-left:3px solid #2563eb;margin:12px 0;padding:10px 14px;background:#f8fafc;border-radius:0 6px 6px 0;">
              <div style="font-size:11px;color:#64748b;margin-bottom:4px;">{source}</div>
              <a href="{item['link']}" style="font-size:15px;font-weight:600;color:#1e293b;text-decoration:none;display:block;margin-bottom:5px;">{item['title']}</a>
              {f'<div style="font-size:13px;color:#475569;">{item["summary"]}</div>' if item["summary"] else ""}
            </div>"""

        sections_html += f"""<div style="margin-bottom:32px;"><h2 style="font-size:18px;color:#1e293b;padding:8px 14px;background:linear-gradient(135deg,#dbeafe,#ede9fe);border-radius:6px;display:inline-block;">{cat} ({len(items)}건)</h2>{articles_html}</div>"""

    # 변경: 기사가 0건이어도 구조적인 빈 메일 양식을 반환하여 메일 전송 프로세스를 강제 진행
    if total_articles == 0:
        sections_html = '<p style="color:#64748b;font-size:14px;padding:20px;text-align:center;background:#f8fafc;border-radius:6px;">최근 시간대 내에 설정하신 경제/IT 핵심 키워드와 일치하는 새로운 뉴스가 없습니다.</p>'

    return f"""<!DOCTYPE html><html><body style="padding:20px;background-color:#f1f5f9;"><div style="max-width:600px;margin:0 auto;background:#ffffff;padding:24px;border-radius:12px;"><h1>🌐 Global News Digest</h1><p>{date_str} 브리핑 (경제/금융/IT 전문)</p><hr style="border:0;border-top:1px solid #e2e8f0;margin:20px 0;">{sections_html}</div></body></html>"""

def send_email(html_content):
    if not EMAIL_USER or not EMAIL_PASSWORD or not RECIPIENT_EMAIL:
        print("❌ 에러: 이메일 환경변수(Secrets) 설정이 누락되었습니다.")
        return

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    subject = f"🌐 경제/금융/IT 뉴스 다이제스트 - {now_kst.strftime('%m/%d')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_content, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        print("📬 이메일 전송 프로세스가 완료되었습니다.")
    except Exception as e:
        print(f"❌ 이메일 발송 중 실패: {e}")

if __name__ == "__main__":
    print("🚀 뉴스 수집 시작...")
    raw_articles = {}
    for name, url in SOURCES.items():
        items = fetch_feed(name, url)
        if items:
            raw_articles[name] = items
        time.sleep(0.5)
    
    print("🎨 HTML 빌드 및 필터링 적용 중...")
    email_body = build_html(raw_articles)
    
    # 무조건 메일 발송 시도
    send_email(email_body)
