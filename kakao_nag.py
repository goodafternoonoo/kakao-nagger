# -*- coding: utf-8 -*-
"""
카톡 답장 독촉 위젯 (Windows 전용)

  py kakao_nag.py          실제 모드: 카톡 PC 채팅 목록에서 안 읽은 방을 찾아 독촉
  py kakao_nag.py --demo   데모 모드: 가짜 이름으로 위젯 모양만 확인
  py kakao_nag.py --diag   진단 모드: 카톡 창 구조를 '진단결과.txt'로 저장 (글자는 ●로 가림)

카톡 창은 다른 창에 가려져도 되지만, 최소화하거나 닫으면 못 읽음(위젯에 그렇게 표시됨).
채팅 목록에 보이는 줄만 읽으니, 창을 길게 두거나 '안읽음' 탭에 두면 빠짐없이 읽음.
자동 답장은 하지 않고 평소엔 화면을 '읽기'만 함. 위젯에서 사람을 직접 누를 때만 그 채팅방을 엶(읽음 처리됨).
Ctrl+Alt+K로 위젯을 완전히 숨기거나 다시 보임. '내대사.txt'에 쓴 대사는 말투 '내 대사'에서 나옴.
설정의 '거르기'로 이름·메시지 문구에 따라 방을 숨기거나 그 방만 볼 수 있음. 메시지 문구를 넣었을 때만 미리보기를 글자로 읽음.
"""
import sys, os, re, csv, json, math, time, random, shutil, sqlite3, struct, tempfile, subprocess, threading, winreg
import ctypes
from ctypes import wintypes as wt
import tkinter as tk
import tkinter.font

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# exe로 묶으면 __file__은 실행 때마다 풀리는 임시 폴더라, 설정 파일은 exe 옆에 둠
HERE = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
POLL_SEC = 6          # 카톡 확인 주기(초)
NAG_SEC = 180         # 대사 바뀌는 주기(초)
SHAKE_SEC = 300       # 1시간 넘게 씹으면 위젯을 흔드는 주기(초)
SNOOZE_MIN = 10       # 한 사람만 조용히 하는 시간(분)
MAX_BUBBLES = 4
PRAISE_SEC = 6        # 읽으면 칭찬을 띄워 두는 시간(초)
MAX_PRAISE = 2        # 한꺼번에 읽었을 때 칭찬 줄 수
UNDO_SEC = 8          # '안 보기'를 되돌릴 수 있게 띄워 두는 시간(초)
HOTKEY_TEXT = "Ctrl+Alt+K"

LEVEL_MIN = (0, 10, 60)   # 대사·말풍선 단계가 오르는 시간(분)
DEFAULT_TONE = "gyeongsang"
# 말투: (키, 이름, [단계별 대사 목록]). 여기에 한 줄 더하면 설정 화면에도 나옴.
TONES = [
    ("gyeongsang", "경상도 사투리", [
        ["마 개쉐끼야! 톡 답장 안하나!", "니 머하노? 톡 왔다 아이가", "어데 갔노? 답장 쫌 해라", "니 얘기 돌던데? 궁금하면 답장해라"],
        ["이 문디 자슥아, 톡 좀 보라카이", "니 폰 어데 뒀노? 단디 좀 봐라", "몇 번을 말하노! 답장하라 안 카나!", "[속보] 니 아직도 답장 안 했다 카더라"],
        ["니 내 차단했나? 와 이라노", "고마 해라, 니 폰 확 뽀사뿐다!!", "마 개쉐끼야!!! 니 내한테 디진다!!!", "동네방네 소문낸다? 쟈 톡 씹는다꼬!!"]]),
    ("jeolla", "전라도 사투리", [
        ["아야, 톡 왔응께 싸게 답 좀 혀", "뭣허냐? 톡 왔당께", "오메, 톡을 씹어부렀냐잉", "아야, 니 소문 돌던디? 궁금허믄 답장혀"],
        ["시방까지 안 읽고 뭣헌다냐", "아따 쪼까 답장 좀 해부러야", "거시기, 답장은 언제 헐 것이여?", "[속보] 아직도 답장 안 했다네잉"],
        ["오메 징한 거, 나 차단해부렀냐?", "이라믄 못 쓴당께, 참말로!!", "아야!!! 염병허네, 싸게싸게 답장 안 혀?!!", "온 동네에 다 말해분다잉? 톡 씹는다고!!"]]),
    ("chungcheong", "충청도 사투리", [
        ["톡 왔슈. 급한 건 아닌디... 답장은 해유", "뭐 하는겨, 바쁜감유?", "그려서 답장은 은제 할 겨?", "별일은 아닌디... 니 얘기 나오던디유?"],
        ["아직도 안 읽었슈? 참 느긋허네유", "천천히 혀도 되는디, 이건 너무 천천히 아녀유?", "개갈 안 나네 참말로, 답장 좀 해유", "[속보] 아직도 답장 안 했대유. 그렇대유"],
        ["...나 차단한 겨? 아니믄 됐구유", "됐슈. 답장 허지 마유. 나는 뭐 괜찮어유", "이제 진짜 화났슈. 티는 안 내는디 화났슈", "동네 사람들헌테 말 안 했슈. 아직은유"]]),
    ("polite", "표준어 (정중)", [  # 회사 메신저 말투
        ["안녕하세요, 톡 확인 부탁드립니다.", "바쁘시겠지만 회신 부탁드려요.", "리마인드 차 다시 연락드립니다.", "[긴급] 매우 중요한 공지입니다. (답장하세요)"],
        ["혹시 제 메시지가 누락됐을까요?", "확인이 늦어지시는 것 같아 재차 여쭙습니다.", "회신 기다리다 다시 연락드려요 ^^;", "귀하의 미회신 건이 대표님께 보고되었습니다."],
        ["여러 차례 말씀드렸는데 회신이 없으시네요.", "오늘 내로 회신 부탁드립니다. 꼭이요.", "이렇게까지 말씀드리고 싶지 않았습니다만, 답장 좀 하십시오.", "본 안읽씹 건은 전사 공지될 예정입니다."]]),
    ("office", "회사용 (순한 맛)", [  # 욕 없음. 말풍선도 안 빨개지고 위젯도 안 흔들림
        ["확인 안 한 메시지가 있어요.", "시간 될 때 답장해 주세요.", "새 메시지가 도착했어요."],
        ["메시지가 조금 밀려 있어요.", "잠깐 짬 날 때 확인해 보세요.", "답장을 기다리는 분이 있어요."],
        ["오래 기다리는 메시지가 있어요.", "오늘 안에 확인하면 좋겠어요.", "이 메시지, 잊으신 건 아니죠?"]]),
    ("bestie", "찐친 모먼트", [
        ["야 ㅁㅎ", "읽어라 좀 ㅋㅋㅋㅋ", "야야야야 톡 왔다고", "야 너 얘기 나오던데 ㅋㅋ 궁금하면 답장"],
        ["또 잠수냐 ㅡㅡ", "이 새끼 또 씹네 ㅋㅋㅋ", "폰 팔았냐? ㅋㅋ 답장 좀", "단톡에 너 안읽씹 캡처 올린다 ㅋㅋ"],
        ["너 죽었냐? 부고 돌린다 ㅇㅇ", "니 결혼식 안 간다 진짜", "야 이 미친놈아!!! 살아는 있냐!!!", "니 흑역사 사진 어디 뒀더라 ㅋㅋ"]]),
    ("mz", "MZ 밈", [  # 2026년 8~10월 밈 정리 기준. 유행이 빨리 바뀌니 가끔 갈아줄 것
        ["톡 왔음. 답장은 알빠노?", "안읽씹 좀 밤티임 ㄹㅇ", "답장 좀요 (무례하지 않게 말해주세요)", "3초 안에 답장 못 하면 바보임 ㅋ"],
        ["이건 억까 아니고 팩트임 ㅇㅈ?", "답장 안 하는 책없쾌 그만 즐기셈", "아니 왜 안 읽음?? 킹받네", "[속보] 아직도 답장 안 함 ㄷㄷ"],
        ["연락 없네 잘 살아", "답장 없으니까 L 가져가셈", "이 안읽씹은 영원할 건가 보다", "안읽씹하는 사람 특징.txt: 너"]]),
    ("hiphop", "힙합 슬랭", [
        ["Yo, you saw my text or nah?", "Bruh. Hit me back.", "Ayo why you got me on read?", "Yo I got some tea about you. Text back."],
        ["Bruh you ghostin' me fr?", "Deadass, pick up your phone.", "Ain't nobody THAT busy, stop playin'.", "Bet you won't text back."],
        ["Aight bet. Don't text me when you need somethin'.", "You foul for this, on God.", "Say less, I'm pullin' up to the crib. No cap.", "Everybody already know you duckin' me. Smh."]]),
    ("hipple", "힙플밈", [  # 유튜브 '힙플밈' 번역체: 글자 사이 @, ;;;, n트, 경상도식 어투, 후드에서 살아남기
        ["뽕@알, 톡 왔다. 뭔말알?", "마, 답장 안 하는 건 쌈@뽕하지 않다;;;", "(톡 입갤) ?... 답장 안 하나", "뽕@알, 니 얘기 돌던데? 뭔말알?"],
        ["답장해라. 2트. 3트.", "바빴다고? 공@갈치지마;;;", "후드에서 살아남기 제1장: 톡은 바로 읽을 것.", "[속보] 뽕@알 아직도 답장 안 함;;;"],
        ["후드에서 살아남기 제2장: 읽씹해도 답장은 할 것.", "(뽕@알 퇴갤) ?... 잠수 타나;;;", "시@밤쾅!!! 뽕@알 실종 신고 들어간다;;;", "후드에서 살아남기 제3장: 안읽씹하면 소문 난다."]]),
    ("custom", "내 대사", [[], [], []]),  # 내대사.txt에서 채움
]
TONE_LINES = {key: levels for key, _, levels in TONES}
MILD_TONES = {"office"}
# 칭찬: 위젯은 안읽음이 사라진 것만 알고 답장했는지는 모름. 그래서 '읽었네, 답장도 했지?' 쪽으로 씀.
PRAISE_LINES = {
    "gyeongsang": ["오, 읽었나? 답장까지 했으면 인정한다", "마 니도 하면 되네", "그래 진작 그랄 것이지"],
    "jeolla": ["오메 읽어부렀네잉! 답장도 혔제?", "아따 잘혔다잉", "긍께 진작 허제"],
    "chungcheong": ["읽었슈? 잘혔슈. 답장도 혔쥬?", "거봐유, 허믄 되잖어유", "늦었지만... 뭐, 괜찮어유"],
    "polite": ["확인 감사합니다. 회신도 부탁드려요.", "금일 건 확인 완료되었습니다.", "신속한 확인 감사드립니다. (신속하진 않았습니다)"],
    "office": ["확인 완료!", "수고하셨어요.", "메시지 하나 정리했어요."],
    "bestie": ["오 읽었네 ㅋㅋ 답장도 했지?", "살아있었네 다행 ㅋㅋ", "그래 이게 사람이지"],
    "mz": ["읽음 인증 완료 ㅇㅈ", "오 이건 좀 킹정", "갓생 한 칸 올라감 ㅋ"],
    "hiphop": ["Aight, respect. You hit 'em back, right?", "Look at you, actin' right.", "W. Took you long enough tho."],
    "hipple": ["뽕@알, 읽었나? 쌈@뽕하다;;;", "후드에서 살아남기 제4장: 답장하는 자가 살아남는다.", "(답장 입갤) 인정;;;"],
    "custom": [],
}
SETTINGS_PATH = os.path.join(HERE, "settings.json")
CUSTOM_PATH = os.path.join(HERE, "내대사.txt")
CUSTOM_MAX = 80     # 대사 한 줄 최대 글자 수 (너무 길면 위젯이 커짐)
CUSTOM_DEFAULT = (("[처음]", ["톡 왔다. 답장해라", "답장 언제 할 건데?"]),
                  ("[10분]", ["아직도 안 읽었네?", "폰 어디 뒀어?"]),
                  ("[1시간]", ["진짜 너무한 거 아니냐", "이제 진짜 화낸다!!"]),
                  ("[칭찬]", ["오 읽었네! 답장도 했지?"]))


