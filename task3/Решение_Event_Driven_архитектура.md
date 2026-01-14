# Решение: Event-Driven архитектура для InsureTech

## Обзор решения

Предлагается переход от синхронной REST-based архитектуры к Event-Driven архитектуре с использованием брокера событий (Apache Kafka) и паттерна Transactional Outbox для обеспечения надежной публикации событий.

---

## Ключевые изменения в архитектуре

### 1. Внедрение брокера событий (Apache Kafka)

**Компонент:** Apache Kafka  
**Роль:** Центральный брокер для асинхронного обмена событиями между сервисами

**Топики событий:**
- `insurance-products` — события об изменении страховых продуктов
- `insurance-policies` — события о создании/изменении страховок
- `client-data` — события об изменении данных клиентов

**Преимущества выбора Kafka:**
- Высокая пропускная способность (миллионы событий в секунду)
- Долговременное хранение событий
- Возможность повторного чтения событий
- Горизонтальное масштабирование
- Гарантия порядка событий в рамках партиции
- Возможность добавления новых потребителей без изменения producer'ов

---

### 2. Изменения в ins-product-aggregator

#### Было:
- Синхронная обработка каждого запроса от потребителей
- Синхронные запросы ко всем страховым компаниям при каждом обращении
- Время отклика = сумма времени запросов ко всем страховым компаниям
- Прямая зависимость потребителей от доступности aggregator'а

#### Стало:
- **Асинхронная модель работы:**
  - Периодическое (например, каждый час) обращение к страховым компаниям
  - Или event-driven обновление при получении уведомлений от страховых компаний
  - Сохранение агрегированных данных в собственную БД (ins-product-agg-db)
  
- **Публикация событий:**
  - `ProductCreated` — при добавлении нового продукта
  - `ProductUpdated` — при изменении существующего продукта
  - `ProductDeleted` — при удалении продукта
  
- **Использование Transactional Outbox:**
  - Сохранение изменений в БД и событий в Outbox-таблицу в одной транзакции
  - Отдельный процесс (Polling Publisher или CDC) отправляет события в Kafka
  - Гарантия: если изменения в БД зафиксированы, события обязательно будут опубликованы

#### Преимущества:
- ✅ Изоляция сбоев отдельных страховых компаний
- ✅ Возможность публикации частичных обновлений
- ✅ Снижение нагрузки на API страховых компаний
- ✅ Потребители не зависят от доступности aggregator'а в реальном времени

---

### 3. Изменения в core-app

#### Было:
- Синхронные запросы к ins-product-aggregator каждые 15 минут
- Локальное кэширование полученных данных
- Зависимость от доступности ins-product-aggregator
- При недоступности aggregator'а — использование устаревших данных

#### Стало:
- **Локальная реплика данных о продуктах:**
  - Подписка на топик `insurance-products` в Kafka
  - Обработка событий `ProductCreated`, `ProductUpdated`, `ProductDeleted`
  - Поддержание актуальной реплики в собственной схеме БД
  - Данные доступны локально без сетевых запросов
  
- **Публикация событий о страховках:**
  - `PolicyCreated` — при оформлении новой страховки
  - `PolicyUpdated` — при изменении существующей страховки
  - Использование Transactional Outbox для надежной публикации
  - События содержат полную информацию о страховке для потребителей

