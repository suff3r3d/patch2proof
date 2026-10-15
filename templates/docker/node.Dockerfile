FROM node:22-bookworm-slim

WORKDIR /app
COPY . /app

# Use package-lock.json/yarn.lock/pnpm-lock.yaml from the case context.
RUN if [ -f package-lock.json ]; then npm ci --ignore-scripts; fi

ENTRYPOINT ["node"]
