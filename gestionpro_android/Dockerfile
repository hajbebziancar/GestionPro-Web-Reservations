FROM python:3.12-slim
WORKDIR /app
COPY relay.py /app/relay.py
COPY mobile /app/mobile
ENV PORT=8766
EXPOSE 8766
CMD ["python", "relay.py"]
