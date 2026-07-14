import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def test_dart_api():
    print("--- DART API Test ---")
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        print("DART_API_KEY not found.")
        return
    
    # 삼성전자(00126380) 기업개황 조회
    url = f"https://opendart.fss.or.kr/api/company.json?crtfc_key={api_key}&corp_code=00126380"
    try:
        res = requests.get(url)
        data = res.json()
        if data.get("status") == "000":
            print("[SUCCESS] DART API works! Data retrieved for:", data.get("corp_name"))
        else:
            print("[FAIL] DART API returned error:", data.get("message"))
    except Exception as e:
        print("[ERROR] DART API Exception:", e)

def test_kis_or_kiwoom_api():
    print("\n--- Trading API Test (Checking if it's KIS or Kiwoom) ---")
    app_key = os.getenv("KIWOOM_APP_KEY")
    secret_key = os.getenv("KIWOOM_SECRET_KEY")
    
    if not app_key or not secret_key:
        print("Trading API keys not found.")
        return
        
    # KIS endpoint
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": secret_key
    }
    try:
        res = requests.post(url, json=payload)
        data = res.json()
        if "access_token" in data:
            print("[SUCCESS] Trading API works! It seems to be Korea Investment & Securities (한국투자증권) API.")
            return
    except Exception as e:
        pass
        
    print("[INFO] Did not authenticate with KIS. It might be Kiwoom's new REST API.")

if __name__ == "__main__":
    test_dart_api()
    test_kis_or_kiwoom_api()
