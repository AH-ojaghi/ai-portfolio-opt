# data_updater/Dockerfile
FROM python:3.11-slim

# Install cron
RUN apt-get update && apt-get install -y cron wget && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy script
COPY update_data.py /app/update_data.py
COPY crontab /app/crontab

# install python deps
RUN pip install --no-cache-dir yfinance pandas python-dateutil

# Set timezone if provided via env (optional)
ENV TZ=Europe/Berlin

# setup cron
RUN chmod +x /app/update_data.py
RUN crontab /app/crontab

# create log
RUN touch /var/log/cron.log

CMD ["sh", "-c", "cron && tail -f /var/log/cron.log"]
