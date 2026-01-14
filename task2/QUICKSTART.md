# Быстрый старт

Краткая инструкция для быстрого запуска и тестирования динамического масштабирования.

## Предварительные требования

```bash
# Проверка установленных инструментов
minikube version
kubectl version --client
python --version
pip --version
helm version
```

Если что-то не установлено:

```bash
# macOS (через Homebrew)
brew install minikube kubectl helm python3

# Установка Locust
pip3 install locust
```

## Часть 1: Масштабирование по памяти (15 минут)

### 1. Запуск кластера

```bash
# Старт Minikube с metrics-server
minikube start --addons=metrics-server --memory=4096 --cpus=2

# Проверка
kubectl get nodes
kubectl get pods -n kube-system | grep metrics-server
```

### 2. Развертывание приложения

```bash
# Применить манифесты
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa-memory.yaml

# Проверка
kubectl get pods -l app=scalable-pod-identifier
kubectl get hpa
```

### 3. Подготовка к тестированию

```bash
# Получить URL сервиса
export SERVICE_URL=$(minikube service scalable-pod-identifier-service --url)
echo $SERVICE_URL

# Запустить Dashboard (в отдельном терминале)
minikube dashboard
```

### 4. Генерация нагрузки

```bash
# Запуск Locust
locust -f locustfile.py --host=$SERVICE_URL

# Открыть в браузере: http://localhost:8089
# Настроить:
# - Number of users: 100
# - Spawn rate: 10
# Нажать "Start swarming"
```

### 5. Мониторинг (в отдельном терминале)

```bash
# Следить за HPA
watch -n 2 kubectl get hpa scalable-pod-identifier-hpa-memory

# Следить за подами
watch -n 2 'kubectl get pods -l app=scalable-pod-identifier'
```

### 6. Создание скриншотов

Сделать скриншоты:
- ✅ HPA с TARGETS выше 80% и увеличенным REPLICAS
- ✅ Несколько подов в статусе Running
- ✅ Dashboard с графиками утилизации памяти

### 7. Очистка (после тестирования)

```bash
kubectl delete -f hpa-memory.yaml
```

---

## Часть 2: Масштабирование по RPS (30 минут)

### 1. Установка Prometheus

```bash
# Добавить Helm репозиторий
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Установить Prometheus Operator
helm install prometheus-operator prometheus-community/kube-prometheus-stack \
  --namespace default \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false

# Ожидание готовности (может занять 2-3 минуты)
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus --timeout=300s
```

### 2. Настройка сбора метрик

```bash
# Применить ServiceMonitor
kubectl apply -f servicemonitor.yaml

# Проверка (подождать 30 секунд)
kubectl get servicemonitor

# Открыть Prometheus UI (в отдельном терминале)
kubectl port-forward svc/prometheus-operator-kube-prom-prometheus 9090:9090
# Открыть в браузере: http://localhost:9090
```

### 3. Проверка метрик в Prometheus

