ARG NODERED_BASE_IMAGE
FROM ${NODERED_BASE_IMAGE}
COPY --chown=node-red:node-red package.json package-lock.json ./
RUN npm ci --omit=dev