#### Преимущества:
- ✅ Данные о продуктах всегда доступны (даже при недоступности aggregator'а)
- ✅ Отсутствие периодических синхронных запросов
- ✅ Актуальность данных в near real-time
- ✅ Снижение времени отклика на запросы пользователей
- ✅ Независимое масштабирование

---

### 4. Изменения в ins-comp-settlement

#### Было:
- Синхронный запрос к ins-product-aggregator раз в сутки (ночью)
- Синхронный запрос к core-app раз в сутки для получения новых страховок
- Пиковая нагрузка на core-app в ночное время
- Зависимость от доступности обоих сервисов

#### Стало:
- **Локальная реплика данных о продуктах:**
  - Подписка на топик `insurance-products` в Kafka
  - Непрерывное обновление локальной реплики
  - Данные всегда актуальны для формирования реестров
  
- **Локальная реплика данных о страховках:**
  - Подписка на топик `insurance-policies` в Kafka
  - Непрерывное получение информации о новых и измененных страховках
  - Отсутствие необходимости в ежедневном синхронном запросе к core-app
  - Возможность формирования реестров в любое время

#### Преимущества:
- ✅ Отсутствие зависимости от доступности других сервисов
- ✅ Устранение пиковых нагрузок на core-app
- ✅ Данные доступны для формирования реестров в любое время
- ✅ Возможность реализации инкрементальных обновлений реестров
- ✅ Независимое масштабирование

---

## Применение паттерна Transactional Outbox

### Что такое Transactional Outbox?

Паттерн, решающий проблему двойной записи в распределённых системах:
- **Проблема:** Необходимо атомарно выполнить две операции: изменить данные в БД и отправить событие в брокер
- **Решение:** Сохранить и изменения данных, и события в БД в рамках одной транзакции

### Архитектура Transactional Outbox

```
┌─────────────────────────────────────────────────────────────────┐
│ Сервис (core-app или ins-product-aggregator)                   │
│                                                                 │
│  1. BEGIN TRANSACTION                                           │
│  2. UPDATE business_data SET ...                                │
│  3. INSERT INTO outbox_table (event_type, payload, ...)         │
│  4. COMMIT TRANSACTION                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│ Message Relay (отдельный процесс)                              │
│                                                                 │
│  Вариант 1: Polling Publisher                                  │
│  - Периодически (например, каждые 100ms) читает Outbox         │
│  - Отправляет новые события в Kafka                            │
│  - Помечает события как отправленные или удаляет               │
│                                                                 │
│  Вариант 2: Transaction Log Tailing (CDC)                      │
│  - Подписка на Write-Ahead Log (WAL) PostgreSQL                │
│  - Автоматическая отправка событий при записи в Outbox         │
│  - Использование Debezium для PostgreSQL                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
                      Apache Kafka
```

### Структура Outbox-таблицы

```sql
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(255) NOT NULL,  -- 'Product', 'Policy'
    aggregate_id VARCHAR(255) NOT NULL,    -- ID бизнес-сущности
    event_type VARCHAR(255) NOT NULL,      -- 'ProductCreated', 'PolicyCreated'
    payload JSONB NOT NULL,                 -- Полные данные события
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP,                 -- Когда было отправлено
    status VARCHAR(50) DEFAULT 'PENDING'    -- 'PENDING', 'SENT', 'FAILED'
);

CREATE INDEX idx_outbox_pending ON outbox_events(status, created_at) 
WHERE status = 'PENDING';
```

### Процесс публикации события

#### Пример: Создание новой страховки в core-app

```kotlin
@Service
@Transactional
class PolicyService(
    private val policyRepository: PolicyRepository,
    private val outboxRepository: OutboxRepository
) {
    fun createPolicy(request: CreatePolicyRequest): Policy {
        // 1. Создаем страховку
        val policy = Policy(
            id = UUID.randomUUID(),
            clientId = request.clientId,
            productId = request.productId,
            // ... другие поля
        )
        policyRepository.save(policy)
        
        // 2. Создаем событие в Outbox
        val event = OutboxEvent(
            aggregateType = "Policy",
            aggregateId = policy.id.toString(),
            eventType = "PolicyCreated",
            payload = objectMapper.writeValueAsString(
                PolicyCreatedEvent(
                    policyId = policy.id,
                    clientId = policy.clientId,
                    productId = policy.productId,
                    amount = policy.amount,
                    startDate = policy.startDate,
                    endDate = policy.endDate,
                    createdAt = policy.createdAt
                )
            )
        )
        outboxRepository.save(event)
        
        // 3. Транзакция автоматически коммитится Spring'ом
        // Либо обе операции выполнены, либо обе откачены
        
        return policy
    }
}
```

#### Пример: Message Relay (Polling Publisher)

```kotlin
@Service
class OutboxMessageRelay(
    private val outboxRepository: OutboxRepository,
    private val kafkaProducer: KafkaProducer
) {
    @Scheduled(fixedDelay = 100) // Каждые 100ms
    fun processOutboxEvents() {
        val pendingEvents = outboxRepository
            .findByStatusOrderByCreatedAtAsc("PENDING", limit = 100)
        
        pendingEvents.forEach { event ->
            try {
                // Отправляем в Kafka
                kafkaProducer.send(
                    topic = determineTopicByAggregateType(event.aggregateType),
                    key = event.aggregateId,
                    value = event.payload
                )
                
                // Помечаем как отправленное
                event.status = "SENT"
                event.processedAt = Instant.now()
                outboxRepository.save(event)
                
            } catch (e: Exception) {
                log.error("Failed to send event ${event.id}", e)
                event.status = "FAILED"
                outboxRepository.save(event)
            }
        }
    }
    
    private fun determineTopicByAggregateType(type: String): String {
        return when (type) {
            "Product" -> "insurance-products"
            "Policy" -> "insurance-policies"
            "Client" -> "client-data"
            else -> throw IllegalArgumentException("Unknown aggregate type: $type")
        }
    }
}
```

### Рекомендуемая реализация для InsureTech

#### Для core-app и ins-product-aggregator:

**Вариант 1: Polling Publisher (Рекомендуется для начала)**

**Преимущества:**
- ✅ Простота реализации
- ✅ Не требует дополнительной инфраструктуры
- ✅ Легко отлаживать и мониторить
- ✅ Можно реализовать прямо внутри приложения

**Недостатки:**
- ⚠️ Небольшая задержка публикации (100-1000ms)
- ⚠️ Дополнительная нагрузка на БД (периодические SELECT)

**Когда подходит:**
- Приемлемая задержка публикации: 100-1000ms
- Объем событий: до нескольких тысяч в секунду
- Команда хочет начать с простого решения

**Вариант 2: Transaction Log Tailing (CDC с Debezium)**

**Преимущества:**
- ✅ Минимальная задержка (миллисекунды)
- ✅ Нет дополнительной нагрузки на БД
- ✅ Высокая производительность

**Недостатки:**
- ⚠️ Сложнее в настройке и поддержке
- ⚠️ Требует развертывания Debezium
- ⚠️ Специфичные настройки для каждой БД

**Когда подходит:**
- Требуется минимальная задержка публикации
- Объем событий: тысячи в секунду и более
- Команда готова к дополнительной инфраструктуре

#### Рекомендация для InsureTech:

**Начать с Polling Publisher**, так как:
1. Задержка 100-1000ms приемлема для бизнес-процессов InsureTech
2. Объем событий умеренный (обновления продуктов, создание страховок)
3. Проще внедрить и поддерживать
4. Можно перейти на CDC позже, если потребуется

---

## Структура событий

### ProductCreated / ProductUpdated

```json
{
  "eventId": "550e8400-e29b-41d4-a716-446655440000",
  "eventType": "ProductUpdated",
  "eventTime": "2024-01-15T10:30:00Z",
  "aggregateId": "product-12345",
  "version": 2,
  "data": {
    "productId": "product-12345",
    "insuranceCompanyId": "company-001",
    "insuranceCompanyName": "Страховая компания Альфа",
    "productType": "LIFE_INSURANCE",
    "name": "Страхование жизни Премиум",
    "description": "Комплексная защита жизни и здоровья",
    "minCoverage": 1000000,
    "maxCoverage": 10000000,
    "basePremium": 15000,
    "conditions": {
      "minAge": 18,
      "maxAge": 65,
      "medicalExamRequired": true
    },
    "active": true,
    "updatedAt": "2024-01-15T10:30:00Z"
  }
}
```

### PolicyCreated

```json
{
  "eventId": "660e8400-e29b-41d4-a716-446655440001",
  "eventType": "PolicyCreated",
  "eventTime": "2024-01-15T11:00:00Z",
  "aggregateId": "policy-67890",
  "version": 1,
  "data": {
    "policyId": "policy-67890",
    "policyNumber": "INS-2024-67890",
    "clientId": "client-123",
    "clientName": "Иванов Иван Иванович",
    "productId": "product-12345",
    "productName": "Страхование жизни Премиум",
    "insuranceCompanyId": "company-001",
    "insuranceCompanyName": "Страховая компания Альфа",
    "coverage": 5000000,
    "premium": 20000,
    "startDate": "2024-02-01",
    "endDate": "2025-02-01",
    "status": "ACTIVE",
    "createdAt": "2024-01-15T11:00:00Z"
  }
}
```

**Принципы проектирования событий:**
1. ✅ События содержат достаточно данных для потребителей (не требуются дополнительные запросы)
2. ✅ События иммутабельны (не изменяются после публикации)
3. ✅ События именуются в прошедшем времени (ProductCreated, PolicyCreated)
4. ✅ Используются бизнес-термины (не технические детали)
5. ✅ Каждое событие имеет уникальный ID для идемпотентности

---

## Управление схемами событий (Schema Registry)

### Проблема эволюции схем

По мере развития системы структура событий может изменяться:
- Добавление новых полей
- Удаление устаревших полей
- Изменение типов данных
- Переименование полей

**Без централизованного управления схемами:**
- ❌ Несовместимость между producer и consumer
- ❌ Сложность отслеживания версий событий
- ❌ Runtime ошибки десериализации
- ❌ Отсутствие валидации на этапе разработки

### Решение: Confluent Schema Registry

**Schema Registry** — это централизованный реестр схем для хранения и управления схемами событий в Kafka.

#### Преимущества использования Schema Registry:

1. **Централизованное управление схемами**
   - Все схемы событий хранятся в одном месте
   - Единая точка истины для структуры событий

2. **Контроль совместимости**
   - Автоматическая проверка совместимости при обновлении схем
   - Предотвращение breaking changes

3. **Версионирование**
   - Каждое изменение схемы создает новую версию
   - История всех изменений сохраняется

4. **Валидация**
   - Producer автоматически валидирует события перед отправкой
   - Consumer проверяет соответствие схеме при чтении

5. **Оптимизация**
   - Схемы не передаются в каждом событии (только ID схемы)
   - Снижение размера сообщений на 30-50%

#### Архитектура с Schema Registry

```
┌──────────────────┐          ┌──────────────────┐
│   Producer       │          │   Consumer       │
│   (core-app)     │          │  (settlement)    │
└────────┬─────────┘          └────────┬─────────┘
         │                             │
         │ 1. Register schema          │ 3. Get schema
         │ 2. Validate & send          │ 4. Validate & read
         │                             │
         ↓                             ↓
    ┌────────────────────────────────────────┐
    │      Schema Registry (Confluent)       │
    │  - Хранение всех версий схем           │
    │  - Проверка совместимости              │
    │  - Выдача схем по ID                   │
    └────────────────┬───────────────────────┘
                     │
         ┌───────────┴────────────┐
         ↓                        ↓
    ┌─────────┐            ┌─────────┐
    │  Kafka  │            │  Kafka  │
    │ Topic 1 │            │ Topic 2 │
    └─────────┘            └─────────┘
```

### Примеры JSON Schema для событий InsureTech

#### ProductCreatedEvent.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ProductCreatedEvent",
  "description": "Событие создания нового страхового продукта",
  "type": "object",
  "required": ["eventId", "eventType", "eventTime", "aggregateId", "version", "data"],
  "properties": {
    "eventId": {
      "type": "string",
      "format": "uuid",
      "description": "Уникальный идентификатор события"
    },
    "eventType": {
      "type": "string",
      "const": "ProductCreated",
      "description": "Тип события"
    },
    "eventTime": {
      "type": "string",
      "format": "date-time",
      "description": "Время возникновения события (ISO 8601)"
    },
    "aggregateId": {
      "type": "string",
      "description": "Идентификатор страхового продукта"
    },
    "version": {
      "type": "integer",
      "minimum": 1,
      "description": "Версия схемы события"
    },
    "data": {
      "type": "object",
      "required": ["productId", "insuranceCompanyId", "productType", "name", "active"],
      "properties": {
        "productId": {
          "type": "string",
          "description": "Идентификатор продукта"
        },
        "insuranceCompanyId": {
          "type": "string",
          "description": "Идентификатор страховой компании"
        },
        "insuranceCompanyName": {
          "type": "string",
          "description": "Название страховой компании"
        },
        "productType": {
          "type": "string",
          "enum": ["LIFE_INSURANCE", "HEALTH_INSURANCE", "CAR_INSURANCE", "PROPERTY_INSURANCE"],
          "description": "Тип страхового продукта"
        },
        "name": {
          "type": "string",
          "minLength": 3,
          "maxLength": 200,
          "description": "Название продукта"
        },
        "description": {
          "type": "string",
          "maxLength": 2000,
          "description": "Описание продукта"
        },
        "minCoverage": {
          "type": "number",
          "minimum": 0,
          "description": "Минимальная сумма покрытия"
        },
        "maxCoverage": {
          "type": "number",
          "minimum": 0,
          "description": "Максимальная сумма покрытия"
        },
        "basePremium": {
          "type": "number",
          "minimum": 0,
          "description": "Базовая премия"
        },
        "conditions": {
          "type": "object",
          "properties": {
            "minAge": {
              "type": "integer",
              "minimum": 0,
              "maximum": 120
            },
            "maxAge": {
              "type": "integer",
              "minimum": 0,
              "maximum": 120
            },
            "medicalExamRequired": {
              "type": "boolean"
            }
          }
        },
        "active": {
          "type": "boolean",
          "description": "Активен ли продукт"
        },
        "createdAt": {
          "type": "string",
          "format": "date-time",
          "description": "Дата и время создания"
        }
      }
    }
  }
}
```

#### PolicyCreatedEvent.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PolicyCreatedEvent",
  "description": "Событие оформления новой страховки",
  "type": "object",
  "required": ["eventId", "eventType", "eventTime", "aggregateId", "version", "data"],
  "properties": {
    "eventId": {
      "type": "string",
      "format": "uuid"
    },
    "eventType": {
      "type": "string",
      "const": "PolicyCreated"
    },
    "eventTime": {
      "type": "string",
      "format": "date-time"
    },
    "aggregateId": {
      "type": "string"
    },
    "version": {
      "type": "integer",
      "minimum": 1
    },
    "data": {
      "type": "object",
      "required": ["policyId", "clientId", "productId", "coverage", "premium", "status"],
      "properties": {
        "policyId": {
          "type": "string"
        },
        "policyNumber": {
          "type": "string",
          "pattern": "^INS-[0-9]{4}-[0-9]{5,}$"
        },
        "clientId": {
          "type": "string"
        },
        "clientName": {
          "type": "string"
        },
        "productId": {
          "type": "string"
        },
        "productName": {
          "type": "string"
        },
        "insuranceCompanyId": {
          "type": "string"
        },
        "insuranceCompanyName": {
          "type": "string"
        },
        "coverage": {
          "type": "number",
          "minimum": 0
        },
        "premium": {
          "type": "number",
          "minimum": 0
        },
        "startDate": {
          "type": "string",
          "format": "date"
        },
        "endDate": {
          "type": "string",
          "format": "date"
        },
        "status": {
          "type": "string",
          "enum": ["DRAFT", "ACTIVE", "SUSPENDED", "EXPIRED", "CANCELLED"]
        },
        "createdAt": {
          "type": "string",
          "format": "date-time"
        }
      }
    }
  }
}
```