def load_custom():
    """내대사.txt를 읽어 '내 대사' 말투에 넣음. 파일이 없거나 비어 있는 구역은 기본 대사로 채움."""
    found = {sec: [] for sec, _ in CUSTOM_DEFAULT}
    for enc in ("utf-8-sig", "cp949"):  # 메모장에서 ANSI로 저장한 파일도 읽음
        try:
            with open(CUSTOM_PATH, encoding=enc) as f:
                text = f.read().splitlines()
        except UnicodeDecodeError:
            continue
        except OSError:
            text = []
        sec = None
        for raw in text:
            line = raw.strip()
            if re.fullmatch(r"\[[^\]]*\]", line):
                sec = line if line in found else None   # 모르는 구역은 통째로 무시
            elif line and not line.startswith("#") and sec:
                found[sec].append(line[:CUSTOM_MAX])
        break
    lists = [found[sec] or list(lines) for sec, lines in CUSTOM_DEFAULT]
    TONE_LINES["custom"][:] = lists[:3]
    PRAISE_LINES["custom"][:] = lists[3]


def open_custom():
    """내대사.txt를 메모장 등 기본 프로그램으로 엶. 없으면 예시를 넣어 만듦."""
    if not os.path.exists(CUSTOM_PATH):
        out = ["# 내 대사. 한 줄에 대사 하나. # 으로 시작하는 줄은 무시함.",
               "# 저장하면 바로 반영됨. 말투 고르기에서 '내 대사'를 고르면 나옴.", ""]
        for sec, lines in CUSTOM_DEFAULT:
            out += [sec] + lines + [""]
        with open(CUSTOM_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
    os.startfile(CUSTOM_PATH)


load_custom()


def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(**changes):
    data = load_settings()
    data.update(changes)
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass  # 저장이 안 돼도 이번 실행에서는 적용됨


def load_tone():
    tone = load_settings().get("tone")
    return tone if isinstance(tone, str) and tone in TONE_LINES else DEFAULT_TONE


def save_tone(tone):
    save_settings(tone=tone)


# 거르기: 숨기기는 이름·메시지 중 하나만 걸려도 숨김. 이것만 보기는 하나라도 있으면 맞는 방만 보임. 숨기기가 먼저.
FILTER_KEYS = ("hide_name", "hide_text", "only_name", "only_text")
DEFAULT_HIDE = ["쿠팡", "토스뱅크"]   # 1:1 방이지만 사람이 아닌 곳(채널 등). 화면만으론 구분이 안 됨
FILTER_MAX = 40       # 문구 하나 최대 글자 수


def load_filters():
    saved = load_settings().get("filters")
    if not isinstance(saved, dict):
        return {"hide_name": list(DEFAULT_HIDE), "hide_text": [], "only_name": [], "only_text": []}
    out = {}
    for key in FILTER_KEYS:
        words = saved.get(key)
        out[key] = [w for w in words if isinstance(w, str) and w.strip()] if isinstance(words, list) else []
    return out


def squash(text):
    """띄어쓰기·대소문자를 무시하고 비교함. 화면에서 읽은 글자는 띄어쓰기가 틀릴 수 있음."""
    return re.sub(r"\s+", "", text or "").lower()


def filter_reason(filters, name, text):
    """이 방을 숨기는 이유 문구. 보여도 되면 None."""
    n, t = squash(name), squash(text)
    for w in filters["hide_name"]:
        if squash(w) in n:
            return f"이름에 '{w}'"
    for w in filters["hide_text"]:
        if squash(w) in t:
            return f"메시지에 '{w}'"
    if filters["only_name"] or filters["only_text"]:
        if any(squash(w) in n for w in filters["only_name"]) or any(squash(w) in t for w in filters["only_text"]):
            return None
        return "'이것만 보기'에 안 맞음"
    return None


AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "답장독촉방"


def autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{os.path.join(os.path.dirname(sys.executable), "pythonw.exe")}" "{os.path.abspath(__file__)}"'


def autostart_on():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
            winreg.QueryValueEx(key, AUTOSTART_NAME)
        return True
    except OSError:
        return False


def set_autostart(on):
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
            if on:
                winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, autostart_command())
            else:
                winreg.DeleteValue(key, AUTOSTART_NAME)
    except OSError:
        pass  # 켜고 끈 결과는 autostart_on으로 다시 확인함


# ───────────────────────── 카톡 읽기 ─────────────────────────

def kakao_pids():
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq KakaoTalk.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, errors="ignore", creationflags=0x08000000,
        ).stdout
    except Exception:
        return []
    pids = []
    for row in csv.reader(out.splitlines()):
        if len(row) > 1 and row[0].lower() == "kakaotalk.exe":
            try:
                pids.append(int(row[1]))
            except ValueError:
                pass
    return pids


# 카톡 채팅 목록(ChatRoomListCtrl)은 직접 그리는 컨트롤이라 UIA/MSAA로 글자가 안 나옴.
# 그래서 창을 PrintWindow로 그림으로만 받아서(클릭·포커스 없음) 픽셀로 읽음.
# 좌표는 100% 배율 기준 실측값. 이름은 맑은 고딕을 직접 그려 픽셀로 대조함(작은 글자라 OCR은 자주 틀림).
# 안읽음 있는 줄의 이름만 글자로 읽음. 메시지 미리보기는 그림 그대로 두었다가 위젯 줄에 마우스를 올릴 때만 보여줌.
# 그림은 메모리에만 두고 저장하지 않음. 방을 여는 게 아니라서 읽음 처리되지 않음.

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32")
user32.GetWindowDC.restype = wt.HDC
user32.GetWindowDC.argtypes = [wt.HWND]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
user32.GetDpiForWindow.argtypes = [wt.HWND]
user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_char_p, wt.UINT]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.CreateFontW.restype = wt.HFONT
gdi32.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wt.DWORD] * 8 + [wt.LPCWSTR]
gdi32.TextOutW.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, wt.LPCWSTR, ctypes.c_int]
gdi32.PatBlt.argtypes = [wt.HDC] + [ctypes.c_int] * 4 + [wt.DWORD]
gdi32.SetBkMode.argtypes = [wt.HDC, ctypes.c_int]
gdi32.SetTextColor.argtypes = [wt.HDC, wt.DWORD]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_char_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
user32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.c_void_p, ctypes.c_void_p, wt.HDC, ctypes.c_void_p,
                                       wt.DWORD, ctypes.c_void_p, wt.DWORD]
user32.GetAncestor.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetWindow.restype = wt.HWND
user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
user32.IsWindow.argtypes = [wt.HWND]
user32.GetForegroundWindow.restype = wt.HWND
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND] + [ctypes.c_int] * 4 + [wt.UINT]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
gdi32.CreateSolidBrush.restype = wt.HBRUSH
gdi32.CreateSolidBrush.argtypes = [wt.DWORD]
gdi32.DeleteDC.argtypes = [wt.HDC]
user32.GetFocus.restype = wt.HWND
user32.MonitorFromPoint.restype = wt.HANDLE
user32.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.restype = wt.HANDLE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
kernel32.CreateEventW.restype = wt.HANDLE
kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
kernel32.SetEvent.argtypes = [wt.HANDLE]
kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
imm32 = ctypes.WinDLL("imm32")
imm32.ImmGetContext.restype = wt.HANDLE
imm32.ImmGetContext.argtypes = [wt.HWND]
imm32.ImmNotifyIME.argtypes = [wt.HANDLE, wt.DWORD, wt.DWORD, wt.DWORD]
imm32.ImmReleaseContext.argtypes = [wt.HWND, wt.HANDLE]
ENUM_PROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

AVATAR_X = (20, 64)     # 프사 가로 범위
ROW_H, AVATAR_TOP = 70, 13   # 줄 높이, 줄 맨 위에서 프사까지
NAME_X = (76, 250)      # 이름이 있을 수 있는 가로 범위
BADGE_X = 250           # 안읽음 배지는 이 x보다 오른쪽 (왼쪽은 미리보기 글자·이모티콘)
BADGE_COLOR = (255, 122, 107)  # 안읽음 배지 바탕색(실측). 높이 17px
SCROLLBAR_W = 14
DARK_LUM = 60           # 이름 글자 밝기(실측 25) 상한
COUNT_COLOR = 0x949494  # 단톡 인원수 글자색(실측, 12px 보통 굵기)
PREVIEW_PX, PREVIEW_COLOR = 12, 0x6E6E6E   # 메시지 미리보기 글자 크기·색(실측)


