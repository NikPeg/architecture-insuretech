# Динамическое масштабирование контейнеров в Kubernetes

## Описание

Реализовано динамическое масштабирование приложения в Kubernetes для решения проблемы нестабильной работы системы в периоды пиковой нагрузки. Решение включает два подхода:

1. **Часть 1**: Масштабирование на основе утилизации памяти (встроенная метрика Kubernetes)
2. **Часть 2**: Масштабирование на основе количества запросов в секунду (кастомная метрика из Prometheus)

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

## Часть 1. Масштабирование по памяти

### Компоненты

- **Окружение**: Minikube с metrics-server
- **Приложение**: Развернуто через `deployment.yaml`
  - Начальное количество реплик: 1
  - Лимит памяти: 30Mi
  - Requests память: 20Mi
  - Порт: 8080
- **Сервис**: NodePort для доступа к приложению (`service.yaml`)
- **HPA**: Horizontal Pod Autoscaler (`hpa-memory.yaml`)
  - Целевая утилизация памяти: 80%
  - Минимум реплик: 1, максимум реплик: 10

### Нагрузочное тестирование

Для генерации нагрузки использован Locust с параметрами:
- Пользователей: 100
- Spawn rate: 10 пользователей/сек
- Сценарий: GET-запросы с интервалом 1-5 секунд

### Результаты

- При росте нагрузки утилизация памяти подов достигла 122%
- HPA увеличил количество реплик с 1 до 7
- Время масштабирования: ~3 минуты
- После снижения нагрузки система вернулась к 1 реплике за ~5-7 минут

**Документация:**
- `screenshots/part1_hpa_status.png` - статус HPA с метриками
- `screenshots/part1_pods_scaling.png` - список подов
- `screenshots/part1_dashboard.png` - Dashboard Kubernetes
- `logs/part1_memory/` - детальные логи тестирования

## Часть 2. Масштабирование по RPS

### Компоненты

- **Prometheus**: Установлен через Helm (kube-prometheus-stack)
- **ServiceMonitor**: Настроен для сбора метрики `http_requests_total` каждые 15 секунд
- **Prometheus Adapter**: Преобразует метрику в `http_requests_per_second` для HPA
- **HPA**: Horizontal Pod Autoscaler (`hpa-rps.yaml`)
  - Целевое значение: 10 RPS на под
  - Минимум реплик: 1, максимум реплик: 10
  - Политики масштабирования:
    - Scale Up: 0 секунд стабилизации, до +100% или +2 пода за 30 секунд
    - Scale Down: 60 секунд стабилизации, до -50% за 60 секунд

### Нагрузочное тестирование

Параметры Locust:
- Пользователей: 200
- Spawn rate: 20 пользователей/сек
- RPS: ~150-200 запросов в секунду

### Результаты

- При росте нагрузки RPS превысил 227 (226675m/10)
- HPA увеличил количество реплик с 1 до 10 (максимум)
- Время масштабирования: 30-60 секунд (быстрее, чем по памяти)
- После снижения нагрузки система вернулась к 1 реплике за ~2 минуты
- Нагрузка равномерно распределена между всеми подами

**Документация:**
- `screenshots/part2_prometheus_metrics.png` - метрики в Prometheus UI
- `screenshots/part2_hpa_status.png` - статус HPA с метриками RPS
- `screenshots/part2_pods_scaling.png` - список подов
- `logs/part2_rps/` - детальные логи тестирования

## Анализ результатов

### Сравнение подходов

| Критерий | По памяти | По RPS |
|----------|-----------|---------|
| **Время реакции** | 2-3 минуты | 30-60 секунд |
| **Точность** | Косвенная метрика | Прямая метрика нагрузки |
| **Сложность настройки** | Низкая | Высокая |
| **Дополнительные компоненты** | Нет | Prometheus, Adapter |
| **Соответствие нагрузке** | Среднее | Высокое |

### Рекомендации

Для production-среды оптимальным решением является комбинированный подход с масштабированием по нескольким метрикам:
- RPS - основная метрика (прямое отражение нагрузки)
- CPU и память - дополнительная защита от перегрузок
- Cluster Autoscaler - управление узлами кластера

## Технические детали

### Проверка работы

```bash
# Статус HPA
kubectl get hpa
kubectl describe hpa scalable-pod-identifier-hpa-rps

# Статус подов
kubectl get pods -l app=scalable-pod-identifier
kubectl top pods -l app=scalable-pod-identifier

# Метрики Prometheus
kubectl port-forward svc/prometheus-operator-kube-prom-prometheus 9090:9090
# http://localhost:9090 - запрос: rate(http_requests_total[1m])

# Кастомные метрики
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1
```

## Альтернативные механизмы масштабирования

### Vertical Pod Autoscaler (VPA)

VPA автоматически корректирует requests и limits CPU/памяти для контейнеров на основе исторического использования ресурсов.

#### Когда использовать VPA:
- **Stateful приложения**: Базы данных, очереди сообщений
- **Ресурсоёмкие задачи**: ML/AI обработка, рендеринг
- **CronJobs**: Регулярные задачи с переменной нагрузкой
- **Legacy приложения**: Не поддерживающие горизонтальное масштабирование