### Стратегии совместимости

Schema Registry поддерживает различные стратегии проверки совместимости:

#### 1. BACKWARD (рекомендуется для большинства случаев)
- Consumer с новой схемой может читать события со старой схемой
- Можно **удалять** поля (с default значениями)
- Можно **добавлять** optional поля
- ✅ Подходит для InsureTech: позволяет добавлять новые поля без остановки consumer'ов

#### 2. FORWARD
- Consumer со старой схемой может читать события с новой схемой
- Можно **добавлять** поля
- Можно **удалять** optional поля

#### 3. FULL (BACKWARD + FORWARD)
- Наиболее строгая совместимость
- Можно только добавлять/удалять optional поля с default значениями

#### 4. NONE
- Без проверки совместимости
- ⚠️ Не рекомендуется для production

### Пример эволюции схемы события

**Версия 1 (исходная):**
```json
{
  "productId": "product-123",
  "name": "Страхование жизни",
  "premium": 15000
}
```

**Версия 2 (добавлено поле discountPercent):**
```json
{
  "productId": "product-123",
  "name": "Страхование жизни",
  "premium": 15000,
  "discountPercent": 5  // Новое optional поле
}
```

**Версия 3 (поле premium переименовано в basePremium):**
```json
{
  "productId": "product-123",
  "name": "Страхование жизни",
  "basePremium": 15000,  // Переименовано
  "discountPercent": 5
}
```

