"""
Global News Digest - Daily Email Newsletter
"""

import feedparser
import smtplib
import ssl
import os
import re
import socket
from html import escape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import time

# 느린/응답 없는 피드 보호용 글로벌 소켓 타임아웃 (초)
socket.setdefaulttimeout(10)

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
    "매일경제":                "https://www.mk.co.kr/rss/30100041/",
    "한국경제":                "https://www.hankyung.com/feed/finance",
}

KEYWORDS = {
    "💹 경제/금융": [
        "economy", "economic", "finance", "financial", "market", "stock", "bond",
        "inflation", "recession", "gdp", "trade", "investment", "bank", "banking", "currency",
        "interest rate", "fed", "ecb", "imf", "wto", "export", "import", "monetary",
        "wirtschaft", "markt", "économie", "経済", "金融", "经济",
        "금리","부채","주식","채권","환율","물가",
    ],
    "💻 기술/IT": [
        "technology", "tech", "ai", "openai", "artificial intelligence", "chip", "chips", "semiconductor",
        "software", "hardware", "cyber", "digital", "physical ai", "startup", "silicon valley",
        "apple", "google", "microsoft", "meta", "amazon", "nvidia", "openai",
        "coreweave", "palantir technology", "nuscale power", "intel", "quantum", "quantum computing",
        "technologie", "テクノロジー", "科技",
    ],
    "🏛️ 정치/외교": [
        "politics", "political", "government", "election", "president", "congress",
        "senate", "parliament", "policy", "diplomacy", "nato", "united nations", "legislation",
        "sanction", "war", "conflict", "treaty", "summit", "minister", "prime minister",
        "trump", "biden", "xi jinping", "putin", "politik", "politique", "政治",
    ],
}

MAX_ITEMS_PER_SOURCE = 5


def fetch_feed(name, url):                        # name(피드이름)과 url(RSS주소)을 받는 함수를 정의합니다.
    try:
        feed = feedparser.parse(url)                # feedparser 라이브러리로 해당 url의 rss/atom 피드를 파싱합니다.
        items = []                                   # 결과를 담을 빈 리스트 생성
        for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:  # 피드에서 가져온 항목들 중 최대 max_items_per_source개만 순회함
            title = entry.get("title", "").strip()        # 항목의 제목을 가져오고 없으면 빈 문자열 앞뒤 공백을 제거함
            link = entry.get("link", "").strip()            # 항목의 링크(url)을 가져옴
            summary = entry.get("summary", entry.get("description", "")).strip()    # 요약문을 가져옴. summary가 없으면 description을 사용하고 둘다 없으면 빈 문자열임
            summary = re.sub(r"<[^>]+>", "", summary)      #정규식으로 요약문 안의 HTML 태그 모두 제거함
            summary = summary[:400] + "…" if len(summary) > 400 else summary    # 요약문이 400자를 넘으면 잘라내고 ... 를 붙임. 200자 이하면 그래로 둠
            pub_date = ""                                                        # 발행일 문자열을 담을 변수를 빈 값으로 초기화
            if hasattr(entry, "published_parsed") and entry.published_parsed:    # 항목에 파싱된 날짜(published_parsed)가 존재하는지 확인
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)    # published_parsed는 튜플형식이므로 앞 6개 값(년,월,일,시,분,초)로 datetime객체를 만듬. UTC기준
                    pub_date = dt.strftime("%Y-%m-%d %H:%M UTC")        # 날짜를 2026-01-02  10:20 UTC 형식의 문자열로 변환
                except (TypeError,ValueError):
                    pass
            # 날짜 필터링: 최근 24시간 이내 기사만 포함
            if title and link:                        # 제목과 링크가 모두 있을때만 처리
                if hasattr(entry, "published_parsed") and entry.published_parsed:        # 날짜 정보가 있는 경우에만 필터링 진행
                    try:
                        pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)  # 기사의 발행시각과      
                        now_utc = datetime.now(timezone.utc)                                # 현재 UTC시각을 각각 구함
                        age_hours = (now_utc - pub_dt).total_seconds() / 3600            # 두 시각 차이를 초 단위로 구한 뒤 3600으로 나눠 경과 시간(시간 단위)을 계산
                        if age_hours > 24:                                            
                            continue  # 24시간 넘은 기사 제외
                    except (TypeError,ValueError):
                        pass  # 날짜 파싱 실패 시 일단 포함
                items.append({"title": title, "link": link,                # 필터를 통과한 기사를 딕셔너리로 만들어 리스트에 추가함
                              "summary": summary, "date": pub_date})
        return items                                                        # 수집된 기사 목록 반환
    except Exception as e:                        # 전체 함수 실행 중 오류가 발생하면 경고 메시지를 출력하고 빈 리스트를 반환(프로그램이 멈추지 않도록 방어 처리)
        print(f"  ⚠️  {name}: {e}")
        return []


