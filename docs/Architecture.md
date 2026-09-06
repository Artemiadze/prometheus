# Архитектура Prometheus

## 1. Назначение документа

Документ описывает целевую архитектуру **Prometheus** — локального
RAG-расширения для Obsidian. Архитектура основана на принципах Clean Architecture и учитывает
следующие требования:

- работа без интернета после первоначальной установки;
- хранение и обработка пользовательских данных только на устройстве;
- отдельный семантический поиск без обязательного вызова LLM;
- ответы, основанные только на содержимом Vault;
- отображение источников ответа;
- автоматическая инкрементальная индексация;
- поддержка нескольких Vault;
- возможность замены embedding-модели, vector store и LLM runtime без
  изменения основной бизнес-логики.

## 2. Архитектурный контекст

Система состоит из трёх процессов:

1. **Prometheus Plugin** — Obsidian Community Plugin: UI, доступ к Vault и
   управление локальным runtime.
2. **Prometheus Runtime** — Python-приложение, выполняющее parsing, chunking,
   indexing, retrieval и построение ответа.
3. **Ollama** — внешний локальный runtime для запуска выбранной пользователем
   LLM.

```text
┌─────────────────────────────────────────────────────────────┐
│                     Компьютер пользователя                  │
│                                                             │
│  ┌──────────────────────────────┐                           │
│  │     Prometheus Plugin        │                           │
│  │                              │                           │
│  │ Chat / Search / Settings     │                           │
│  │ Vault API / Runtime Manager  │                           │
│  └──────────────┬───────────────┘                           │
│                 │ HTTP на 127.0.0.1                         │
│                 ▼                                           │
│  ┌──────────────────────────────┐       localhost           │
│  │      Prometheus Runtime      │────────────────────┐      │
│  │                              │                    ▼      │
│  │ Parser / Chunker / Retrieval │           ┌────────────┐  │
│  │ FastEmbed / Qdrant Local     │           │   Ollama   │  │
│  └──────────────────────────────┘           │ Local LLM  │  │
│                                             └────────────┘  │
└─────────────────────────────────────────────────────────────┘

                      Интернет не требуется
```

HTTP здесь является механизмом межпроцессного взаимодействия, а не публичным
сетевым API. Runtime должен принимать соединения только на `127.0.0.1`.

## 3. Основные архитектурные принципы

### 3.1. Dependency Rule

Зависимости направлены от внешних слоёв к внутренним:

```text
Adapters → Application → Domain
```

- Domain не зависит от фреймворков и способов хранения.
- Application зависит от Domain и абстрактных ports.
- Adapters реализуют ports с помощью Obsidian API, FastAPI, Qdrant,
  FastEmbed, Ollama и файловой системы.
- Bootstrap связывает абстракции с конкретными реализациями.

### 3.2. Use cases вместо технологий

Центром backend является не последовательность технологических сервисов
`QdrantService → FastEmbedService → OllamaService`, а бизнес-сценарии:

```text
AnswerQuestion
├── Embedder
├── VectorIndex
├── Reranker
└── LanguageModel
```

Конкретные реализации подключаются только во внешнем слое:

```text
Embedder      ← FastEmbed
VectorIndex   ← Qdrant Local
LanguageModel ← Ollama
```

### 3.3. Один владелец каждой ответственности

- Plugin владеет UI, Vault API, событиями Obsidian и жизненным циклом runtime.
- Prometheus Runtime владеет обработкой текста, индексом и RAG pipeline.
- Ollama владеет загрузкой и выполнением LLM.
- Исходный Markdown Vault остаётся единственным источником истины.

## 4. Организация репозитория

Проект называется **Prometheus** (имя расширения в Obsidian и репозитория на GitHub).
Рекомендуется хранить его как monorepo:

```text
prometheus/
├── apps/
│   ├── prometheus-plugin/
│   └── prometheus-runtime/
│
├── contracts/
│   ├── openapi.yaml
│   └── examples/
│
├── evals/
│   ├── retrieval/
│   └── rag/
│
├── packaging/
│   ├── linux/
│   ├── windows/
│   └── macos/
│
├── docs/
│   ├── Architecture.md
│   ├── Project_analytics.md
│   └── adr/
│
└── README.md
```