def window_text(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(h, b, 256)
    return b.value


def find_chat_list(pids):
    """(메인 창, 채팅 목록 컨트롤) 또는 None. 채팅 탭이 아니면 목록이 보이지 않는 상태로 나옴."""
    found = []

    def on_top(h, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids:
            def on_child(c, _):
                if window_text(c).startswith("ChatRoomListCtrl"):
                    found.append((h, c))
                return True
            user32.EnumChildWindows(h, ENUM_PROC(on_child), 0)
        return True

    user32.EnumWindows(ENUM_PROC(on_top), 0)
    return found[0] if found else None


def grab(hwnd):
    """창을 그림으로 받음 → 세로×가로×3(RGB) 배열. 창이 다른 창에 가려져 있어도 됨."""
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return None
    wdc = user32.GetWindowDC(hwnd)
    dc = gdi32.CreateCompatibleDC(wdc)
    bmp = gdi32.CreateCompatibleBitmap(wdc, w, h)
    gdi32.SelectObject(dc, bmp)
    try:
        if not user32.PrintWindow(hwnd, dc, 2):  # PW_RENDERFULLCONTENT
            return None
        info = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        if not gdi32.GetDIBits(dc, bmp, 0, h, buf, info, 0):
            return None
    finally:
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(dc)
        user32.ReleaseDC(hwnd, wdc)
    bgra = np.frombuffer(buf.raw, np.uint8).reshape(h, w, 4)
    return bgra[:, :, [2, 1, 0]].astype(int)


def runs(mask, merge=0):
    """True가 이어지는 구간 [(시작, 끝)]. merge칸 이하로 끊긴 건 하나로 침."""
    out = []
    for i in np.flatnonzero(mask):
        if out and i - out[-1][1] <= merge + 1:
            out[-1][1] = int(i)
        else:
            out.append([int(i), int(i)])
    return [tuple(r) for r in out]


def find_rows(img):
    """프사 위치로 줄을 찾음 → [(윗 y, 아랫 y)]. 스크롤로 프사가 잘린 줄은 뺌."""
    x0, x1 = AVATAR_X
    diff = np.abs(img[:, x0:x1] - img[:, 3:4]).sum(axis=2) > 12  # 줄 배경(선택·호버 포함)과 비교
    avatars = runs(diff.any(axis=1), merge=6)
    return [(t - AVATAR_TOP, t - AVATAR_TOP + ROW_H) for t, b in avatars
            if b - t >= 40 and t >= AVATAR_TOP and t - AVATAR_TOP + ROW_H <= len(img)]


def is_badge_color(a):
    return (np.abs(a - BADGE_COLOR) <= 25).all(axis=2)


def find_badge(img, top, bottom):
    """줄 오른쪽의 빨간 안읽음 배지 → (x0, y0, x1, y1) 또는 None"""
    a = img[top:bottom, BADGE_X:img.shape[1] - SCROLLBAR_W]
    red = is_badge_color(a)
    if not red.any():
        return None
    ys, xs = runs(red.any(axis=1), merge=1), runs(red.any(axis=0), merge=3)
    y0, y1 = max(ys, key=lambda r: r[1] - r[0])
    x0, x1 = max(xs, key=lambda r: r[1] - r[0])
    if y1 - y0 < 14 or x1 - x0 < 14 or red[y0:y1 + 1, x0:x1 + 1].mean() < 0.4:
        return None  # 글자 번짐 같은 잡티
    return x0 + BADGE_X, y0 + top, x1 + BADGE_X, y1 + top


def name_line(img, top, bottom):
    """이름 줄 → (y0, y1, x0, x1) 또는 None. 이름은 그 줄에서 맨 위의 가장 진한 글자."""
    nx0, nx1 = NAME_X
    lum = img[top:bottom, nx0:nx1].mean(axis=2)
    ys = runs((lum < DARK_LUM).any(axis=1), merge=1)
    if not ys:
        return None
    y0, y1 = ys[0]
    xs = np.flatnonzero((lum[y0:y1 + 1] < DARK_LUM).any(axis=0))
    x0 = int(xs[0])
    bg = img[y0 + top, 3].mean()  # 선택·호버된 줄은 배경이 어두움
    while x0 > 0 and (lum[y0:y1 + 1, x0 - 1] < bg - 20).any():  # ㅇ처럼 둥근 글자는 왼쪽 끝이 옅음
        x0 -= 1
    return y0 + top, y1 + top, x0 + nx0, int(xs[-1]) + nx0


def has_member_count(img, line):
    """이름 뒤에 회색 숫자(단톡 인원수)가 있는지. 핀·음소거 아이콘도 회색이라 숫자 모양까지 대조함."""
    y0, y1, _, x1 = line
    a = (img * 255.0 / img[y0, 3]).astype(np.float32)
    table = glyph_table("0123456789", 12, 400, COUNT_COLOR)
    tail = a[y0:y1 + 1, x1 + 2:NAME_X[1]].mean(axis=2).min(axis=0)
    for s, _ in runs(tail < 215):
        if best_glyph(a, x1 + 2 + s, range(max(y0 - 5, 0), y0 + 1), table):
            return True
    return False


def has_grid_avatar(img, top):
    """프사가 격자로 나뉘었는지. 격자는 가운데 가로줄이 칸 사이 틈이라 거의 통째로 배경색."""
    mid = top + AVATAR_TOP + 21
    x0, x1 = AVATAR_X
    gap = np.abs(img[mid:mid + 2, x0:x1] - img[mid, 3]).sum(axis=2) <= 12
    return bool(gap.any(axis=0).mean() >= 0.9)


def is_group(img, top, line):
    return has_member_count(img, line) or has_grid_avatar(img, top)


HANGUL = "".join(chr(c) for c in range(0xAC00, 0xD7A4))
ASCII = "".join(chr(c) for c in range(0x21, 0x7F))
JAMO = "".join(chr(c) for c in range(0x3131, 0x3164))   # ㅋㅋㅋ 같은 낱자
UNREAD_RE = re.compile(r"\d{1,3}\+?")
GLYPH_H = 18
MATCH_ERR = 0.05        # 글자 대조 허용 오차 (0~1)
SPACE_GAP = 3           # 이 칸 이상 비면 띄어쓰기 (글자 사이는 2칸 이하)
_glyph_tables, _name_cache, _preview_cache = {}, {}, {}


def glyph_table(chars, px=12, weight=700, color=0x191919, bg=(255, 255, 255)):
    """카톡과 똑같이 ClearType로 글자를 그려 둠 → {폭: (글자들, 배열[개수, 높이, 폭, 3])}
    color는 0xBBGGRR, bg는 (R, G, B)."""
    key = (chars, px, weight, color, bg)
    if key not in _glyph_tables:
        w, h = 40, GLYPH_H
        sdc = user32.GetWindowDC(None)
        dc = gdi32.CreateCompatibleDC(sdc)
        bmp = gdi32.CreateCompatibleBitmap(sdc, w, h)
        gdi32.SelectObject(dc, bmp)
        font = gdi32.CreateFontW(-px, 0, 0, 0, weight, 0, 0, 0, 1, 0, 0, 5, 0, "맑은 고딕")  # 5 = ClearType
        gdi32.SelectObject(dc, font)
        gdi32.SetBkMode(dc, 1)
        gdi32.SetTextColor(dc, color)
        brush = gdi32.CreateSolidBrush(bg[0] | bg[1] << 8 | bg[2] << 16)
        gdi32.SelectObject(dc, brush)
        info = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        by_width = {}
        for ch in chars:
            gdi32.PatBlt(dc, 0, 0, w, h, 0x00F00021)  # PATCOPY: 바탕색으로 칠함
            gdi32.TextOutW(dc, 4, 0, ch, 1)
            gdi32.GetDIBits(dc, bmp, 0, h, buf, info, 0)
            a = np.frombuffer(buf.raw, np.uint8).reshape(h, w, 4)[:, :, [2, 1, 0]]
            xs = np.flatnonzero((np.abs(a.astype(int) - bg) > 8).any(axis=(0, 2)))
            if len(xs):
                by_width.setdefault(int(xs[-1] - xs[0] + 1), []).append((ch, a[:, xs[0]:xs[-1] + 1]))
        gdi32.DeleteObject(font)
        gdi32.DeleteObject(brush)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(dc)
        user32.ReleaseDC(None, sdc)
        _glyph_tables[key] = {wd: ("".join(c for c, _ in v), np.stack([g for _, g in v]).astype(np.float32))
                              for wd, v in by_width.items()}
    return _glyph_tables[key]


def best_glyph(a, x, ys, table, tol=0.008):
    """x 근처에서 가장 잘 맞는 글자 → (오차, 글자, 폭, 글자 왼쪽 x, 글자 위 y).
    오차가 tol 안에서 거의 같으면 폭이 넓은 쪽(좁은 글자가 큰 글자의 일부에 들어맞는 경우 방지)."""
    found = []
    for width, (chars, stack) in table.items():
        for dx in (0, -1, 1):
            for y in ys:
                r = a[y:y + GLYPH_H, x + dx:x + dx + width]
                if r.shape != stack.shape[1:]:
                    continue
                errs = np.abs(stack - r).mean(axis=(1, 2, 3)) / 255
                i = int(errs.argmin())
                if errs[i] < MATCH_ERR:
                    found.append((float(errs[i]), chars[i], width, x + dx, y))
    if not found:
        return None
    least = min(f[0] for f in found)
    return max((f for f in found if f[0] <= least + tol), key=lambda f: (f[2], -f[0]))


def read_glyphs(a, x0, x1, ys, tables, ink, drop_tail=False, tol=0.008):
    """왼쪽부터 글자 대조로 읽음. tables는 앞의 것부터 시도, ink는 가로줄별 '뭔가 그려져 있음' 여부.
    못 읽은 칸은 □. drop_tail이면 맨 뒤의 못 읽는 칸(이름 뒤 상태 아이콘)은 버림."""
    x, out, ys = x0, "", list(ys)
    while x <= x1:
        g = None
        for table in tables:
            g = g or best_glyph(a, x, ys, table, tol)
        if g is None:
            if drop_tail and x1 - x < 16:
                break
            out, x = out + "□", x + 11  # 사전에 없는 글자(한자·이모지)
        else:
            out += g[1]
            ys = [g[4]]  # 첫 글자로 세로 위치가 정해짐
            x = g[3] + g[2]
        gap = 0
        while x + gap <= x1 and not ink[x + gap]:
            gap += 1
        if gap >= SPACE_GAP and x + gap <= x1:
            out += " "
        x += gap
    return out.strip()


def read_name(img, line):
    y0, y1, x0, x1 = line
    oy = max(y0 - GLYPH_H, 0)
    crop = img[oy:y1 + GLYPH_H, :x1 + 16]
    key = crop[:, x0:x1 + 1].tobytes()
    if key not in _name_cache:
        if len(_name_cache) > 300:
            _name_cache.clear()
        a = (crop * 255.0 / img[y0, 3]).astype(np.float32)  # 선택·호버로 줄 배경이 달라도 흰 바탕 기준으로
        ink = (a[y0 - oy - 1:y1 - oy + 2] < 230).any(axis=(0, 2))
        _name_cache[key] = read_glyphs(a, x0, x1, range(y0 - oy - 5, y0 - oy + 1),
                                       [glyph_table(HANGUL), glyph_table(ASCII)], ink, drop_tail=True)
    return _name_cache[key]


def read_count(img, box):
    """배지 숫자. 못 읽으면 '?'(안읽음인 건 확실함)."""
    x0, y0, x1, y1 = box
    crop = img[y0:y1 + 1, x0:x1 + 1].copy()
    for row in crop:  # 둥근 모서리 바깥의 흰 부분은 글자가 아니니 바탕색으로 덮음
        xs = np.flatnonzero(is_badge_color(row[None])[0])
        row[:xs[0] if len(xs) else len(row)] = BADGE_COLOR
        if len(xs):
            row[xs[-1] + 1:] = BADGE_COLOR
    pad = GLYPH_H
    a = np.full((crop.shape[0] + pad * 2, crop.shape[1] + pad * 2, 3), BADGE_COLOR, np.float32)
    a[pad:pad + crop.shape[0], pad:pad + crop.shape[1]] = crop
    ink = (np.abs(a - BADGE_COLOR).sum(axis=2) > 60).any(axis=0)
    xs = np.flatnonzero(ink)
    if not len(xs):
        return "?"
    table = glyph_table("0123456789+", 12, 700, 0xFFFFFF, BADGE_COLOR)
    text = read_glyphs(a, int(xs[0]), int(xs[-1]), range(pad - 2, pad + 5), [table], ink).replace(" ", "")
    return text if UNREAD_RE.fullmatch(text) else "?"


def preview_crop(img, top, bottom, line):
    """이름 아래 메시지 미리보기 부분의 그림(글자로 읽지 않음) 또는 None"""
    a = img[line[1] + 3:bottom - 1, NAME_X[0] + 4:BADGE_X]
    ink = np.abs(a - img[top + 1, 3]).sum(axis=2) > 30
    if not ink.any():
        return None
    ys, xs = np.flatnonzero(ink.any(axis=1)), np.flatnonzero(ink.any(axis=0))
    return a[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1]


def read_preview(img, top, bottom, line):
    """이름 아래 메시지 미리보기를 글자로 읽음. 거르기에 메시지 문구가 있을 때만 호출. 못 읽은 칸은 □."""
    y_off, bg = line[1] + 3, img[top + 1, 3]
    a = img[y_off:bottom - 1, NAME_X[0]:BADGE_X]
    ink = np.abs(a - bg).sum(axis=2) > 30
    if not ink.any():
        return ""
    key = a.tobytes()
    if key not in _preview_cache:
        if len(_preview_cache) > 300:
            _preview_cache.clear()
        norm = (img * 255.0 / bg).astype(np.float32)   # 선택·호버로 줄 배경이 달라도 흰 바탕 기준으로
        # 회색 글자는 대비가 작아 글자 간 오차 차이도 작음. 한 표에서 겨루고 tol도 좁혀야 '.'을 'ㅡ'로 안 읽음
        tables = [glyph_table(HANGUL + JAMO + ASCII, PREVIEW_PX, 400, PREVIEW_COLOR)]
        parts = []
        for y0, y1 in runs(ink.any(axis=1), merge=1):
            xs = np.flatnonzero(ink[y0:y1 + 1].any(axis=0))
            yy0, yy1 = y0 + y_off, y1 + y_off
            mask_x = (norm[yy0 - 1:yy1 + 2] < 240).any(axis=(0, 2))
            parts.append(read_glyphs(norm, int(xs[0]) + NAME_X[0], int(xs[-1]) + NAME_X[0],
                                     range(max(yy0 - 5, 0), yy0 + 1), tables, mask_x, tol=0.002))
        _preview_cache[key] = " ".join(parts)
    return _preview_cache[key]


def scan_rows(img, need_text=False):
    """목록 그림 → 안읽음 있는 줄 [{name, count, group}]. need_text면 메시지도 글자로 읽어 text에 넣음."""
    out = []
    for top, bottom in find_rows(img):
        box = find_badge(img, top, bottom)
        line = name_line(img, top, bottom)
        if box and line:
            ax0, ax1 = AVATAR_X
            ay = top + AVATAR_TOP
            out.append({"name": read_name(img, line), "count": read_count(img, box),
                        "group": is_group(img, top, line), "photo": img[ay:ay + ax1 - ax0, ax0:ax1],
                        "preview": preview_crop(img, top, bottom, line),
                        "text": read_preview(img, top, bottom, line) if need_text else ""})
    return out


STATUS_SCALE = "화면 배율을 100%로 바꿔 주세요 · 눌러서 설정 열기"


def read_kakao(need_text=False):
    """→ (안읽음 있는 1:1 방 목록, 상태 문구). 못 읽는 상황이면 '다 읽음'으로 착각하지 않게 상태 문구를 냄."""
    pids = kakao_pids()
    if not pids:
        return [], "카톡이 꺼져 있어요. 켜면 바로 읽어요"
    found = find_chat_list(pids)
    if not found:
        return [], "카톡 채팅 목록을 못 찾았어요 · 눌러서 열기"
    main, lst = found
    if user32.IsIconic(main) or not user32.IsWindowVisible(main):
        return [], "카톡 창이 닫혀 있어 못 읽어요 · 눌러서 열기"
    if not user32.IsWindowVisible(lst):
        return [], "카톡에서 채팅 탭을 눌러 주세요 · 눌러서 열기"
    if user32.GetDpiForWindow(lst) != 96:
        return [], STATUS_SCALE
    img = grab(lst)
    if img is None:
        return [], "카톡 화면을 못 받아왔어요. 곧 다시 해 볼게요"
    return [r for r in scan_rows(img, need_text) if r["name"] and not r["group"]], ""


def bring_to_front(hwnd):
    user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)  # SW_RESTORE / SW_SHOW
    user32.SetForegroundWindow(hwnd)


def show_kakao():
    """카톡 메인 창을 앞으로 띄움 (최소화·트레이 상태 포함)"""
    found = find_chat_list(kakao_pids())
    if found:
        bring_to_front(found[0])


def top_windows(pids):
    """카톡의 보이는 최상위 창 {핸들: 제목}"""
    found = {}

    def on_top(h, _):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(h):
            found[h] = window_text(h)
        return True

    user32.EnumWindows(ENUM_PROC(on_top), 0)
    return found


def room_window(pids, name, before=None):
    """이미 열려 있는 채팅방 창. 채팅방 창 제목은 방 이름.
    before(열기 전 창 목록)를 주면 제목이 달라도 새로 뜬 채팅방 창을 찾음. 채팅방 창은 크기 조절 테두리가 있음(실측)."""
    windows = top_windows(pids)
    for h, title in windows.items():
        if title == name:
            return h
    if before is not None:
        for h, title in windows.items():
            if h not in before and title and user32.GetWindowLongPtrW(h, -16) & 0x40000:  # WS_THICKFRAME
                return h
    return None


def window_above(main):
    """메인 창 바로 위의 보이는 창. 안 보이는 창(IME 등)과 메인 창이 거느린 작은 창은 메인과 같이 움직일 수 있어 건너뜀.
    항상 위 창 바로 아래면(메인이 맨 앞) None."""
    h = user32.GetWindow(main, 3)  # GW_HWNDPREV
    while h and (not user32.IsWindowVisible(h) or user32.GetWindow(h, 4) == main):  # GW_OWNER
        h = user32.GetWindow(h, 3)
    if h and user32.GetWindowLongPtrW(h, -20) & 8:  # WS_EX_TOPMOST
        return None
    return h


def send_back(main, above, room):
    """방을 열 때 따라 올라온 메인 창을 원래 겹침 순서로 돌려놓음. 맨 앞이었으면 방 바로 아래로."""
    after = above if above and user32.IsWindow(above) else room
    user32.SetWindowPos(main, after, 0, 0, 0, 0, 0x13)  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE


def keep_behind(main, above, room, sec=3):
    """방이 뜨고 1초쯤 뒤에 메인 창이 따라 올라옴. 잠깐 지켜보다 바로 내림. 사용자가 마우스를 누르면 손 뗌."""
    end = time.time() + sec
    while time.time() < end and not user32.GetAsyncKeyState(1) & 0x8000:  # VK_LBUTTON
        send_back(main, above, room)
        if user32.GetForegroundWindow() == main:
            user32.SetForegroundWindow(room)
        time.sleep(0.03)


def find_room_row(img, name):
    """안읽음 배지가 있는 줄 중 이름이 맞는 줄 → (윗 y, 아랫 y). 같은 이름이 둘이면 잘못 열 수 있어 None."""
    rows = []
    for top, bottom in find_rows(img):
        line = name_line(img, top, bottom)
        if line and find_badge(img, top, bottom) and read_name(img, line) == name:
            rows.append((top, bottom))
    return rows[0] if len(rows) == 1 else None


def double_click_row(lst, row):
    x, y = NAME_X[0] + 60, (row[0] + row[1]) // 2
    pos = y << 16 | x
    for msg, keys in ((0x200, 0), (0x201, 1), (0x202, 0), (0x203, 1), (0x202, 0)):  # 이동·누름·뗌·더블클릭·뗌
        user32.PostMessageW(lst, msg, keys, pos)


def open_room(name):
    """위젯에서 사람을 눌렀을 때만 호출. 방금 받은 화면에서 줄을 다시 찾아 열고(읽음 처리됨), 안 되면 메인 창을 띄움."""
    pids = kakao_pids()
    opened = room_window(pids, name)
    if opened:
        bring_to_front(opened)
        return
    found = find_chat_list(pids)
    row = None
    if found and user32.IsWindowVisible(found[1]) and not user32.IsIconic(found[0]):
        img = grab(found[1])
        row = find_room_row(img, name) if img is not None else None
    if not row:
        show_kakao()
        return
    main = found[0]
    above = window_above(main)
    before = top_windows(pids)
    double_click_row(found[1], row)
    end = time.time() + 5   # 방이 늦게 떠도 메인 창을 먼저 띄우지 않게 넉넉히 기다림
    while not opened and time.time() < end:
        time.sleep(0.05)
        opened = room_window(pids, name, before)
    if not opened:
        show_kakao()
        return
    bring_to_front(opened)
    keep_behind(main, above, opened)


class KakaoSource:
    """백그라운드에서 카톡을 주기적으로 읽음. 결과: {이름: 안읽음수}"""

    def open_room(self, name):
        threading.Thread(target=open_room, args=(name,), daemon=True).start()

    def open_kakao(self):
        show_kakao()

    def __init__(self):
        self.lock = threading.Lock()
        self.result = {}
        self.avatars = {}
        self.previews = {}
        self.texts = {}
        self.need_text = False   # 메시지 문구로 거를 때만 위젯이 켬
        self.status = ""
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))  # 실제 픽셀 크기로 받기
        while True:
            try:
                rooms, status = read_kakao(self.need_text)
                self.avatars = {r["name"]: r["photo"] for r in rooms}
                self.previews = {r["name"]: r["preview"] for r in rooms}
                self.texts = {r["name"]: r["text"] for r in rooms}
                self._set({r["name"]: r["count"] for r in rooms}, status)
            except Exception as e:
                self._set({}, f"읽기 실패: {e.__class__.__name__}")
            time.sleep(POLL_SEC)

    def _set(self, result, status):
        with self.lock:
            self.result, self.status = result, status

    def get(self):
        with self.lock:
            return dict(self.result), self.status


