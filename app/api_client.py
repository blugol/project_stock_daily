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
