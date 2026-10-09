import os
import logging
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ==================== 日志配置 ====================

logger = logging.getLogger("glados_checkin")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(handler)


# ==================== 常量定义 ====================

class CheckinStatus(Enum):
    SUCCESS = 0
    REPEAT = 1
    FAILURE = -2


class APIEndpoint(Enum):
    CHECKIN = "/api/user/checkin"
    STATUS = "/api/user/status"
    POINTS = "/api/user/points"


class LogEmoji:
    SUCCESS = "✅"
    FAIL = "❌"
    REPEAT = "🔄"
    CHECKIN = "🎫"
    STATUS = "📊"
    POINTS = "💰"
    START = "🚀"
    END = "🏁"
    COOKIE = "🍪"
    DOMAIN = "🌐"
    WARNING = "⚠️"
    ERROR = "🔴"
    INFO = "ℹ️"


PLATFORM_UA = {
    "Windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "macOS": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "iPhone": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Android": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
}


# ==================== 配置管理 ====================

class Config:
    ENV_COOKIES = "GLADOS_COOKIES"
    ENV_VERBOSE = "GLADOS_VERBOSE"
    ENV_TG_BOT_TOKEN = "TG_BOT_TOKEN"
    ENV_TG_CHAT_ID = "TG_CHAT_ID"

    DEFAULT_VERBOSE = False
    DOMAINS = ["glados.cloud"]

    def __init__(self):
        self.cookies_list: List[str] = []
        self.verbose = self.DEFAULT_VERBOSE
        self.tg_bot_token = ""
        self.tg_chat_id = ""
        self._load_config()

    def _load_config(self):
        raw_cookies = os.environ.get(self.ENV_COOKIES, "").strip()
        verbose_env = os.environ.get(self.ENV_VERBOSE, "").strip()

        self.tg_bot_token = os.environ.get(
            self.ENV_TG_BOT_TOKEN, ""
        ).strip()
        self.tg_chat_id = os.environ.get(
            self.ENV_TG_CHAT_ID, ""
        ).strip()

        if raw_cookies:
            self.cookies_list = [
                cookie.strip()
                for cookie in raw_cookies.split("&")
                if cookie.strip()
            ]

        if not self.cookies_list:
            logger.warning(
                f"{LogEmoji.WARNING} 未配置有效的 "
                f"{self.ENV_COOKIES}"
            )

        if verbose_env:
            value = verbose_env.lower()
            if value in ("true", "1", "yes", "y"):
                self.verbose = True
            elif value in ("false", "0", "no", "n"):
                self.verbose = False
            else:
                logger.warning(
                    f"{LogEmoji.WARNING} 无效的详细日志配置："
                    f"{verbose_env}，使用默认值。"
                )

        logger.info(
            f"{LogEmoji.INFO} 已加载 {len(self.cookies_list)} 个 Cookie"
        )
        logger.info(
            f"{LogEmoji.INFO} 详细日志：{self.verbose}"
        )


# ==================== GLaDOS API ====================

