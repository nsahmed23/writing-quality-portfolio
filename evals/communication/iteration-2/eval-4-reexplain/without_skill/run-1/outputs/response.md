Fair, that was a lot at once. Let's back up to just the first step.

Where things stand: your server can't restart because something already has port 8080, and we don't know what yet. Everything else depends on that one fact.

Open PowerShell and run this:

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).OwningProcess
```

In plain terms: it asks Windows "which program is sitting on port 8080 right now?" and prints that program's name and PID (the number Windows uses to identify a running process).

Two things can happen:

- It prints a process, likely `node.exe`. That means an old copy of your own server never shut down, and it's blocking the new one.
- It prints nothing. That means something unrelated to your app has claimed port 8080.

Paste back whichever one you get. I'll hand you one specific fix for that case instead of listing every branch again.

On the Node 24 question: set it aside for now. Short version, it's probably not the cause; I brought it up mainly to rule it out. The command above is what will actually tell us what's happening.
