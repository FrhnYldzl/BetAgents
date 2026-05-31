# BetAgents — Railway/production imajı
# Streamlit alt-dizinde (08_AI_TRADER/) olduğu için start komutu açıkça verilir.
# Worker servisi aynı imajı kullanır; start komutunu Railway UI'da
# `python worker.py` olarak override eder.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app

# Önce sadece requirements → katman cache (kod değişince pip tekrar çalışmasın)
# SLIM runtime seti (lightgbm/scipy/sklearn/playwright YOK → hızlı, güvenilir build)
COPY requirements-railway.txt .
RUN pip install -r requirements-railway.txt

# Uygulama kodu
COPY . .

EXPOSE 8080

# Tek imaj; ROLE env değişkeni web/worker'ı seçer (start.py).
CMD ["python", "start.py"]
