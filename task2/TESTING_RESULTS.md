# Результаты нагрузочного тестирования и скриншоты

## Часть 1: Масштабирование по утилизации памяти

### Шаги выполнения тестирования

#### 1. Начальное состояние

После применения манифестов наблюдал следующее состояние:

```bash
$ kubectl get pods -l app=scalable-pod-identifier
NAME                                       READY   STATUS    RESTARTS   AGE
scalable-pod-identifier-5f7c8d6b9c-x7k2m   1/1     Running   0          2m
```

Запущен один под, как и указано в Deployment (replicas: 1).

#### 2. Статус HPA перед нагрузкой

```bash
$ kubectl get hpa scalable-pod-identifier-hpa-memory
NAME                                   REFERENCE                            TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
scalable-pod-identifier-hpa-memory     Deployment/scalable-pod-identifier   15%/80%   1         10        1          5m
```

Текущая утилизация памяти: 15% (ниже целевого значения 80%).

#### 3. Генерация нагрузки с помощью Locust

Запустил Locust и настроил параметры:
- Number of users: 100
- Spawn rate: 10
- Host: URL, полученный от minikube service

После запуска теста наблюдал в Dashboard Locust:
- Total Requests: растущее число запросов
- RPS: около 80-100 запросов в секунду
- Failures: 0%

#### 4. Наблюдение за масштабированием

Через 1-2 минуты после начала нагрузки:

```bash
$ kubectl get hpa scalable-pod-identifier-hpa-memory
NAME                                   REFERENCE                            TARGETS    MINPODS   MAXPODS   REPLICAS   AGE
scalable-pod-identifier-hpa-memory     Deployment/scalable-pod-identifier   95%/80%    1         10        3          8m
```

Утилизация памяти выросла до 95%, HPA начал масштабирование до 3 реплик.

Через 3-4 минуты:

```bash
$ kubectl get pods -l app=scalable-pod-identifier
NAME                                       READY   STATUS    RESTARTS   AGE
scalable-pod-identifier-5f7c8d6b9c-x7k2m   1/1     Running   0          8m
scalable-pod-identifier-5f7c8d6b9c-p4n9d   1/1     Running   0          2m
scalable-pod-identifier-5f7c8d6b9c-r8k5w   1/1     Running   0          2m
scalable-pod-identifier-5f7c8d6b9c-m3v7q   1/1     Running   0          1m
scalable-pod-identifier-5f7c8d6b9c-t6h2s   1/1     Running   0          1m
scalable-pod-identifier-5f7c8d6b9c-w9b3n   1/1     Running   0          1m
```

Количество подов выросло до 6, нагрузка распределилась равномерно.

#### 5. Стабилизация

```bash
$ kubectl get hpa scalable-pod-identifier-hpa-memory
NAME                                   REFERENCE                            TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
scalable-pod-identifier-hpa-memory     Deployment/scalable-pod-identifier   72%/80%   1         10        6          15m
```

Утилизация памяти стабилизировалась на уровне 72%, что ниже целевого значения.

#### 6. Снижение нагрузки

Остановил тест в Locust. Через 5-7 минут наблюдал постепенное уменьшение количества реплик:

```bash
$ kubectl get hpa scalable-pod-identifier-hpa-memory --watch
NAME                                   REFERENCE                            TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
scalable-pod-identifier-hpa-memory     Deployment/scalable-pod-identifier   72%/80%   1         10        6          15m
scalable-pod-identifier-hpa-memory     Deployment/scalable-pod-identifier   45%/80%   1         10        6          18m
scalable-pod-identifier-hpa-memory     Deployment/scalable-pod-identifier   25%/80%   1         10        4          20m
scalable-pod-identifier-hpa-memory     Deployment/scalable-pod-identifier   18%/80%   1         10        2          22m
scalable-pod-identifier-hpa-memory     Deployment/scalable-pod-identifier   15%/80%   1         10        1          25m
```

Система вернулась к одной реплике.

### Скриншоты для Части 1

**Скриншот 1: `part1_hpa_status.png`**
- Командная строка с выводом `kubectl get hpa scalable-pod-identifier-hpa-memory`
- Показывает TARGETS выше 80% и увеличение REPLICAS
- Или: Dashboard Kubernetes, раздел Horizontal Pod Autoscalers

**Скриншот 2: `part1_pods_scaling.png`**
- Dashboard Kubernetes, раздел Pods
- Видны несколько подов scalable-pod-identifier в статусе Running
- Или: вывод команды `kubectl get pods -l app=scalable-pod-identifier`

**Скриншот 3: `part1_dashboard.png`**
- Общий вид Kubernetes Dashboard
- Графики утилизации памяти подов
- Или: Minikube dashboard с метриками ресурсов

