"""
Global News Digest - Daily Email Newsletter
"""

import feedparser
import smtplib
import ssl
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import time

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
    "🇯🇵 Yomiuri Shimbun":     "https://www.yomiuri.co.jp/rss/feed",
    "🇯🇵 Nikkei Asia":         "https://asia.nikkei.com/rss/feed/nar",
    "🇨🇳 Global Times":        "https://www.globaltimes.cn/rss/outbrain.xml",
    "🇨🇳 People's Daily":      "http://en.people.cn/rss/90001.xml",
    "🇯🇴 Jordan Times":        "https://jordantimes.com/rss/all",
    "🇫🇷 Le Monde":            "https://www.lemonde.fr/rss/une.xml",
    "🇫🇷 Le Figaro":           "https://www.lefigaro.fr/rss/figaro_actualites.xml",
    "🇩🇪 Der Spiegel":         "https://www.spiegel.de/international/index.rss",
    "🇩🇪 Die Welt":            "https://www.welt.de/feeds/section/wirtschaft.rss",
    "🇩🇪 FAZ":                 "https://www.faz.net/rss/aktuell/",
    "이코노미스트":            "https://www.economist.co.kr/article/list/ecn_sc003001000",
    "매일경제":                "https://www.mk.co.kr/news/finalcial/financial-policy",
}

KEYWORDS = {
    "💹 경제/금융": [
        "economy", "economic", "finance", "financial", "market", "stock", "bond",
        "inflation", "recession", "gdp", "trade", "investment", "bank", "currency",
        "interest rate", "fed", "ecb", "imf", "wto", "export", "import",
        "wirtschaft", "markt", "économie", "経済", "金融", "经济","금리","부채","주식","채권",
    ],
    "💻 기술/IT": [
        "technology", "tech", "ai", "artificial intelligence", "chip", "semiconductor",
        "software", "hardware", "cyber", "digital", "physical ai", "startup", "silicon valley",
        "apple", "google", "microsoft", "meta", "amazon", "nvidia", "openai",
        "coreweave", "palantir technology", "nuscale power", "intel",
        "technologie", "テクノロジー", "科技",
    ],
    "🏛️ 정치/외교": [
        "politics", "political", "government", "election", "president", "congress",
        "senate", "parliament", "policy", "diplomacy", "nato", "united nations",
        "sanction", "war", "conflict", "treaty", "summit", "minister",
        "trump", "biden", "xi jinping", "putin", "politik", "politique", "政治",
    ],
}

MAX_ITEMS_PER_SOURCE = 5


def fetch_feed(name, url):
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            summary = re.sub(r"<[^>]+>", "", summary)
            summary = summary[:200] + "…" if len(summary) > 200 else summary
            pub_date = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    pub_date = dt.strftime("%Y-%m-%d %H:%M UTC")
                except Exception:
                    pass
            # 날짜 필터링: 최근 24시간 이내 기사만 포함
            if title and link:
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        now_utc = datetime.now(timezone.utc)
                        age_hours = (now_utc - pub_dt).total_seconds() / 3600
                        if age_hours > 24:
                            continue  # 24시간 넘은 기사 제외
                    except Exception:
                        pass  # 날짜 파싱 실패 시 일단 포함
                items.append({"title": title, "link": link,
                              "summary": summary, "date": pub_date})
        return items
    except Exception as e:
        print(f"  ⚠️  {name}: {e}")
        return []


def categorize(title, summary):
    text = (title + " " + summary).lower()
    for cat, kws in KEYWORDS.items():
        if any(kw in text for kw in kws):
            return cat
    return "🌍 일반/국제"


def collect_all_news():
    all_articles = {}
    total = 0
    for name, url in SOURCES.items():
        print(f"  📰 {name} 수집 중...")
        items = fetch_feed(name, url)
        if items:
            all_articles[name] = items
            total += len(items)
        time.sleep(0.3)
    print(f"\n  ✅ 총 {total}개 기사 수집 완료")
    return all_articles


def build_html(articles):
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    date_str = now_kst.strftime("%Y년 %m월 %d일 (%A)")
    cat_map = {}
    for source, items in articles.items():
        for item in items:
            cat = categorize(item["title"], item["summary"])
            cat_map.setdefault(cat, []).append((source, item))

    cat_order = ["💹 경제/금융", "💻 기술/IT", "🏛️ 정치/외교", "🌍 일반/국제"]
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

    source_stats = "".join(
        f'<span style="display:inline-block;margin:3px 4px;padding:2px 8px;background:#f1f5f9;border-radius:12px;font-size:11px;color:#64748b;">{s} ({len(i)})</span>'
        for s, i in articles.items()
    )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>글로벌 뉴스 다이제스트 - {date_str}</title></head>
<body style="margin:0;padding:0;font-family:'Segoe UI','Apple SD Gothic Neo',sans-serif;background:#f0f4f8;">
<div style="max-width:720px;margin:0 auto;background:#ffffff;">
  <div style="background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);padding:32px;text-align:center;">
    <div style="font-size:11px;letter-spacing:3px;color:#93c5fd;text-transform:uppercase;margin-bottom:8px;">Global News Digest</div>
    <h1 style="margin:0;font-size:26px;font-weight:800;color:#ffffff;">{date_str}</h1>
    <div style="margin-top:12px;font-size:13px;color:#bfdbfe;">
      📊 총 <strong style="color:#fff;">{total_articles}건</strong> · <strong style="color:#fff;">{len(articles)}개</strong> 언론사
    </div>
  </div>
  <div style="padding:28px 32px;">{sections_html}</div>
  <div style="padding:20px 32px;background:#f8fafc;border-top:1px solid #e2e8f0;">{source_stats}</div>
  <div style="padding:20px 32px;background:#1e3a5f;text-align:center;">
    <div style="font-size:12px;color:#93c5fd;">
      GitHub Actions + RSS로 자동 생성<br>
      <span style="color:#64748b;font-size:11px;">Generated at {now_kst.strftime('%Y-%m-%d %H:%M KST')}</span>
    </div>
  </div>
</div></body></html>"""


def send_email(html_content, subject):
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipients_raw = os.environ.get("RECIPIENT_EMAILS", sender)
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"글로벌 뉴스 다이제스트 <{sender}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())
    print(f"  ✉️  발송 완료 → {', '.join(recipients)}")


def main():
    print("\n🌐 글로벌 뉴스 다이제스트 시작\n" + "─" * 50)
    print("\n[1/3] RSS 피드 수집 중...")
    articles = collect_all_news()
    print("\n[2/3] HTML 생성 중...")
    html = build_html(articles)
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    subject = f"📰 글로벌 뉴스 다이제스트 | {now_kst.strftime('%Y년 %m월 %d일')}"
    print("\n[3/3] 이메일 발송 중...")
    send_email(html, subject)
    print("\n✅ 완료!\n" + "─" * 50)


if __name__ == "__main__":
    main()
