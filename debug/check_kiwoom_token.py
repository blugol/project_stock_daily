import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

app_key = os.getenv("KIWOOM_APP_KEY")
secret_key = os.getenv("KIWOOM_SECRET_KEY")

payload = {
    "grant_type": "client_credentials",
    "appkey": app_key,
    "secretkey": secret_key
}

out = ""

# 1. 모의투자 도메인 테스트
mock_url = "https://mockapi.kiwoom.com/oauth2/token"
try:
    res_mock = requests.post(mock_url, json=payload, timeout=5)
    out += f"Mock Status: {res_mock.status_code}\n"
    out += f"Mock Response: {res_mock.json()}\n"
except Exception as e:
    out += f"Mock Error: {e}\n"

# 2. 실전투자 도메인 테스트
real_url = "https://api.kiwoom.com/oauth2/token"
try:
    res_real = requests.post(real_url, json=payload, timeout=5)
    out += f"\nReal Status: {res_real.status_code}\n"
    out += f"Real Response: {res_real.json()}\n"
except Exception as e:
    out += f"Real Error: {e}\n"

with open("debug/api_res.txt", "w", encoding="utf-8") as f:
    f.write(out)