Plugin и Prometheus Runtime находятся в одном репозитории, но собираются и
версионируются как отдельные приложения. Контракт localhost API хранится
независимо от обеих реализаций.

## 5. Prometheus Plugin

### 5.1. Ответственность

Plugin отвечает за:

- Chat, Search, Settings и Status UI;
- чтение Markdown через Obsidian Vault API;
- обработку событий `create`, `modify`, `rename`, `delete`;
- открытие файла и конкретного heading по ссылке-источнику;
- выбор области поиска;
- скачивание, проверку версии, запуск и остановку managed runtime;
- подключение к custom runtime;
- передачу документов в runtime;
- отображение прогресса индексации и диагностических ошибок.

Plugin не выполняет chunking, embeddings, vector search или LLM inference.

### 5.2. Структура кода

```text
apps/prometheus-plugin/
├── src/
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── ChatMessage.ts
│   │   │   ├── SourceReference.ts
│   │   │   └── RuntimeStatus.ts
│   │   └── value-objects/
│   │       ├── VaultId.ts
│   │       └── SearchScope.ts
│   │
│   ├── application/
│   │   ├── ports/
│   │   │   ├── RagGateway.ts
│   │   │   ├── VaultGateway.ts
│   │   │   ├── RuntimeGateway.ts
│   │   │   └── SettingsRepository.ts
│   │   └── use-cases/
│   │       ├── AskQuestion.ts
│   │       ├── SearchNotes.ts
│   │       ├── SynchronizeVault.ts
│   │       ├── StartRuntime.ts
│   │       └── OpenSourceNote.ts
│   │
│   ├── adapters/
│   │   ├── inbound/obsidian/
│   │   │   ├── views/
│   │   │   │   ├── ChatView.ts
│   │   │   │   ├── SearchView.ts
│   │   │   │   └── StatusView.ts
│   │   │   ├── commands/
│   │   │   └── SettingsTab.ts
│   │   └── outbound/
│   │       ├── rag-api/HttpRagGateway.ts
│   │       ├── vault/ObsidianVaultGateway.ts
│   │       ├── runtime/ManagedRuntimeGateway.ts
│   │       └── settings/ObsidianSettingsRepository.ts
│   │
│   └── bootstrap/
│       └── main.ts
│
├── manifest.json
├── styles.css
└── package.json
```

`main.ts` является composition root: создаёт адаптеры, внедряет их в use cases
и регистрирует Obsidian views и commands.

UI не должен напрямую вызывать HTTP или управлять дочерним процессом.
Представления вызывают application use cases, а инфраструктурные операции
скрыты за ports.

### 5.3. Сборка и публикация

В каталоге Community Plugin должны находиться только:

```text
main.js
manifest.json
styles.css
```

Python runtime, модели и vector index нельзя размещать внутри Vault или
`.obsidian/plugins`, чтобы они не попадали в Obsidian Sync и Git.

## 6. Prometheus Runtime

### 6.1. Ответственность

Runtime отвечает за:

- проверку и нормализацию входных документов;
- Markdown parsing;
- Markdown-aware chunking;
- генерацию document и query embeddings;
- хранение и обновление vector index;
- dense retrieval;
- последующие hybrid search и reranking;
- ограничение и построение контекста;
- grounded prompt;
- вызов локальной LLM;
- формирование ответа и списка источников;
- хранение manifest индексации и технического состояния.

### 6.2. Структура кода

