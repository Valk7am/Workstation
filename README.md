<div align="center">

<img src="https://img.shields.io/badge/Django-6.0.4-0C4B33?style=for-the-badge&logo=django&logoColor=white"/>
<img src="https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/yt--dlp-2026.3.17-FF0000?style=for-the-badge&logo=youtube&logoColor=white"/>
<img src="https://img.shields.io/badge/Pillow-imaging-blue?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge"/>

<br/><br/>

# 🛠️ Workstation

**A self-hosted Django toolkit — download media, read files, edit images, and track everything in one place.**

[Features](#-features) · [Tools](#-tools) · [Getting Started](#-getting-started) · [Project Structure](#-project-structure) · [Screenshots](#-screenshots)

</div>

---

## ✨ Features

| | Feature |
|---|---|
| 🔐 | **Authentication** — register, log in, manage your profile with a custom avatar |
| 🔔 | **Notification Bell** — live-updating activity feed in the navbar, polling every 7 s |
| 🌙 | **Dark / Light Mode** — persistent theme toggle baked into the nav |
| ⚡ | **Async Downloads** — long-running jobs run in background threads; stay on the page and get notified when files are ready |
| 🗂️ | **Activity History** — every tool run is logged with status, timestamp, and expiry |
| 🔎 | **Spotlight Search** — `Ctrl/Cmd + K` overlay to jump to any tool instantly |
| ⏱️ | **Auto-Expiry** — downloaded files are cleaned up after 24 hours |

---

## 🧰 Tools

### 📥 Media Downloaders

All downloaders are powered by **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** and run asynchronously. Results appear in-page without a page reload.

| Platform | Description |
|---|---|
| <img src="static/icons/youtube.svg" width="16"/> **YouTube** | Download videos in best quality, merged to MP4 via FFmpeg |
| <img src="static/icons/instagram.svg" width="16"/> **Instagram** | Reels, posts, and stories |
| <img src="static/icons/facebook.svg" width="16"/> **Facebook** | Public videos and reels |
| <img src="static/icons/tiktok.svg" width="16"/> **TikTok** | Videos and audio tracks |
| <img src="static/icons/soundcloud.svg" width="16"/> **SoundCloud** | Tracks and playlists as MP3 |
| <img src="static/icons/x.svg" width="16"/> **X / Twitter** | Video posts and GIFs |

### 🛠️ Utility Tools

| Tool | Description |
|---|---|
| 📄 **Word Counter** | Count words, characters, sentences, and reading time |
| 🔄 **Text Reverser** | Reverse any string instantly |
| 🖼️ **Image Editor** | Crop and rotate images with a live Cropper.js canvas, saved server-side |
| 📧 **.MSG Reader** | Parse Outlook `.msg` files — view body, metadata, embedded images, and HTML |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/download.html) (required for YouTube video merging)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/Valk7am/Workstation.git
cd Workstation

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate

# 5. Create a superuser (optional)
python manage.py createsuperuser

# 6. Run the development server
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

### Configuration

Key settings in `config/settings.py`:

| Setting | Default | Description |
|---|---|---|
| `SECRET_KEY` | dev key | Replace with a strong random key in production |
| `DEBUG` | `True` | Set to `False` in production |
| `DOWNLOAD_RETENTION_HOURS` | `24` | Hours before downloaded files are auto-deleted |
| `MEDIA_ROOT` | `media/` | Directory for user-uploaded files (avatars) |

---

## 📁 Project Structure

```
Workstation/
├── config/                 # Django project settings & root URLs
│   ├── settings.py
│   └── urls.py
│
├── accounts/               # Auth, user profiles, activity history
│   ├── models.py           #   Profile (avatar, bio)
│   ├── views.py            #   register, login, profile
│   └── signals.py          #   Auto-create Profile on user save
│
├── toolset/                # All tools live here
│   ├── models.py           #   ToolActivity (status, expiry, files)
│   ├── views.py            #   Tool dispatch, async workers, activity API
│   ├── activity_helpers.py #   Cleanup, expiry logic
│   └── urls.py
│
├── templates/
│   ├── base.html           # Glass nav, bell, theme toggle, spotlight search
│   ├── home.html
│   ├── accounts/
│   └── toolset/
│
├── static/
│   ├── css/workshop.css    # Full design system (light + dark CSS variables)
│   └── icons/              # Simple Icons brand SVGs
│
├── media/                  # User uploads (gitignored)
├── downloads/              # Temp download files (gitignored)
├── requirements.txt
└── manage.py
```

---

## 🔄 How Async Downloads Work

```
User submits URL
      │
      ▼
  ToolActivity created (status = in_progress)
      │
      ├──► Background thread starts yt-dlp
      │
      └──► Page stays open, polls /activity-status/ every 3 s
                │
                ▼
           status = completed  ──►  Download buttons appear in-page
           status = failed     ──►  Error message shown
```

Files are stored in `downloads/<platform>/` and automatically expired after `DOWNLOAD_RETENTION_HOURS`.

---

## 🎨 Design System

The entire UI is driven by CSS custom properties in `static/css/workshop.css`:

```css
/* Light mode */
--bg:      #f2f2f2;
--surface: #ffffff;
--ink:     #111111;
--accent:  #007ea7;

/* Dark mode */
--bg:      #171717;
--surface: #222222;
--ink:     #f0f0f0;
--accent:  #00a8e8;
```

- **Background**: diagonal dot-grid pattern
- **Navbar**: fixed frosted-glass bar with blur
- **Theme**: toggled via a slider in the avatar dropdown, persisted in `localStorage`

---

## 📸 Screenshots

> _Coming soon — run the project locally to see it in action._

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">
  Built with Django · yt-dlp · Pillow · Cropper.js · Simple Icons
</div>
