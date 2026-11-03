# Backend image for CodeReviewBot.
# Includes the compilers so the verify-and-repair loop works when hosted:
#   - python (base image)   -> Python verifier
#   - gcc                   -> C verifier
#   - default-jdk (javac)   -> Java verifier
# The whole backend runs inside this container, which is the isolation boundary
# for compiling user-submitted code. The compiler subprocess additionally runs
# with CPU/memory rlimits (see verifier.py). For stronger per-request isolation,
# put a sandbox (nsjail/gVisor) or a separate worker in front of the verifier.

FROM python:3.11-slim

# Compilers for C and Java verification.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user (defense in depth for the compile step).
RUN useradd --create-home appuser
USER appuser

ENV CRB_DEBUG=false
EXPOSE 5000

# gthread workers so the NDJSON streaming responses aren't buffered by a sync
# worker; timeout covers slow generations.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --worker-class gthread --threads 8 --timeout 600 app:app"]
