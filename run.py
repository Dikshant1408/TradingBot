"""
QuantDesk India - Application Launcher.
Starts the local workstation server on 127.0.0.1:8000.
"""
import sys
import uvicorn
from app.config.settings import get_settings

# Reconfigure stdout for UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

settings = get_settings()

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(f"       QUANTDESK INDIA - QUANTITATIVE TRADING TERMINAL")
    print("=" * 60)
    print(f" Operating Mode:   {settings.APP_MODE.upper()}")
    print(f" Local URL:        http://{settings.HOST}:{settings.PORT}")
    print(f" SQLite Database:  {settings.DATABASE_URL}")
    print(f" Log File:         {settings.LOGS_DIR / 'trading_bot.log'}")
    print(f" Timezone Display: {settings.TIMEZONE} (Stored internally in UTC)")
    print("=" * 60 + "\n")

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
