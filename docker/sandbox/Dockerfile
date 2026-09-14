# The Layer 3 sandbox image. See PREREGISTRATION_PHASE3.md, amendments A1 and A2.
#
# Base pinned by digest. The three libraries are the exact versions in
# requirements.txt. Their own dependencies are whatever pip resolves; the
# full resolved set is written to /usr/local/share/sandbox-freeze.txt and
# recorded in A2.
#
# The network is used here, at build time, and never when a tool runs.
#
#   docker build -t honest-mistake-sandbox docker/sandbox

FROM python@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir numpy==2.4.6 pandas==3.0.3 pyarrow==24.0.0 \
    && pip freeze > /usr/local/share/sandbox-freeze.txt
