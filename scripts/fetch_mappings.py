import os
import json
import zipfile
import io
import requests
import xml.etree.ElementTree as ET
import FinanceDataReader as fdr
from dotenv import load_dotenv

# Run from root, so dot env is at root
load_dotenv()

def fetch_krx_codes():
    print("Fetching KRX stock codes...")
    df = fdr.StockListing('KRX')
    
    mapping = {}
    for idx, row in df.iterrows():
        mapping[str(row['Name']).strip()] = str(row['Code']).strip()
    
    # Save to app/ directory so the server can load it easily
    with open("app/stock_codes.json", "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(mapping)} KRX codes.")

def fetch_dart_codes():
    print("Fetching DART corp codes...")
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        print("DART_API_KEY not found. Skipping DART.")
        return
        
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
    res = requests.get(url)
    if res.status_code != 200:
        print("Failed to download DART codes.")
        return
        
    # Extract the XML file from the ZIP archive in memory
    with zipfile.ZipFile(io.BytesIO(res.content)) as z:
        xml_content = z.read("CORPCODE.xml")
        
    # Parse the XML to build a mapping of Company Name -> DART Corp Code
    root = ET.fromstring(xml_content)
    mapping = {}
    for list_tag in root.findall('list'):
        corp_name = list_tag.find('corp_name').text.strip() if list_tag.find('corp_name') is not None else ""
        corp_code = list_tag.find('corp_code').text.strip() if list_tag.find('corp_code') is not None else ""
        stock_code = list_tag.find('stock_code').text.strip() if list_tag.find('stock_code') is not None else ""
        
        # We only care about listed companies (which have a stock_code)
        if stock_code and stock_code.strip() and corp_name:
            mapping[corp_name] = corp_code
            
    with open("app/dart_codes.json", "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(mapping)} DART codes for listed companies.")

if __name__ == "__main__":
    fetch_krx_codes()
    fetch_dart_codes()