⚠️ **Версия 3 несовместима** с версиями 1 и 2! Переименование поля = breaking change.

**Правильный подход для версии 3:**
```json
{
  "productId": "product-123",
  "name": "Страхование жизни",
  "premium": 15000,        // Deprecated, но оставлено для совместимости
  "basePremium": 15000,    // Новое поле
  "discountPercent": 5
}
```

### Внедрение Schema Registry для InsureTech

#### Этап 1: Установка Schema Registry
```bash
# Через Docker Compose
docker-compose up -d schema-registry

# Проверка
curl http://localhost:8081/subjects
```

#### Этап 2: Регистрация схем
```bash
# Регистрация схемы для топика insurance-products
curl -X POST -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"schema": "..."}' \
  http://localhost:8081/subjects/insurance-products-value/versions
```

#### Этап 3: Настройка Producer (ins-product-aggregator)
```kotlin
// build.gradle.kts
dependencies {
    implementation("io.confluent:kafka-avro-serializer:7.5.0")
}

// application.yml
spring:
  kafka:
    producer:
      value-serializer: io.confluent.kafka.serializers.KafkaJsonSchemaSerializer
      properties:
        schema.registry.url: http://schema-registry:8081
        auto.register.schemas: false  // Схемы регистрируются вручную
        use.latest.version: true
```

