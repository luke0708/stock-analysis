from pydantic import BaseModel
from pathlib import Path
import os

# Try to load .env file if exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded .env from {env_path}")
except ImportError:
    pass  # python-dotenv not installed, skip

class Settings(BaseModel):
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    CACHE_DIR: Path = DATA_DIR / "cache"
    
    # Tushare Configuration
    TUSHARE_TOKEN: str = os.getenv("TUSHARE_TOKEN", "")
    
    # Default stocks for demo
    DEFAULT_STOCKS: list[str] = ["300661", "300059", "600519"]
    
    # Data Provider Priority ("tushare" or "akshare")
    PREFERRED_PROVIDER: str = "tushare"
    
    def init_dirs(self):
        self.DATA_DIR.mkdir(exist_ok=True)
        self.CACHE_DIR.mkdir(exist_ok=True)

settings = Settings()
settings.init_dirs()
