"""
DART 공시/실적 트래커
----------------------
관심 기업들의 DART 신규 공시(전체) + 최근 실적(재무) 정보를 취합해
이메일로 요약 발송합니다.

동작 방식:
1) DART Open API의 고유번호(corpCode) 매핑 파일을 다운로드/캐시
2) 종목코드 -> corp_code 변환
3) 최근 N일간의 신규 공시 목록 조회 (list.json)
4) 정기보고서(사업/분기/반기보고서)가 있으면 주요 재무수치(매출, 영업이익, 순이익) 조회
5) 결과를 정리해서 이메일 발송

필요한 GitHub Secrets (기존 뉴스 스크랩 repo에 이미 등록되어 있는 것을 그대로 재사용):
- DART_API_KEY       : opendart.fss.or.kr 에서 발급받은 인증키 (신규 추가 필요)
- gmail_address       : 보내는 Gmail 주소 (기존 것 재사용)
- gmail_app_password  : Gmail 앱 비밀번호 (기존 것 재사용)
- recipient_emails    : 받는 사람 이메일. 여러 명이면 쉼표(,)로 구분된 문자열 (기존 것 재사용)

SMTP는 Gmail 고정값(smtp.gmail.com:587)을 사용합니다.
"""

import os
import io
import json
import zipfile
import smtplib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DART_API_KEY = os.environ["DART_API_KEY"]

# ── 관심 기업 목록 (종목코드 기준) ──────────────────────────────
WATCHLIST = {
    "082920": "비츠로셀",
    "267270": "HD현대건설기계",
    "006730": "서부T&D",
    "042660": "한화오션",
    "187870": "디바이스이엔지",  # 종목코드 기준 정식 종목명은 실행 시 자동 검증됨
}

# 조회 기간 (기본: 최근 1일 = 스케줄 주기에 맞춰 조정)
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "1"))

CORP_CODE_CACHE = "corpCode.json"

# 실적/재무 관련으로 간주할 보고서명 키워드
FINANCIAL_REPORT_KEYWORDS = ["사업보고서", "분기보고서", "반기보고서", "잠정실적", "실적"]

# 주요사항(이슈)으로 강조할 키워드
ISSUE_KEYWORDS = [
    "유상증자", "무상증자", "자기주식", "자사주", "전환사채", "신주인수권부사채",
    "타법인 주식", "대규모 계약", "영업정지", "감사보고서", "관리종목", "상장폐지",
    "최대주주", "합병", "분할", "소송",
]


def get_corp_code_map():
    """DART 전체 고유번호 매핑을 다운로드(1회 캐시)하고 종목코드->corp_code 딕셔너리 반환."""
    if os.path.exists(CORP_CODE_CACHE):
        with open(CORP_CODE_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)

    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    resp = requests.get(url, params={"crtfc_key": DART_API_KEY}, timeout=30)
    resp.raise_for_status()

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    xml_bytes = zf.read("CORPCODE.xml")
    root = ET.fromstring(xml_bytes)

    mapping = {}
    for item in root.findall("list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        corp_code = (item.findtext("corp_code") or "").strip()
        corp_name = (item.findtext("corp_name") or "").strip()
        if stock_code:
            mapping[stock_code] = {"corp_code": corp_code, "corp_name": corp_name}

    with open(CORP_CODE_CACHE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False)

    return mapping


def get_recent_disclosures(corp_code, bgn_de, end_de):
    """특정 기업의 기간 내 신규 공시 목록 조회."""
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_count": 100,
    }
    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()
    if data.get("status") != "000":
        return []
    return data.get("list", [])


def get_financial_summary(corp_code, bsns_year, reprt_code="11013"):
    """
    단일회사 주요계정 재무정보 조회.
    reprt_code: 11013(1분기) 11012(반기) 11014(3분기) 11011(사업보고서/연간)
    """
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "fs_div": "CFS",  # 연결재무제표 (없으면 개별 OFS로 재시도)
    }
    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()

    if data.get("status") != "000":
        params["fs_div"] = "OFS"
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        if data.get("status") != "000":
            return None

    items = data.get("list", [])
    targets = {"매출액": None, "영업이익": None, "당기순이익": None}
    for it in items:
        name = it.get("account_nm", "")
        if it.get("fs_div") not in ("CFS", "OFS"):
            continue
        for key in targets:
            if targets[key] is None and key in name:
                targets[key] = it.get("thstrm_amount")
    return targets


def classify(report_nm):
    is_financial = any(k in report_nm for k in FINANCIAL_REPORT_KEYWORDS)
    is_issue = any(k in report_nm for k in ISSUE_KEYWORDS)
    return is_financial, is_issue


def build_report():
    corp_map = get_corp_code_map()
    end_de = datetime.now().strftime("%Y%m%d")
    bgn_de = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")

    sections = []

    for stock_code, fallback_name in WATCHLIST.items():
        info = corp_map.get(stock_code)
        if not info:
            sections.append(f"### {fallback_name} ({stock_code})\n- corp_code를 찾을 수 없습니다. 종목코드를 확인해주세요.\n")
            continue

        corp_code = info["corp_code"]
        corp_name = info["corp_name"] or fallback_name

        disclosures = get_recent_disclosures(corp_code, bgn_de, end_de)

        lines = [f"### {corp_name} ({stock_code})"]

        if not disclosures:
            lines.append("- 최근 신규 공시 없음")
        else:
            for d in disclosures:
                report_nm = d.get("report_nm", "")
                rcept_dt = d.get("rcept_dt", "")
                rcept_no = d.get("rcept_no", "")
                flrer = d.get("flr_nm", "")
                link = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

                is_financial, is_issue = classify(report_nm)
                tag = ""
                if is_financial:
                    tag = " 📊[실적]"
                elif is_issue:
                    tag = " ⚠️[주요이슈]"

                lines.append(f"- [{rcept_dt}]{tag} {report_nm} (제출인: {flrer})\n  {link}")

                # 실적 보고서면 주요계정 시도 조회
                if is_financial and "사업보고서" in report_nm or "분기보고서" in report_nm or "반기보고서" in report_nm:
                    year = rcept_dt[:4]
                    reprt_code = "11011"
                    if "1분기" in report_nm:
                        reprt_code = "11013"
                    elif "반기" in report_nm:
                        reprt_code = "11012"
                    elif "3분기" in report_nm:
                        reprt_code = "11014"

                    fin = get_financial_summary(corp_code, year, reprt_code)
                    if fin and any(fin.values()):
                        fin_line = ", ".join(f"{k}: {v}" for k, v in fin.items() if v)
                        lines.append(f"  └ 주요계정(누적, 원): {fin_line}")

        sections.append("\n".join(lines))

    header = f"# DART 관심기업 리포트 ({bgn_de} ~ {end_de})\n"
    return header + "\n\n".join(sections)


def send_email(body_text):
    sender = os.environ["gmail_address"]
    password = os.environ["gmail_app_password"]
    # recipient_emails 는 콤마(,)로 구분된 문자열일 수 있음 (예: "a@x.com,b@y.com")
    receivers = [e.strip() for e in os.environ["recipient_emails"].split(",") if e.strip()]

    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(receivers)
    msg["Subject"] = f"[DART 리포트] {datetime.now().strftime('%Y-%m-%d')} 관심기업 공시/실적 요약"
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receivers, msg.as_string())


if __name__ == "__main__":
    report = build_report()
    print(report)  # GitHub Actions 로그에도 남도록
    send_email(report)
