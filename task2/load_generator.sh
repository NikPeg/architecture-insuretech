#!/bin/bash

# Скрипт для генерации нагрузки на приложение
# Использование: ./load_generator.sh <количество_процессов> <продолжительность_секунд>

PROCESSES=${1:-10}
DURATION=${2:-60}
URL="http://localhost:8080/"

echo "Генерация нагрузки: $PROCESSES параллельных процессов в течение $DURATION секунд"
echo "URL: $URL"
echo "Начало: $(date)"

# Функция для генерации запросов
generate_load() {
    local end_time=$((SECONDS + DURATION))
    while [ $SECONDS -lt $end_time ]; do
        curl -s "$URL" > /dev/null
    done
}

# Запуск параллельных процессов
for i in $(seq 1 $PROCESSES); do
    generate_load &
done

echo "Запущено $PROCESSES процессов генерации нагрузки"
echo "Для мониторинга используйте: kubectl get hpa -w"
echo ""
echo "Ожидание завершения..."

# Ожидание завершения всех процессов
wait

echo "Конец: $(date)"
echo "Нагрузка завершена"
