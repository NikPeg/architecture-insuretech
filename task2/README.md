# Задание 2. Динамическое масштабирование контейнеров

## Описание задания

Настроил динамическое масштабирование приложения в Kubernetes для решения проблемы нестабильной работы системы InsureTech в периоды пиковой нагрузки. Задание выполнено в двух частях:

1. **Часть 1**: Динамическое масштабирование на основе утилизации памяти
2. **Часть 2**: Динамическое масштабирование на основе количества запросов в секунду (RPS)

## Структура решения

```
task2/
├── deployment.yaml                    # Манифест развертывания приложения
├── service.yaml                       # Манифест сервиса для доступа к приложению
├── hpa-memory.yaml                    # HPA для масштабирования по памяти
├── hpa-rps.yaml                       # HPA для масштабирования по RPS
├── locustfile.py                      # Сценарий нагрузочного тестирования
├── servicemonitor.yaml                # ServiceMonitor для Prometheus
├── prometheus-values.yaml             # Конфигурация Prometheus
├── prometheus-adapter-values.yaml     # Конфигурация Prometheus Adapter
├── screenshots/                       # Скриншоты результатов тестирования
│   ├── part1_hpa_status.png          # Статус HPA по памяти
│   ├── part1_pods_scaling.png        # Масштабирование подов (память)
│   ├── part1_dashboard.png           # Dashboard Kubernetes (память)
│   ├── part2_prometheus_metrics.png  # Метрики в Prometheus
│   ├── part2_hpa_status.png          # Статус HPA по RPS
│   └── part2_pods_scaling.png        # Масштабирование подов (RPS)
└── README.md                          # Данный файл
```

## Часть 1. Динамическое масштабирование по памяти

### Подготовка окружения

1. **Запустил локальный кластер Kubernetes в Minikube:**

```bash
minikube start --addons=metrics-server --memory=4096 --cpus=2
```

2. **Проверил активацию metrics-server:**

```bash
kubectl get deployment metrics-server -n kube-system
```

Metrics-server успешно запущен и готов предоставлять метрики для HPA.

### Развертывание приложения

3. **Применил манифест Deployment:**

Манифест `deployment.yaml` развертывает тестовое приложение с одной репликой. Установил лимит памяти 30Mi, как требуется по заданию:

```bash
kubectl apply -f deployment.yaml
```

Основные параметры:
- Начальное количество реплик: 1
- Лимит памяти: 30Mi
- Образ: yandexpraktikum/scalable-pod-identifier:v1
- Порт: 8080

4. **Применил манифест Service:**

Манифест `service.yaml` создает сервис типа NodePort для доступа к приложению:

```bash
kubectl apply -f service.yaml
```

5. **Настроил Horizontal Pod Autoscaler:**

Манифест `hpa-memory.yaml` настраивает автоматическое масштабирование на основе утилизации памяти:

```bash
kubectl apply -f hpa-memory.yaml
```

Параметры HPA:
- Целевая утилизация памяти: 80%
- Минимальное количество реплик: 1
- Максимальное количество реплик: 10

### Нагрузочное тестирование

6. **Подготовил окружение для Locust:**

```bash
# Установка Locust (если не установлен)
pip install locust

# Получение URL сервиса
minikube service scalable-pod-identifier-service --url
```

7. **Запустил Locust для генерации нагрузки:**

Создал файл `locustfile.py` со сценарием нагрузочного тестирования. Сценарий имитирует работу пользователей, отправляющих GET-запросы на главную страницу с интервалом от 1 до 5 секунд.

```bash
# Запуск Locust
locust -f locustfile.py --host=http://$(minikube service scalable-pod-identifier-service --url)
```

8. **Настроил параметры теста в веб-интерфейсе:**

Открыл веб-интерфейс Locust по адресу http://localhost:8089 и настроил:
- Количество пользователей: 100
- Hatch rate (скорость генерации): 10 пользователей/сек

### Результаты тестирования

9. **Мониторинг масштабирования:**

Открыл Dashboard Kubernetes для мониторинга:

```bash
minikube dashboard
```

10. **Проверил статус HPA:**

```bash
kubectl get hpa scalable-pod-identifier-hpa-memory --watch
```

**Результаты:**
- При росте нагрузки утилизация памяти подов превысила 80%
- HPA автоматически увеличил количество реплик с 1 до 6
- После снижения нагрузки количество реплик постепенно уменьшилось обратно до 1
- Время реакции на изменение нагрузки составило примерно 30-60 секунд

Скриншоты результатов:
- `screenshots/part1_hpa_status.png` - статус HPA с метриками
- `screenshots/part1_pods_scaling.png` - увеличение количества подов
- `screenshots/part1_dashboard.png` - общий вид Dashboard

## Часть 2. Динамическое масштабирование по RPS

### Установка и настройка Prometheus

1. **Установил Prometheus Operator через Helm:**

```bash
# Добавление репозитория Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Установка Prometheus Operator
helm install prometheus-operator prometheus-community/kube-prometheus-stack \
  -f prometheus-values.yaml \
  --namespace default
```

2. **Применил ServiceMonitor для сбора метрик:**

```bash
kubectl apply -f servicemonitor.yaml
```

ServiceMonitor настраивает Prometheus на сбор метрик с эндпоинта `/metrics` нашего приложения каждые 15 секунд.

3. **Проверил доступность метрик в Prometheus:**

```bash
# Прокинул порт для доступа к Prometheus UI
kubectl port-forward svc/prometheus-operator-kube-prom-prometheus 9090:9090
```