#### Этап 4: Настройка Consumer (core-app, ins-comp-settlement)
```kotlin
// application.yml
spring:
  kafka:
    consumer:
      value-deserializer: io.confluent.kafka.serializers.KafkaJsonSchemaDeserializer
      properties:
        schema.registry.url: http://schema-registry:8081
        specific.json.value.type: com.insuretech.events.ProductEvent
```

### Рекомендации для InsureTech

1. **Использовать BACKWARD совместимость** как стратегию по умолчанию
2. **Версионировать схемы**: ProductCreatedEvent v1, v2, v3...
3. **Документировать изменения**: Changelog для каждой версии схемы
4. **Тестировать совместимость**: Автотесты для проверки десериализации старых событий
5. **Не удалять схемы**: Даже устаревшие версии могут понадобиться для восстановления данных
6. **Мониторить Schema Registry**: Алерты на ошибки регистрации/валидации

---

## Обработка событий потребителями

### Пример: core-app обрабатывает события о продуктах

```kotlin
@Service
class ProductEventConsumer(
    private val productReplicaRepository: ProductReplicaRepository
) {
    @KafkaListener(
        topics = ["insurance-products"],
        groupId = "core-app-product-consumers"
    )
    @Transactional
    fun handleProductEvent(
        @Payload event: ProductEvent,
        @Header(KafkaHeaders.RECEIVED_MESSAGE_KEY) key: String
    ) {
        // Проверка идемпотентности
        if (eventAlreadyProcessed(event.eventId)) {
            log.info("Event ${event.eventId} already processed, skipping")
            return
        }
        
        when (event.eventType) {
            "ProductCreated", "ProductUpdated" -> {
                val product = ProductReplica(
                    id = event.data.productId,
                    insuranceCompanyId = event.data.insuranceCompanyId,
                    insuranceCompanyName = event.data.insuranceCompanyName,
                    productType = event.data.productType,
                    name = event.data.name,
                    description = event.data.description,
                    // ... остальные поля
                    version = event.version,
                    lastUpdated = event.eventTime
                )
                productReplicaRepository.save(product)
            }
            
            "ProductDeleted" -> {
                productReplicaRepository.softDelete(event.aggregateId)
            }
        }
        
        // Сохраняем факт обработки для идемпотентности
        saveProcessedEvent(event.eventId)
    }
    
    private fun eventAlreadyProcessed(eventId: String): Boolean {
        return processedEventsRepository.existsByEventId(eventId)
    }
    
    private fun saveProcessedEvent(eventId: String) {
        processedEventsRepository.save(
            ProcessedEvent(eventId = eventId, processedAt = Instant.now())
        )
    }
}
```

