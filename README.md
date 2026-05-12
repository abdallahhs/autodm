# AutoDM — Instagram Comment-to-DM Automation

Automate Instagram comment replies and private DMs based on keyword triggers — like ManyChat, but self-hosted and built on the official Instagram Graph API.

---

## How It Works

1. A user comments a keyword (e.g. "link", "info") on your Instagram post
2. The webhook receives the comment event from Instagram
3. AutoDM matches it against your active campaigns
4. It automatically **replies to the comment** and **sends a private DM** to the commenter

---

## Instagram API Setup (Step-by-Step)

### Step 1 — Convert to Business or Creator Account

You need an **Instagram Business** or **Creator** account. To convert:
1. Open Instagram → Profile → Menu (☰) → Settings → Account
2. Tap **Switch to Professional Account**
3. Choose **Business** or **Creator**
4. Connect it to a **Facebook Page** (create one if needed)

---

### Step 2 — Create a Facebook Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Click **My Apps → Create App**
3. Choose **"Other"** → **"Business"** type
4. Name your app (e.g. "AutoDM Bot") and click Create
5. In your app dashboard, click **Add Product** → find **Instagram Graph API** → click **Set Up**

---

### Step 3 — Add Permissions

In your app, go to **App Review → Permissions and Features** and request:
- `instagram_manage_comments` — required to reply to comments
- `instagram_manage_messages` — required to send DMs *(see DM note below)*
- `pages_read_engagement` — to read page/post data
- `instagram_basic` — basic access

> **For testing:** You can add yourself as a test user under **Roles → Test Users** and use your own token without full app review.

---

### Step 4 — Generate a Long-Lived Access Token

**Short-lived token (valid 1 hour):**
1. Go to **Tools → Graph API Explorer**
2. Select your app from the top-right dropdown
3. Click **Generate Access Token** and log in with your Facebook account
4. Copy the short-lived token

**Exchange for long-lived token (valid 60 days):**

```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token \
  ?grant_type=fb_exchange_token \
  &client_id=YOUR_APP_ID \
  &client_secret=YOUR_APP_SECRET \
  &fb_exchange_token=SHORT_LIVED_TOKEN"
```

The response will contain a `access_token` valid for 60 days.

**Refresh before expiry (60-day tokens can be refreshed):**

```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token \
  ?grant_type=fb_exchange_token \
  &client_id=YOUR_APP_ID \
  &client_secret=YOUR_APP_SECRET \
  &fb_exchange_token=CURRENT_LONG_LIVED_TOKEN"
```

> ⚠️ Set a calendar reminder every 50 days to refresh your token.

---

### Step 5 — Get Your Instagram Business Account ID

```bash
curl "https://graph.facebook.com/v19.0/me/accounts \
  ?access_token=YOUR_LONG_LIVED_TOKEN"
```

Find your Page ID, then:

```bash
curl "https://graph.facebook.com/v19.0/YOUR_PAGE_ID \
  ?fields=instagram_business_account \
  &access_token=YOUR_TOKEN"
```

The `instagram_business_account.id` is your **Instagram Business Account ID**.

---

### Step 6 — Configure the Webhook

1. In your Facebook Developer App → **Products → Webhooks**
2. Click **Add Subscriptions** → Select **Instagram**
3. **Callback URL:** `https://your-domain.com/webhook`
4. **Verify Token:** The same value you set in `WEBHOOK_VERIFY_TOKEN` env var
5. **Subscribe to fields:** `comments`
6. Click **Verify and Save**

> The app must be running and publicly accessible (via Railway, Render, or ngrok for local dev) for webhook verification to succeed.

**For local development with ngrok:**
```bash
ngrok http 8000
# Use the https://xxxx.ngrok.io/webhook URL as your callback URL
```

---

### Step 7 — Get a Post ID

Using Graph API Explorer:

```bash
curl "https://graph.facebook.com/v19.0/YOUR_IG_ACCOUNT_ID/media \
  ?fields=id,caption,permalink \
  &access_token=YOUR_TOKEN"
```

Find the post you want to automate and copy its `id` — this is the Post ID you enter in the campaign form.

---

## ⚠️ DM Permission Note

Instagram's Graph API restricts who you can DM:

- **Option A (No approval needed):** Users who have **previously sent your business a message** can receive DMs.
- **Option B (Requires approval):** Apply for `instagram_manage_messages` with an approved use case in App Review.

**To apply for DM permission:**
1. Facebook Developer App → **App Review → Permissions and Features**
2. Request `instagram_manage_messages`
3. Provide a use case description (e.g. "Send automated welcome messages to users who request information via Instagram comments")
4. Approval takes 5–10 business days

Until approved, comment replies will still work — only DMs to first-time contacts will fail.

---

## Local Development

### Prerequisites
- Python 3.11+

### Setup

```bash
git clone https://github.com/your-username/autodm
cd autodm

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
# Edit .env with your values

# Run the server
uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) → Dashboard

---

## Deployment

### Railway (Recommended)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub Repo
3. Set environment variables in Railway dashboard
4. Railway auto-detects the Dockerfile and deploys

### Render

1. Push to GitHub
2. New Web Service → Connect repo
3. Environment: Docker
4. Add environment variables
5. Deploy

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Yes | Long-lived access token |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Yes | Your IG Business Account ID |
| `FACEBOOK_APP_SECRET` | Recommended | Used to verify webhook signatures |
| `WEBHOOK_VERIFY_TOKEN` | Yes | Random string for webhook setup |
| `DATABASE_URL` | No | Defaults to `sqlite:///./app.db` |

---

## Project Structure

```
/
├── main.py              # FastAPI app entry point
├── instagram.py         # Instagram Graph API client
├── models.py            # SQLAlchemy models
├── database.py          # DB session setup
├── routes/
│   ├── webhook.py       # Webhook endpoints (GET verification + POST events)
│   ├── dashboard.py     # Dashboard HTML routes
│   └── api.py           # REST API for campaigns & config
├── static/
│   ├── css/style.css    # Dashboard styles
│   └── js/app.js        # Dashboard JavaScript
├── templates/
│   └── dashboard.html   # Jinja2 dashboard template
├── .env.example         # Environment variable template
├── Dockerfile
├── railway.toml
├── render.yaml
└── requirements.txt
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/webhook` | Facebook webhook verification |
| `POST` | `/webhook` | Receive Instagram events |
| `GET` | `/api/config` | Get config status |
| `POST` | `/api/config` | Save credentials |
| `GET` | `/api/campaigns` | List all campaigns |
| `POST` | `/api/campaigns` | Create campaign |
| `PUT` | `/api/campaigns/{id}` | Update campaign |
| `PATCH` | `/api/campaigns/{id}/toggle` | Toggle active/inactive |
| `DELETE` | `/api/campaigns/{id}` | Delete campaign |
| `GET` | `/api/post-preview?post_id=...` | Fetch post thumbnail/caption |
| `GET` | `/api/stats` | Automation statistics |
| `GET` | `/api/logs` | Recent activity logs |

---

## Security

- Webhook signatures are verified using `X-Hub-Signature-256` + your App Secret
- Credentials are stored in the SQLite DB and never exposed to the frontend
- `.env` values are the source of truth at startup; dashboard settings override them in DB

---

## Limitations

- Uses only the **official Instagram Graph API** — no Selenium, no unofficial libraries
- SQLite is suitable for single-server deployments; migrate to PostgreSQL for high-volume use by changing `DATABASE_URL`
- Instagram rate limits apply (approximately 200 calls/hour per user token)

---

## License

MIT
