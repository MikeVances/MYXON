FROM python:3.12-slim

# Системные зависимости
RUN apt-get update -q && \
    apt-get install -y -q --no-install-recommends \
      wget curl ca-certificates iproute2 && \
    rm -rf /var/lib/apt/lists/*

# Установить frpc (туннельный клиент)
ARG FRPC_VERSION=0.61.1
RUN wget -q "https://github.com/fatedier/frp/releases/download/v${FRPC_VERSION}/frp_${FRPC_VERSION}_linux_amd64.tar.gz" \
      -O /tmp/frp.tar.gz && \
    tar -xzf /tmp/frp.tar.gz -C /tmp/ && \
    mv "/tmp/frp_${FRPC_VERSION}_linux_amd64/frpc" /usr/local/bin/frpc && \
    chmod +x /usr/local/bin/frpc && \
    rm -rf /tmp/frp*

# Python-зависимости агента (минимальный набор)
RUN pip install --no-cache-dir httpx

WORKDIR /app

# Копируем агент и фейковый контроллер
COPY ../edge-agent/myxon_agent.py ./myxon_agent.py
COPY fake_controller.py ./fake_controller.py
COPY start.sh ./start.sh
RUN chmod +x start.sh

# ── Переменные окружения (переопределяются при docker run) ──────────────────
ENV MYXON_CLOUD_URL=http://192.168.10.243
ENV MYXON_SERIAL=MX-2024-00001
ENV MYXON_HEARTBEAT_INTERVAL=15
ENV MYXON_DISCOVERY_INTERVAL=60
ENV CONTROLLER_PORT=8080

# Фиксируем ресурс вручную — агент не будет сканировать LAN
# host=127.0.0.1 — контроллер в том же контейнере
ENV MYXON_RESOURCES='[{"id":"hmi-panel","protocol":"http","host":"127.0.0.1","port":8080,"name":"Climate Controller HMI"}]'

EXPOSE 8080

CMD ["./start.sh"]
