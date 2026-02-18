# 📊 Telegram Excel Lookup Bot v2

A 24/7 Telegram bot for your team — search any row by Cell ID using either a shared **master file** or your own uploaded file.

---

## ✨ Features

| Feature | Details |
|---|---|
| 📂 Master File | Admin uploads once, whole team uses it |
| 📤 Personal Upload | Any user can upload their own file |
| 🔄 Auto-refresh | Master file is reloaded on every search — always up to date |
| 🔐 Admin Control | Only admins can update the master file |
| 🔍 Cell ID Search | Case-insensitive, returns full row data |
| 👥 Multi-user | Each user has their own session |

---

## 🗂️ Project Structure

```
telegram_excel_bot_v2/
├── bot.py              ← Main bot code
├── requirements.txt    ← Python dependencies
├── Procfile            ← For Railway deployment
├── master.xlsx         ← Master file lives here (created when admin uploads)
├── uploads/            ← Auto-created; stores user-uploaded files
└── README.md
```

---

## ⚙️ Setup

### 1. Create your Telegram Bot
1. Open Telegram → search **@BotFather**
2. Send `/newbot` → follow prompts → copy your **API Token**

### 2. Get your Telegram User ID (for admin access)
1. Search **@userinfobot** on Telegram
2. Send any message → it replies with your numeric User ID
3. Share this with anyone who needs admin rights

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set environment variables

**Linux / macOS:**
```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
export ADMIN_IDS="123456789,987654321"   # comma-separated user IDs
```

**Windows (PowerShell):**
```powershell
$env:TELEGRAM_BOT_TOKEN="your_token_here"
$env:ADMIN_IDS="123456789,987654321"
```

> 💡 If `ADMIN_IDS` is left empty, **anyone** can upload the master file.

### 5. Run the bot
```bash
python bot.py
```

---

## 🚀 Deploy 24/7 on Railway (Recommended)

1. Push all files to a **GitHub repository**
2. Go to [railway.app](https://railway.app) → sign in with GitHub
3. **New Project** → **Deploy from GitHub repo** → select your repo
4. Go to **Variables** tab and add:
   ```
   TELEGRAM_BOT_TOKEN = your_token_here
   ADMIN_IDS          = 123456789,987654321
   ```
5. Railway reads the `Procfile` automatically and starts the bot ✅

> Every time you push to GitHub, Railway redeploys automatically.

---

## 📋 Excel File Requirements

Your Excel file must have a column named exactly:
```
Cell id
```

Example layout:

| Cell id | Site Name  | Region | Status  | Power (kW) | Notes       |
|---------|------------|--------|---------|------------|-------------|
| LKI0    | Alpha Site | North  | Active  | 120        | Main hub    |
| LKI09   | Beta Site  | South  | Pending | 85         | Under review|
| LKI10   | Gamma Site | East   | Active  | 200        | Expansion   |

> If your column is named differently, change `CELL_ID_COLUMN = "Cell id"` at the top of `bot.py`.

---

## 🤖 Bot Commands

| Command | Who | Description |
|---|---|---|
| `/start` | Everyone | Start the bot, show main menu |
| `/menu` | Everyone | Go back to main menu |
| `/reload` | Everyone | Refresh master file data |
| `/info` | Everyone | Show session info and your User ID |
| `/uploadmaster` | Admins only | Upload a new master file |

---

## 👥 How the Team Uses It

### Regular team member:
1. Open the bot → `/start`
2. Tap **📂 Use Master File**
3. Type a Cell ID like `LKI09`
4. Get all row data instantly

### Admin (updating the master file):
1. Open the bot → `/uploadmaster`
2. Send the new `.xlsx` file
3. Bot validates and replaces the master file
4. All team members get the new data on their next search

---

## 🔧 Customization

### Change the Cell ID column name
```python
# In bot.py, line ~14:
CELL_ID_COLUMN = "Cell id"   # ← change this to match your column
```

### Read a specific sheet (not the first one)
```python
# In bot.py, inside load_excel():
df = pd.read_excel(path, dtype=str)
# Change to:
df = pd.read_excel(path, sheet_name="YourSheetName", dtype=str)
```

---

## ❓ Troubleshooting

| Problem | Solution |
|---|---|
| `Column 'Cell id' not found` | Check your Excel column name matches exactly |
| Master file missing | Admin needs to run `/uploadmaster` |
| Bot not responding | Check Railway logs; ensure token is set correctly |
| No admin access | Add your User ID to the `ADMIN_IDS` environment variable |
| File upload fails | Must be `.xlsx` or `.xls` format |
