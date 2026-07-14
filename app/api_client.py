import os
import requests
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class KiwoomClient:
    def __init__(self):
        self.app_key = os.getenv("KIWOOM_APP_KEY")
        self.secret_key = os.getenv("KIWOOM_SECRET_KEY")
        self.base_url = "https://api.kiwoom.com"
        self.access_token = None

    def auth(self):
        url = f"{self.base_url}/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.secret_key
        }
        try:
            res = requests.post(url, json=payload, timeout=5)
            data = res.json()
            # KIS/Kiwoom returns "access_token" or "token"
            if "access_token" in data:
                self.access_token = data["access_token"]
                return True
            elif "token" in data:
                self.access_token = data["token"]
                return True
        except Exception as e:
            print("Kiwoom Auth Error:", e)
        return False

    async def get_price_info(self, stock_code):
        if not self.access_token:
            if not self.auth():
                return None
                
        # KIS style endpoint which Kiwoom adopted
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.secret_key,
            "tr_id": "FHKST01010100" # KIS domestic current price TR ID
        }
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": stock_code
        }
        try:
            # We use run_in_executor to not block the asyncio loop
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, params=params, timeout=5))
            data = res.json()
            return data
        except Exception as e:
            print("Kiwoom Price Error:", e)
            return None

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
