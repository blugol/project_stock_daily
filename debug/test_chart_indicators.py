import os
import requests
import json
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app_key = os.getenv("KIWOOM_APP_KEY")
secret_key = os.getenv("KIWOOM_SECRET_KEY")
base_url = "https://api.kiwoom.com"

# 1. 토큰 발급
url_token = f"{base_url}/oauth2/token"
payload = {
    "grant_type": "client_credentials",
    "appkey": app_key,
    "secretkey": secret_key
}
res = requests.post(url_token, json=payload, timeout=5)
data = res.json()
token = data.get("access_token") or data.get("token")

if not token:
    print("Token auth failed!")
    exit(1)

# 2. 일봉 차트 조회 (삼성전자 005930)
url_chart = f"{base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
today = datetime.now().strftime("%Y%m%d")
start_date = (datetime.now() - timedelta(days=800)).strftime("%Y%m%d") # 과거 약 2년치 (영업일 기준 500일 이상 필요)

headers = {
    "Content-Type": "application/json; charset=utf-8",
    "authorization": f"Bearer {token}",
    "appkey": app_key,
    "appsecret": secret_key,
    "tr_id": "FHKST03010100" # KIS 일봉차트 TR ID
}
params = {
    "fid_cond_mrkt_div_code": "J",
    "fid_input_iscd": "005930",
    "fid_input_date_1": start_date,
    "fid_input_date_2": today,
    "fid_period_div_code": "D",
    "fid_org_adj_prc": "1" # 수정주가
}

print(f"Fetching chart data for Samsung Electronics from {start_date} to {today}...")
res_chart = requests.get(url_chart, headers=headers, params=params, timeout=10)
data = res_chart.json()

if "output2" not in data or not data["output2"]:
    print("Failed to fetch chart data. Response:", data)
    exit(1)

# 3. pandas DataFrame 변환
# output2 contains the daily data: stck_bsop_date, stck_clpr, stck_oprc, stck_hgpr, stck_lwpr, acml_vol
df = pd.DataFrame(data["output2"])
df = df[['stck_bsop_date', 'stck_oprc', 'stck_hgpr', 'stck_lwpr', 'stck_clpr', 'acml_vol']]
df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']

# 날짜순 정렬 (과거 -> 현재)
df = df.sort_values(by='Date').reset_index(drop=True)

# 숫자형으로 변환
for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# 4. pandas-ta를 이용한 고급 지표 계산 (단테님 농사매매 밥그릇 라인)
print("Calculating advanced indicators...")
df['SMA_112'] = ta.sma(df['Close'], length=112)
df['SMA_224'] = ta.sma(df['Close'], length=224)
df['SMA_448'] = ta.sma(df['Close'], length=448)

# 일목균형표
ichimoku, _ = ta.ichimoku(df['High'], df['Low'], df['Close'])
if ichimoku is not None:
    df = pd.concat([df, ichimoku], axis=1)

# 최근 5일치 결과 출력
print("\n=== 삼성전자(005930) 최근 5일 고급 지표 계산 결과 ===")
recent = df.tail(5)
for idx, row in recent.iterrows():
    date = row['Date']
    close = row['Close']
    sma112 = row['SMA_112']
    sma224 = row['SMA_224']
    print(f"[{date}] 종가: {close:,.0f} | 112일선: {sma112:,.0f} | 224일선: {sma224:,.0f}")
