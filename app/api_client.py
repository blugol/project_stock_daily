import os
import requests
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

import sys
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QAxContainer import QAxWidget
    from PyQt5.QtCore import QEventLoop
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False

class KiwoomClient:
    def __init__(self):
        self.app = None
        self.ocx = None
        self.loop = None
        self.tr_data = {}
        self.stock_themes = {}
        
        if not HAS_PYQT:
            print("PyQt5 패키지가 설치되지 않아 Kiwoom OpenAPI 연동이 불가능합니다.")
            return
            
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
            
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        
        # 64-bit Python 환경에서는 QAxWidget이 이벤트를 매핑하지 못하므로 AttributeError 발생
        try:
            self.ocx.OnReceiveTrData.connect(self._on_receive_tr_data)
        except AttributeError:
            print("\n🚨 [치명적 오류] 키움증권 OpenAPI+는 32비트 환경에서만 구동됩니다.")
            print("현재 사용 중인 Python은 64비트이므로 COM 객체 로드에 실패했습니다.")
            print("이 기능을 사용하려면 32비트 Python을 설치하거나, REST API로 우회해야 합니다.\n")
            self.ocx = None
            return
        
        if self.ocx.dynamicCall("GetConnectState()") == 0:
            print("[Kiwoom] 자동 로그인 시도 중...")
            self.ocx.dynamicCall("CommConnect()")

    def _on_receive_tr_data(self, scr_no, rq_name, tr_code, record_name, prev_next, data_len, err_code, msg1, msg2):
        if rq_name == "주식기본정보요청":
            ratio = self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, rq_name, 0, "유통비율")
            if ratio:
                self.tr_data["float_ratio"] = ratio.strip()
            
            if self.loop:
                self.loop.exit()

    async def get_price_info(self, stock_code):
        if not self.ocx:
            return None
            
        self.tr_data.clear()
        self.loop = QEventLoop()
        
        # 1. 파라미터 세팅
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        print(f"[Kiwoom DEBUG] SetInputValue('종목코드', '{stock_code}') 입력 완료")
        
        # 2. TR 호출
        res = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)", "주식기본정보요청", "opt10001", 0, "1000")
        print(f"[Kiwoom DEBUG] CommRqData(opt10001) 호출 완료, 리턴코드: {res}")
        
        # 3. 비동기 이벤트 수신 대기
        self.loop.exec_()
        
        return {"output": {"유통비율": self.tr_data.get("float_ratio", "")}}
        
    def load_theme_mapping(self):
        """키움 API를 통해 테마 그룹 및 소속 종목 데이터를 캐싱 (동기/블로킹)"""
        if not self.ocx or self.ocx.isNull():
            return
            
        try:
            print("[Kiwoom] 백그라운드 테마 매핑 연산 시작...")
            # 1. 테마 그룹 리스트 조회 (포맷: 테마코드|테마명;테마코드|테마명;...)
            theme_list_str = self.ocx.dynamicCall("GetThemeGroupList(int)", 1)
            if not theme_list_str:
                return
                
            theme_items = str(theme_list_str).split(";")
            for item in theme_items:
                if not item or "|" not in item:
                    continue
                theme_code, theme_name = item.split("|", 1)
                
                # 2. 특정 테마코드에 속한 종목코드 리스트 조회 (포맷: A005930;A000660;...)
                # 키움은 종목코드 앞에 A를 붙여서 리턴할 수 있으므로 제거 로직 추가
                stock_codes_str = self.ocx.dynamicCall("GetThemeGroupCode(QString)", theme_code)
                if stock_codes_str:
                    codes = str(stock_codes_str).split(";")
                    for code in codes:
                        code = code.strip().replace("A", "") # 'A005930' -> '005930'
                        if not code:
                            continue
                        if code not in self.stock_themes:
                            self.stock_themes[code] = []
                        if theme_name not in self.stock_themes[code]:
                            self.stock_themes[code].append(theme_name)
                            
            print(f"[Kiwoom] 테마 매핑 완료 (총 {len(self.stock_themes)}개 종목 캐싱됨)")
        except Exception as e:
            print(f"[Kiwoom] 테마 매핑 중 오류 발생: {e}")

    def get_stock_themes(self, stock_code):
        """특정 종목의 소속 테마명을 콤마로 연결하여 반환"""
        if not hasattr(self, 'stock_themes') or not self.stock_themes:
            self.load_theme_mapping()
            
        themes = self.stock_themes.get(stock_code, []) if hasattr(self, 'stock_themes') else []
        return ", ".join(themes) if themes else "해당 테마 없음"

