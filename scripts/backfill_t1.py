"""每日 T+1/T+5/T+20 回填脚本，由 launchd 在 16:10 自动执行。"""
import sys
import os
import logging
from datetime import date
from pathlib import Path

# A股法定节假日（补充周末外的非交易日）——每年初根据交易所公告更新
_MARKET_HOLIDAYS = {
    # 2026
    date(2026, 1, 1),  date(2026, 1, 2),   # 元旦
    date(2026, 1, 28), date(2026, 1, 29), date(2026, 1, 30),
    date(2026, 2, 2),  date(2026, 2, 3),  date(2026, 2, 4),   # 春节
    date(2026, 4, 6),                                           # 清明
    date(2026, 5, 1),  date(2026, 5, 4),  date(2026, 5, 5),   # 劳动节
    date(2026, 6, 19),                                          # 端午
    date(2026, 9, 30),                                          # 中秋调休
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5),
    date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8),  # 国庆+中秋
}

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env（不强依赖 dotenv，手动解析即可）
_env_file = PROJECT_ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# 日志：追加写入，保留历史
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "backfill_t1.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    today = date.today()
    weekday_names = ["一", "二", "三", "四", "五", "六", "日"]

    # 跳过周末
    if today.weekday() >= 5:
        logger.info("今天是周%s（%s），非交易日，跳过回填", weekday_names[today.weekday()], today)
        return

    # 跳过法定节假日
    if today in _MARKET_HOLIDAYS:
        logger.info("今天是法定节假日（%s），跳过回填", today)
        return

    logger.info("=== 开始 T+1/T+5/T+20 回填 (%s 周%s) ===", today, weekday_names[today.weekday()])
    try:
        from stock_analysis.analysis.advice_journal import AdviceJournal
        n = AdviceJournal().follow_up_pending()
        logger.info("回填完成，本次更新 %d 条", n)
    except Exception:
        logger.error("回填失败", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
