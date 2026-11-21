FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

WORKDIR /opt/rlsmatrix

LABEL org.opencontainers.image.title="RLSMatrix" \
      org.opencontainers.image.description="Mutation testing for PostgreSQL Row-Level Security policies" \
      org.opencontainers.image.licenses="MIT"

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir ".[ui]" \
    && groupadd --system --gid 10001 rlsmatrix \
    && useradd --system --uid 10001 --gid rlsmatrix --home-dir /tmp rlsmatrix

COPY src/rlsmatrix/examples ./examples
COPY .streamlit ./.streamlit

USER 10001:10001
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=2).read()" || exit 1

CMD ["streamlit", "run", "src/rlsmatrix/ui/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