class DemoSource:
    def open_room(self, name):
        pass

    def open_kakao(self):
        pass

    def __init__(self):
        self.result = {"엄마": "3", "김지수": "1", "동네친구 민수": "12"}
        self.preseed = {"엄마": 75, "김지수": 15, "동네친구 민수": 1}  # 몇 분 전부터
        self.texts = {"엄마": "밥은 먹었나 전화 좀 받아라", "김지수": "내일 몇 시에 볼까?", "동네친구 민수": "야 이거 봤냐ㅋㅋㅋ"}
        self.previews = {n: self._fake_preview(t) for n, t in self.texts.items()}

    @staticmethod
    def _fake_preview(text):
        pic = Image.new("RGBA", (px(170), px(16)), (255, 255, 255, 255))
        put_text(pic, (0, px(8)), text, (90, 90, 90), "lm", font(11.5))
        return np.asarray(pic.convert("RGB")).astype(int)

    def get(self):
        return dict(self.result), ""


# ───────────────────────── 위젯 ─────────────────────────
# 화면 구석에 떠 있는 작은 카톡방. Tk 기본 부품으로는 둥근 모서리·그림자가 안 돼서
# 전체를 그림으로 그려 창에 통째로 올림(UpdateLayeredWindow). Tk는 마우스 이벤트만 받음.

SCALE = 1.0             # 화면 배율 (시작할 때 정함)
PANEL_W = 352
MARGIN = 16             # 그림자 여백
AVATAR = 38
BUBBLE_MAX = 196
CHAT_BG = (186, 206, 224)       # 카톡 채팅방 기본 배경
INK, INK_SOFT = (25, 25, 25), (56, 72, 88)
PILL_RED = (255, 90, 70)
HANDLE_SIZE = 44
# 안 읽은 시간에 따른 말풍선 (바탕색, 글자색, 굵게)
LEVEL_STYLE = [((255, 255, 255), INK, False), ((254, 229, 0), INK, False), ((232, 62, 50), (255, 255, 255), True),
               ((168, 226, 140), INK, False)]  # 마지막은 칭찬
AVATAR_COLORS = [(255, 170, 130), (160, 196, 255), (178, 220, 160), (216, 180, 240), (250, 200, 110), (140, 210, 210)]
PRAISE_STYLE = 3
BUTTONS = [("settings", "설정 · 말투 · 거르기"), ("all", "30분 동안 전부 조용히"), ("collapse", f"작게 접기 · 숨기기는 {HOTKEY_TEXT}"), ("quit", "위젯 끄기")]
ROW_TIPS = {"row:": "누르면 방이 열리고 읽음 처리돼요", "snooze:": "10분 동안 이 사람만 조용히", "hide:": "이 사람을 위젯에서 숨겨요"}
_fonts = {}


def px(n):
    return round(n * SCALE)


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype("malgunbd.ttf" if bold else "malgun.ttf", px(size) * 3)
    return _fonts[key]


def text_w(f, s):
    return f.getlength(s) / 3


def put_text(img, xy, s, fill, anchor, f):
    """글자를 3배로 그려 줄임. 작은 한글이 힌팅으로 뭉개지는 걸 막음."""
    x, y = xy
    l, t, r, b = f.getbbox(s, anchor=anchor)
    x0, y0 = max(int(x + l / 3) - 1, 0), max(int(y + t / 3) - 1, 0)
    w, h = int(r / 3 - l / 3) + 4, int(b / 3 - t / 3) + 4
    big = Image.new("L", (w * 3, h * 3), 0)
    ImageDraw.Draw(big).text(((x - x0) * 3, (y - y0) * 3), s, font=f, fill=255, anchor=anchor)
    layer = Image.new("RGBA", (w, h), tuple(fill) + (255,))
    layer.putalpha(big.resize((w, h), Image.LANCZOS))
    img.alpha_composite(layer, (x0, y0))


