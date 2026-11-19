# Frontend (Next.js, saída "standalone"). Build a partir da pasta frontend/:
#   docker build -t ribeiro-frontend --build-arg NEXT_PUBLIC_API_URL=https://api.seudominio.com ./frontend
#
# ATENÇÃO: NEXT_PUBLIC_API_URL é gravado no JavaScript durante o build. Mudou o endereço da API? Faça o build de novo.

# ---- 1. dependências ----
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- 2. build ----
FROM node:22-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- 3. imagem final: só o necessário para rodar ----
FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=build /app/public ./public
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD wget -qO- "http://127.0.0.1:${PORT}/login" > /dev/null || exit 1
CMD ["node", "server.js"]