В Prometheus UI (http://localhost:9090):
1. Перейти в "Graph"
2. Ввести запрос: `http_requests_total`
3. Нажать "Execute"
4. Убедиться, что метрика собирается

**Сделать скриншот** метрики в Prometheus

### 4. Установка Prometheus Adapter

```bash
# Установить Prometheus Adapter
helm install prometheus-adapter prometheus-community/prometheus-adapter \
  -f prometheus-adapter-values.yaml \
  --namespace default

# Ожидание готовности
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus-adapter --timeout=180s

# Проверка кастомных метрик (подождать 1 минуту)
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | jq . | grep http_requests_per_second
```

Должна появиться строка: `"name": "pods/http_requests_per_second"`

### 5. Применение HPA для RPS

```bash
# Применить новый HPA
kubectl apply -f hpa-rps.yaml

# Проверка
kubectl get hpa scalable-pod-identifier-hpa-rps
```

### 6. Генерация нагрузки

```bash
# Если Locust не запущен
export SERVICE_URL=$(minikube service scalable-pod-identifier-service --url)
locust -f locustfile.py --host=$SERVICE_URL

# Открыть в браузере: http://localhost:8089
# Настроить:
# - Number of users: 200
# - Spawn rate: 20
# Нажать "Start swarming"
```

### 7. Мониторинг

```bash
# Следить за HPA (в отдельном терминале)
watch -n 2 kubectl get hpa scalable-pod-identifier-hpa-rps

# Следить за подами
watch -n 2 'kubectl get pods -l app=scalable-pod-identifier'

# Метрики подов
watch -n 5 kubectl top pods -l app=scalable-pod-identifier
```

В Prometheus UI посмотреть распределение нагрузки:
```
sum(rate(http_requests_total{namespace="default"}[30s])) by (pod)
```

### 8. Создание скриншотов

Сделать скриншоты:
- ✅ Метрики в Prometheus UI
- ✅ HPA с TARGETS выше 10/10
- ✅ Несколько подов в статусе Running
- ✅ График RPS по подам в Prometheus

---

## Полная очистка

```bash
# Удалить все ресурсы
kubectl delete -f deployment.yaml
kubectl delete -f service.yaml
kubectl delete -f hpa-rps.yaml
kubectl delete -f servicemonitor.yaml

# Удалить Helm releases
helm uninstall prometheus-operator
helm uninstall prometheus-adapter

# Остановить Minikube (опционально)
minikube stop

# Или полностью удалить кластер
minikube delete
```

---

## Troubleshooting

### Проблема: HPA показывает `<unknown>`

**Решение:**
```bash
# Проверить metrics-server
kubectl get deployment metrics-server -n kube-system

# Если не запущен
minikube addons enable metrics-server

# Подождать 1-2 минуты
```

### Проблема: Метрики не появляются в Prometheus

**Решение:**
```bash
# Проверить ServiceMonitor
kubectl describe servicemonitor scalable-pod-identifier-sm

# Проверить Service labels
kubectl get svc scalable-pod-identifier-service -o yaml | grep -A 5 "labels:"

# Проверить targets в Prometheus UI:
# Status -> Targets -> должен быть UP
```

### Проблема: Кастомная метрика недоступна

**Решение:**
```bash
# Проверить логи adapter
kubectl logs -l app.kubernetes.io/name=prometheus-adapter

# Проверить подключение к Prometheus
kubectl get svc | grep prometheus

# Переустановить adapter с правильным URL
helm uninstall prometheus-adapter
helm install prometheus-adapter prometheus-community/prometheus-adapter \
  -f prometheus-adapter-values.yaml
```

### Проблема: Поды не масштабируются

**Решение:**
```bash
# Проверить события
kubectl get events --sort-by='.lastTimestamp' | tail -20

# Проверить describe HPA
kubectl describe hpa scalable-pod-identifier-hpa-rps

# Проверить ресурсы кластера
kubectl describe nodes
```

### Проблема: Locust не подключается к сервису

**Решение:**
```bash
# Проверить сервис
kubectl get svc scalable-pod-identifier-service

# Получить правильный URL
minikube service scalable-pod-identifier-service --url

# Проверить доступность
curl $(minikube service scalable-pod-identifier-service --url)
```

---

## Полезные команды для демонстрации

```bash
# Полный статус системы
kubectl get all -l app=scalable-pod-identifier

# Детальная информация о HPA
kubectl describe hpa

# События масштабирования
kubectl get events --sort-by='.lastTimestamp' | grep -i scale

# Метрики всех подов
kubectl top pods

# Логи пода
kubectl logs <pod-name>

# Проверка работы приложения
curl $(minikube service scalable-pod-identifier-service --url)
curl $(minikube service scalable-pod-identifier-service --url)/metrics
```

---

## Временные затраты

- **Подготовка окружения**: 5-10 минут (первый раз)
- **Часть 1 (Память)**: 15-20 минут
- **Часть 2 (RPS)**: 30-40 минут
- **Создание скриншотов**: 10 минут
- **Всего**: ~1-1.5 часа

## Дополнительные ресурсы

- [Kubernetes HPA Docs](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Minikube Docs](https://minikube.sigs.k8s.io/docs/)
- [Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator)
- [Locust Docs](https://docs.locust.io/)
