# Troubleshooting & Frequently Asked Questions

### 1. Port 8000 Already in Use
If port 8000 is occupied by another process:
- Modify `PORT=8001` in your `.env` file.
- Or terminate the conflicting application using PowerShell:
  ```powershell
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
  ```

### 2. Bot State is "HALTED" or "EMERGENCY_STOPPED"
- If the emergency banner is visible, navigate to the **Risk Controls** tab.
- Inspect the halt reason displayed on screen.
- Verify your account P&L or risk limits.
- Click **MANUAL EMERGENCY STOP RESET** to return the system to `IDLE`.

### 3. CSV Data Upload Issues
- Ensure your CSV file has headers representing date/time and OHLC prices:
  `Date, Open, High, Low, Close, Volume`
- Ensure prices are positive and $High \ge \max(Open, Close)$ and $Low \le \min(Open, Close)$.
- The normalizer will automatically detect and clean date formats and strip invalid rows.

### 4. Windows PowerShell Script Execution Policy
If `activate` script is blocked by PowerShell execution policy:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Alternatively, run via cmd or use `start_bot.bat`.
