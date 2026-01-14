# Инструкции для создания скриншотов

Все готово для создания скриншотов! Выполнены оба задания.

## Текущее состояние системы

✅ **Minikube кластер** - запущен и работает
✅ **Приложение** - развернуто и доступно через http://localhost:8080
✅ **Prometheus** - установлен и собирает метрики через http://localhost:9091
✅ **HPA по RPS** - работает и масштабирует систему (10 реплик)
✅ **Нагрузочное тестирование** - выполняется

## Часть 1: Масштабирование по памяти

### Команды для получения данных:

```bash
# 1. Статус HPA (для скриншота part1_hpa_status.png)
kubectl get hpa scalable-pod-identifier-hpa-memory
# Или посмотреть историю масштабирования:
kubectl describe hpa scalable-pod-identifier-hpa-memory

# 2. Список подов (для скриншота part1_pods_scaling.png)
kubectl get pods -l app=scalable-pod-identifier

# 3. Метрики подов (для скриншота part1_dashboard.png)
kubectl top pods -l app=scalable-pod-identifier

# 4. Открыть Dashboard
minikube dashboard
# В Dashboard перейти:
# Workloads -> Horizontal Pod Autoscalers -> scalable-pod-identifier-hpa-memory
# Workloads -> Pods -> фильтр по app=scalable-pod-identifier
```

### Что показать на скриншотах:

**part1_hpa_status.png:**
- TARGETS должно показывать значение выше 80% (например, 95%/80% или 122%/80%)
- REPLICAS должно быть больше 1 (было 4-7 реплик)
- Видно MINPODS=1, MAXPODS=10

**part1_pods_scaling.png:**
- Несколько подов в статусе Running (4-7 штук)
- Разный AGE подов (показывает, что они создавались постепенно)

**part1_dashboard.png:**
- График утилизации памяти или общий вид Dashboard
- Показано масштабирование Deployment

---

## Часть 2: Масштабирование по RPS

### Команды для получения данных:

```bash
# 1. Проверка метрик в Prometheus (для скриншота part2_prometheus_metrics.png)
# Prometheus UI уже доступен через port-forward на http://localhost:9091

# Открыть в браузере: http://localhost:9091
# В поле Query ввести: http_requests_total
# Или: rate(http_requests_total[1m])
# Или: sum(rate(http_requests_total[30s])) by (pod)

# 2. Статус HPA (для скриншота part2_hpa_status.png)
kubectl get hpa scalable-pod-identifier-hpa-rps

# Детальная информация:
kubectl describe hpa scalable-pod-identifier-hpa-rps

# 3. Список подов (для скриншота part2_pods_scaling.png)
kubectl get pods -l app=scalable-pod-identifier

# 4. Проверка кастомной метрики (для скриншота part2_custom_metrics.png)
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | python3 -m json.tool | grep http_requests_per_second

# Значения метрики:
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/default/pods/*/http_requests_per_second" | python3 -m json.tool

# 5. Метрики подов
kubectl top pods -l app=scalable-pod-identifier
```

### Что показать на скриншотах:

**part2_prometheus_metrics.png:**
- Prometheus UI по адресу http://localhost:9091
- Вкладка "Graph"
- Запрос: `http_requests_total` или `rate(http_requests_total[1m])`
- График показывает несколько линий (по одной на каждый под)
- Видно, что метрики собираются

**part2_hpa_status.png:**
- TARGETS показывает значение в формате "XXXm/10" (например, 226675m/10)
- REPLICAS = 10 (максимальное значение)
- Видно, что метрика называется "pods metric http_requests_per_second"

**part2_pods_scaling.png:**
- 10 подов в статусе Running
- Показано масштабирование до максимума

**part2_custom_metrics.png (опционально):**
- Вывод API кастомных метрик
- Видно, что метрика `http_requests_per_second` доступна для подов

---

## Prometheus UI - Как открыть

Prometheus уже доступен через port-forward:

```bash
# Проверить, что port-forward работает:
curl http://localhost:9091/-/healthy

# Открыть в браузере:
open http://localhost:9091
```

### Полезные запросы в Prometheus:

```
# Все запросы к приложению
http_requests_total

# RPS за последнюю минуту
rate(http_requests_total[1m])

# Суммарный RPS по всем подам
sum(rate(http_requests_total[30s]))

# RPS для каждого пода отдельно
sum(rate(http_requests_total[30s])) by (pod)

# RPS для каждого пода с группировкой по endpoint
sum(rate(http_requests_total[30s])) by (pod, endpoint)
```

