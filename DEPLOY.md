# Deploying ITSM Suite (VPS + Docker Compose)

1. **Server**: any Linux VPS (1–2 GB RAM) with Docker + the compose plugin. Point your domain's DNS A record at it.
2. **Copy the project** to the server (git clone or scp), then `cp .env.example .env` and fill in every value
   (SECRET_KEY, POSTGRES_PASSWORD, ADMIN_PASSWORD, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, email).
3. **TLS certificate** (Let's Encrypt), saved to `nginx/certs/fullchain.pem` and `nginx/certs/privkey.pem`:
   ```bash
   sudo certbot certonly --standalone -d helpdesk.example.com   # port 80 must be free
   mkdir -p nginx/certs
   sudo cp /etc/letsencrypt/live/helpdesk.example.com/{fullchain,privkey}.pem nginx/certs/
   ```
   Renew every ~60 days and re-copy, then `docker compose restart nginx`.
4. **Start** (the `-f` skips the dev override file):
   ```bash
   docker compose -f docker-compose.yml up -d --build
   docker compose -f docker-compose.yml logs -f web
   ```
   On first start it migrates, collects static files, seeds categories, SLA policies and the `admin` user.
5. Visit `https://your-domain/`, sign in as `admin` with ADMIN_PASSWORD, and create agent/user accounts under Users.
6. **SLA checks** run automatically every 5 minutes in the `sla_worker` container.
7. **Backups** (daily via cron):
   ```bash
   docker compose -f docker-compose.yml exec -T db pg_dump -U itsm_user itsm_db > backup-$(date +%F).sql
   ```
   Also back up the `media_files` volume (uploaded attachments).
8. **Update**: `git pull && docker compose -f docker-compose.yml up -d --build`.

Local development: `USE_SQLITE=True DEBUG=True python manage.py runserver`.

---

# Alternative: managed platform (Render)

No server to maintain; Render builds the `Dockerfile`, provides HTTPS and Postgres.

1. Push this project to a GitHub repository (`.env`, `db.sqlite3` and credentials are git-ignored).
2. In Render: **New → Blueprint**, select the repo. It reads `render.yaml` and creates the web service, the
   Postgres database, and a cron job that runs `check_sla` every 5 minutes.
3. When prompted, fill in `ADMIN_PASSWORD`, `ALLOWED_HOSTS` (e.g. `itsm-web.onrender.com`),
   `CSRF_TRUSTED_ORIGINS` (e.g. `https://itsm-web.onrender.com`) and the SMTP values.
   `SECRET_KEY` is generated for you.
4. After the first deploy, sign in at the service URL as `admin`.
5. Custom domain: add it under the service's Settings, then add it to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

**Known limitation:** on this route there is no nginx, so uploaded files (ticket attachments, avatars) are not
served in production and Render's disk is wiped on redeploy unless you attach a persistent disk and add a media
route. Static files are fine (served by WhiteNoise). The VPS route above does not have this limitation.
Plan names in `render.yaml` (`starter`, `basic-256mb`) may need adjusting to Render's current plans.