```text
apps/prometheus-runtime/
├── src/
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── document.py
│   │   │   ├── chunk.py
│   │   │   ├── search_hit.py
│   │   │   └── grounded_answer.py
│   │   ├── value_objects/
│   │   │   ├── vault_id.py
│   │   │   ├── document_id.py
│   │   │   ├── source_reference.py
│   │   │   └── search_scope.py
│   │   ├── services/
│   │   │   └── grounding_policy.py
│   │   └── errors.py
│   │
│   ├── application/
│   │   ├── ports/
│   │   │   ├── document_repository.py
│   │   │   ├── vector_index.py
│   │   │   ├── embedder.py
│   │   │   ├── language_model.py
│   │   │   ├── markdown_parser.py
│   │   │   ├── reranker.py
│   │   │   └── unit_of_work.py
│   │   ├── use_cases/
│   │   │   ├── index_document.py
│   │   │   ├── synchronize_vault.py
│   │   │   ├── remove_document.py
│   │   │   ├── search_notes.py
│   │   │   ├── answer_question.py
│   │   │   └── get_runtime_status.py
│   │   └── dto/
│   │
│   ├── adapters/
│   │   ├── inbound/http/
│   │   │   ├── app.py
│   │   │   ├── routes/
│   │   │   └── schemas/
│   │   └── outbound/
│   │       ├── qdrant/
│   │       ├── fastembed/
│   │       ├── ollama/
│   │       ├── markdown/
│   │       ├── sqlite/
│   │       └── filesystem/
│   │
│   └── bootstrap/
│       ├── container.py
│       ├── config.py
│       └── cli.py
│
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── e2e/
```

Ports находятся в Application Layer, поскольку `Embedder`, `VectorIndex` и
`LanguageModel` необходимы сценариям приложения, но не являются частью
предметной модели заметок.

Pydantic-модели HTTP API не должны использоваться в Domain. Inbound adapter
преобразует их в application DTO и domain value objects.

## 7. Основные domain-модели

### Document

Содержит идентификатор, Vault ID, относительный путь, Markdown, revision,
content hash и время изменения.

### Chunk

Содержит стабильный идентификатор, Document ID, текст, heading path, позицию в
документе, token count и content hash.

### SearchHit

Содержит Chunk, итоговый score и при необходимости отдельные dense, lexical и
reranker scores.

### GroundedAnswer

Содержит текст ответа, источники, использованные chunk IDs и признак
`insufficient_context`.

### SearchScope

Описывает область поиска:

- весь Vault;
- текущая заметка;
- текущая папка;
- выбранные папки.

## 8. Application use cases

### IndexDocument

1. Проверяет Vault ID, Document ID и revision.
2. Пропускает документ, если `content_hash` не изменился.
3. Разбирает Markdown.
4. Создаёт chunks.
5. Генерирует embeddings.
6. Атомарно заменяет старые chunks новыми.
7. Обновляет manifest.

### SearchNotes

1. Валидирует запрос и SearchScope.
2. Генерирует query embedding.
3. Выполняет dense search.
4. На следующих этапах объединяет dense и lexical search.
5. При наличии reranker пересортировывает кандидатов.
6. Возвращает результаты без вызова LLM.

### AnswerQuestion

1. Выполняет retrieval через общий поисковый компонент.
2. Проверяет достаточность контекста.
3. Ограничивает контекст по token budget.
4. Строит grounded prompt.
5. Вызывает `LanguageModel`.
6. Возвращает ответ только вместе с реально использованными источниками.

Если найденного контекста недостаточно, use case должен вернуть явное состояние
`insufficient_context`, а не полагаться только на добросовестность LLM.

## 9. Indexing pipeline

```text
Obsidian Vault event
        ↓
Plugin debounce
        ↓
Read through Vault API
        ↓
Send document + revision + content hash
        ↓
Markdown parser
        ↓
Heading-aware chunker
        ↓
FastEmbed
        ↓
Qdrant upsert
        ↓
SQLite manifest update
```

Операция индексации должна быть идемпотентной. Повторный запрос с тем же
`content_hash` не должен заново вычислять embeddings.

При rename сохраняется Document ID и изменяется путь. При delete удаляются
manifest, chunks и vectors соответствующего документа.

## 10. Query и RAG pipeline

### MVP

```text
Question
   ↓
Query embedding
   ↓
Dense vector search
   ↓
Top 10–20 chunks
   ↓
Context selection
   ↓
Grounded prompt
   ↓
Local LLM
   ↓
Answer + sources
```

