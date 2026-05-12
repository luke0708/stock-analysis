"""
stock_cache.db 的 DDL 定义。

分三层：
  L1 原始缓存 — daily_ohlc / minute_bars / stock_meta / stock_news
  L2 衍生快照 — trend_signal_snapshot / flow_summary_daily / price_range_snapshot
  L4 训练标签 — labels
  元数据     — cache_meta（TTL 时间戳等）
"""

SCHEMA_VERSION = 1

# 按顺序执行；IF NOT EXISTS 保证幂等
DDL_STATEMENTS = [
    # ── L1 原始数据缓存 ──────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS daily_ohlc (
        code         TEXT    NOT NULL,
        date         TEXT    NOT NULL,
        open         REAL,
        high         REAL,
        low          REAL,
        close        REAL,
        volume       REAL,
        amount       REAL,
        adjust_flag  TEXT    NOT NULL DEFAULT 'qfq',
        source       TEXT,
        fetched_at   TEXT    NOT NULL,
        PRIMARY KEY (code, date, adjust_flag)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_daily_code_date
        ON daily_ohlc(code, date)
    """,
    """
    CREATE TABLE IF NOT EXISTS minute_bars (
        code        TEXT NOT NULL,
        datetime    TEXT NOT NULL,
        open        REAL,
        high        REAL,
        low         REAL,
        close       REAL,
        volume      REAL,
        amount      REAL,
        fetched_at  TEXT NOT NULL,
        PRIMARY KEY (code, datetime)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_meta (
        code        TEXT PRIMARY KEY,
        name        TEXT,
        industry    TEXT,
        concept     TEXT,
        market      TEXT,
        updated_at  TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_news (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        code          TEXT NOT NULL,
        published_at  TEXT,
        title         TEXT,
        summary       TEXT,
        source        TEXT,
        fetched_at    TEXT NOT NULL,
        UNIQUE(code, published_at, title)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_news_code_pub
        ON stock_news(code, published_at DESC)
    """,
    # ── L2 衍生数据快照（两个页面共享） ─────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS trend_signal_snapshot (
        code           TEXT NOT NULL,
        analysis_date  TEXT NOT NULL,
        snapshot_json  TEXT NOT NULL,
        created_at     TEXT NOT NULL,
        PRIMARY KEY (code, analysis_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS flow_summary_daily (
        code               TEXT NOT NULL,
        date               TEXT NOT NULL,
        net_inflow         REAL,
        large_order_count  INTEGER,
        buy_amount         REAL,
        sell_amount        REAL,
        neutral_amount     REAL,
        summary_json       TEXT,
        created_at         TEXT NOT NULL,
        PRIMARY KEY (code, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS price_range_snapshot (
        code           TEXT NOT NULL,
        analysis_date  TEXT NOT NULL,
        support_zone   REAL,
        resistance_zone REAL,
        analysis_json  TEXT,
        created_at     TEXT NOT NULL,
        PRIMARY KEY (code, analysis_date)
    )
    """,
    # ── L4 训练标签 ───────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS labels (
        code              TEXT NOT NULL,
        date              TEXT NOT NULL,
        next_1d_pct       REAL,
        next_5d_pct       REAL,
        next_20d_pct      REAL,
        next_1d_high_pct  REAL,
        next_1d_low_pct   REAL,
        backfilled_at     TEXT,
        PRIMARY KEY (code, date)
    )
    """,
    # ── 元数据 ───────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS cache_meta (
        key         TEXT PRIMARY KEY,
        value       TEXT,
        updated_at  TEXT NOT NULL
    )
    """,
]
