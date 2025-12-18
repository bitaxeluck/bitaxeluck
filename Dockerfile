# BitAxeLuck Agent Docker Image
# =============================
# Collects metrics from BitAxe and sends to BitAxeLuck
#
# Build:
#   docker build -t bitaxeluck-agent .
#
# Run:
#   docker run -d --name bitaxeluck-agent \
#     -e BITAXE_IP=192.168.1.50 \
#     -e BITAXELUCK_TOKEN=your_token_here \
#     -e INTERVAL=10 \
#     --network host \
#     bitaxeluck-agent

FROM python:3.11-alpine

LABEL maintainer="BitAxeLuck"
LABEL description="BitAxe metrics agent for BitAxeLuck"

# Install dependencies
RUN pip install --no-cache-dir requests

# Create app directory
WORKDIR /app

# Copy agent script
COPY bitaxeluck-agent.py .

# Make executable
RUN chmod +x bitaxeluck-agent.py

# Environment variables (to be overridden at runtime)
ENV BITAXE_IP=""
ENV BITAXELUCK_TOKEN=""
ENV INTERVAL="10"
ENV VERBOSE=""

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f bitaxeluck-agent || exit 1

# Run the agent
CMD python3 bitaxeluck-agent.py \
    --bitaxe-ip ${BITAXE_IP} \
    --token ${BITAXELUCK_TOKEN} \
    --interval ${INTERVAL} \
    ${VERBOSE:+--verbose}