### Последующее развитие

```text
                 ┌─ Dense search
Query ───────────┤
                 └─ BM25 lexical search
                          ↓
                        Fusion
                          ↓
                       Reranker
                          ↓
                    Context selection
```

Один и тот же retrieval use case должен использоваться как Chat, так и обычным
Semantic Search. Это предотвращает появление двух расходящихся поисковых
реализаций.

## 11. API между Plugin и Runtime

Контракт описывается в `contracts/openapi.yaml`. Рекомендуемая первая версия:

```text
GET    /v1/health
GET    /v1/status
GET    /v1/models

PUT    /v1/vaults/{vaultId}/documents/{documentId}
DELETE /v1/vaults/{vaultId}/documents/{documentId}
POST   /v1/vaults/{vaultId}/sync/complete

POST   /v1/vaults/{vaultId}/search
POST   /v1/vaults/{vaultId}/chat
POST   /v1/vaults/{vaultId}/reindex

GET    /v1/jobs/{jobId}
DELETE /v1/jobs/{jobId}
```

Требования к API:

- обязательный `vaultId` во всех операциях с пользовательскими данными;
- session token во всех запросах, кроме первоначального health check;
- request/correlation ID для диагностики;
- единый versioned error envelope;
- идемпотентность document upsert;
- совместимость версий plugin и runtime;
- streaming ответа чата через SSE или NDJSON;
- длительная индексация через фоновые jobs с progress и cancellation.

Runtime не должен самостоятельно обходить файловую систему Vault. Документы
передаёт Plugin, поскольку именно он является владельцем Obsidian Vault API.

## 12. Хранение данных

Данные runtime располагаются вне Vault:

```text
Linux:
~/.local/share/prometheus/

macOS:
~/Library/Application Support/Prometheus/

Windows:
%LOCALAPPDATA%\Prometheus\
```

Внутренняя структура:

```text
prometheus/
├── bin/
│   └── prometheus-runtime
├── models/
│   └── embeddings/
├── vaults/
│   └── <vault-id>/
│       ├── metadata.sqlite
│       └── qdrant/
├── state/
│   └── runtime.json
└── logs/
```

Распределение данных:

- Vault хранит исходные Markdown-файлы;
- SQLite хранит документы, revisions, hashes, jobs и состояние индексации;
- Qdrant хранит vectors и поисковый payload chunks;
- plugin `data.json` хранит только настройки UI и runtime;
- история чата в MVP не сохраняется;
- в будущем история может сохраняться только через явную opt-in настройку.

Логи не должны содержать полный текст заметок, запросов, prompt или ответов.

## 13. Версионирование индекса

Для каждого Vault сохраняется fingerprint:

```text
embedding provider and model
vector dimension
parser schema version
chunking algorithm version
chunk size and overlap
payload schema version
```

Изменение embedding-модели, размерности vector или несовместимой схемы требует
полной переиндексации. Изменения, не влияющие на индекс, не должны удалять
готовые vectors.

Во время rebuild старый индекс желательно оставлять доступным до готовности
нового, после чего выполнять атомарное переключение.

## 14. Поддержка нескольких Vault

Каждый Vault получает отдельный случайный `VaultId` и логически изолированный
индекс. Нельзя полагаться только на фильтр `vault_id` в запросах: application
use case должен получать уже scoped repository или scoped vector index.

Это снижает риск смешивания результатов Work, Personal и других Vault при
ошибке в фильтрации.

## 15. Безопасность и приватность

- Runtime слушает только `127.0.0.1`, но не `0.0.0.0`.
- Plugin создаёт случайный session token при запуске runtime.
- Token передаётся дочернему процессу и проверяется HTTP middleware.
- CORS отключён или ограничен ожидаемым локальным клиентом.
- Runtime не предоставляет endpoint для чтения произвольного файла по пути.
- Пути нормализуются и не используются для выхода за границы Vault.
- Downloaded binary проверяется по checksum и подписи релиза.
- В базовом режиме отсутствуют cloud LLM и cloud embedding providers.
- Сетевые обновления отделены от RAG-функций и могут быть отключены.