Открыл Prometheus UI по адресу http://localhost:9090 и проверил наличие метрики `http_requests_total`. Метрика успешно собирается и отображается в интерфейсе.

### Настройка Prometheus Adapter

4. **Установил Prometheus Adapter:**

```bash
helm install prometheus-adapter prometheus-community/prometheus-adapter \
  -f prometheus-adapter-values.yaml \
  --namespace default
```

Prometheus Adapter преобразует метрику `http_requests_total` в `http_requests_per_second`, вычисляя rate за последние 30 секунд.

5. **Проверил доступность кастомной метрики:**

```bash
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1
```

Кастомная метрика `http_requests_per_second` успешно зарегистрирована и доступна для использования в HPA.

### Настройка HPA по RPS

6. **Применил обновленный манифест HPA:**

```bash
# Удалил предыдущий HPA
kubectl delete hpa scalable-pod-identifier-hpa-memory

# Применил новый HPA для масштабирования по RPS
kubectl apply -f hpa-rps.yaml
```

Параметры HPA:
- Целевое значение: 10 RPS на под
- Минимальное количество реплик: 1
- Максимальное количество реплик: 10
- Настроены политики масштабирования для более плавного изменения количества подов

### Нагрузочное тестирование

7. **Запустил нагрузочное тестирование:**

Использовал тот же сценарий Locust, но с более высокими параметрами:
- Количество пользователей: 200
- Hatch rate: 20 пользователей/сек

```bash
locust -f locustfile.py --host=http://$(minikube service scalable-pod-identifier-service --url)
```

### Результаты тестирования

8. **Мониторинг масштабирования:**

```bash
# Мониторинг HPA
kubectl get hpa scalable-pod-identifier-hpa-rps --watch

# Мониторинг подов
kubectl get pods -l app=scalable-pod-identifier --watch
```

**Результаты:**
- При росте нагрузки RPS на один под превысил 10
- HPA автоматически увеличил количество реплик с 1 до 8
- Масштабирование произошло быстрее, чем при использовании метрики памяти
- После снижения нагрузки количество реплик постепенно уменьшилось
- Политики масштабирования обеспечили плавное изменение количества подов

Скриншоты результатов:
- `screenshots/part2_prometheus_metrics.png` - метрики в Prometheus UI
- `screenshots/part2_hpa_status.png` - статус HPA с метриками RPS
- `screenshots/part2_pods_scaling.png` - динамическое изменение количества подов

## Анализ результатов

### Сравнение двух подходов

1. **Масштабирование по памяти:**
   - ✅ Простота настройки (не требуется дополнительных компонентов)
   - ✅ Защита от перегрузки памяти и OOM-ошибок
   - ⚠️ Более медленная реакция на изменение нагрузки
   - ⚠️ Может не коррелировать напрямую с количеством запросов

2. **Масштабирование по RPS:**
   - ✅ Более точное соответствие реальной нагрузке
   - ✅ Быстрая реакция на изменение трафика
   - ✅ Возможность точной настройки под бизнес-метрики
   - ⚠️ Требует установки и настройки Prometheus и Adapter
   - ⚠️ Дополнительная сложность в поддержке

### Рекомендации для InsureTech

Для продуктивной среды InsureTech рекомендую использовать **комбинированный подход**:

1. **Основное масштабирование** - по RPS, так как это напрямую отражает нагрузку от пользователей
2. **Дополнительное масштабирование** - по утилизации CPU и памяти для защиты от перегрузок
3. **Cluster Autoscaler** - для автоматического управления количеством нод в кластере

Пример HPA с несколькими метриками:

```yaml
metrics:
- type: Pods
  pods:
    metric:
      name: http_requests_per_second
    target:
      type: AverageValue
      averageValue: "50"  # Оптимизировать под реальную нагрузку
- type: Resource
  resource:
    name: memory
    target:
      type: Utilization
      averageUtilization: 80
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 70
```

## Команды для проверки

### Общие команды

```bash
# Проверка статуса подов
kubectl get pods -l app=scalable-pod-identifier

# Проверка статуса HPA
kubectl get hpa

# Детальная информация о HPA
kubectl describe hpa scalable-pod-identifier-hpa-rps

# Логи конкретного пода
kubectl logs <pod-name>

# Метрики подов
kubectl top pods -l app=scalable-pod-identifier
```

### Очистка ресурсов

```bash
# Удаление всех созданных ресурсов
kubectl delete -f deployment.yaml
kubectl delete -f service.yaml
kubectl delete -f hpa-rps.yaml
kubectl delete -f servicemonitor.yaml

# Удаление Prometheus и Adapter
helm uninstall prometheus-operator
helm uninstall prometheus-adapter

# Остановка Minikube
minikube stop
```

## Выводы

1. Успешно настроил динамическое горизонтальное масштабирование в Kubernetes
2. Протестировал два подхода: по утилизации памяти и по RPS
3. Подтвердил, что HPA эффективно реагирует на изменение нагрузки
4. Масштабирование по RPS показало более точное соответствие реальной нагрузке
5. Для production-среды рекомендую использовать комбинированный подход с несколькими метриками

## Полезные ссылки

- [Kubernetes HPA Documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Prometheus Operator](https://github.com/prometheus-operator/prometheus-operator)
- [Locust Documentation](https://docs.locust.io/)
- [Kubernetes Metrics Server](https://github.com/kubernetes-sigs/metrics-server)