### Обеспечение идемпотентности

**Проблема:** Kafka гарантирует доставку "at-least-once", поэтому событие может быть доставлено несколько раз.

**Решение:** Отдельная таблица для отслеживания обработанных событий

```sql
CREATE TABLE processed_events (
    event_id UUID PRIMARY KEY,
    processed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_processed_events_time ON processed_events(processed_at);
```

**Процесс обработки:**
1. Получить событие из Kafka
2. Проверить, обработано ли событие (SELECT FROM processed_events WHERE event_id = ?)
3. Если да — пропустить (ACK в Kafka)
4. Если нет — обработать событие
5. В рамках той же транзакции: обновить бизнес-данные И вставить запись в processed_events
6. Commit транзакции
7. ACK в Kafka

**Периодическая очистка:** Удалять записи старше N дней для экономии места

---

## Управление порядком событий

### Проблема

В распределенной системе с несколькими экземплярами потребителя события могут обрабатываться параллельно и не в том порядке, в котором были опубликованы.

### Решение: Использование ключа партицирования в Kafka

**Kafka гарантирует:**
- События с одинаковым ключом попадают в одну партицию
- События в одной партиции обрабатываются строго по порядку одним потребителем

**Применение в InsureTech:**

```kotlin
// При публикации события о продукте
kafkaProducer.send(
    topic = "insurance-products",
    key = event.data.productId,  // Ключ = ID продукта
    value = event.payload
)

// При публикации события о страховке
kafkaProducer.send(
    topic = "insurance-policies",
    key = event.data.policyId,   // Ключ = ID страховки
    value = event.payload
)
```

**Результат:**
- Все события об одном продукте обрабатываются последовательно
- Все события об одной страховке обрабатываются последовательно
- События о разных продуктах/страховках могут обрабатываться параллельно

---

## Мониторинг и наблюдаемость

### Ключевые метрики для отслеживания

#### Для Outbox Message Relay:
- **Количество необработанных событий в Outbox** — критическая метрика
  - Норма: < 100
  - Предупреждение: > 1000
  - Критическое: > 10000
  
- **Средняя задержка публикации** — время от создания события до отправки в Kafka
  - Норма: < 500ms
  - Предупреждение: > 2s
  - Критическое: > 10s
  
- **Количество ошибок публикации**
  - Норма: 0
  - Предупреждение: > 10 за 5 минут

#### Для Kafka:
- **Consumer lag** — отставание потребителя от последнего события
  - Норма: < 100 событий
  - Предупреждение: > 1000 событий
  - Критическое: > 10000 событий
  
