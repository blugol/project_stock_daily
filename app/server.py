import asyncio
import websockets
import win32gui
import re
import json
import os
from api_client import KiwoomClient, DartClient, QuantClient, NaverClient

# Load mappings
try:
    with open(os.path.join(os.path.dirname(__file__), "stock_codes.json"), "r", encoding="utf-8") as f:
        STOCK_CODES = json.load(f)
except Exception:
    STOCK_CODES = {}

try:
    with open(os.path.join(os.path.dirname(__file__), "dart_codes.json"), "r", encoding="utf-8") as f:
        DART_CODES = json.load(f)
except Exception:
    DART_CODES = {}

kiwoom = KiwoomClient()
dart = DartClient()
quant = QuantClient()

# HTS 화면의 핸들과 이전 텍스트를 저장하는 딕셔너리
window_titles = {}

# 절대로 종목명이 될 수 없는 고정 텍스트들 (완벽 차단)
IGNORE_EXACT = {
    "매도", "매수", "필드", "예상", "등록", "소리", "지표분석", "비교분석", "대상", "조건", 
    "관심", "뉴스", "종목연동", "자동삭제", "이탈삭제", "계좌연동", "최근매매종목", "메모보기", 
    "수익률추이", "매매수익", "일별잔고", "시장가", "종목", "가격", "수량", "종류", "체결", 
    "호가", "신용", "현금", "자동", "미수", "메뉴툴바", "버튼", "화면찾기", "빅데이터 티커", 
    "쾌속주문툴바", "QuickOrderForm", "차트툴바", "계좌번호", "비밀번호", "손대원", "다음", 
    "상장폐지제외", "조회", "자동(현재가)", "현금매도", "현금매수"
}

def is_valid_stock_name(name):
    name = name.strip()
    if len(name) < 2: return False # 너무 짧은 글자 제외
    if len(name) > 20: return False # 너무 긴 글자(조건식 등) 제외
    if name.isdigit(): return False # 숫자만 있는 것 제외 (120, 60 등)
    if re.match(r'^[\d,\.]+$', name): return False # 금액, 가격 등 제외
    if "[" in name or "]" in name or "<" in name or ">" in name: return False # 설정창 제외
    if "└─" in name: return False
    if "(F" in name: return False # 단축키 버튼 제외
    if ":" in name: return False # 시간이나 설정값 제외
    if " " in name and not any(c.isalpha() or c >= '가' and c <= '힣' for c in name): return False # 특수기호/숫자 공백 제외
    
    # 정확히 일치하는 금지어 제외
    if name in IGNORE_EXACT: return False
    
    # 일부 포함된 금지어 제외
    for kw in ["잔고", "실시간", "조회", "주문", "체결", "미체결", "계좌", "수익", "설정", "관심"]:
        if kw in name: return False
        
    return True