## 16. Управление runtime

```text
Obsidian starts
      ↓
Locate managed or custom runtime
      ↓
Check version and checksum
      ↓
Select free localhost port
      ↓
Generate session token
      ↓
Spawn runtime
      ↓
Wait for health readiness
      ↓
Use API
```

При выгрузке Plugin останавливает только тот процесс, который был запущен этим
экземпляром Plugin. Custom runtime и системный Ollama автоматически не
останавливаются.

Runtime поставляется как frozen binary для:

- Windows x64;
- Linux x64;
- macOS x64;
- macOS arm64.

Managed binary размещается вне Vault. Custom path остаётся дополнительным
режимом для разработчиков и advanced users.

## 17. Обработка ошибок

Ошибки разделяются по уровням:

- domain errors — нарушенные инварианты;
- application errors — недостаточный контекст, конфликт revision, индекс не
  готов;
- adapter errors — Ollama недоступна, Qdrant повреждён, модель отсутствует;
- presentation errors — безопасное сообщение для пользователя.

HTTP adapter преобразует внутреннюю ошибку в стабильный код:

```json
{
  "error": {
    "code": "LLM_MODEL_NOT_FOUND",
    "message": "Selected local model is not installed",
    "request_id": "..."
  }
}
```

UI должен показывать пользователю действие для восстановления: скачать
runtime, выбрать установленную модель, повторить индексацию или открыть
диагностику.

## 18. Тестирование

### Backend

- unit tests Domain и use cases без FastAPI, Qdrant и Ollama;
- fake implementations application ports;
- integration tests Qdrant Local, SQLite, FastEmbed и Ollama adapter;
- OpenAPI contract tests;
- end-to-end tests indexing → search → answer;
- migration и index compatibility tests.

### Plugin

- unit tests use cases и state/presenters;
- Obsidian API adapter tests с mock Vault;
- HTTP contract tests с локальным fake runtime;
- runtime lifecycle tests;
- UI tests основных состояний и ошибок.

### Качество RAG

В `evals/` хранится обезличенный тестовый corpus с вопросами и ожидаемыми
источниками. Основные метрики:

- Recall@K;
- MRR;
- nDCG;
- доля корректных citations;
- доля необоснованных ответов;
- latency indexing, retrieval и generation;
- потребление RAM и размер индекса.

## 19. Этапы реализации

### MVP

1. Базовые Domain и Application слои.
2. Plugin UI и управление managed/custom runtime.
3. Document synchronization и инкрементальная индексация.
4. Markdown-aware chunking.
5. FastEmbed и Qdrant Local adapters.
6. Dense semantic search.
7. Ollama adapter и grounded answers.
8. Переход к заметкам-источникам.
9. Runtime status, progress и основные ошибки.

### Этап 2

- hybrid dense + BM25 search;
- локальный reranker;
- current note, folder и selected folders scopes;
- более точные ссылки на headings;
- streaming ответа и отмена длительных операций.

### Этап 3

- альтернативные embedding providers;
- llama.cpp и другие локальные LLM runtimes;
- framework для автоматической RAG-оценки;
- профилирование и адаптация к слабому оборудованию;
- опциональная зашифрованная история чата.

## 20. Ключевые архитектурные решения

1. Два независимо собираемых приложения в одном monorepo.
2. Clean Architecture применяется внутри Plugin и Prometheus Runtime.
3. API contract не принадлежит ни UI, ни backend-адаптеру.
4. Ports находятся в Application Layer.
5. Vault является источником истины, индекс можно полностью восстановить.
6. Plugin читает Vault, Runtime не обходит его файловую систему.
7. SQLite хранит manifest, Qdrant — vector index.
8. Любая операция с данными выполняется в контексте конкретного Vault.
9. LLM является заменяемым output adapter, а не основой архитектуры.
10. Retrieval используется совместно Semantic Search и Chat.
11. Privacy и offline-first обеспечиваются архитектурными границами, а не
    только настройками интерфейса.
