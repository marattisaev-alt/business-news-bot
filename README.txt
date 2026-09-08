MRK BUSINESS NEWS 8.0

What changed:
- visual news cards generated automatically with Pillow;
- category labels;
- importance levels;
- "Why is this important?" block;
- duplicate protection;
- Russian text is stored in Unicode escape form inside the source to avoid mojibake;
- RSS data is read from response bytes;
- state.json records the latest run;
- up to 2 posts per GitHub Actions run.

Files:
- bot.py
- requirements.txt
- .github/workflows/bot.yml
- posted.json (keep your existing file)
- state.json

Secrets:
BOT_TOKEN
CHANNEL

Replace only bot.py and requirements.txt if you already have the workflow.
If you use the included workflow, replace the workflow file too.
Do NOT delete posted.json.