def get_changed_stock_name():
    global window_titles
    changed_stock = None
    
    top_windows = []
    def enum_top(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            top_windows.append(hwnd)
    win32gui.EnumWindows(enum_top, None)

    for hwnd in top_windows:
        title = win32gui.GetWindowText(hwnd)
        if "영웅문" in title or "키움" in title:
            child_windows = []
            def enum_child(child_hwnd, _):
                if win32gui.IsWindowVisible(child_hwnd):
                    child_windows.append(child_hwnd)
            win32gui.EnumChildWindows(hwnd, enum_child, None)
            
            for child_hwnd in child_windows:
                child_title = win32gui.GetWindowText(child_hwnd).strip()
                if not child_title:
                    continue
                    
                if child_hwnd in window_titles and window_titles[child_hwnd] != child_title:
                    # 텍스트가 변경되었을 때, 그 텍스트가 유효한 종목명 형태인지 검사!
                    # HTS 설정에 따라 창 제목이 아니라, 화면 내 특정 라벨(글자) 자체가 종목명으로 변경됨
                    new_text = child_title
                    
                    # 혹시 기존처럼 '- 삼성전자' 형태의 창 제목이 바뀌었다면
                    if "-" in new_text:
                        match = re.search(r'-\s*([^-]+?)(?:\s*\([A-Za-z0-9]+\))?\s*$', new_text)
                        if match:
                            extracted = match.group(1).strip()
                            if is_valid_stock_name(extracted):
                                changed_stock = extracted
                    
                    # 하이픈 없이 글자 자체가 '솔루엠', '코스모화학' 등 쌩으로 바뀐 경우!
                    if not changed_stock and is_valid_stock_name(new_text):
                        changed_stock = new_text
                            
                window_titles[child_hwnd] = child_title

    return changed_stock

def format_shareholders(raw_data):
    if not isinstance(raw_data, dict):
        return str(raw_data)
        
    lines = []
    
    hyslr = raw_data.get("hyslrSttus", [])
    if hyslr:
        lines.append("■ 최대주주 및 특수관계인 (사업보고서 기준)")
        for item in hyslr:
            name = item.get("nm", "")
            relate = item.get("relate", "")
            rate = item.get("trmend_posesn_stock_qota_rt", "0")
            if name == "계" or "총계" in name: continue
            lines.append(f"  - {name} ({relate}): {rate}%")
        lines.append("")
        
    major = raw_data.get("majorstock", [])
    if major:
        lines.append("■ 5% 이상 대량보유 주요 주주")
        seen = set()
        # 최신 공시 순으로 정렬하여 중복 인원 제외
        major_sorted = sorted(major, key=lambda x: x.get("rcept_dt", ""), reverse=True)
        for item in major_sorted:
            name = item.get("repror", "")
            rate = item.get("stkrt", "0")
            if name not in seen:
                lines.append(f"  - {name}: {rate}%")
                seen.add(name)
        lines.append("")
        
    mrhl = raw_data.get("mrhlSttus", [])
    if mrhl:
        lines.append("■ 소액주주 현황")
        for item in mrhl:
            rate = item.get("hold_stock_rate", "0%")
            lines.append(f"  - 소액주주 전체 합계: {rate}")
        lines.append("")
        
    # 총 발행주식수 파싱
    totqy = raw_data.get("stockTotqySttus", [])
    total_stock_count = 0
    for item in totqy:
        if item.get("stock_knd", "") == "보통주":
            try:
                val = str(item.get("isu_stock_totqy", "0")).replace(",", "")
                total_stock_count = int(val)
            except ValueError:
                pass
            break
            
        
    ele = raw_data.get("elestock", [])
    if ele:
        lines.append("■ 임원 및 주요주주")
        seen = set()
        ele_sorted = sorted(ele, key=lambda x: x.get("rcept_dt", ""), reverse=True)
        for item in ele_sorted:
            name = item.get("repror", "")
            pos = item.get("isu_exctv_ofcps", "")
            rate = item.get("sp_stock_lmp_rate", "0")
            if name not in seen:
                lines.append(f"  - {name} ({pos}): {rate}%")
                seen.add(name)
        lines.append("")
        
    return "\n".join(lines).strip() if lines else "지분율 데이터를 찾을 수 없습니다."

async def stock_handler(websocket):
    current_stock = None
    try:
        while True:
            new_stock = get_changed_stock_name()
            if new_stock and new_stock != current_stock:
                current_stock = new_stock
                print(f"✅ 종목 인식됨: {current_stock}")
                
                payload = {"stock_name": current_stock, "shareholders": None}
                
                dart_code = DART_CODES.get(current_stock)
                base_text = ""
                if dart_code:
                    print(f"⏳ DART 지분율 데이터 수집 중... (DART:{dart_code})")
                    raw_data = await dart.get_shareholder_info(dart_code)
                    base_text = format_shareholders(raw_data)
                else:
                    base_text = "DART 고유번호를 찾을 수 없습니다."
                    
                # Kiwoom 연동 (opt10001)
                stock_code = STOCK_CODES.get(current_stock)
                kiwoom_text = ""
                if stock_code:
                    print(f"⏳ Kiwoom 실시간 유통비율 데이터 수집 중... (Code:{stock_code})")
                    kiwoom_data = await kiwoom.get_price_info(stock_code)
                    float_ratio = "0.00"
                    if kiwoom_data:
                        out = kiwoom_data.get("output", {}) or kiwoom_data.get("output1", {}) or kiwoom_data
                        if isinstance(out, list) and len(out) > 0:
                            out = out[0]
                        float_ratio_val = out.get("유통비율", "")
                        if float_ratio_val:
                            try:
                                float_ratio = f"{float(float_ratio_val):.2f}"
                            except ValueError:
                                float_ratio = str(float_ratio_val)
                    kiwoom_text = f"\n■ 실시간 유통비율 (키움 연동): {float_ratio}%\n"
                    
                # Naver/FnGuide 섹터 및 재료(테마)
                naver_text = ""
                if stock_code:
                    print(f"⏳ 섹터 및 재료(테마) 데이터 수집 중... (Code:{stock_code})")
                    naver_data = await naver.get_sector_and_theme(stock_code)
                    if naver_data:
                        sec = naver_data.get('sector', '알 수 없음')
                        thm = naver_data.get('theme_summary', '요약 정보 없음')
                        naver_text = f"■ 섹터 및 테마(재료)\n  - 섹터(업종): {sec}\n  - 기업개요(재료): {thm}\n"
                
                payload["shareholders"] = base_text + kiwoom_text + naver_text
                    
                await websocket.send(json.dumps(payload))
                
            await asyncio.sleep(0.3)
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print("WebSocket Error:", e)

async def main():
    print("=========================================")
    print("웹소켓 서버가 정상적으로 시작되었습니다.")
    print("HTS에서 종목을 클릭하시면 이곳과 웹페이지에 종목명이 표시됩니다.")
    print("=========================================")
    async with websockets.serve(stock_handler, "localhost", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
