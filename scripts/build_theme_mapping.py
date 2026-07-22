import os
import json
import time
import requests
from bs4 import BeautifulSoup
import FinanceDataReader as fdr
from tqdm import tqdm

def fetch_sectors():
    print("[1] 상장사 산업(Sector) 정보 수집 중 (FinanceDataReader)...")
    try:
        # Get all KRX listed stocks
        df = fdr.StockListing('KRX')
        
        # Build mapping: stock_code -> sector
        # Not all stocks have a 'Sector'. Some might be ETFs or unclassified.
        sector_map = {}
        for idx, row in df.iterrows():
            code = str(row['Code'])
            sector = str(row['Sector']) if 'Sector' in df.columns and str(row['Sector']) != 'nan' else ""
            industry = str(row['Industry']) if 'Industry' in df.columns and str(row['Industry']) != 'nan' else ""
            
            # Prefer sector, fallback to industry, or empty
            final_sector = sector if sector else industry
            if final_sector:
                sector_map[code] = final_sector
        print(f"    -> 총 {len(sector_map)}개 종목의 섹터 정보 수집 완료.")
        return sector_map
    except Exception as e:
        print(f"Error fetching sectors: {e}")
        return {}

def fetch_themes():
    print("[2] 네이버 금융 테마 및 소속 종목 수집 중...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"
    }
    base_url = "https://finance.naver.com/sise/theme.naver"
    
    # First, figure out how many pages of themes there are (usually 1 to 7)
    # To be safe, we'll loop until we hit a page with no new themes.
    theme_links = []
    
    for page in range(1, 10):
        url = f"{base_url}?&page={page}"
        res = requests.get(url, headers=headers)
        res.encoding = 'euc-kr'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Find theme links in the table
        trs = soup.select('table.type_1 tr')
        page_themes_count = 0
        for tr in trs:
            a_tag = tr.select_one('a')
            if a_tag and 'href' in a_tag.attrs:
                href = a_tag['href']
                name = a_tag.text.strip()
                if '/sise/sise_group_detail.naver' in href:
                    theme_links.append((name, "https://finance.naver.com" + href))
                    page_themes_count += 1
                    
        if page_themes_count == 0:
            break
            
    print(f"    -> 총 {len(theme_links)}개의 테마 발견. 개별 테마 소속 종목 조회 시작...")
    
    stock_to_themes = {}
    
    # Scrape each theme page
    for name, link in tqdm(theme_links, desc="테마 파싱 진행률"):
        res = requests.get(link, headers=headers)
        res.encoding = 'euc-kr'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # In the theme detail page, the stocks are in a table with class 'type_5'
        # The stock code is in the link href: /item/main.naver?code=XXXXXX
        trs = soup.select('table.type_5 tbody tr')
        if not trs:
            # Fallback if tbody isn't there
            trs = soup.select('table.type_5 tr')
            
        for tr in trs:
            a_tag = tr.select_one('td.name a')
            if a_tag and 'href' in a_tag.attrs:
                href = a_tag['href']
                if 'code=' in href:
                    code = href.split('code=')[-1].strip()
                    if code not in stock_to_themes:
                        stock_to_themes[code] = []
                    if name not in stock_to_themes[code]:
                        stock_to_themes[code].append(name)
                        
        time.sleep(0.1) # Be polite to Naver servers
        
    return stock_to_themes

def main():
    print("=======================================")
    print(" 로컬 테마/섹터 맵핑 DB 구축 시작")
    print("=======================================")
    
    sectors = fetch_sectors()
    themes = fetch_themes()
    
    print("[3] 데이터 병합 및 JSON 저장 중...")
    
    # Merge them together
    # All stocks from sectors, plus any extra stocks from themes
    all_codes = set(list(sectors.keys()) + list(themes.keys()))
    
    mapping = {}
    for code in all_codes:
        mapping[code] = {
            "sector": sectors.get(code, ""),
            "themes": themes.get(code, [])
        }
        
    # Save to data/theme_mapping.json
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "theme_mapping.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=4)
        
    print("=======================================")
    print(f" 구축 완료! 총 {len(mapping)}개 종목 매핑 완료.")
    print(f" 저장 위치: {output_path}")
    print("=======================================")

if __name__ == "__main__":
    main()
