# Satu container untuk seluruh aplikasi: FastAPI (internal, 127.0.0.1:8000) + Next.js (port publik Railway).
# Browser hanya mengenal satu domain; Next.js meneruskan /api/* ke backend (lihat next.config.mjs).

# ---- Tahap 1: build frontend ----
FROM node:20-slim AS web
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Panggilan API memakai alamat relatif (same-origin). App ID OneSignal bersifat publik dan ditanam saat build.
ENV NEXT_PUBLIC_API_URL=/api \
    NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_ONESIGNAL_APP_ID=""
ENV NEXT_PUBLIC_ONESIGNAL_APP_ID=$NEXT_PUBLIC_ONESIGNAL_APP_ID
RUN npm run build && npm prune --omit=dev

# ---- Tahap 2: runtime (Python + Node) ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=node:20-slim /usr/local/bin/node /usr/local/bin/node

WORKDIR /srv/api
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY backend/app ./app

WORKDIR /srv/web
COPY --from=web /web/.next ./.next
COPY --from=web /web/node_modules ./node_modules
COPY --from=web /web/public ./public
COPY --from=web /web/package.json /web/next.config.mjs ./

# Railway menyuntikkan PORT. Bila salah satu proses berhenti, container ikut berhenti agar Railway memulai ulang.
CMD ["bash", "-c", "trap 'kill $(jobs -p) 2>/dev/null' TERM INT; (cd /srv/api && exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips='*') & (cd /srv/web && exec node node_modules/next/dist/bin/next start -p ${PORT:-3000} -H 0.0.0.0) & wait -n; code=$?; kill $(jobs -p) 2>/dev/null; exit $code"]
