ARG FUXA_BASE_IMAGE
FROM ${FUXA_BASE_IMAGE}

# Keep the base application's dependency tree intact. Node can resolve these
# isolated, locked industrial drivers through NODE_PATH before runtime startup.
COPY --chown=1000:1000 package.json package-lock.json /usr/src/app/FUXA/server/rsb-drivers/
RUN cd /usr/src/app/FUXA/server/rsb-drivers && npm ci --omit=dev
ENV NODE_PATH=/usr/src/app/FUXA/server/rsb-drivers/node_modules