def round_mask(w, h, r):
    m = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), r * 4, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def fill_round(img, box, r, color, alpha=255):
    x0, y0, x1, y1 = box
    mask = round_mask(x1 - x0, y1 - y0, r)
    if alpha < 255:
        mask = mask.point(lambda v: v * alpha // 255)
    layer = Image.new("RGBA", mask.size, tuple(color) + (255,))
    layer.putalpha(mask)
    img.alpha_composite(layer, (x0, y0))


def drop_shadow(img, box, r):
    x0, y0, x1, y1 = box
    m = Image.new("L", img.size, 0)
    m.paste(round_mask(x1 - x0, y1 - y0, r), (x0, y0 + px(3)))
    m = m.filter(ImageFilter.GaussianBlur(px(7))).point(lambda v: v * 70 // 255)
    layer = Image.new("RGBA", img.size, (20, 30, 45, 255))
    layer.putalpha(m)
    img.alpha_composite(layer)


def wrap(text, f, width):
    """글자 단위로 줄바꿈하되 가능하면 띄어쓰기에서 끊음"""
    lines, cur = [], ""
    for ch in text:
        if text_w(f, cur + ch) > width and cur:
            cut = cur.rfind(" ")
            if cut > 0:
                lines.append(cur[:cut])
                cur = cur[cut + 1:] + ch
            else:
                lines.append(cur)
                cur = ch
        else:
            cur += ch
    return lines + [cur] if cur else lines


def waited_text(mins):
    if mins < 1:
        return "방금"
    if mins < 60:
        return f"{mins}분째"
    return f"{mins // 60}시간 {mins % 60}분째" if mins % 60 else f"{mins // 60}시간째"


def draw_avatar(img, x, y, name, photo):
    s = px(AVATAR)
    if photo is not None:
        pic = Image.fromarray(photo.astype(np.uint8)).resize((s, s), Image.LANCZOS).convert("RGBA")
    else:
        pic = Image.new("RGBA", (s, s), AVATAR_COLORS[sum(map(ord, name)) % len(AVATAR_COLORS)] + (255,))
        put_text(pic, (s / 2, s / 2), name[:1], (255, 255, 255), "mm", font(15, True))
    pic.putalpha(round_mask(s, s, px(14)))
    img.alpha_composite(pic, (x, y))


def draw_bubble(img, box, color):
    x0, y0, x1, y1 = box
    fill_round(img, box, px(11), color)
    tw, th = px(7), px(9)
    tail = Image.new("L", (tw * 4, th * 4), 0)
    ImageDraw.Draw(tail).polygon([(tw * 4, 0), (0, px(2) * 4), (tw * 4, th * 4)], fill=255)
    tail = tail.resize((tw, th), Image.LANCZOS)
    layer = Image.new("RGBA", (tw, th), tuple(color) + (255,))
    layer.putalpha(tail)
    img.alpha_composite(layer, (x0 - tw + px(1), y0 + px(9)))


def draw_icon(img, kind, cx, cy, color):
    n, c = px(16), px(8) * 4   # 선은 4배로 그려 줄여서 매끈하게
    r, w = px(5) * 4, round(px(1.5) * 4)
    big = Image.new("L", (n * 4, n * 4), 0)
    d = ImageDraw.Draw(big)
    if kind == "quit":
        d.line((c - r, c - r, c + r, c + r), fill=255, width=w)
        d.line((c - r, c + r, c + r, c - r), fill=255, width=w)
    elif kind == "settings":     # 톱니바퀴
        for i in range(8):
            a = i * math.pi / 4
            d.line((c + math.cos(a) * r * 0.8, c + math.sin(a) * r * 0.8, c + math.cos(a) * r * 1.4, c + math.sin(a) * r * 1.4),
                   fill=255, width=round(w * 1.3))
        d.ellipse((c - r, c - r, c + r, c + r), fill=255)
        d.ellipse((c - r * 0.45, c - r * 0.45, c + r * 0.45, c + r * 0.45), fill=0)
    elif kind == "all":          # 초승달: 방해 금지
        d.ellipse((c - r * 1.25, c - r * 1.25, c + r * 1.25, c + r * 1.25), fill=255)
        d.ellipse((c - r * 0.55, c - r * 1.65, c + r * 1.75, c + r * 0.65), fill=0)
    elif kind == "back":
        d.line((c + r * 0.5, c - r, c - r * 0.5, c, c + r * 0.5, c + r), fill=255, width=w, joint="curve")
    elif kind == "next":
        d.line((c - r * 0.4, c - r * 0.8, c + r * 0.4, c, c - r * 0.4, c + r * 0.8), fill=255, width=w, joint="curve")
    elif kind == "check":
        d.line((c - r, c, c - r * 0.25, c + r * 0.75, c + r, c - r * 0.7), fill=255, width=w, joint="curve")
    else:
        d.line((c - r, c, c + r, c), fill=255, width=w)
    layer = Image.new("RGBA", (n, n), tuple(color) + (255,))
    layer.putalpha(big.resize((n, n), Image.LANCZOS))
    img.alpha_composite(layer, (cx - n // 2, cy - n // 2))


def render_panel(items, more, hover, title="답장 독촉방", foot=None):
    """펼친 카톡방 → (RGBA 그림, 누를 수 있는 영역 [(x0, y0, x1, y1, 이름)]). foot은 맨 아래 줄 (글자, 눌렀을 때 이름)."""
    m, w = px(MARGIN), px(PANEL_W)
    head, pad = px(42), px(12)
    f_msg, f_bold, f_name, f_small = font(13), font(13, True), font(11.5, True), font(10.5)
    line_h = px(19)
    laid = []
    total = head
    for it in items:
        lines = wrap(it["line"], f_bold if LEVEL_STYLE[it.get("style", it["level"])][2] else f_msg, px(BUBBLE_MAX) - px(20))
        h = px(18) + len(lines) * line_h + px(14)
        laid.append((it, lines, total, h))
        total += max(h, px(AVATAR)) + pad
    if more:
        total += px(22)
    total += px(4)
    more_y = m + total - px(16)
    if foot:
        total += px(34)
    img = Image.new("RGBA", (w + m * 2, total + m * 2), (0, 0, 0, 0))
    panel = (m, m, m + w, m + total)
    drop_shadow(img, panel, px(16))
    fill_round(img, panel, px(16), CHAT_BG)
    hits = []

    tip = dict(BUTTONS).get(hover)
    for prefix, text in ROW_TIPS.items():
        if hover and hover.startswith(prefix):
            tip = text
    if tip:
        put_text(img, (m + px(14), m + head // 2), clip(tip, font(12), px(212)), INK_SOFT, "lm", font(12))
    else:
        put_text(img, (m + px(14), m + head // 2), title, INK, "lm", font(13.5, True))
        tw = text_w(font(13.5, True), title)
        waiting = sum(1 for it in items if "note" not in it) + more
        if waiting:
            put_text(img, (m + px(14) + tw + px(6), m + head // 2), str(waiting), INK_SOFT, "lm", font(13))
    bx = m + w - px(8)
    for key, _ in reversed(BUTTONS):
        s = px(28)
        box = (bx - s, m + (head - s) // 2, bx, m + (head - s) // 2 + s)
        if hover == key:
            fill_round(img, box, px(8), (40, 60, 80), 34)
        draw_icon(img, key, (box[0] + box[2]) // 2, (box[1] + box[3]) // 2, INK if hover == key else INK_SOFT)
        hits.append(box + (key,))
        bx -= s + px(2)
    hits.append((m, m, bx, m + head, "drag"))

    for it, lines, y, h in laid:
        name = it["name"]
        top = m + y
        row_hit = (m, top - pad // 2, m + w, top + max(h, px(AVATAR)) + pad // 2, "row:" + name)
        row_hover = hover in ("row:" + name, "snooze:" + name, "hide:" + name)
        if row_hover:
            fill_round(img, (m + px(5), top - px(4), m + w - px(5), top + max(h, px(AVATAR)) + px(4)), px(10), (255, 255, 255), 70)
        draw_avatar(img, m + px(12), top, name, it.get("photo"))
        nx = m + px(12) + px(AVATAR) + px(9)
        put_text(img, (nx, top + px(7)), name, INK_SOFT, "lm", f_name)
        nw = int(text_w(f_name, name))
        if it["count"]:
            ctext = str(it["count"])
            cw = max(px(17), int(text_w(font(10, True), ctext)) + px(10))
            pill = (nx + nw + px(6), top, nx + nw + px(6) + cw, top + px(15))
            fill_round(img, pill, px(8), PILL_RED)
            put_text(img, ((pill[0] + pill[2]) // 2, top + px(7)), ctext, (255, 255, 255), "mm", font(10, True))
        color, ink, bold = LEVEL_STYLE[it.get("style", it["level"])]
        f = f_bold if bold else f_msg
        bw = int(max(text_w(f, l) for l in lines)) + px(20)
        by = top + px(18)
        bub = (nx + px(2), by, nx + px(2) + bw, by + len(lines) * line_h + px(14))
        draw_bubble(img, bub, color)
        for i, l in enumerate(lines):
            put_text(img, (bub[0] + px(10), by + px(7) + line_h * i + line_h // 2), l, ink, "lm", f)
        rx = bub[2] + px(6)
        if "note" in it:     # 칭찬 줄은 누를 게 없음
            put_text(img, (rx, bub[3] - px(1)), it["note"], INK_SOFT, "ld", f_small)
            continue
        if row_hover:
            label = f"{SNOOZE_MIN}분 조용히"
            cw = int(text_w(f_small, label)) + px(14)
            chip = (rx, bub[3] - px(21), rx + cw, bub[3])
            fill_round(img, chip, px(7), (40, 60, 80), 225 if hover.startswith("snooze") else 150)
            put_text(img, ((chip[0] + chip[2]) // 2, (chip[1] + chip[3]) // 2), label, (255, 255, 255), "mm", f_small)
            hits.append(chip + ("snooze:" + name,))
            label = "안 보기"     # 말풍선이 길어도 안 겹치게 이름 줄 오른쪽에 둠
            cw = int(text_w(f_small, label)) + px(14)
            chip = (m + w - px(12) - cw, top - px(2), m + w - px(12), top + px(17))
            fill_round(img, chip, px(7), (40, 60, 80), 225 if hover.startswith("hide") else 150)
            put_text(img, ((chip[0] + chip[2]) // 2, (chip[1] + chip[3]) // 2), label, (255, 255, 255), "mm", f_small)
            hits.append(chip + ("hide:" + name,))
        else:
            put_text(img, (rx, bub[3] - px(1)), waited_text(it["mins"]), INK_SOFT, "ld", f_small)
        hits.append(row_hit)
    if more:
        put_text(img, (m + w // 2, more_y), f"외 {more}명 더", INK_SOFT, "mm", f_small)
    if foot:
        text, key = foot
        box = (m + px(10), m + total - px(36), m + w - px(10), m + total - px(8))
        fill_round(img, box, px(9), (255, 255, 255), 200 if hover == key else 110)
        put_text(img, (m + w // 2, (box[1] + box[3]) // 2), clip(text, font(11.5), box[2] - box[0] - px(16)), INK, "mm", font(11.5))
        hits.append(box + (key,))
    return img, hits


def clip(text, f, width):
    """폭을 넘으면 뒤를 잘라 …을 붙임"""
    if text_w(f, text) <= width:
        return text
    while text and text_w(f, text + "…") > width:
        text = text[:-1]
    return text + "…"


def render_tones(current, hover, hotkey_ok=True):
    """말투 고르는 화면. 고르면 바로 적용됨."""
    m, w = px(MARGIN), px(PANEL_W)
    head, row_h, foot = px(42), px(44), px(38)
    total = head + row_h * len(TONES) + foot
    img = Image.new("RGBA", (w + m * 2, total + m * 2), (0, 0, 0, 0))
    panel = (m, m, m + w, m + total)
    drop_shadow(img, panel, px(16))
    fill_round(img, panel, px(16), CHAT_BG)
    s = px(28)
    back = (m + px(8), m + (head - s) // 2, m + px(8) + s, m + (head - s) // 2 + s)
    if hover == "tone_close":
        fill_round(img, back, px(8), (40, 60, 80), 34)
    draw_icon(img, "back", (back[0] + back[2]) // 2, (back[1] + back[3]) // 2, INK if hover == "tone_close" else INK_SOFT)
    put_text(img, (back[2] + px(4), m + head // 2), "말투 고르기", INK, "lm", font(13.5, True))
    hits = [back + ("tone_close",), (back[2], m, m + w, m + head, "drag")]
    for i, (key, label, levels) in enumerate(TONES):
        y = m + head + row_h * i
        box = (m + px(8), y + px(2), m + w - px(8), y + row_h - px(2))
        if key == current:
            fill_round(img, box, px(11), LEVEL_STYLE[1][0])
        elif hover == "tone:" + key:
            fill_round(img, box, px(11), (255, 255, 255), 130)
        put_text(img, (box[0] + px(12), y + px(14)), label, INK, "lm", font(12.5, True))
        sample = clip(levels[0][0], font(11), box[2] - box[0] - px(24))
        put_text(img, (box[0] + px(12), y + px(30)), sample, INK if key == current else INK_SOFT, "lm", font(11))
        if key == current:
            draw_icon(img, "check", box[2] - px(20), (box[1] + box[3]) // 2, INK)
        hits.append(box + ("tone:" + key,))
    fy = m + total - foot // 2
    label = "내 대사 고치기"
    cw = int(text_w(font(11), label)) + px(20)
    chip = (m + w - px(10) - cw, fy - px(12), m + w - px(10), fy + px(12))
    fill_round(img, chip, px(8), (255, 255, 255), 255 if hover == "edit_lines" else 150)
    put_text(img, ((chip[0] + chip[2]) // 2, fy), label, INK, "mm", font(11))
    hits.append(chip + ("edit_lines",))
    hint = f"{HOTKEY_TEXT}: 숨기기·다시 보이기" if hotkey_ok else "다른 프로그램이 단축키를 쓰는 중"
    put_text(img, (m + px(20), fy), hint, INK_SOFT, "lm", font(10.5))
    return img, hits


def render_settings(tone_label, filter_note, auto_on, hover, hotkey_ok=True):
    """설정 첫 화면: 말투, 거르기, 자동 실행."""
    m, w = px(MARGIN), px(PANEL_W)
    head, row_h, foot = px(42), px(54), px(34)
    rows = (("open_tones", "말투", tone_label), ("open_filters", "거르기", filter_note),
            ("autostart", "윈도우 켤 때 같이 켜기", "재부팅해도 다시 켤 필요 없어요"))
    total = head + row_h * len(rows) + foot
    img = Image.new("RGBA", (w + m * 2, total + m * 2), (0, 0, 0, 0))
    panel = (m, m, m + w, m + total)
    drop_shadow(img, panel, px(16))
    fill_round(img, panel, px(16), CHAT_BG)
    put_text(img, (m + px(14), m + head // 2), "설정", INK, "lm", font(13.5, True))
    s = px(28)
    close = (m + w - px(8) - s, m + (head - s) // 2, m + w - px(8), m + (head - s) // 2 + s)
    if hover == "settings_close":
        fill_round(img, close, px(8), (40, 60, 80), 34)
    draw_icon(img, "quit", (close[0] + close[2]) // 2, (close[1] + close[3]) // 2, INK if hover == "settings_close" else INK_SOFT)
    hits = [close + ("settings_close",), (m, m, close[0], m + head, "drag")]
    for i, (key, label, note) in enumerate(rows):
        y = m + head + row_h * i
        box = (m + px(8), y + px(2), m + w - px(8), y + row_h - px(2))
        fill_round(img, box, px(11), (255, 255, 255), 215 if hover == key else 130)
        put_text(img, (box[0] + px(12), y + px(18)), label, INK, "lm", font(12.5, True))
        put_text(img, (box[0] + px(12), y + px(36)), clip(note, font(11), px(250)), INK_SOFT, "lm", font(11))
        cy = (box[1] + box[3]) // 2
        if key == "autostart":
            sw = (box[2] - px(46), cy - px(10), box[2] - px(12), cy + px(10))
            fill_round(img, sw, px(10), (254, 229, 0) if auto_on else (150, 165, 180))
            kx = sw[2] - px(10) if auto_on else sw[0] + px(10)
            fill_round(img, (kx - px(8), cy - px(8), kx + px(8), cy + px(8)), px(8), (255, 255, 255))
        else:
            draw_icon(img, "next", box[2] - px(18), cy, INK_SOFT)
        hits.append(box + (key,))
    hint = f"{HOTKEY_TEXT}: 숨기기·다시 보이기" if hotkey_ok else "다른 프로그램이 단축키를 쓰는 중"
    put_text(img, (m + px(20), m + total - foot // 2), hint, INK_SOFT, "lm", font(10.5))
    return img, hits


WELCOME_LINES = ("안 읽은 1:1 톡이 있으면 여기서 잔소리해요.",
                 "카톡 채팅 목록 창을 열어 두세요. 다른 창에 가려져도 되지만, 최소화하면 못 읽어요.",
                 "기본 말투에 욕이 나와요. 회사에서는 '회사용 (순한 맛)'을 고르세요.")


def render_welcome(hover):
    """처음 켰을 때 한 번만 나오는 안내."""
    m, w = px(MARGIN), px(PANEL_W)
    head, f = px(46), font(12.5)
    wrapped = [wrap(line, f, w - px(58)) for line in WELCOME_LINES]
    line_h, gap, foot = px(20), px(10), px(52)
    total = head + sum(len(l) * line_h + gap for l in wrapped) + foot
    img = Image.new("RGBA", (w + m * 2, total + m * 2), (0, 0, 0, 0))
    panel = (m, m, m + w, m + total)
    drop_shadow(img, panel, px(16))
    fill_round(img, panel, px(16), CHAT_BG)
    put_text(img, (m + px(16), m + head // 2 + px(2)), "답장독촉방이 켜졌어요", INK, "lm", font(14, True))
    y = m + head
    for no, lines in enumerate(wrapped, 1):
        fill_round(img, (m + px(16), y + px(1), m + px(34), y + px(19)), px(9), (255, 255, 255), 180)
        put_text(img, (m + px(25), y + px(10)), str(no), INK, "mm", font(10.5, True))
        for i, line in enumerate(lines):
            put_text(img, (m + px(42), y + px(10) + line_h * i), line, INK, "lm", f)
        y += len(lines) * line_h + gap
    hits = [(m, m, m + w, m + head, "drag")]
    x = m + w - px(14)
    by = m + total - px(44)
    for key, label, color in (("welcome_ok", "시작하기", (254, 229, 0)), ("welcome_tone", "말투 고르기", (255, 255, 255))):
        cw = int(text_w(font(12.5, True), label)) + px(28)
        box = (x - cw, by, x, by + px(32))
        fill_round(img, box, px(10), color, 255 if hover == key else 215)
        put_text(img, ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), label, INK, "mm", font(12.5, True))
        hits.insert(0, box + (key,))
        x -= cw + px(8)
    return img, hits


def add_preview(img, hits, name, count, crop):
    """줄에 마우스를 올렸을 때 카톡방 왼쪽에 미리보기 카드를 붙임. 줄이 움직이지 않게 위아래 배치는 그대로 둠."""
    m, gap = px(MARGIN), px(8)
    pic = Image.fromarray(crop.astype(np.uint8)).convert("RGBA")
    try:
        unseen = int(count) - 1
    except ValueError:
        unseen = 1
    note = f"읽음 처리 안 돼요 · 앞의 {unseen}개는 안 보여요" if unseen > 0 else "읽음 처리 안 돼요"
    f = font(10.5)
    cw = max(pic.size[0], int(text_w(f, note))) + px(24)
    ch = pic.size[1] + px(44)
    dx = cw + gap
    H = max(img.size[1], ch + m * 2)
    canvas = Image.new("RGBA", (img.size[0] + dx, H), (0, 0, 0, 0))
    dy = H - img.size[1]
    canvas.alpha_composite(img, (dx, dy))
    row_top = next(h[1] for h in hits if h[4] == "row:" + name) + dy
    y = min(max(row_top, m), H - m - ch)
    box = (m, y, m + cw, y + ch)
    drop_shadow(canvas, box, px(12))
    fill_round(canvas, box, px(12), tuple(int(v) for v in np.median(crop.reshape(-1, 3), axis=0)))  # 바탕은 가장 흔한 색
    put_text(canvas, (m + px(12), y + px(17)), note, INK_SOFT, "lm", f)
    canvas.alpha_composite(pic, (m + px(12), y + px(32)))
    return canvas, [(a + dx, b + dy, c + dx, d + dy, n) for a, b, c, d, n in hits]


def render_handle(count, label, warn, hover, quiet=False):
    """접힌 모양: 동그란 손잡이. 마우스를 올리거나 알릴 게 있으면 왼쪽으로 글자가 펼쳐짐. quiet면 달 표시."""
    m, s = px(MARGIN), px(HANDLE_SIZE)
    f = font(12)
    open_ = bool(warn or hover)
    tw = int(text_w(f, label)) + px(26) if open_ and label else 0
    qw = px(60) if hover else 0
    img = Image.new("RGBA", (tw + qw + s + m * 2, s + m * 2), (0, 0, 0, 0))
    W = img.size[0] - m
    body = (m, m, W, m + s)
    drop_shadow(img, body, s // 2)
    if tw + qw:
        fill_round(img, body, s // 2, (255, 255, 255))
    circle = (W - s, m, W, m + s)
    fill_round(img, circle, s // 2, (254, 229, 0))
    cx, cy = W - s // 2, m + s // 2
    # 말풍선 아이콘
    big = Image.new("L", (s * 4, s * 4), 0)
    bd = ImageDraw.Draw(big)
    a, b = px(11) * 4, px(9) * 4
    c = s * 2
    bd.ellipse((c - a, c - b - px(1) * 4, c + a, c + b - px(1) * 4), fill=255)
    bd.polygon([(c - px(5) * 4, c + px(5) * 4), (c - px(7) * 4, c + px(12) * 4), (c + px(2) * 4, c + px(7) * 4)], fill=255)
    layer = Image.new("RGBA", (s, s), (60, 40, 30, 255))
    layer.putalpha(big.resize((s, s), Image.LANCZOS))
    img.alpha_composite(layer, (W - s, m))
    if warn:
        fill_round(img, (W - px(15), m + px(1), W - px(1), m + px(15)), px(7), (240, 150, 30))
        put_text(img, (W - px(8), m + px(8)), "!", (255, 255, 255), "mm", font(10, True))
    elif count:
        t = str(count)
        cw = max(px(18), int(text_w(font(10, True), t)) + px(10))
        fill_round(img, (W - cw, m, W, m + px(18)), px(9), PILL_RED)
        put_text(img, (W - cw // 2, m + px(9)), t, (255, 255, 255), "mm", font(10, True))
    if quiet:
        fill_round(img, (W - px(18), m, W, m + px(18)), px(9), (56, 72, 88))
        draw_icon(img, "all", W - px(9), m + px(9), (255, 255, 255))
    hits = [(W - s, m, W, m + s, "handle")]
    if tw:
        tip = {"quit": "위젯 끄기", "settings": "설정"}.get(hover, label)
        put_text(img, (m + qw + px(14), cy), clip(tip, f, tw - px(26)), INK, "lm", f)
        hits.append((m + qw, m, W - s, m + s, "handle"))
    if qw:
        for i, key in enumerate(("quit", "settings")):
            box = (m + px(7 + 28 * i), cy - px(13), m + px(33 + 28 * i), cy + px(13))
            if hover == key:
                fill_round(img, box, px(8), (40, 60, 80), 34)
            draw_icon(img, key, (box[0] + box[2]) // 2, cy, INK if hover == key else INK_SOFT)
            hits.append(box + (key,))
        hits.append((0, 0, img.size[0], img.size[1], "drag"))   # 버튼 사이 틈을 지나도 접히지 않게
    return img, hits


SHOW_EVENT = "Local\\KakaoNaggerShow"


def already_running():
    """이미 켜져 있으면 그쪽 위젯이 나타나게 신호를 보내고 True. 안 보여서 또 실행해도 위젯이 둘이 되지 않게 함."""
    global _instance_mutex
    _instance_mutex = kernel32.CreateMutexW(None, False, "Local\\KakaoNagger")
    if ctypes.get_last_error() != 183:  # ERROR_ALREADY_EXISTS
        return False
    kernel32.SetEvent(kernel32.CreateEventW(None, False, False, SHOW_EVENT))
    return True


class _Blend(ctypes.Structure):
    _fields_ = [("op", ctypes.c_ubyte), ("flags", ctypes.c_ubyte), ("alpha", ctypes.c_ubyte), ("fmt", ctypes.c_ubyte)]


def watch_hotkey(pressed, failed):
    """전역 단축키를 기다림. 단축키 신호는 등록한 스레드로 오므로 Tk와 따로 돌림."""
    if not user32.RegisterHotKey(None, 1, 0x4003, 0x4B):  # MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, K
        failed.set()
        return
    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == 0x312:  # WM_HOTKEY
            pressed.set()


class FilterWindow:
    """거르기 규칙 창. 글자를 쳐야 해서 위젯 그림이 아니라 보통 창으로 띄움. 바꾸면 바로 적용됨."""
    GROUPS = (("숨기기", "이 문구가 들어가면 위젯에 안 나와요.", (("hide_name", "이름"), ("hide_text", "메시지"))),
              ("이것만 보기", "하나라도 넣으면 여기 맞는 방만 나와요. 비워 두면 전부 나와요.", (("only_name", "이름"), ("only_text", "메시지"))))
    SOFT, LINE, CHIP, ACCENT = "#5A6B7B", "#D5DCE3", "#EEF2F6", "#FEE500"

    def __init__(self, widget):
        self.widget = widget
        self.win = win = tk.Toplevel(widget.root)
        win.title("거르기")
        win.configure(bg="white", padx=px(20), pady=px(14))
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", self.close)
        icon = sys.executable if getattr(sys, "frozen", False) else os.path.join(HERE, "assets", "icon.ico")
        try:
            win.iconbitmap(icon)
        except tk.TclError:
            pass
        self.f = ("맑은 고딕", -px(13))
        self.f_small = ("맑은 고딕", -px(12))
        self.f_bold = ("맑은 고딕", -px(15), "bold")
        self.entries, self.chips = {}, {}
        for no, (title, desc, keys) in enumerate(self.GROUPS):
            tk.Label(win, text=title, font=self.f_bold, bg="white", anchor="w").pack(fill="x", pady=(px(14) if no else 0, 0))
            tk.Label(win, text=desc, font=self.f_small, fg=self.SOFT, bg="white", anchor="w").pack(fill="x", pady=(0, px(6)))
            for key, label in keys:
                self.add_row(key, label)
        tk.Frame(win, bg=self.LINE, height=1).pack(fill="x", pady=(px(12), px(10)))
        tk.Label(win, text="지금 안 읽은 방", font=self.f_bold, bg="white", anchor="w").pack(fill="x")
        self.rooms = tk.Frame(win, bg="white")
        self.rooms.pack(fill="x", pady=(px(4), px(8)))
        tk.Label(win, text="메시지는 카톡 목록에 보이는 최근 메시지만 확인해요. 사진·이모티콘은 못 읽을 수 있어요.",
                 font=self.f_small, fg=self.SOFT, bg="white", anchor="w").pack(fill="x")
        self.room_sig = None
        self.redraw()
        self.show_rooms()
        win.update_idletasks()
        win.geometry(f"+{(win.winfo_screenwidth() - win.winfo_reqwidth()) // 2}+{(win.winfo_screenheight() - win.winfo_reqheight()) // 3}")
        win.update()
        user32.SetForegroundWindow(user32.GetAncestor(win.winfo_id(), 2))   # 위젯은 포커스를 안 받으니 이 창을 바로 칠 수 있게 올림
        win.focus_force()
        self.entries["hide_name"].focus_set()

    def add_row(self, key, label):
        row = tk.Frame(self.win, bg="white")
        row.pack(fill="x", pady=px(2))
        tk.Label(row, text=label, font=self.f, bg="white", width=6, anchor="w").pack(side="left")
        add = tk.Label(row, text="추가", font=self.f, bg=self.ACCENT, padx=px(12), pady=px(3), cursor="hand2")
        add.pack(side="right", padx=(px(6), 0))
        add.bind("<Button-1>", lambda e: self.add_word(key))
        entry = tk.Entry(row, font=self.f, relief="solid", bd=1, highlightthickness=0, width=34)
        entry.pack(side="left", fill="x", expand=True, ipady=px(3))
        entry.bind("<Return>", lambda e: self.add_word(key))
        chips = tk.Frame(self.win, bg="white")
        chips.pack(fill="x", padx=(px(52), 0))
        self.entries[key], self.chips[key] = entry, chips

    def add_word(self, key):
        entry = self.entries[key]
        # 한글 조합 중에 '추가'를 누르면 마지막 글자가 아직 칸에 안 들어와 있음
        hwnd = user32.GetFocus()
        himc = imm32.ImmGetContext(hwnd)
        if himc:
            imm32.ImmNotifyIME(himc, 0x15, 1, 0)   # NI_COMPOSITIONSTR, CPS_COMPLETE
            imm32.ImmReleaseContext(hwnd, himc)
        self.win.update()
        word = " ".join(entry.get().split())[:FILTER_MAX]
        entry.delete(0, "end")
        words = self.widget.filters[key]
        if word and word not in words:
            words.append(word)
            self.widget.apply_filters()
        entry.focus_set()

    def remove_word(self, key, word):
        self.widget.filters[key].remove(word)
        self.widget.apply_filters()

    def redraw(self):
        """문구 칩을 다시 그림. 칸 폭을 넘으면 다음 줄로."""
        limit = self.entries["hide_name"].winfo_reqwidth() + px(50)
        measure = tk.font.Font(font=self.f).measure
        for key, frame in self.chips.items():
            for child in frame.winfo_children():
                child.destroy()
            row, used = None, 0
            for word in self.widget.filters[key]:
                width = measure(word) + px(44)
                if row is None or used + width > limit:
                    row, used = tk.Frame(frame, bg="white"), 0
                    row.pack(anchor="w", pady=(px(3), 0))
                used += width
                chip = tk.Frame(row, bg=self.CHIP)
                chip.pack(side="left", padx=(0, px(4)))
                tk.Label(chip, text=word, font=self.f_small, bg=self.CHIP, padx=px(6), pady=px(2)).pack(side="left")
                x = tk.Label(chip, text="✕", font=self.f_small, fg=self.SOFT, bg=self.CHIP, padx=px(5), cursor="hand2")
                x.pack(side="left")
                x.bind("<Button-1>", lambda e, k=key, w=word: self.remove_word(k, w))
        self.room_sig = None

    def show_rooms(self):
        """지금 안 읽은 방이 규칙에 따라 어떻게 되는지 바로 보여 줌."""
        rooms = [(n, self.widget.filtered.get(n)) for n in sorted(self.widget.raw)]
        if rooms == self.room_sig:
            return
        self.room_sig = rooms
        for child in self.rooms.winfo_children():
            child.destroy()
        if not rooms:
            tk.Label(self.rooms, text="지금 안 읽은 1:1 방이 없어요.", font=self.f_small, fg=self.SOFT, bg="white", anchor="w").pack(fill="x")
        for name, why in rooms[:6]:
            row = tk.Frame(self.rooms, bg="white")
            row.pack(fill="x")
            tk.Label(row, text=name, font=self.f, fg=self.SOFT if why else "black", bg="white", anchor="w").pack(side="left")
            tk.Label(row, text=f"숨김 · {why}" if why else "보임", font=self.f_small, fg=self.SOFT if why else "#1E7B34",
                     bg="white", anchor="e").pack(side="right")
        if len(rooms) > 6:
            tk.Label(self.rooms, text=f"외 {len(rooms) - 6}개", font=self.f_small, fg=self.SOFT, bg="white", anchor="w").pack(fill="x")

    def close(self):
        self.win.destroy()
        self.widget.filter_win = None


class NagWidget:
    def __init__(self, root, source):
        self.root, self.source = root, source
        self.first_seen, self.snoozed, self.lines, self.counts, self.last_shake = {}, {}, {}, {}, {}
        self.bags = {}           # (말투, 단계) → 아직 안 나온 대사
        self.praised, self.photos = {}, {}   # 칭찬 중인 사람, 칭찬 줄에 쓸 프사
        self.custom_mtime = None
        self.hidden = False      # 단축키로 완전히 숨긴 상태
        self.hotkey_pressed, self.hotkey_failed = threading.Event(), threading.Event()
        threading.Thread(target=watch_hotkey, args=(self.hotkey_pressed, self.hotkey_failed), daemon=True).start()
        self.show_event = kernel32.CreateEventW(None, False, False, SHOW_EVENT)
        self.quiet_until = 0     # '전부 조용히' 끝나는 시각
        self.collapsed = False
        self.tone = load_tone()
        settings = load_settings()
        self.screen = None if "welcomed" in settings or "tone" in settings else "welcome"   # None, welcome, settings, tones
        self.filters = load_filters()
        self.raw, self.filtered = {}, {}     # 거르기 전 안 읽은 방, 숨긴 방 {이름: 이유}
        self.filter_win = None
        self.undo = None         # (이름, 되돌리기 끝나는 시각)
        self.hover = None
        self.press = None
        self.sig = None
        self.hits, self.img = [], None
        self.pos = (0, 0)
        self.items_shown = set()
        self.anim_id = None

        now = time.time()
        for n, m in getattr(source, "preseed", {}).items():
            self.first_seen[n] = now - m * 60

        area = wt.RECT()
        user32.SystemParametersInfoW(0x30, 0, ctypes.byref(area), 0)  # SPI_GETWORKAREA
        self.anchor = (area.right - px(4), area.bottom - px(4))
        saved = settings.get("anchor")
        if (isinstance(saved, list) and len(saved) == 2 and all(isinstance(v, int) for v in saved)
                and user32.MonitorFromPoint(wt.POINT(saved[0] - px(30), saved[1] - px(30)), 0)):  # 모니터를 뺐으면 기본 자리로
            self.anchor = tuple(saved)

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.update_idletasks()
        self.hwnd = user32.GetAncestor(root.winfo_id(), 2)
        # 레이어드 창 + 작업표시줄에 안 뜸 + 눌러도 다른 창의 포커스를 안 뺏음
        style = user32.GetWindowLongPtrW(self.hwnd, -20)
        user32.SetWindowLongPtrW(self.hwnd, -20, style | 0x00080000 | 0x00000080 | 0x08000000)

        root.bind("<Motion>", self.on_move)
        root.bind("<Leave>", lambda e: self.set_hover(None))
        root.bind("<ButtonPress-1>", self.on_press)
        root.bind("<B1-Motion>", self.on_drag)
        root.bind("<ButtonRelease-1>", self.on_release)
        self.tick()
        self.poll_hotkey()

    # ── 거르기 ──
    def apply_filters(self):
        save_settings(filters=self.filters)
        if self.filter_win:
            self.filter_win.redraw()
        self.refresh()

    def hide_person(self, name, now):
        if name not in self.filters["hide_name"]:
            self.filters["hide_name"].append(name)
        self.undo = (name, now + UNDO_SEC)
        self.apply_filters()

    def undo_hide(self):
        if self.undo and self.undo[0] in self.filters["hide_name"]:
            self.filters["hide_name"].remove(self.undo[0])
        self.undo = None
        self.apply_filters()

    def open_filters(self):
        if self.filter_win:
            self.filter_win.win.lift()
            self.filter_win.win.focus_force()
        else:
            self.filter_win = FilterWindow(self)

    # ── 화면에 올리기 ──
    def push(self, img, x, y, alpha=255):
        w, h = img.size
        a = np.asarray(img).astype(np.uint16)
        pre = np.empty((h, w, 4), np.uint8)
        for i, c in enumerate((2, 1, 0)):  # BGRA, 알파를 곱해 둔 값이어야 함
            pre[:, :, i] = a[:, :, c] * a[:, :, 3] // 255
        pre[:, :, 3] = a[:, :, 3]
        sdc = user32.GetWindowDC(None)
        dc = gdi32.CreateCompatibleDC(sdc)
        bits = ctypes.c_void_p()
        info = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        bmp = gdi32.CreateDIBSection(sdc, info, 0, ctypes.byref(bits), None, 0)
        old = gdi32.SelectObject(dc, bmp)
        ctypes.memmove(bits, pre.tobytes(), w * h * 4)
        if (w, h, x, y) != getattr(self, "geom", None):
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self.geom = (w, h, x, y)
        user32.UpdateLayeredWindow(self.hwnd, sdc, ctypes.byref(wt.POINT(x, y)), ctypes.byref(wt.SIZE(w, h)), dc,
                                   ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(_Blend(0, 0, alpha, 1)), 2)
        gdi32.SelectObject(dc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(dc)
        user32.ReleaseDC(None, sdc)

    def screen_xy(self, dx=0):
        w, h = self.img.size
        # 화면 위쪽으로 옮겨 둬도 펼친 위젯의 버튼이 화면 밖으로 안 나가게
        return (max(self.anchor[0] - w, user32.GetSystemMetrics(76)) + dx,
                max(self.anchor[1] - h, user32.GetSystemMetrics(77)))

    def paint(self):
        self.img, self.hits = self.compose()
        self.pos = self.screen_xy()
        self.push(self.img, *self.pos)

    def slide_in(self, step=0):
        """새 사람이 왔을 때 오른쪽에서 스르륵"""
        n = 9
        t = (step + 1) / n
        ease = 1 - (1 - t) ** 3
        x, y = self.screen_xy(int((1 - ease) * px(26)))
        self.pos = (x, y)
        self.push(self.img, x, y, int(255 * ease))
        if step + 1 < n:
            self.anim_id = self.root.after(16, self.slide_in, step + 1)

    def shake(self, step=0):
        n = 12
        x, y = self.screen_xy()
        dx = 0 if step >= n else int((px(7) if step % 2 else -px(7)) * (1 - step / n))
        self.push(self.img, x + dx, y)
        if step < n:
            self.anim_id = self.root.after(35, self.shake, step + 1)

    # ── 무엇을 보여줄지 ──
    def visible_items(self, now):
        if now < self.quiet_until:
            return []
        return [n for n in self.current if self.snoozed.get(n, 0) < now]

    def compose(self):
        if self.screen == "welcome":
            return render_welcome(self.hover)
        if self.screen == "tones":
            return render_tones(self.tone, self.hover, not self.hotkey_failed.is_set())
        if self.screen == "settings":
            rules = sum(len(self.filters[k]) for k in FILTER_KEYS)
            note = f"규칙 {rules}개 · 지금 숨긴 방 {len(self.filtered)}개" if rules else "이름이나 메시지로 방을 숨기거나 골라 봐요"
            label = next(label for key, label, _ in TONES if key == self.tone)
            return render_settings(label, note, autostart_on(), self.hover, not self.hotkey_failed.is_set())
        now = time.time()
        names = sorted(self.visible_items(now), key=lambda n: self.first_seen.get(n, now))
        waited = {n: int((now - self.first_seen[n]) / 60) for n in names}
        if self.status:
            return render_handle(0, self.status, True, self.hover)
        if now < self.quiet_until:
            return render_handle(0, f"{int((self.quiet_until - now) / 60) + 1}분 더 조용히 · 눌러서 깨우기", False, self.hover, True)
        undoing = self.undo and self.undo[1] > now
        if self.collapsed or not (names or self.praised or undoing):
            label = f"답장 밀린 사람 {len(names)}명 · 눌러서 펼치기" if names else "밀린 답장 없음"
            if self.filtered and not names:
                label += f" · 숨긴 방 {len(self.filtered)}개"
            return render_handle(len(names), label, False, self.hover)
        foot = None
        if undoing:
            foot = (f"{self.undo[0]} 숨겼어요 · 되돌리기", "undo")
        elif self.filtered:
            foot = (f"거르기로 숨긴 방 {len(self.filtered)}개 · 규칙 보기", "open_filters")
        mild = self.tone in MILD_TONES
        items = [{"name": n, "count": "", "mins": 0, "level": 0, "style": PRAISE_STYLE, "line": v[0], "note": v[1], "photo": v[2]}
                 for n, v in list(self.praised.items())[-MAX_PRAISE:]]
        for n in names[:MAX_BUBBLES]:
            mins = waited[n]
            level = sum(1 for threshold in LEVEL_MIN[1:] if mins >= threshold)
            it = {"name": n, "count": self.current.get(n, ""), "mins": mins, "level": level,
                  "line": self.nag_line(n, level, now), "photo": getattr(self.source, "avatars", {}).get(n)}
            if mild:
                it["style"] = 0
            items.append(it)
        img, hits = render_panel(items, max(0, len(names) - MAX_BUBBLES), self.hover, "확인할 메시지" if mild else "답장 독촉방", foot)
        target = self.hover.split(":", 1)[1] if self.hover and self.hover.startswith(("row:", "snooze:", "hide:")) else None
        crop = getattr(self.source, "previews", {}).get(target)
        if crop is not None and target in names[:MAX_BUBBLES]:
            img, hits = add_preview(img, hits, target, self.current.get(target, ""), crop)
        return img, hits

    def nag_line(self, name, level, now):
        """대사는 단계가 오르거나 시간이 좀 지나야 바뀜 (자꾸 바뀌면 산만함)"""
        saved = self.lines.get(name)
        if not saved or saved[0] != level or now - saved[2] > NAG_SEC:
            saved = (level, self.next_line(level), now)
            self.lines[name] = saved
        return saved[1]

    def next_line(self, level):
        """대사를 섞어 두고 하나씩 꺼냄. 다 나오기 전엔 같은 대사가 또 안 나옴."""
        bag = self.bags.get((self.tone, level))
        if not bag:
            lines = PRAISE_LINES[self.tone] if level == PRAISE_STYLE else TONE_LINES[self.tone][level]
            bag = self.bags[(self.tone, level)] = random.sample(lines, len(lines))
        return bag.pop()

    def praise(self, name, now):
        """안읽음이 사라진 사람에게 잠깐 칭찬. 접어두거나 조용히 중이면 안 띄움."""
        if self.status or self.collapsed or now < self.quiet_until:
            return
        mins = int((now - self.first_seen[name]) / 60)
        note = waited_text(mins).replace("째", " 만에") if mins else "바로!"
        self.praised[name] = (self.next_line(PRAISE_STYLE), note, self.photos.get(name), now + PRAISE_SEC)

    def refresh_custom(self):
        """내대사.txt를 저장하면 재시작 없이 반영"""
        try:
            mtime = os.path.getmtime(CUSTOM_PATH)
        except OSError:
            mtime = None
        if mtime != self.custom_mtime:
            self.custom_mtime = mtime
            load_custom()
            self.bags.clear()
            if self.tone == "custom":
                self.lines.clear()
            self.sig = None

    def poll_hotkey(self):
        if self.hotkey_pressed.is_set():
            self.hotkey_pressed.clear()
            self.toggle_hidden()
        if self.show_event and kernel32.WaitForSingleObject(self.show_event, 0) == 0:   # 또 실행해서 신호가 옴
            if self.hidden:
                self.toggle_hidden()
            self.shake()
        self.root.after(50, self.poll_hotkey)

    def toggle_hidden(self):
        self.hidden = not self.hidden
        if self.hidden:
            self.hover = self.press = None
            user32.ShowWindow(self.hwnd, 0)  # SW_HIDE
        else:
            self.sig = None
            self.paint()
            user32.ShowWindow(self.hwnd, 8)  # SW_SHOWNA: 포커스를 안 뺏음

    def tick(self):
        self.refresh()
        self.root.after(1000, self.tick)

    def refresh(self):
        self.raw, self.status = self.source.get()
        self.source.need_text = bool(self.filters["hide_text"] or self.filters["only_text"])
        texts = getattr(self.source, "texts", {})
        was_filtered = self.filtered
        self.filtered = {}
        for n in self.raw:
            why = filter_reason(self.filters, n, texts.get(n))
            if why:
                self.filtered[n] = why
        self.current = {n: c for n, c in self.raw.items() if n not in self.filtered}
        if self.filter_win:
            self.filter_win.show_rooms()
        now = time.time()
        self.refresh_custom()
        photos = getattr(self.source, "avatars", {})
        for n in self.raw:        # 숨긴 방도 기다린 시간은 재 둠. 규칙을 지우면 이어서 보임
            self.first_seen.setdefault(n, now)
            if n in photos:
                self.photos[n] = photos[n]
            self.praised.pop(n, None)
        for n in list(self.first_seen):
            if n not in self.raw:
                if n not in was_filtered:   # 숨겨 둔 방을 읽은 건 칭찬할 일이 아님
                    self.praise(n, now)
                for d in (self.first_seen, self.snoozed, self.lines, self.counts, self.last_shake, self.photos):
                    d.pop(n, None)
        self.praised = {n: v for n, v in self.praised.items() if v[3] > now}
        undoing = bool(self.undo and self.undo[1] > now)
        if self.undo and not undoing:
            self.undo = None
        visible = set(self.visible_items(now))
        arrived = visible - self.items_shown
        if arrived:
            self.collapsed = False   # 새 사람이 오면 접어둔 걸 펼침
        self.items_shown = visible
        if self.hover and not self.pointer_inside():
            self.hover = None
        if arrived and self.screen != "welcome":
            self.screen = None       # 새 사람이 오면 독촉이 먼저
        sig = (tuple(sorted(self.current.items())), self.status, tuple(sorted(visible)), self.collapsed, self.hover,
               self.screen, self.tone, tuple(sorted(self.praised)), undoing, tuple(sorted(self.filtered)),
               self.quiet_until > now and int((self.quiet_until - now) / 60),
               tuple(int((now - self.first_seen[n]) / 60) for n in sorted(visible)),
               tuple(v[1] for _, v in sorted(self.lines.items())) if self.lines else ())
        if sig != self.sig and not self.hidden:
            self.sig = sig
            self.paint()
            if arrived:
                self.slide_in()
        angry = [n for n in visible if now - self.first_seen[n] >= LEVEL_MIN[-1] * 60]
        due = [n for n in angry if now - self.last_shake.get(n, 0) >= SHAKE_SEC]
        if due and not (self.collapsed or self.screen or self.hidden or self.tone in MILD_TONES):
            for n in angry:
                self.last_shake[n] = now
            self.shake()

    # ── 마우스 ──
    def pointer_inside(self):
        x, y = self.root.winfo_pointerxy()
        return self.img is not None and 0 <= x - self.pos[0] < self.img.size[0] and 0 <= y - self.pos[1] < self.img.size[1]

    def hit_at(self, x, y):
        for x0, y0, x1, y1, name in self.hits:
            if x0 <= x < x1 and y0 <= y < y1:
                return name
        return None

    def set_hover(self, name):
        if name != self.hover:
            self.hover = name
            self.root.configure(cursor="hand2" if name and name != "drag" else "")
            self.paint()

    def on_move(self, e):
        if not self.press:
            self.set_hover(self.hit_at(e.x_root - self.pos[0], e.y_root - self.pos[1]))

    def on_press(self, e):
        self.press = (e.x_root, e.y_root, self.anchor, self.hit_at(e.x_root - self.pos[0], e.y_root - self.pos[1]), False)

    def on_drag(self, e):
        if not self.press or self.press[3] not in ("drag", "handle"):
            return
        sx, sy, anchor, hit, moved = self.press
        dx, dy = e.x_root - sx, e.y_root - sy
        if moved or abs(dx) + abs(dy) > 3:
            self.press = (sx, sy, anchor, hit, True)
            self.anchor = (anchor[0] + dx, anchor[1] + dy)
            self.pos = self.screen_xy()
            self.push(self.img, *self.pos)

    def on_release(self, e):
        press, self.press = self.press, None
        if not press:
            return
        if press[4]:
            save_settings(anchor=list(self.anchor))   # 옮긴 자리를 다음에 켤 때도 씀
            return
        hit = press[3]
        now = time.time()
        if hit == "quit":
            self.root.destroy()
            return
        if hit == "settings":
            self.screen = "settings"
        elif hit == "settings_close":
            self.screen = None
        elif hit == "open_tones":
            self.screen = "tones"
        elif hit == "tone_close":
            self.screen = "settings"
        elif hit == "welcome_ok":
            self.screen = None
            save_settings(welcomed=True)
        elif hit == "welcome_tone":
            self.screen = "tones"
            save_settings(welcomed=True)
        elif hit == "open_filters":
            self.open_filters()
            return
        elif hit == "autostart":
            set_autostart(not autostart_on())
        elif hit and hit.startswith("tone:"):
            self.tone = hit[5:]
            self.lines.clear()   # 대사를 새 말투로 다시 고름
            save_tone(self.tone)
        elif hit == "edit_lines":
            open_custom()
        elif hit == "all":
            self.quiet_until = now + 30 * 60
        elif hit == "collapse":
            self.collapsed = True
        elif hit == "handle":
            if self.status == STATUS_SCALE:
                os.startfile("ms-settings:display")
            elif self.status:
                self.source.open_kakao()
            self.collapsed = False
            self.quiet_until = 0
        elif hit == "undo":
            self.undo_hide()
        elif hit and hit.startswith("row:"):
            self.source.open_room(hit[4:])
            return
        elif hit and hit.startswith("snooze:"):
            self.snoozed[hit[7:]] = now + SNOOZE_MIN * 60
        elif hit and hit.startswith("hide:"):
            self.hide_person(hit[5:], now)
        else:
            return
        self.hover = None
        self.items_shown = set(self.visible_items(now))
        self.sig = None
        self.refresh()   # 다음 주기를 기다리지 않고 바로 화면에 보임


# ───────────────────────── 진단 ─────────────────────────

def mask(s):
    """구조(숫자·시간·공백)만 남기고 글자는 ●로 가림"""
    return re.sub(r"[^\s\d:+.,/()\[\]\-]", "●", s or "")


def diagnose():
    out_path = os.path.join(HERE, "진단결과.txt")
    lines = []
    p = lines.append
    p(f"python {sys.version.split()[0]}")
    pids = kakao_pids()
    p(f"KakaoTalk.exe PID: {pids}")
    user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))

    found = find_chat_list(pids) if pids else None
    p(f"채팅 목록: {'있음' if found else '없음'}")
    if found:
        main, lst = found
        p(f"최소화={bool(user32.IsIconic(main))} 메인 보임={bool(user32.IsWindowVisible(main))} "
          f"목록 보임={bool(user32.IsWindowVisible(lst))} dpi={user32.GetDpiForWindow(lst)}")
        img = grab(lst)
        if img is None:
            p("캡처 실패")
        else:
            p(f"캡처 크기 {img.shape[1]}x{img.shape[0]}")
            for top, bottom in find_rows(img):
                box = find_badge(img, top, bottom)
                line = name_line(img, top, bottom)
                a = img[top:bottom, BADGE_X:img.shape[1] - SCROLLBAR_W]
                y, x = np.unravel_index((a.max(axis=2) - a.min(axis=2)).argmax(), a.shape[:2])
                detail = f"가장 진한 색 RGB={tuple(int(v) for v in a[y, x])}"  # 배지 색이 기준에서 벗어났는지 확인용
                if box and line:
                    detail += (f" 배지={box} 숫자={read_count(img, box)!r} 이름={mask(read_name(img, line))!r}"
                               f" 인원수={has_member_count(img, line)} 격자={has_grid_avatar(img, top)}")
                elif line:
                    detail += f" 배지없음 인원수={has_member_count(img, line)} 격자={has_grid_avatar(img, top)}"
                p(f"  줄 y={top}-{bottom} {detail}")

    # 윈도우 알림센터에 카톡 알림이 쌓이는지
    p("")
    p("=== 윈도우 알림 기록 ===")
    src = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Notifications\wpndatabase.db")
    tmp = tempfile.mkdtemp()
    try:
        for suf in ("", "-wal", "-shm"):
            if os.path.exists(src + suf):
                shutil.copy2(src + suf, os.path.join(tmp, "w.db" + suf))
        con = sqlite3.connect(os.path.join(tmp, "w.db"))
        rows = con.execute(
            "SELECT h.PrimaryId, COUNT(*) FROM Notification n "
            "JOIN NotificationHandler h ON n.HandlerId = h.RecordId GROUP BY h.PrimaryId").fetchall()
        con.close()
        for app, c in rows:
            if "kakao" in str(app).lower():
                p(f"카톡 알림 {c}개: {app}")
        if not any("kakao" in str(a).lower() for a, _ in rows):
            p(f"카톡 알림 없음 (다른 앱 {len(rows)}개)")
    except Exception as e:
        p(f"알림 기록 읽기 실패: {e!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    if sys.stdout:  # 콘솔 없는 exe에서는 없음
        print("\n".join(lines[:40]))
        print(f"\n저장됨: {out_path}")


if __name__ == "__main__":
    if "--diag" in sys.argv:
        diagnose()
    else:
        demo = "--demo" in sys.argv
        if not demo and already_running():
            sys.exit()
        if not demo and autostart_on():
            set_autostart(True)   # exe를 다른 폴더로 옮겼어도 자동 실행이 끊기지 않게
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        SCALE = user32.GetDpiForSystem() / 96
        root = tk.Tk()
        NagWidget(root, DemoSource() if demo else KakaoSource())
        root.mainloop()
