# Connecting YouTube, Instagram, Telegram and Discord

All of this happens in **The Apothecary** (Settings). Keys are saved only in your local `.env` and `config/secrets/`, both gitignored, and are shown masked after saving.

Each platform has two login methods (**Publishing accounts → Login method**):

- **Cookie Login** (default): signs in once in a real browser window and uploads like you would. Works today, no app approval.
- **Official API**: uses the platform's API. More robust, but each platform restricts new, unreviewed apps (details below).

You only need the Official API if you prefer it to cookies. This guide covers setting it up for YouTube and Instagram, plus Telegram and Discord alerts.

---

## 1. YouTube Data API (about 15 minutes)

**What you get:** uploads with a title, description, tags and thumbnail through Google's API.
**Restriction:** until your Google Cloud project passes Google's API audit, API uploads are **locked to Private**, and the default quota allows about **6 uploads a day**. Cookie Login has neither limit.

### Steps

1. **Create a project.** Open https://console.cloud.google.com/, then click the project picker → **New project**. Name it (e.g. `video-factory`) and click **Create**.
2. **Enable the API.** Go to **APIs & Services → Library**, search for **YouTube Data API v3**, and click **Enable**.
3. **Set up the consent screen.** Go to **APIs & Services → OAuth consent screen** (in newer consoles: **Google Auth Platform → Branding / Audience**).
   - User type: **External**. Fill in the app name and your email.
   - Under **Audience → Test users**, add the Google account that owns your YouTube channel. Without this, sign-in fails with "access blocked".
   - The app only asks for the `youtube.upload` permission.
4. **Create the credentials.** Go to **APIs & Services → Credentials → Create credentials → OAuth client ID**.
   - Application type: **Desktop app** (not "Web application").
   - Click **Create**, then **Download JSON**.
5. **Add them in the app.** Go to **The Apothecary → Publishing accounts → YouTube**.
   - Set **Login method** to **Official API**.
   - Either click **Upload client_secret.json** and pick the downloaded file, or paste the **Client ID** and **Client secret** into their fields.
   - Leave **Access token** empty. The app creates and refreshes its own token.
6. **Connect.** Click **Connect YouTube API**. A browser window opens.
   - Sign in with the channel's Google account and allow access.
   - If Google warns "Google hasn't verified this app", click **Continue**: it's your own app in test mode.
   - The token is saved to `config/secrets/youtube_token.json`.
7. **Test it.** Click **Test Connection**. It should name your channel.

**Visibility:** the default upload visibility (unlisted) is set in Publishing accounts and per schedule. While your project is unaudited, YouTube still forces Private on API uploads. To publish publicly through the API, apply for the audit at https://support.google.com/youtube/contact/yt_api_form, or use Cookie Login.

**If it goes wrong:**

| Error | Fix |
| --- | --- |
| `access_denied` / "access blocked" | Add your account as a **Test user** (step 3). |
| `redirect_uri_mismatch` | You created a **Web** client; create a **Desktop** one. |
| `quotaExceeded` | You've used the day's quota (about 6 uploads); it resets at midnight Pacific time. |
| `invalid_grant` later on | Testing-mode tokens expire after 7 days. Click **Connect YouTube API** again, or publish the consent screen to "In production". |

---

## 2. Instagram Graph API, Reels (about 30 to 45 minutes)

**What you get:** Reels uploaded straight from the file on your PC (resumable upload, so no hosting is needed), with caption and cover frame.

**Requirements:**
- An Instagram **Business or Creator** account (in the Instagram app: Settings → Account type and tools → switch to professional).
- A **Facebook Page** linked to that Instagram account (Page settings → Linked accounts → Instagram).
- A **Meta developer account** at https://developers.facebook.com/.

### Steps

1. **Create a Meta app.** At https://developers.facebook.com/apps, click **Create app**.
   - Use case: **Other**, then type **Business**.
   - Add the **Instagram** product and choose **API setup with Facebook login** (the app uses `graph.facebook.com`).