---

## Текущее состояние (для справки)

### HPA:
```
NAME                              REFERENCE                            TARGETS      MINPODS   MAXPODS   REPLICAS
scalable-pod-identifier-hpa-rps   Deployment/scalable-pod-identifier   226675m/10   1         10        10
```

### Поды:
```
10 подов в статусе Running
```

### События масштабирования:
- Сначала система уменьшилась до 8 реплик (метрики были низкими)
- Затем при увеличении нагрузки масштабировалась до 10 реплик
- HPA реагирует быстро (30-60 секунд)

---

## Если нужно перезапустить тест

### Для Части 1 (память):

```bash
# 1. Применить HPA по памяти
kubectl delete hpa scalable-pod-identifier-hpa-rps
kubectl apply -f hpa-memory.yaml

# 2. Запустить нагрузку
./load_generator.sh 20 90

# 3. Мониторить
kubectl get hpa -w
# или
watch -n 2 kubectl get hpa
```

### Для Части 2 (RPS):

```bash
# 1. Применить HPA по RPS (уже применен)
kubectl get hpa scalable-pod-identifier-hpa-rps

# 2. Запустить нагрузку
./load_generator.sh 30 120

# 3. Мониторить
kubectl get hpa scalable-pod-identifier-hpa-rps -w
```

---

## Остановка нагрузки

```bash
# Остановить load_generator
pkill -f load_generator.sh
pkill -f "curl.*localhost:8080"

# Проверить, что процессы остановлены
ps aux | grep curl
```

---

## Ожидаемое поведение при создании скриншотов

### Часть 1 (Память):
- ✅ HPA увеличил количество реплик с 1 до 6-7
- ✅ Утилизация памяти превысила 80%
- ✅ После снижения нагрузки система вернулась к минимуму

### Часть 2 (RPS):
- ✅ Prometheus собирает метрики http_requests_total
- ✅ Кастомная метрика http_requests_per_second доступна
- ✅ HPA масштабирует на основе RPS
- ✅ При высокой нагрузке достигнут максимум (10 реплик)
- ✅ Масштабирование происходит быстрее, чем по памяти

---

## Полезные команды для отладки

```bash
# Логи приложения
kubectl logs -l app=scalable-pod-identifier --tail=50

# Логи HPA контроллера
kubectl get events --sort-by='.lastTimestamp' | grep -i horizontal

# Проверка Service
kubectl get svc scalable-pod-identifier-service
kubectl get endpoints scalable-pod-identifier-service

# Проверка ServiceMonitor
kubectl get servicemonitor scalable-pod-identifier-sm
kubectl describe servicemonitor scalable-pod-identifier-sm

# Проверка Prometheus targets
# Открыть http://localhost:9091/targets в браузере
```

---

## Итого для сдачи

### Обязательные файлы в task2/:

✅ deployment.yaml - Манифест развертывания
✅ service.yaml - Манифест сервиса
✅ hpa-memory.yaml - HPA для масштабирования по памяти
✅ hpa-rps.yaml - HPA для масштабирования по RPS
✅ servicemonitor.yaml - ServiceMonitor для Prometheus
✅ locustfile.py - Сценарий нагрузочного тестирования
✅ prometheus-adapter-values-fixed.yaml - Конфигурация Prometheus Adapter
✅ README.md - Подробная документация
✅ load_generator.sh - Скрипт генерации нагрузки
✅ app/ - Директория с приложением (app.py, Dockerfile, requirements.txt)

### Обязательные скриншоты:

**Часть 1:**
- [ ] part1_hpa_status.png
- [ ] part1_pods_scaling.png
- [ ] part1_dashboard.png

**Часть 2:**
- [ ] part2_prometheus_metrics.png
- [ ] part2_hpa_status.png
- [ ] part2_pods_scaling.png

Сохраните скриншоты в папку `screenshots/`

---

## Готово к созданию скриншотов!

Все компоненты запущены и работают. Можете начинать делать скриншоты по инструкциям выше.

**Prometheus UI:** http://localhost:9091
**Приложение:** http://localhost:8080
**Minikube Dashboard:** `minikube dashboard`
