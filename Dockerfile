FROM hermes-agent:latest

RUN pip install --no-cache-dir aiohttp cryptography numpy

COPY healthcheck.sh /opt/data/healthcheck.sh
RUN chmod +x /opt/data/healthcheck.sh

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD /opt/data/healthcheck.sh