def categorize(title, summary):
    text = (title + " " + summary).lower()    # 제목과 요약을 합쳐서 소문자로 변환한 텍스트를 만듦(대소문자 구분 없이 키워드를 찾기 위함)
    # HTML 엔티티 및 특수문자 정규화
    text = re.sub(r"['\u2019\u2018]","'", text) # 스마트 따옴표 정규화(' 일반따옴표, U2019: 왼쪽 방향 스마트 따옴표(`), U2018: 오른쪽 방향)
    text = re.sub(r"[-–—]", " ", text)    # 하이픈, en dash, em dash -> 공백 (interest-rate -> interest rate)
    text = re.sub(r"[^\w\s]", " ", text)    # 나머지 특수문자 제거: (^ 뒤에 오는 것(\w\s) 제외, \w 영어알파벳 숫자 언더스코어, \s 공백문자(스페이스, 탭, 줄바꿈)
    text = re.sub(r"\s+", " ", text)        # 다중 공백 정리, 검색대상이 2개 이상일때 대괄호[] 사용하고 or의 의미임
    
    for cat, kws in KEYWORDS.items():
        for kw in kws:
            kw_clean = re.sub(r"[-–—]", " ", kw.lower())
            if " " in kw_clean:
                # 복합 키워드 : 구문 그대로 검색 (단어 경계 불필요)
                if kw_clean in text:
                    return cat
            else:
                # 단일 키워드: 반드시 단어 경계(\b) 적용
                if re.search(rf"\b{re.escape(kw_clean)}\b",text):
                    return cat
                    
#        if any(kw in text for kw in kws):
#            return cat                        # keywords 딕셔너리(카테고리별 키워드 목록)를 순회하며, 키워드 중 하나라도 text에 포함되어 있으면 해당 카테고리를 반환함
    return "🌍 일반/국제"                      # 어떤 카테고리에도 매칭되지 않으면 기본값으로 "일반/국제"카테고리를 반환함


def collect_all_news():
    all_articles = {}
    total = 0                                    # 모든 뉴스를 담을 딕셔너리와 총 기사수를 셀 변수를 초기화함
    for name, url in SOURCES.items():
        print(f"  📰 {name} 수집 중...")
        items = fetch_feed(name, url)            # sources(언론사명:URL)를 순회하며 각 소스에서 fetch_feed로 기사를 가져옴
        if items:
            all_articles[name] = items
            total += len(items)                    # 가져온 기사가 있으면 딕셔너리에 저장하고 총 개수에 더함
        time.sleep(0.3)                            # 다음 요청 전 0.3초 대기(서버 부담 방지/차단 회피)
    print(f"\n  ✅ 총 {total}개 기사 수집 완료")
    return all_articles                            # 수집 결과를 출력하고 소스별 기사 딕셔너리를 반환함


