import win32gui
import time
import re

print("="*50)
print("영웅문(키움) 윈도우 제목 분석 도구")
print("이 창을 켜두고 HTS에서 종목을 이리저리 클릭해보세요.")
print("어떤 창 제목들이 잡히는지 실시간으로 출력합니다.")
print("="*50)

last_titles = {}

def get_all_kiwoom_titles():
    titles = []
    
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
                if child_title:
                    titles.append((child_hwnd, child_title))
                    
    return titles

while True:
    current_titles = get_all_kiwoom_titles()
    for hwnd, title in current_titles:
        if hwnd not in last_titles or last_titles[hwnd] != title:
            # 새로 발견된 창이거나, 제목이 바뀐 창만 출력
            print(f"[변경 감지] {title}")
            last_titles[hwnd] = title
            
    time.sleep(1)