- **Throughput** — количество событий в секунду
- **Размер топиков**
- **Состояние партиций и реплик**

#### Для потребителей:
- **Время обработки события**
  - P95 < 100ms
  - P99 < 500ms
  
- **Количество ошибок обработки**
- **Количество обработанных событий по типам**

### Инструменты мониторинга

1. **Prometheus + Grafana**
   - Сбор и визуализация метрик
   - Настройка дашбордов
   
2. **Kafka Manager / Kafdrop**
   - Мониторинг состояния Kafka
   - Просмотр топиков и consumer groups
   
3. **Spring Boot Actuator**
   - Метрики приложений
   - Health checks
   
4. **Distributed Tracing (Jaeger / Zipkin)**
   - Отслеживание пути события через систему
   - Анализ узких мест

---

## План внедрения

### Этап 1: Подготовка инфраструктуры (1-2 недели)

- [ ] Развернуть Kafka кластер (минимум 3 брокера)
- [ ] Настроить репликацию и отказоустойчивость
- [ ] Создать топики: `insurance-products`, `insurance-policies`, `client-data`
- [ ] Настроить мониторинг Kafka
- [ ] Протестировать производительность и надежность

### Этап 2: Внедрение Transactional Outbox в ins-product-aggregator (2-3 недели)

- [ ] Создать Outbox-таблицу в ins-product-agg-db
- [ ] Реализовать сохранение событий в Outbox при изменении данных
- [ ] Реализовать Message Relay (Polling Publisher)
- [ ] Настроить мониторинг Outbox
- [ ] Протестировать на тестовом окружении
- [ ] Развернуть на продакшен с минимальной нагрузкой
- [ ] Постепенно увеличивать нагрузку

### Этап 3: Внедрение потребителя в core-app (2-3 недели)

- [ ] Создать схему для реплики данных о продуктах
- [ ] Реализовать потребителя событий из `insurance-products`
- [ ] Реализовать идемпотентность обработки
- [ ] Реализовать начальную загрузку данных (bootstrap)
- [ ] Настроить мониторинг consumer lag
- [ ] Протестировать на тестовом окружении
- [ ] Развернуть на продакшен параллельно со старым механизмом
- [ ] Постепенно переключать трафик на новый механизм
- [ ] Отключить старые периодические запросы к ins-product-aggregator

### Этап 4: Внедрение Transactional Outbox в core-app (2-3 недели)

- [ ] Создать Outbox-таблицу в core-db
- [ ] Реализовать публикацию событий о страховках
- [ ] Реализовать Message Relay
- [ ] Настроить мониторинг
- [ ] Протестировать
- [ ] Развернуть на продакшен

### Этап 5: Внедрение потребителей в ins-comp-settlement (2-3 недели)

- [ ] Создать схемы для реплик данных о продуктах и страховках
- [ ] Реализовать потребителей событий
- [ ] Реализовать идемпотентность
- [ ] Реализовать начальную загрузку данных
- [ ] Настроить мониторинг
- [ ] Протестировать
- [ ] Развернуть на продакшен параллельно со старым механизмом
- [ ] Постепенно переключать на новый механизм
- [ ] Отключить старые синхронные запросы

### Этап 6: Оптимизация и масштабирование (ongoing)

- [ ] Анализ производительности
- [ ] Настройка количества партиций в Kafka
- [ ] Оптимизация обработки событий
- [ ] Масштабирование потребителей
- [ ] Внедрение CDC (если потребуется)

---

## Обработка граничных случаев

### 1. Начальная загрузка данных (Bootstrap)

**Проблема:** При первом запуске потребителя нужно загрузить существующие данные, а не только новые события.

**Решение:**
1. **Вариант А: Историческая публикация**
   - ins-product-aggregator единоразово публикует события о всех существующих продуктах
   - Потребители обрабатывают эти события и строят начальную реплику
   
2. **Вариант Б: Прямая загрузка + подписка на события**
   - Потребитель делает единоразовый REST запрос для получения всех данных
   - Одновременно подписывается на события с момента начала загрузки
   - Может получить дубликаты — идемпотентность решит проблему

**Рекомендация:** Вариант Б проще и надежнее для InsureTech

### 2. Отставание потребителя (Consumer Lag)

**Проблема:** Потребитель не успевает обрабатывать события с той же скоростью, с которой они публикуются.

**Причины:**
- Высокая нагрузка на потребителя
- Медленные операции с БД
- Проблемы с производительностью

**Решения:**
- Горизонтальное масштабирование потребителей
- Оптимизация обработки событий (батчинг, кэширование)
- Увеличение количества партиций в топике
- Настройка prefetch для более эффективного чтения