2. **Get a user token.** Open **Tools → Graph API Explorer** (https://developers.facebook.com/tools/explorer).
   - Select your app, then **Get Token → Get User Access Token**.
   - Tick these permissions: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`.
   - Click **Generate Access Token**, and select your Page and Instagram account in the dialog.
3. **Make it long-lived.** The token from step 2 lasts about an hour; a long-lived one lasts about 60 days.
   - Open https://developers.facebook.com/tools/debug/accesstoken, paste the token, click **Debug**, then **Extend Access Token**.
   - Or call this in a browser, with your App ID and App secret from **App settings → Basic**:
     `https://graph.facebook.com/v23.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN`
4. **Find your Instagram user ID.** In the Graph API Explorer, using the long-lived token:
   - `GET me/accounts` returns your Pages; copy your Page's `id`.
   - `GET {page-id}?fields=instagram_business_account` returns the ID you need: `instagram_business_account.id`. It's a long number, and it is not your @handle.
5. **Add them in the app.** Go to **The Apothecary → Publishing accounts → Instagram**.
   - Set **Login method** to **Official API**.
   - Paste the **Access token** (the long-lived one) and the **Instagram user ID**, then click **Save**.
   - **App (client) ID** and **App secret** can stay empty; the uploader doesn't use them.
6. **Test it.** Click **Test Connection**. It should show your Instagram username.

**Restrictions:** in **Development mode**, a Meta app can only post to accounts that hold a role on the app (you, as admin, are fine). Posting for other people needs **App Review** for `instagram_content_publish`. The API allows **50 posts in 24 hours**, and the app's own daily cap keeps you far below that. Keep Instagram at 1 to 2 posts a day (Witching Hour → Time zone and daily caps) to avoid account challenges.

**Every ~60 days:** the token expires. Repeat steps 2 and 3, paste the new token, and save. Test Connection tells you when it has expired (`Error validating access token`).

**If it goes wrong:**

| Error | Fix |
| --- | --- |
| `(#10) Application does not have permission` | Step 2 is missing `instagram_content_publish`, or the token was created before you added it. Generate a new token. |
| `instagram_business_account` is missing | The Instagram account isn't a Business/Creator account, or it isn't linked to that Page. |
| `Media upload has failed` / code 2207026 | The video doesn't meet Reels specs (the app's 9:16 H.264/AAC renders do). Re-render, or check that the file isn't 0 bytes. |
| `(#100) The parameter user_id is required` | You pasted your @handle; use the numeric ID from step 4. |

---

## 3. Telegram alerts (about 3 minutes)

The lab messages you when an overnight batch finishes or a job fails, with links.

1. In Telegram, open **@BotFather** and send `/newbot`. Pick a name and a username ending in `bot`. BotFather replies with a **token** like `123456789:AAH…`.
2. Open a chat with your new bot and send it any message (bots can't message you first).
3. Get your **chat ID**. Open this in a browser, with your token in place of `<TOKEN>`:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Find `"chat":{"id": 123456789 …}`; that number is the chat ID.
   - **For a group:** add the bot to the group, send a message there, and reload. Group IDs are negative, like `-1001234567890`.
4. Go to **The Apothecary → Alerts**. Paste the **Telegram bot token** and **Telegram chat ID**, click **Save Alerts**, then **Send Test Message**.

If `getUpdates` returns `"result": []`, send the bot another message and reload. If you set a webhook on that bot somewhere else, `getUpdates` stays empty; use a fresh bot.

---

## 4. Discord alerts (about 2 minutes)

1. In Discord, open the server and channel → **Edit Channel** (the gear icon) → **Integrations → Webhooks → New Webhook**. You need the *Manage Webhooks* permission.
2. Name it (e.g. "The Lab"), optionally give it an avatar, then click **Copy Webhook URL**. It looks like `https://discord.com/api/webhooks/1234…/AbCd…`.
3. Go to **The Apothecary → Alerts**. Paste it into **Discord webhook URL**, click **Save Alerts**, then **Send Test Message**.

Treat the webhook URL like a password: anyone who has it can post in that channel. If it leaks, delete the webhook in Discord and make a new one.

---

## Where everything is stored

| Item | Stored in |
| --- | --- |
| YouTube client file and token | `config/secrets/youtube_client_secret.json`, `config/secrets/youtube_token.json` |
| YouTube Client ID / secret (if typed in) | `.env` as `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` |
| Instagram token and user ID | `.env` as `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID` |
| Telegram | `.env` as `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Discord | `.env` as `DISCORD_WEBHOOK_URL` |
| Login method per platform | `config/settings.json` → `publish.<platform>.method` |

None of these are committed to Git, and the app never sends them back to the browser unmasked.
