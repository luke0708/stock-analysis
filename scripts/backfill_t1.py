"""每日 T+1/T+5 回填脚本，由 launchd 在 16:10 自动执行。"""
import sys
import os
import logging
from datetime import date
from pathlib import Path

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

    # 跳过周末（A 股不开市，无数据可回填）
    if today.weekday() >= 5:
        logger.info("今天是周%s（%s），非交易日，跳过回填", weekday_names[today.weekday()], today)
        return

    logger.info("=== 开始 T+1/T+5 回填 (%s 周%s) ===", today, weekday_names[today.weekday()])
    try:
        from stock_analysis.analysis.advice_journal import AdviceJournal
        n = AdviceJournal().follow_up_pending()
        logger.info("回填完成，本次更新 %d 条", n)
    except Exception:
        logger.error("回填失败", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
