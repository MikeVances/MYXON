#!/bin/bash
# Стартовый скрипт тестового контейнера.
# Запускает fake_controller и MYXON-агент параллельно.
# При падении любого из процессов — контейнер останавливается (для легкой диагностики).

set -e

echo "=== MYXON Test Device ==="
echo "  Serial:  ${MYXON_SERIAL}"
echo "  Server:  ${MYXON_CLOUD_URL}"
echo "  Port:    ${CONTROLLER_PORT:-8080}"
echo ""

# Запустить фейковый контроллер в фоне
python /app/fake_controller.py &
CONTROLLER_PID=$!
echo "[start] fake_controller PID=$CONTROLLER_PID"

# Подождать пока контроллер поднимется
sleep 1

# Запустить MYXON-агент (он будет держать туннель)
python /app/myxon_agent.py &
AGENT_PID=$!
echo "[start] myxon_agent PID=$AGENT_PID"

# Ждём завершения любого из процессов
wait -n $CONTROLLER_PID $AGENT_PID
echo "[start] One of the processes exited — stopping container"
kill $CONTROLLER_PID $AGENT_PID 2>/dev/null
exit 1
