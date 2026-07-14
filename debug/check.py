import win32gui

count = 0
def cb(hwnd, _):
    global count
    if win32gui.IsWindowVisible(hwnd):
        t = win32gui.GetWindowText(hwnd)
        if t:
            try:
                print(f"[{count}] {t}")
            except UnicodeEncodeError:
                print(f"[{count}] <Unicode Error>")
            count += 1

win32gui.EnumWindows(cb, None)