#### Пример конфигурации VPA:
```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: scalable-pod-identifier-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: scalable-pod-identifier
  updatePolicy:
    updateMode: "Auto"  # Также: "Off", "Initial"
  resourcePolicy:
    containerPolicies:
    - containerName: scalable-pod-identifier
      minAllowed:
        memory: "50Mi"
        cpu: "50m"
      maxAllowed:
        memory: "500Mi"
        cpu: "500m"
```

#### Режимы работы VPA:
- **Off**: Только рекомендации, без автоматического применения
- **Initial**: Применяется только при создании пода
- **Auto**: Автоматическое обновление (требует перезапуск пода)

#### Сравнение HPA vs VPA:

| Критерий | HPA | VPA |
|----------|-----|-----|
| **Тип масштабирования** | Горизонтальное (количество подов) | Вертикальное (ресурсы на под) |
| **Скорость реакции** | Быстрая (секунды) | Медленная (минуты, требует перезапуск) |
| **Подходит для** | Stateless приложения | Stateful приложения |
| **Перезапуск подов** | Нет | Да (в режиме Auto) |
| **Использование с другим** | ⚠️ Не использовать с VPA | ⚠️ Не использовать с HPA |

#### ⚠️ Важно: 
Не рекомендуется использовать HPA и VPA одновременно для одних и тех же метрик (CPU/Memory), так как они будут конкурировать друг с другом. Допустимо использовать HPA на кастомных метриках вместе с VPA на CPU/Memory.

### KEDA (Kubernetes Event-Driven Autoscaler)

KEDA расширяет возможности HPA, позволяя масштабировать приложения на основе событий из внешних источников.

#### Преимущества KEDA:
- **Масштабирование до нуля**: Может уменьшить количество реплик до 0 при отсутствии событий
- **Широкий выбор scaler'ов**: 50+ встроенных интеграций (Kafka, RabbitMQ, Azure Queue, AWS SQS, Redis, Prometheus и др.)
- **Event-driven**: Идеально для event-driven архитектур
- **Упрощение**: Не требует Prometheus Adapter для внешних метрик

#### Пример: Масштабирование на основе очереди RabbitMQ

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: rabbitmq-consumer-scaler
spec:
  scaleTargetRef:
    name: scalable-pod-identifier
  minReplicaCount: 0   # Масштабирование до нуля!
  maxReplicaCount: 30
  pollingInterval: 30
  cooldownPeriod: 300
  triggers:
  - type: rabbitmq
    metadata:
      queueName: tasks
      queueLength: "20"  # Целевое количество сообщений на под
      host: amqp://user:password@rabbitmq:5672
```

#### Пример: Масштабирование на основе Kafka lag

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: kafka-consumer-scaler
spec:
  scaleTargetRef:
    name: scalable-pod-identifier
  minReplicaCount: 1
  maxReplicaCount: 20
  triggers:
  - type: kafka
    metadata:
      bootstrapServers: kafka:9092
      consumerGroup: my-group
      topic: events
      lagThreshold: "100"  # Максимальное отставание
```

#### Когда использовать KEDA:
- ✅ Event-Driven архитектуры с очередями сообщений
- ✅ Обработка асинхронных задач (workers)
- ✅ Serverless функции в Kubernetes
- ✅ Периодическая обработка с масштабированием до нуля
- ✅ Интеграция с внешними метриками без сложной настройки

#### Установка KEDA:
```bash
# Через Helm
helm repo add kedacore https://kedacore.github.io/charts
helm install keda kedacore/keda --namespace keda --create-namespace

# Проверка
kubectl get pods -n keda
```

### Рекомендации по выбору механизма

| Сценарий | Рекомендуемый механизм |
|----------|------------------------|
| Stateless web-приложение (REST API) | **HPA** (CPU/Memory/RPS) |
| Stateful база данных | **VPA** |
| Event-driven обработка сообщений | **KEDA** + HPA |
| ML/AI batch-обработка | **VPA** или KEDA (для CronJob) |
| Serverless функции | **KEDA** (с scale to zero) |
| Микросервисы с высокой нагрузкой | **HPA + Cluster Autoscaler** |

### Комбинированное использование

Для максимальной эффективности можно комбинировать механизмы:

**1. HPA + Cluster Autoscaler** (текущее решение):
- HPA масштабирует поды
- Cluster Autoscaler добавляет узлы при нехватке ресурсов
- ✅ Идеально для production web-приложений

**2. KEDA + VPA** (для worker'ов):
- KEDA масштабирует количество worker'ов по очереди
- VPA оптимизирует ресурсы для каждого worker'а
- ✅ Эффективно для обработки асинхронных задач

**3. KEDA + Cluster Autoscaler** (для event-driven систем):
- KEDA масштабирует на основе событий (включая до нуля)
- Cluster Autoscaler управляет узлами
- ✅ Максимальная экономия при переменной нагрузке

## Выводы

1. HPA эффективно масштабирует приложение в ответ на изменение нагрузки
2. Масштабирование по RPS быстрее (30-60 сек) и точнее, чем по памяти (2-3 мин)
3. Оба подхода стабильно работают и возвращаются к минимальному количеству реплик при снижении нагрузки
4. Для production-среды рекомендуется комбинированный подход с несколькими метриками
5. **VPA** подходит для stateful приложений и ресурсоёмких задач
6. **KEDA** идеален для event-driven архитектур и позволяет масштабировать до нуля
7. Комбинирование механизмов (HPA + Cluster Autoscaler, KEDA + VPA) даёт максимальную гибкость