class DartClient:
    def __init__(self):
        self.api_key = os.getenv("DART_API_KEY")

    async def get_recent_disclosures(self, corp_code):
        if not self.api_key: return []
        
        url = "https://opendart.fss.or.kr/api/list.json"
        today = datetime.now().strftime("%Y%m%d")
        bgn_de = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d") # Last 90 days
        
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": today,
            "page_count": 5
        }
        try:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: requests.get(url, params=params, timeout=5))
            data = res.json()
            if data.get("status") == "000":
                return data.get("list", [])
        except Exception as e:
            print("DART Error:", e)
        return []

    async def get_shareholder_info(self, corp_code):
        if not self.api_key: return {}
        
        base_url = "https://opendart.fss.or.kr/api"
        
        async def fetch(endpoint, extra_params=None):
            url = f"{base_url}/{endpoint}.json"
            params = {"crtfc_key": self.api_key, "corp_code": corp_code}
            if extra_params:
                params.update(extra_params)
            try:
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, lambda: requests.get(url, params=params, timeout=5))
                data = res.json()
                if data.get("status") == "000":
                    return data.get("list", [])
            except Exception as e:
                pass
            return []

        # 가장 최신 보고서를 동적으로 찾기 (현재 연도 기준 역순 추적)
        from datetime import datetime
        current_year = datetime.now().year
        candidates = [
            (str(current_year), "11014"), # 3분기
            (str(current_year), "11012"), # 반기
            (str(current_year), "11013"), # 1분기
            (str(current_year - 1), "11011"), # 전년 사업보고서
            (str(current_year - 1), "11014"),
            (str(current_year - 1), "11012"),
            (str(current_year - 1), "11013"),
            (str(current_year - 2), "11011")
        ]
        
        best_year = "2025"
        best_code = "11011"
        stock_tot_data = []
        
        for year, code in candidates:
            res = await fetch("stockTotqySttus", {"bsns_year": year, "reprt_code": code})
            if res:
                best_year = year
                best_code = code
                stock_tot_data = res
                print(f"[DART] 최신 보고서 동적 매칭 성공: {best_year}년 {best_code} (DART:{corp_code})")
                break

        tasks = [
            fetch("majorstock"), # 대량보유 (5% 이상)
            fetch("elestock"), # 임원 및 주요주주
            fetch("hyslrSttus", {"bsns_year": best_year, "reprt_code": best_code}), # 최대주주
            fetch("tesstkAcqsDspsSttus", {"bsns_year": best_year, "reprt_code": best_code}), # 자사주 취득 처분
            fetch("mrhlSttus", {"bsns_year": best_year, "reprt_code": best_code}) # 소액주주
        ]
        
        results = await asyncio.gather(*tasks)
        
        return {
            "majorstock": results[0],
            "elestock": results[1],
            "hyslrSttus": results[2],
            "tesstkAcqsDspsSttus": results[3],
            "mrhlSttus": results[4],
            "stockTotqySttus": stock_tot_data
        }

class QuantClient:
    def __init__(self):
        # fdr is loaded on demand
        pass

    async def get_technical_indicators(self, stock_code):
        import FinanceDataReader as fdr
        import pandas as pd
        import pandas_ta as ta
        from datetime import datetime, timedelta
        
        try:
            # 과거 약 2.5년치 데이터 (거래일 기준 448일 이상 확보 목적)
            start_date = (datetime.now() - timedelta(days=900)).strftime("%Y-%m-%d")
            
            loop = asyncio.get_event_loop()
            # fdr.DataReader는 I/O 바운드/네트워크 요청이므로 run_in_executor로 묶습니다.
            df = await loop.run_in_executor(None, lambda: fdr.DataReader(stock_code, start_date))
            
            if df.empty:
                return None
                
            # 단테님 핵심 이평선 연산
            df['SMA_112'] = ta.sma(df['Close'], length=112)
            df['SMA_224'] = ta.sma(df['Close'], length=224)
            df['SMA_448'] = ta.sma(df['Close'], length=448)
            
            # 볼린저밴드 (기간20, 승수2)
            bb = ta.bbands(df['Close'], length=20, std=2)
            if bb is not None:
                df = pd.concat([df, bb], axis=1)
                
            # 일목균형표
            ichimoku, _ = ta.ichimoku(df['High'], df['Low'], df['Close'])
            if ichimoku is not None:
                df = pd.concat([df, ichimoku], axis=1)
                
            # MACD
            macd = ta.macd(df['Close'])
            if macd is not None:
                df = pd.concat([df, macd], axis=1)
            
            # 5일 / 20일 평균 거래량
            df['VOL_SMA_5'] = ta.sma(df['Volume'], length=5)
            df['VOL_SMA_20'] = ta.sma(df['Volume'], length=20)
            
            # 가장 마지막 날짜(최신) 데이터 추출
            latest = df.iloc[-1]
            
            # NaN 방지용 헬퍼 함수
            def safe_val(val):
                return round(float(val), 2) if pd.notna(val) else None
                
            # Dictionary로 리턴
            result = {
                "date": latest.name.strftime("%Y-%m-%d") if hasattr(latest, "name") else "",
                "close": safe_val(latest['Close']),
                "volume": safe_val(latest['Volume']),
                "vol_sma_5": safe_val(latest.get('VOL_SMA_5')),
                "vol_sma_20": safe_val(latest.get('VOL_SMA_20')),
                "sma_112": safe_val(latest.get('SMA_112')),
                "sma_224": safe_val(latest.get('SMA_224')),
                "sma_448": safe_val(latest.get('SMA_448')),
            }
            
            # 볼린저밴드 필드 매핑 (pandas-ta 컬럼명은 BBL_20_2.0, BBM_20_2.0, BBU_20_2.0)
            bb_lower = [c for c in df.columns if c.startswith('BBL_')]
            bb_upper = [c for c in df.columns if c.startswith('BBU_')]
            if bb_lower and bb_upper:
                result["bb_lower"] = safe_val(latest.get(bb_lower[0]))
                result["bb_upper"] = safe_val(latest.get(bb_upper[0]))
                
            # 일목균형표 필드 매핑 (ISA_9, ISB_26 등)
            isa = [c for c in df.columns if c.startswith('ISA_')]
            isb = [c for c in df.columns if c.startswith('ISB_')]
            if isa and isb:
                result["ichimoku_span_a"] = safe_val(latest.get(isa[0]))
                result["ichimoku_span_b"] = safe_val(latest.get(isb[0]))
                
            return result
            
        except Exception as e:
            print("Quant Engine Error:", e)
            return None
