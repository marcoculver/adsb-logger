# Security Setup Guide

## ⚠️ IMPORTANT: Bot Token Security

Your Telegram bot tokens are like passwords - they give full control over your bots. **Never commit them to git!**

## Initial Setup

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Get your bot tokens from @BotFather:**
   - Message @BotFather on Telegram
   - Use `/mybots` to select your bot
   - Click "API Token" to view/regenerate

3. **Get your Telegram User ID:**
   - Message @userinfobot on Telegram
   - It will reply with your user ID

4. **Edit `.env` file:**
   ```bash
   nano .env  # or use your preferred editor
   ```

5. **Fill in your actual tokens:**
   ```env
   FLIGHT_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789
   CALLSIGN_BOT_TOKEN=9876543210:XYZabcDEFghiJKLmnoPQRstuVWX987654321
   HEALTH_BOT_TOKEN=5555555555:AAAbbbCCCdddEEEfffGGGhhhIIIjjjKKKll
   TELEGRAM_ALLOWED_USERS=123456789
   TELEGRAM_CHAT_ID=123456789
   ```

6. **Verify `.env` is in `.gitignore`:**
   ```bash
   grep "\.env" .gitignore
   ```
   Should show: `.env` and `*.env`

## If Your Token Was Exposed

If you accidentally committed a token to git:

1. **Revoke it IMMEDIATELY:**
   - Message @BotFather
   - Select your bot
   - Choose "API Token" → "Revoke current token"
   - Generate a new token

2. **Update your `.env` file** with the new token

3. **Remove from git history** (this is complex, consider the token permanently compromised)

## Best Practices

- ✅ Always use `.env` files for secrets
- ✅ Keep `.env` in `.gitignore`
- ✅ Use `.env.example` for documentation (no real tokens!)
- ✅ Rotate tokens periodically
- ✅ Use user ID whitelist (`TELEGRAM_ALLOWED_USERS`)
- ❌ Never commit tokens to git
- ❌ Never share tokens in chat/email
- ❌ Never post tokens in public forums/issues

## Running the Bots

After setting up `.env`:

```bash
# Linux/WSL
export $(cat .env | xargs)
./run_bot.sh

# Or for systemd services, they read .env automatically
sudo systemctl start adsb-flight-bot
```

```powershell
# Windows PowerShell
Get-Content .env | ForEach-Object {
    $name, $value = $_.split('=')
    Set-Content env:\$name $value
}
.\run_bot.bat
```

## Verification

Check that tokens are not in your working directory:

```bash
# Should return nothing
grep -r "8230471568\|8380442252\|8279120117" . --include="*.sh" --include="*.py"

# Check git history (harder to fix if found)
git log -p | grep -i "bot.*token"
```

## Questions?

See `.env.example` for all required environment variables.
