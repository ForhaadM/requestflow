# RequestFlow — Manual AWS Deploy Checklist

This is a walkthrough for deploying RequestFlow to AWS by hand through the
Console, so you actually learn what each piece does. Nothing here is
automated — you click through every step yourself.

Rough shape: **RDS** (managed Postgres) + **EC2** (runs the Docker backend
container) + **S3 + CloudFront** (hosts the static React build). This is a
simple, cheap, understandable setup for a portfolio project — not
production-grade HA (no auto-scaling, no multi-AZ, no load balancer). Good
enough to demo and to talk through in interviews.

---

## 0. Before you start

- [X] Create an AWS account if you don't have one (or use an existing one you're comfortable spending small amounts in)
- [X] **Set a billing alarm** in AWS Budgets (e.g. alert at $5) before creating anything — this is the single easiest way to avoid a surprise bill
- [X] Pick a region close to you (e.g. `us-east-1`) and stick with it for every resource below — cross-region resources can't talk to each other by default

## 1. IAM — don't use your root account day to day

- [ ] In IAM, create a new IAM user for yourself (not root) with console access
- [ ] Attach `AdministratorAccess` for now (fine for a learning project; in a real job you'd scope this down)
- [ ] Enable MFA on both the root account and this IAM user
- [ ] Log out of root, log in as this IAM user for everything below
- [ ] (Optional, more realistic) Later, create a narrower IAM role/policy just for EC2 (e.g. only what's needed to pull from ECR if you go that route) — good talking point for interviews about least-privilege

## 2. RDS — the database

- [ ] RDS console → Create database
- [ ] Engine: PostgreSQL (pick a version matching your local `postgres:16` if possible)
- [ ] Template: **Free tier** (if eligible) or "Dev/Test"
- [ ] DB instance identifier: `requestflow-db`
- [ ] Master username/password: set these — you'll put them in `backend/.env.production` as `POSTGRES_USER` / `POSTGRES_PASSWORD`
- [ ] Instance class: smallest available (e.g. `db.t3.micro` / `db.t4g.micro`)
- [ ] Storage: minimum (20GB gp2/gp3 is plenty for this)
- [ ] **Public access: No** — the DB should only be reachable from your EC2 instance, not the whole internet
- [ ] VPC: leave as default unless you have a reason to customize
- [ ] **Create a new security group for RDS** (e.g. `requestflow-db-sg`) — don't reuse the default one, so you can scope its inbound rule precisely (see step 4)
- [ ] Initial database name: `requestflow` — matches `POSTGRES_DB`
- [ ] Create the database, wait for status "Available" (~5-10 min)
- [ ] Copy the **endpoint** (hostname) from the RDS instance's "Connectivity & security" tab → this is `POSTGRES_HOST`
- [ ] Note the port (default `5432`) → this is `POSTGRES_PORT`

## 3. EC2 — where the backend container runs

- [ ] EC2 console → Launch instance
- [ ] Name: `requestflow-backend`
- [ ] AMI: Amazon Linux 2023 (has good Docker support, free-tier eligible)
- [ ] Instance type: `t2.micro` or `t3.micro` (free-tier eligible)
- [ ] Key pair: create a new one, **download the .pem file and keep it safe** — you can't re-download it later, and you need it to SSH in
- [ ] Network settings → **create a new security group** for this instance (e.g. `requestflow-ec2-sg`) — see step 4 for the actual rules
- [ ] Storage: default (8GB gp3) is fine
- [ ] Launch the instance, wait for it to be "Running" with status checks passed
- [ ] Note its **public IPv4 address / public DNS** — you'll need this to SSH in and later as part of your API URL

## 4. Security groups — who can talk to what

Security groups are stateful firewalls attached to RDS/EC2. Configure them narrowly:

**`requestflow-ec2-sg`** (attached to the EC2 instance), inbound rules:
- [ ] SSH (port 22) from **your IP only** (use the "My IP" option in the console, not `0.0.0.0/0`) — anything open to the world gets bruteforced within hours
- [ ] Custom TCP (port 8000, wherever uvicorn listens) from `0.0.0.0/0` — this is what the frontend will call. (If you later put a load balancer or Nginx/TLS in front, restrict this and only open 80/443.)

**`requestflow-db-sg`** (attached to the RDS instance), inbound rules:
- [ ] PostgreSQL (port 5432) — source: **the `requestflow-ec2-sg` security group itself** (not an IP range). This means "only things using that other security group can reach me," which is exactly the EC2 instance and nothing else on the internet.

## 5. Get Docker running on the EC2 instance

- [ ] SSH in: `ssh -i your-key.pem ec2-user@<ec2-public-dns>`
- [ ] Install Docker: `sudo dnf install -y docker` (Amazon Linux 2023) then `sudo systemctl enable --now docker`
- [ ] Add your user to the docker group so you don't need `sudo` every time: `sudo usermod -aG docker ec2-user` (log out/in after)
- [ ] Verify: `docker --version` and `docker run hello-world`

## 6. Get the backend code + image onto EC2

Two ways to do this — pick whichever, both are common:

**Option A — build directly on EC2 (simplest for a small project):**
- [ ] `git clone` your repo onto the EC2 instance (you may need to set up a deploy key or use HTTPS with a PAT since the repo may be private)
- [ ] `cd backend`
- [ ] Copy `.env.production.example` to `.env`, fill in the **real** RDS host/port/user/password/db name from step 2, a fresh `SECRET_KEY`, and `ALLOWED_ORIGINS` (you'll fill this in properly once you have the CloudFront/S3 URL from step 8 — put a placeholder for now, come back and update it)
- [ ] `docker build -t requestflow-backend .`
- [ ] `docker run -d --restart unless-stopped --env-file .env -p 8000:8000 --name requestflow-backend requestflow-backend`

**Option B — build locally, push to ECR, pull on EC2** (more realistic for a "real" pipeline, more setup):
- [ ] Create an ECR repository in the console
- [ ] Build/tag/push the image from your machine (the console's "View push commands" button gives you the exact `docker` commands)
- [ ] On EC2, authenticate to ECR and `docker pull` the image, then `docker run` as above

- [ ] Check it's up: `curl http://localhost:8000/users` from inside the instance, then `curl http://<ec2-public-dns>:8000/users` from your own machine
- [ ] Check logs if something's wrong: `docker logs requestflow-backend`

## 7. Run the database schema against RDS

Your app currently doesn't have migrations (SQLAlchemy models create tables directly) — check how your models get created locally (e.g. `Base.metadata.create_all`) and make sure that runs once against the new RDS database, either by hitting the app once (if it auto-creates on startup) or running a one-off script. Verify by connecting with `psql` from the EC2 instance:
- [ ] `psql -h <rds-endpoint> -U <user> -d requestflow` and `\dt` to list tables

## 8. Frontend hosting — S3 + CloudFront

- [ ] On your local machine, set `VITE_API_URL=http://<ec2-public-dns>:8000` in `frontend/.env.production` (copy from `.env.production.example`)
- [ ] `cd frontend && npm run build` → produces `frontend/dist`
- [ ] S3 console → Create bucket (e.g. `requestflow-frontend-yourname`), block all public access (CloudFront will access it privately via OAC, not the public bucket policy)
- [ ] Upload the contents of `dist/` to the bucket
- [ ] CloudFront console → Create distribution, origin = your S3 bucket, use **Origin Access Control (OAC)** (CloudFront's current recommended way to let it — and only it — read from a private bucket)
- [ ] Set default root object to `index.html`
- [ ] Since this is a single-page app with client-side routing, add a custom error response: for 403 and 404, return `/index.html` with a 200 status (otherwise refreshing on a non-root route breaks)
- [ ] Wait for the distribution to deploy (~5-15 min), note its `*.cloudfront.net` domain

## 9. Wire CORS to the real frontend URL

- [ ] Back on the EC2 instance, edit `backend/.env`, set `ALLOWED_ORIGINS=https://<your-cloudfront-domain>.cloudfront.net` (comma-separate if you also set up a custom domain)
- [ ] Restart the container: `docker restart requestflow-backend`
- [ ] From the CloudFront URL in a browser, confirm login/register/requests all work end-to-end (open devtools Network tab — a CORS failure shows up clearly there)

## 10. Sanity checks / cleanup

- [ ] Confirm RDS is **not** publicly accessible (step 2) and its security group only allows the EC2 security group in
- [ ] Confirm EC2 SSH is restricted to your IP, not open to the world
- [ ] Note ongoing cost: RDS + EC2 running 24/7 will incur small charges once free tier runs out — **stop (not delete) the EC2 instance and consider stopping/deleting the RDS instance when you're done demoing**, to avoid ongoing charges. Stopped EC2 instances still cost for attached EBS storage but not compute.
- [ ] If you want a custom domain instead of the raw CloudFront URL: Route 53 + ACM certificate (separate, optional follow-up)

---

## What's already done for you (code side)

- `backend/Dockerfile` — builds the FastAPI app into a container image; run `docker build -t requestflow-backend .` from `backend/`
- `backend/database.py` — reads all DB connection info from env vars (`POSTGRES_*`), no hardcoded host; supports `POSTGRES_SSLMODE` for RDS's TLS requirement
- `backend/main.py` — CORS allowed origins now come from `ALLOWED_ORIGINS` env var (comma-separated), defaulting to the local Vite dev origins so local dev is unaffected
- `backend/.env.production.example` — template for the real values you'll fill in during steps 2/4/9 above
- `frontend/src/api/client.js` — already reads `VITE_API_URL` from the environment (defaults to `localhost:8000` for dev)
- `frontend/.env.production.example` — template for pointing the built frontend at your real backend URL

Nothing above provisions real AWS resources or touches your AWS account —
that part is entirely on you, by design.