class API:
    def __init__(
        self,
        domain: str,
        cookie_index: int = 0,
        verbose: bool = False,
    ):
        self.domain = domain
        self.cookie_index = cookie_index
        self.verbose = verbose

        self.session = requests.Session()
        self.session.headers.update({
            "origin": f"https://{domain}",
            "user-agent": PLATFORM_UA["Windows"],
        })

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _log(self, level, emoji, message, force=False):
        if self.verbose or force:
            log_message = (
                f"{LogEmoji.COOKIE}[{self.cookie_index}] "
                f"{LogEmoji.DOMAIN}[{self.domain}] "
                f"{emoji} {message}"
            )

            if level == "error":
                logger.error(log_message)
            elif level == "warning":
                logger.warning(log_message)
            else:
                logger.info(log_message)

    def _request(
        self,
        path: str,
        method: str,
        cookie: str,
        data: Optional[Dict] = None,
    ) -> Optional[Dict]:
        url = f"https://{self.domain}{path}"

        headers = {
            "cookie": cookie,
            "referer": f"https://{self.domain}/",
        }

        try:
            if method.upper() == "POST":
                response = self.session.post(
                    url,
                    headers=headers,
                    data=data,
                    timeout=(15, 60),
                )
            else:
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=(15, 60),
                )

            if not response.ok:
                self._log(
                    "error",
                    LogEmoji.ERROR,
                    f"请求失败，HTTP {response.status_code}",
                    force=True,
                )
                return None

            result = response.json()
            if not isinstance(result, dict):
                self._log(
                    "error",
                    LogEmoji.ERROR,
                    "服务器返回的数据格式不正确",
                    force=True,
                )
                return None

            if self.verbose:
                self._log(
                    "info",
                    LogEmoji.INFO,
                    f"接口返回：{result}",
                )

            return result

        except (requests.RequestException, ValueError) as exc:
            self._log(
                "error",
                LogEmoji.ERROR,
                f"请求异常：{exc}",
                force=True,
            )
            return None

    def checkin(self, cookie: str) -> Dict:
        result = self._request(
            APIEndpoint.CHECKIN.value,
            "POST",
            cookie,
            data={"token": self.domain},
        )

        if not result:
            return {
                "status": "签到失败",
                "points": "0",
                "message": "网络请求失败",
                "code": CheckinStatus.FAILURE,
            }

        code = result.get("code", -2)
        message = result.get("message", "")
        points = str(result.get("points", 0))

        if code == CheckinStatus.SUCCESS.value:
            self._log(
                "info",
                LogEmoji.SUCCESS,
                f"签到成功，获得 {points} 积分：{message}",
                force=True,
            )
            return {
                "status": "签到成功",
                "points": points,
                "message": message,
                "code": CheckinStatus.SUCCESS,
            }

        if code == CheckinStatus.REPEAT.value:
            self._log(
                "info",
                LogEmoji.REPEAT,
                f"今日已签到：{message}",
                force=True,
            )
            return {
                "status": "重复签到",
                "points": "0",
                "message": message,
                "code": CheckinStatus.REPEAT,
            }

        self._log(
            "warning",
            LogEmoji.WARNING,
            f"签到失败，code={code}，{message}",
            force=True,
        )
        return {
            "status": "签到失败",
            "points": "0",
            "message": message,
            "code": CheckinStatus.FAILURE,
        }

    def get_status(self, cookie: str) -> Tuple[str, int]:
        result = self._request(
            APIEndpoint.STATUS.value,
            "GET",
            cookie,
        )

        if not result:
            return "未知", -2

        try:
            code = result.get("code", -2)
            left_days = result.get("data", {}).get("leftDays")

            if left_days is None:
                return "未知", code

            return f"{int(float(left_days))} 天", code

        except (TypeError, ValueError, AttributeError):
            return "未知", -2

    def get_points(self, cookie: str) -> Tuple[str, int]:
        result = self._request(
            APIEndpoint.POINTS.value,
            "GET",
            cookie,
        )

        if not result:
            return "未知", 0

        try:
            points = result.get("points")

            if points is None:
                return "未知", 0

            points_int = int(float(points))
            return f"{points_int} 积分", points_int

        except (TypeError, ValueError):
            return "未知", 0


# ==================== 签到结果 ====================

@dataclass
class CheckinResult:
    cookie_index: int
    domain: str
    status: str = "签到失败"
    points: str = "0"
    days: str = "未知"
    points_total: str = "未知"
    code: CheckinStatus = CheckinStatus.FAILURE

    def to_dict(self):
        return asdict(self)


# ==================== Telegram 推送 ====================

class PushService:
    def __init__(self, config: Config):
        self.config = config

    def send(self, title: str, content: str) -> bool:
        if not self.config.tg_bot_token or not self.config.tg_chat_id:
            logger.info(
                f"{LogEmoji.WARNING} 未配置 Telegram，跳过推送。"
            )
            return False

        url = (
            "https://api.telegram.org/bot"
            f"{self.config.tg_bot_token}/sendMessage"
        )

        message = f"<b>{title}</b>\n\n{content}"

        payload = {
            "chat_id": self.config.tg_chat_id,
            "text": message,
            "parse_mode": "HTML",
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=15,
            )
            response.raise_for_status()

            result = response.json()
            if not result.get("ok"):
                raise RuntimeError(str(result))

            logger.info(
                f"{LogEmoji.SUCCESS} Telegram 推送成功。"
            )
            return True

        except Exception as exc:
            logger.error(
                f"{LogEmoji.ERROR} Telegram 推送失败：{exc}"
            )
            return False


# ==================== 签到执行器 ====================

class Checker:
    def __init__(self, config: Config):
        self.config = config
        self.results: List[CheckinResult] = []

    def checkin_all(self):
        total