### 3. Обработка ошибок

**Сценарии ошибок:**
- Невалидное событие (нарушение схемы)
- Ошибка при записи в БД (constraint violation)
- Временная недоступность БД

**Стратегия обработки:**

```kotlin
@KafkaListener(topics = ["insurance-products"])
fun handleEvent(event: ProductEvent) {
    try {
        processEvent(event)
    } catch (e: ValidationException) {
        // Невалидное событие - пропускаем и логируем
        log.error("Invalid event: ${event.eventId}", e)
        sendToDeadLetterQueue(event, e)
        // ACK - не пытаемся обработать повторно
    } catch (e: RetryableException) {
        // Временная ошибка - можно повторить
        log.warn("Retryable error for event: ${event.eventId}", e)
        throw e  // Kafka retry mechanism
    } catch (e: Exception) {
        // Неизвестная ошибка
        log.error("Unexpected error for event: ${event.eventId}", e)
        sendToDeadLetterQueue(event, e)
        // ACK - не блокируем обработку следующих событий
    }
}
```

**Dead Letter Queue (DLQ):**
- Отдельный топик для событий, которые не удалось обработать
- Позволяет продолжить обработку остальных событий
- Требует ручного или автоматического анализа и переобработки

### 4. Версионирование событий

**Проблема:** Со временем структура событий может меняться.

**Решение: Schema Evolution**

```json
{
  "eventId": "...",
  "eventType": "ProductUpdated",
  "eventVersion": "2.0",  // <-- Версия схемы события
  "data": {
    // поля v2.0
  }
}
```

**Стратегии:**
- **Backward compatibility:** Новая версия может читать старые события
- **Forward compatibility:** Старая версия может игнорировать новые поля
- **Full compatibility:** И то, и другое

**Рекомендация для InsureTech:**
- Использовать Avro или Protocol Buffers для строгой типизации
- Регистрировать схемы в Schema Registry (Confluent)
- Всегда добавлять новые поля как опциональные

### 5. Восстановление после сбоев

**Сценарий:** Потребитель упал, пока обрабатывал события.

**Kafka автоматически:**
- Переназначает партиции другому потребителю в группе
- Продолжает чтение с последнего зафиксированного offset

**Важно:**
- Фиксировать offset только после успешной обработки
- Использовать `enable.auto.commit=false` и ручной commit
- Либо использовать транзакционную семантику Kafka

---

## Сравнение: Было vs Стало

### Получение данных о продуктах в core-app

| Аспект | Было (REST) | Стало (Event-Driven) |
|--------|-------------|----------------------|
| **Частота обновления** | Каждые 15 минут | Near real-time (секунды) |
| **Зависимость от ins-product-aggregator** | Критическая | Отсутствует |
| **Время отклика** | Зависит от сети и aggregator'а | Мгновенно (локальная БД) |
| **Нагрузка на сеть** | Повторяющиеся запросы | Только новые/измененные данные |
| **Масштабируемость** | Линейная (больше запросов = больше нагрузки) | Независимая |
| **Отказоустойчивость** | Низкая | Высокая |

### Получение данных о страховках в ins-comp-settlement

| Аспект | Было (REST) | Стало (Event-Driven) |
|--------|-------------|----------------------|
| **Частота обновления** | Раз в сутки (ночью) | Непрерывно |
| **Зависимость от core-app** | Критическая | Отсутствует |
| **Пиковая нагрузка** | Высокая (ночью) | Равномерная |
| **Доступность данных** | Только после ночного обновления | Всегда актуальны |
| **Гибкость формирования реестров** | Только после обновления | В любое время |

---

## Выводы

Переход на Event-Driven архитектуру с использованием Apache Kafka и паттерна Transactional Outbox обеспечивает:

✅ **Масштабируемость**
- Независимое масштабирование каждого сервиса
- Готовность к росту до 10+ страховых компаний
- Линейная производительность при росте нагрузки

✅ **Отказоустойчивость**
- Изоляция сбоев отдельных компонентов
- Отсутствие каскадных отказов
- Деградация функциональности вместо полного отказа

✅ **Производительность**
- Снижение времени отклика для пользователей
- Отсутствие блокирующих синхронных запросов
- Эффективное использование ресурсов

✅ **Надежность**
- Гарантированная доставка событий (Transactional Outbox)
- Идемпотентность обработки
- Возможность повторной обработки событий

✅ **Гибкость**
- Простота добавления новых потребителей событий
- Возможность изменения одного сервиса без влияния на другие
- Версионирование событий

Данная архитектура является оптимальным решением для InsureTech и обеспечивает готовность к масштабированию бизнеса.