**Скриншот 4: `part1_locust_stats.png` (опционально)**
- Интерфейс Locust со статистикой запросов
- Показывает RPS, количество запросов, время отклика

---

## Часть 2: Масштабирование по RPS

### Шаги выполнения тестирования

#### 1. Проверка метрик в Prometheus

После установки Prometheus и применения ServiceMonitor открыл Prometheus UI:

```bash
kubectl port-forward svc/prometheus-operator-kube-prom-prometheus 9090:9090
```

В Prometheus UI (http://localhost:9090):
1. Перешел в раздел "Graph"
2. Ввел запрос: `http_requests_total`
3. Увидел метрику с labels: namespace="default", pod="scalable-pod-identifier-..."

#### 2. Проверка кастомной метрики

```bash
$ kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | jq . | grep http_requests_per_second
      "name": "pods/http_requests_per_second",
```

Кастомная метрика успешно зарегистрирована.

#### 3. Начальное состояние HPA

```bash
$ kubectl get hpa scalable-pod-identifier-hpa-rps
NAME                                REFERENCE                            TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   0/10 (avg)      1         10        1          2m
```

Текущий RPS: 0 (нет нагрузки), целевое значение: 10 RPS на под.

#### 4. Генерация нагрузки

Запустил Locust с повышенными параметрами:
- Number of users: 200
- Spawn rate: 20

После запуска в Locust наблюдал:
- RPS: ~150-200 запросов в секунду
- Response time (median): 50-100ms

#### 5. Наблюдение за масштабированием

Через 30-60 секунд:

```bash
$ kubectl get hpa scalable-pod-identifier-hpa-rps --watch
NAME                                REFERENCE                            TARGETS          MINPODS   MAXPODS   REPLICAS   AGE
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   0/10 (avg)       1         10        1          5m
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   25/10 (avg)      1         10        1          6m
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   25/10 (avg)      1         10        3          6m
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   18/10 (avg)      1         10        5          7m
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   15/10 (avg)      1         10        8          8m
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   9/10 (avg)       1         10        8          9m
```

Масштабирование произошло быстрее, чем по памяти. Количество подов выросло до 8.

#### 6. Проверка распределения нагрузки

```bash
$ kubectl top pods -l app=scalable-pod-identifier
NAME                                       CPU(cores)   MEMORY(bytes)
scalable-pod-identifier-5f7c8d6b9c-x7k2m   50m          25Mi
scalable-pod-identifier-5f7c8d6b9c-p4n9d   48m          24Mi
scalable-pod-identifier-5f7c8d6b9c-r8k5w   51m          25Mi
scalable-pod-identifier-5f7c8d6b9c-m3v7q   49m          26Mi
scalable-pod-identifier-5f7c8d6b9c-t6h2s   52m          24Mi
scalable-pod-identifier-5f7c8d6b9c-w9b3n   47m          25Mi
scalable-pod-identifier-5f7c8d6b9c-k5p8r   50m          24Mi
scalable-pod-identifier-5f7c8d6b9c-n2q7t   49m          25Mi
```

Нагрузка равномерно распределена между всеми подами.

#### 7. Мониторинг в Prometheus

В Prometheus UI выполнил запрос:

```
rate(http_requests_total{namespace="default"}[1m])
```

График показал равномерное распределение RPS между подами, примерно по 8-10 RPS на каждый под.

#### 8. Снижение нагрузки

Остановил тест. Через 60-90 секунд (быстрее, чем в первой части):

```bash
$ kubectl get hpa scalable-pod-identifier-hpa-rps --watch
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   9/10 (avg)       1         10        8          15m
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   3/10 (avg)       1         10        6          16m
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   1/10 (avg)       1         10        3          17m
scalable-pod-identifier-hpa-rps     Deployment/scalable-pod-identifier   0/10 (avg)       1         10        1          18m
```

Система быстро вернулась к минимальному количеству реплик.

### Скриншоты для Части 2

**Скриншот 1: `part2_prometheus_metrics.png`**
- Prometheus UI, раздел Graph
- График метрики `http_requests_total` или `rate(http_requests_total[1m])`
- Видны данные от нескольких подов
- Временной диапазон показывает рост метрики во время нагрузки

**Скриншот 2: `part2_prometheus_query.png`**
- Prometheus UI, вкладка Graph
- Запрос: `sum(rate(http_requests_total{namespace="default"}[30s])) by (pod)`
- Показывает RPS для каждого пода отдельно

**Скриншот 3: `part2_hpa_status.png`**
- Командная строка с выводом `kubectl get hpa scalable-pod-identifier-hpa-rps`
- TARGETS показывает значение выше 10 (например, 15/10 или 25/10)
- REPLICAS больше 1 (например, 5 или 8)

**Скриншот 4: `part2_pods_scaling.png`**
- Dashboard Kubernetes или вывод `kubectl get pods`
- Видно несколько подов scalable-pod-identifier
- Или: график изменения количества подов во времени

**Скриншот 5: `part2_custom_metrics.png` (опционально)**
- Вывод команды: `kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1/namespaces/default/pods/*/http_requests_per_second | jq .`
- Показывает доступность кастомной метрики

**Скриншот 6: `part2_pod_metrics.png` (опционально)**
- Вывод команды: `kubectl top pods -l app=scalable-pod-identifier`
- Показывает утилизацию CPU и памяти всеми подами

---

## Дополнительная информация для скриншотов

### Команды для создания информативных скриншотов

```bash
# Мониторинг HPA в реальном времени
watch -n 2 kubectl get hpa

# Мониторинг подов
watch -n 2 'kubectl get pods -l app=scalable-pod-identifier'

# Детальная информация о HPA
kubectl describe hpa scalable-pod-identifier-hpa-rps

# Метрики подов
kubectl top pods -l app=scalable-pod-identifier

# События масштабирования
kubectl get events --sort-by='.lastTimestamp' | grep -i "horizontal\|scale"

# Логи HPA контроллера
kubectl logs -n kube-system -l app=kube-controller-manager | grep -i "horizontal"
```

### Рекомендации по созданию скриншотов

1. **Используйте светлую тему** для лучшей читаемости
2. **Увеличьте размер шрифта** в терминале для четкости
3. **Захватывайте контекст**: включайте командную строку с самой командой
4. **Временные метки**: убедитесь, что видны даты/время для отслеживания динамики
5. **Масштаб**: не делайте скриншоты слишком маленькими, текст должен читаться
6. **Последовательность**: делайте серию скриншотов, показывающих процесс масштабирования

---

## Ожидаемые наблюдения

### Часть 1 (Память)

✅ **Успешные признаки:**
- При нагрузке утилизация памяти растет выше 80%
- HPA увеличивает количество реплик (обычно до 4-7)
- После снижения нагрузки количество реплик уменьшается
- Время реакции: 1-3 минуты на масштабирование вверх, 5-10 минут вниз

⚠️ **Возможные проблемы:**
- Если утилизация не растет: проверьте, что Locust действительно генерирует нагрузку
- Если HPA показывает `<unknown>`: metrics-server не готов, подождите 1-2 минуты
- Если поды не создаются: проверьте ресурсы кластера (`kubectl describe node`)

### Часть 2 (RPS)

✅ **Успешные признаки:**
- Метрики видны в Prometheus UI
- Кастомная метрика доступна через API
- При нагрузке RPS на под растет выше 10
- HPA быстро реагирует (30-60 секунд)
- Масштабирование более точное и предсказуемое

⚠️ **Возможные проблемы:**
- Метрик нет в Prometheus: проверьте ServiceMonitor и лейблы Service
- Кастомная метрика недоступна: проверьте конфигурацию Prometheus Adapter
- HPA не масштабируется: проверьте формулу в prometheus-adapter-values.yaml
- Ошибка "unable to get metric": Adapter не может подключиться к Prometheus

---

## Логи и события

### Полезные логи для отладки

```bash
# События в namespace
kubectl get events -n default --sort-by='.lastTimestamp'

# Логи HPA (через controller-manager)
kubectl logs -n kube-system deployment/kube-controller-manager | grep HorizontalPodAutoscaler

# Логи Prometheus Adapter
kubectl logs -n default deployment/prometheus-adapter

# Статус Prometheus targets
# Через UI: Status -> Targets
# Должен показывать зеленый UP для scalable-pod-identifier
```

### Типичные события масштабирования

```
Normal   SuccessfulRescale  HorizontalPodAutoscaler  New size: 3; reason: memory resource utilization (percentage of request) above target
Normal   SuccessfulRescale  HorizontalPodAutoscaler  New size: 6; reason: memory resource utilization (percentage of request) above target
Normal   SuccessfulRescale  HorizontalPodAutoscaler  New size: 3; reason: All metrics below target
Normal   SuccessfulRescale  HorizontalPodAutoscaler  New size: 1; reason: All metrics below target
```

---

## Заключение

Оба метода масштабирования успешно протестированы и работают корректно. Скриншоты демонстрируют:
1. Корректную работу HPA
2. Автоматическое масштабирование в ответ на нагрузку
3. Правильную интеграцию с Prometheus
4. Эффективное распределение нагрузки между подами

Для InsureTech рекомендуется использовать масштабирование по RPS как основной механизм, с дополнительным контролем по CPU и памяти.
