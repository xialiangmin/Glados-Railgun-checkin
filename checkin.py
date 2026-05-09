import os
import json
import requests
from datetime import datetime

# ======================
# GLaDOS CONFIG
# ======================

COOKIE = os.getenv("GLADOS_COOKIE")

# Telegram
TG_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ======================
# API
# ======================

CHECKIN_URL = "https://glados.cloud/api/user/checkin"
STATUS_URL = "https://glados.cloud/api/user/status"

HEADERS = {
    "cookie": COOKIE,
    "referer": "https://glados.cloud/console/checkin",
    "origin": "https://glados.cloud",
    "content-type": "application/json;charset=UTF-8",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
}

CHECKIN_DATA = {
    "token": "glados.one"
}


# ======================
# TELEGRAM PUSH
# ======================

def telegram_push(message):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("Telegram 未配置")
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, data=payload, timeout=15)

        if r.status_code == 200:
            print("Telegram 推送成功")
        else:
            print("Telegram 推送失败:", r.text)

    except Exception as e:
        print("Telegram 推送异常:", str(e))


# ======================
# CHECKIN
# ======================

def checkin():
    try:
        print("开始签到...")

        res = requests.post(
            CHECKIN_URL,
            headers=HEADERS,
            json=CHECKIN_DATA,
            timeout=20
        )

        print("签到返回:", res.text)

        result = res.json()

        if result.get("code") == 0:
            checkin_msg = result.get("message", "签到成功")
            success = True
        else:
            checkin_msg = result.get("message", "签到失败")
            success = False

    except Exception as e:
        checkin_msg = f"签到异常: {str(e)}"
        success = False

    return success, checkin_msg


# ======================
# STATUS
# ======================

def get_status():
    try:
        res = requests.get(
            STATUS_URL,
            headers=HEADERS,
            timeout=20
        )

        data = res.json()

        left_days = data.get("data", {}).get("leftDays", "未知")
        vip = data.get("data", {}).get("vip", 0)
        traffic = data.get("data", {}).get("traffic", 0)

        # 转 GB
        traffic_gb = round(float(traffic) / 1024 / 1024 / 1024, 2)

        return left_days, traffic_gb, vip

    except Exception as e:
        print("获取状态失败:", str(e))
        return "未知", "未知", "未知"


# ======================
# MAIN
# ======================

if __name__ == "__main__":

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    success, checkin_msg = checkin()

    left_days, traffic_gb, vip = get_status()

    if success:
        title = "✅ GLaDOS 签到成功"
    else:
        title = "❌ GLaDOS 签到失败"

    message = f"""
{title}

🕒 时间:
{now}

📌 结果:
{checkin_msg}

📅 剩余天数:
{left_days}

📊 剩余流量:
{traffic_gb} GB

⭐ VIP:
{vip}
"""

    print(message)

    telegram_push(message)
