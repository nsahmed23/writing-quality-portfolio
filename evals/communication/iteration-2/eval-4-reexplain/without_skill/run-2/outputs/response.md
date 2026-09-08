One step at a time. Right now I just need to know what's using port 8080.

1. Open PowerShell (Windows key, type "PowerShell", press Enter).
2. Paste this in and press Enter:

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).OwningProcess
```

3. Send me back whatever it prints. If nothing prints, tell me that.

Ignore the rest of my last message for now, the nodemon explanation and the four-step list. That's all for later. This one command tells us what's actually blocking port 8080, and that decides what we do next.