def build_html(articles):
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    date_str = now_kst.strftime("%Y년 %m월 %d일 (%A)")            # 한국 시간 기준 현재 시각을 구하고 "2026년 06월 12일(Friday)"형식의 날짜 문자열을 만듭니다
    # 카테고리별로 (출처,기사) 묶기
    cat_map = {}
    for source, items in articles.items():
        for item in items:
            cat = categorize(item["title"], item["summary"])
            cat_map.setdefault(cat, []).append((source, item))        # 모든 기사를 순회하며 categorize로 카테고리를 정하고 카테고리별로 (출처,기사) 튜플을 모은
                                                                        # 딕셔너리(cat_map)를 만듦
    cat_order = ["💹 경제/금융", "💻 기술/IT", "🏛️ 정치/외교", "🌍 일반/국제"]        # HTML에 출력할 카테고리 순서를 정의함
    sections_html = ""
    total_articles = sum(len(v) for v in cat_map.values())                    # 섹션 HTML을 누적할 빈 문자열과 전체 기사수를 계산

    for cat in cat_order:
        if cat not in cat_map:
            continue                # 정해진 카테고리 순서대로 순회하며 해당 카테고리에 기사가 없으면 건너뜀
        items = cat_map[cat]
        articles_html = ""
        for source, item in items:        # 해당 카테고리의(출처, 기사)목록을 가져와, 각 기사별 HTML을 누적할 변수를 준비합니다.
            safe_source = escape(source)
            safe_title = escape(item["title"])
            safe_summary = escape(item["summary"]) if item["summary"] else ""
            safe_link = escape(item["link"], quote=True)
            safe_date = escape(item["date"]) if item["date"] else ""
            date_html = f' <span style="color:#94a3b8;">· {safe_date}</span>' if safe_date else ""
            summary_html = (
                f'<div style="font-size:13px;color:#475569;line-height:1.6;">{safe_summary}</div>'
                if safe_summary else ""
            )
            articles_html += f"""
            <div style="border-left:3px solid #2563eb;margin:12px 0;padding:10px 14px;background:#f8fafc;border-radius:0 6px 6px 0;">
              <div style="font-size:11px;color:#64748b;margin-bottom:4px;">
                {safe_source}{date_html}
              </div>
              <a href="{safe_link}" style="font-size:15px;font-weight:600;color:#1e293b;text-decoration:none;line-height:1.4;display:block;margin-bottom:5px;">
                {safe_title}
              </a>
              {summary_html}
            </div>"""
    
        sections_html += f"""
             <div style="margin-bottom:32px;">
               <h2 style="font-size:18px;font-weight:700;color:#1e293b;margin:0 0 12px 0;
                     padding:8px 14px;background:linear-gradient(135deg,#dbeafe,#ede9fe);
                     border-radius:6px;display:inline-block;">{escape(cat)}
             <span style="font-size:13px;font-weight:400;color:#64748b;margin-left:8px;">{len(items)}건</span>
             </h2>
             {articles_html}
        </div>"""

    source_stats = "".join(
        f'<span style="display:inline-block;margin:3px 4px;padding:2px 8px;background:#f1f5f9;border-radius:12px;font-size:11px;color:#64748b;">{escape(s)} ({len(i)})</span>'
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
    password = os.environ["GMAIL_APP_PASSWORD"]                            # GitHub Actions의 환경변수(시크릿)에서 발신자 이메일과 앱 비밀번호를 가져옴
    recipients_raw = os.environ.get("RECIPIENT_EMAILS", sender)
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]    # 수신자 목록을 환경변수에서 읽되, 없으면 발신자 자신을 수신자로 사용.쉼표로 구분된 여러 이메일을 리스트로 만듬(공백제거, 빈값제외)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"글로벌 뉴스 다이제스트 <{sender}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_content, "html", "utf-8"))        # 이메일 메시지를 구성: 제목, 발신자 표시 이름, 수신자 목록, HTML본문을 첨부

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())    # SSL로 Gmail SMTP서버에 접속하여 로그인 후 메일을 발송함
    print(f"  ✉️  발송 완료 → {', '.join(recipients)}")        # 발송 완료 메시지를 출력함


def main():
    print("\n🌐 글로벌 뉴스 다이제스트 시작\n" + "─" * 50)    # 시작 안내 메시지를 출력(구분선 포함)
    print("\n[1/3] RSS 피드 수집 중...")
    articles = collect_all_news()                            # 1단계: 모든 소스에서 뉴스를 수집함
    print("\n[2/3] HTML 생성 중...")                        
    html = build_html(articles)                               # 2단계: 수집한 기사로 HTML콘텐츠를 생성함
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    subject = f"📰 글로벌 뉴스 다이제스트 | {now_kst.strftime('%Y년 %m월 %d일')}"        # 현재 한국 시각 기준으로 메일 제목 작성
    print("\n[3/3] 이메일 발송 중...")
    send_email(html, subject)                # 3단계: 생성된 HTML을 이메일로 발송함
    print("\n✅ 완료!\n" + "─" * 50)        # 완료 메시지를 출력


if __name__ == "__main__":
    main()                    # 이 파일을 직접 실행할 때 main()함수를 호출(다른 파일에서 import할때는 실행되지 않음)
