# Отчёт по проекту Prometheus — локального RAG-расширения для Obsidian

## 1. Концепция проекта

**Prometheus** — локальное расширение для Obsidian с AI-чатом и семантическим поиском по заметкам пользователя.

Пользователь задаёт вопрос на естественном языке, после чего система:

1. выполняет семантический поиск по локальному Obsidian Vault;
2. находит наиболее релевантные фрагменты заметок;
3. передаёт найденный контекст локальной языковой модели;
4. формирует ответ исключительно на основании найденных заметок;
5. показывает пользователю источники, из которых был сформирован ответ.

Пример:

```text
Пользователь:

Что я писал про оптимизацию Docker-образов?

                    ↓

            Semantic Search
                    ↓

Backend/Docker.md
DevOps/Containers.md
University/Docker.md

                    ↓

                Local LLM
                    ↓

В заметках описаны следующие подходы:

1. Использование multi-stage builds.
2. Использование минимальных базовых образов.
3. Очистка package cache после установки зависимостей.

Источники:
[[Backend/Docker]]
[[DevOps/Containers]]
```

Ключевой особенностью проекта является принцип:

> **Local First / Offline First**

После первоначальной установки программных компонентов и загрузки моделей система должна быть способна работать **полностью без подключения к интернету**.

Пользовательские заметки, embeddings, история поиска и запросы к LLM не должны покидать компьютер пользователя.

---

# 2. Формат системы

Продукт представляет собой:

**Prometheus = Obsidian Community Plugin + локальный Prometheus Runtime.**

Community Plugin остаётся тонким TypeScript-клиентом. Тяжёлый Prometheus Runtime поставляется отдельно как managed sidecar (скачивание frozen binary при первой настройке во вне-Vault каталог пользователя) с возможностью указать уже установленный binary вручную. Модели LLM не вызываются через внешние API: пользователь выбирает локально установленную модель (Ollama).

На уровне пользовательского интерфейса это обычное расширение Obsidian.

Оно добавляет отдельную панель:

```text
┌────────────────────────────────────────┐
│ Prometheus                            │
├────────────────────────────────────────┤
│                                        │
│ You                                    │
│ Что я писал про индексы PostgreSQL?    │
│                                        │
│ Assistant                              │
│ В ваших заметках рассматриваются       │
│ B-Tree, Hash и GIN индексы...          │
│                                        │
│ Sources                                │
│ 📄 PostgreSQL/Indexes.md               │
│ 📄 Database/Optimization.md            │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │ Ask your notes...                  │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

Obsidian предоставляет плагинам `Vault API` для работы с файлами хранилища, поэтому расширение может читать Markdown-файлы и реагировать на изменения внутри Vault.

---

# 3. Цель проекта

Основная цель системы — предоставить пользователю **интеллектуальный поиск по личной базе знаний Obsidian**, который способен находить информацию не только по точному совпадению слов, но и по смыслу.

Существующий поиск:

```text
запрос:
"ускорение SQL"

↓

ищет слова:
"ускорение"
"SQL"
```

RAG-поиск:

```text
запрос:
"Как я оптимизировал медленные запросы в PostgreSQL?"

↓

может найти:

"Для уменьшения времени выполнения SELECT
был создан составной индекс..."
```

Даже если слова из запроса непосредственно не встречаются в заметке.

---

# 4. Основные бизнес-требования

## BR-1. Полностью локальная работа

Система должна обеспечивать локальную обработку пользовательских данных.

Локально должны выполняться:

* чтение заметок;
* парсинг Markdown;
* chunking;
* генерация embeddings;
* хранение vector index;
* semantic search;
* reranking;
* генерация ответа;
* хранение служебных данных.

Базовый режим приложения **не должен требовать подключения к внешним API**.

После установки моделей пользователь должен иметь возможность:

```text
отключить Wi-Fi
      ↓
открыть Obsidian
      ↓
задать вопрос
      ↓
получить RAG-ответ
```

---

# 5. BR-2. Конфиденциальность пользовательских данных

Ни один Markdown-файл не должен автоматически отправляться:

* OpenAI;
* Anthropic;
* Google;
* Qdrant Cloud;
* сторонним embedding API;
* другим облачным сервисам.

Архитектура должна обеспечивать:

```text
Vault
 ↓
Local RAG
 ↓
Local LLM
```

а не:

```text
Vault
 ↓
Cloud API
```

Это является одним из основных преимуществ продукта.

---

# 6. BR-3. AI-чат по Vault

Расширение должно предоставлять чат-интерфейс.

Пользователь может задавать вопросы вроде:

```text
Что я писал про алгоритм Эрли?
```

```text
Какие команды Docker я использовал для очистки контейнеров?
```

```text
Сравни мои заметки про FastAPI и Django.
```

```text
Какие проблемы с OpenVPN я раньше фиксировал?
```

Ответ должен строиться **по найденной информации**, а не по знаниям LLM.

---

# 7. BR-4. Ответы только по данным Vault

LLM должна получать инструкцию:

```text
Answer using only the provided context.

If the information required to answer the question
is not present in the context, say that there is
not enough information in the user's notes.
```

Это важно для предотвращения ситуации:

```text
нет информации в Vault
        ↓
LLM использует собственные знания
        ↓
пользователь думает,
что эта информация была в его заметках
```

Вместо этого система должна отвечать:

```text
В найденных заметках недостаточно информации,
чтобы ответить на этот вопрос.
```

---

# 8. BR-5. Источники ответа

Каждый ответ должен сопровождаться ссылками на заметки.

Например:

```text
В заметках рекомендуется использовать
multi-stage build для уменьшения размера Docker image.

Sources:

1. [[Docker/Optimization]]
2. [[Backend/Containers]]
```

При нажатии:

```text
[[Docker/Optimization]]
```

плагин должен открыть соответствующую заметку Obsidian.

В перспективе желательно открывать не только файл, но и конкретный heading:

```text
Docker/Optimization.md
        ↓
## Multi-stage builds
```

---

# 9. BR-6. Семантический поиск без генерации ответа

Пользователь должен иметь возможность использовать RAG retrieval отдельно от LLM.

Например:

```text
Semantic Search

> оптимизация запросов postgres
```

Результат:

```text
0.91  PostgreSQL/Indexes.md
      ## Composite indexes

0.87  Database/Optimization.md
      ## Query optimization

0.80  Backend/PostgreSQL.md
      ## EXPLAIN ANALYZE
```

Это позволяет использовать приложение как улучшенный поиск Obsidian.

---

# 10. BR-7. Автоматическая индексация Vault

При первом запуске система должна построить индекс:

```text
Vault
 ↓
Markdown files
 ↓
Parser
 ↓
Chunker
 ↓
Embedding model
 ↓
Qdrant
```

После этого полная переиндексация при каждом запуске приложения не требуется.

---

# 11. BR-8. Инкрементальная индексация

Если пользователь изменил:

```text
Backend/FastAPI.md
```

система не должна заново обрабатывать тысячи остальных файлов.

Нужно выполнить:

```text
FastAPI.md changed
       ↓
debounce
       ↓
calculate file hash
       ↓
remove/update old chunks
       ↓
chunk changed document
       ↓
generate embeddings
       ↓
Qdrant upsert
```

Obsidian API позволяет плагинам подписываться на события приложения и файловой системы Vault.

Необходимо обрабатывать:

```text
create
modify
rename
delete
```

---

# 12. BR-9. Поддержка больших заметок

Система не должна считать:

```text
1 Markdown file = 1 vector
```

Из-за особенностей пользовательских Vault некоторые Markdown-файлы могут быть очень большими.

Предполагаемые данные:

```text
Markdown files : 4,169

Average chars  : 13,237
Median chars   : 2,967

P75            : 8,743
P90            : 25,919
P95            : 42,728
P99            : 163,077

Max chars      : 2,033,440
```

Поэтому должен использоваться **Markdown-aware chunking**.

---

# 13. BR-10. Работа с Markdown-структурой

Chunker должен учитывать:

````markdown
# Heading 1

## Heading 2

### Heading 3

paragraph

- list
- list

```code```
````

Необходимо стараться сохранять логически связанные элементы внутри одного chunk.

Пример:

```text
Document
│
├── # PostgreSQL
│
├── ## Indexes
│      ├── chunk 1
│      └── chunk 2
│
├── ## Transactions
│      ├── chunk 3
│      └── chunk 4
│
└── ## Optimization
       └── chunk 5
```

---

# 14. BR-11. Фильтрация поиска

В перспективе пользователь должен иметь возможность ограничивать область поиска.

Например:

```text
Search scope:

● Entire vault
○ Current folder
○ Current note
○ Selected folders
```

Или:

```text
@University

Что я писал про градиентный спуск?
```

В Qdrant можно хранить вместе с vector произвольный payload и использовать его при поиске и фильтрации.

Например:

```json
{
    "file_path": "University/ML/GradientDescent.md",
    "folder": "University/ML",
    "heading": "Gradient Descent",
    "chunk_index": 5
}
```

---

# 15. Нефункциональные требования

## NFR-1. Offline First

После скачивания Prometheus Runtime и необходимых моделей все основные функции должны работать без сети.

Допустима однократная сеть при первой настройке:

```text
Download Prometheus Runtime
      ↓
Download / pull embedding model (если нужно)
      ↓
ollama pull <local-model>
      ↓
отключить сеть
      ↓
полноценная локальная работа
```

Базовый режим не опирается на облачные LLM API.

---

## NFR-2. Privacy First

Пользовательские данные не должны покидать устройство.

---

## NFR-3. Desktop First

Первую версию рекомендуется разрабатывать для:

```text
Obsidian Desktop

Windows
Linux
macOS
```

Поддержка мобильных версий должна рассматриваться отдельно, поскольку запуск локальной vector DB и полноценной LLM на iOS/Android существенно сложнее.

---

## NFR-4. Производительность

Semantic search должен занимать существенно меньше времени, чем генерация LLM.

Целевая последовательность:

```text
Question
 ↓
Embedding
 ↓
Vector Search
 ↓
Top-K
 ↓
LLM
```

Qdrant должен обеспечивать быстрый retrieval даже при десятках тысяч chunks.

При данном масштабе Vault нагрузка для vector DB небольшая.

---

# 16. Оценка объёма данных

Исходя из статистики:

```text
4,169 × 15,920 bytes
≈ 66.4 MB Markdown
```

Количество символов:

```text
4,169 × 13,237
≈ 55.2 млн
```

Количество слов:

```text
4,169 × 1,435
≈ 5.98 млн
```

Если после chunking получится ориентировочно:

```text
20 000–40 000 chunks
```

это остаётся небольшим набором данных для vector DB.

Для сравнения, vector:

```text
1024 float32
```

занимает:

```text
1024 × 4
=
4096 bytes
≈
4 KB
```

Даже:

```text
40 000 × 4 KB
≈ 156 MB
```

сырых vectors.

С учётом индексов, payload и служебных структур база останется вполне пригодной для хранения на обычном пользовательском компьютере.

---

# 17. Технологический стек

Предлагаемый стек:

| Компонент       | Технология                                       |
| --------------- | ------------------------------------------------ |
| Obsidian plugin | TypeScript                                       |
| Plugin API      | Obsidian API                                     |
| UI              | Obsidian View API + HTML/CSS                     |
| RAG backend     | Python                                           |
| Local interface | FastAPI / localhost                              |
| Validation      | Pydantic                                         |
| Vector DB       | Qdrant Local                                     |
| Embeddings      | FastEmbed                                        |
| LLM runtime     | Ollama                                           |
| LLM             | Qwen / Gemma / другая компактная instruct-модель |
| Tests Backend   | pytest                                           |
| Tests Plugin    | Vitest                                           |
| Packaging       | managed sidecar (freeze + first-run download) + optional custom binary path |

---

# 18. Почему Python backend

Теоретически всю систему можно реализовать внутри TypeScript-плагина:

```text
Obsidian
│
├── UI
├── chunking
├── embeddings
├── vector DB
└── LLM
```

Однако это заметно усложняет работу с ML-инфраструктурой.

Python предоставляет удобный доступ к:

```text
FastEmbed
Qdrant Client
ONNX Runtime
rerankers
tokenizers
LLM clients
```

Поэтому лучше разделить систему:

```text
Prometheus Plugin
       │
       │ localhost
       ▼
Prometheus Runtime
```

---

# 19. Зачем нужны endpoints, если приложение локальное

Endpoint не обязательно означает интернет.

Например:

```text
http://127.0.0.1:8765/search
```

является локальным endpoint.

Запрос проходит:

```text
Obsidian
   ↓
Operating System
   ↓
localhost
   ↓
Python process
```

и никогда не выходит за пределы компьютера.

Поэтому можно использовать:

```text
POST /search
POST /chat
POST /index
DELETE /document
GET /status
```

в качестве внутреннего протокола взаимодействия между TypeScript-плагином и Python runtime.

---

# 20. Граница приложения

Очень важно понимать, что:

```text
localhost API
```

не является серверной частью SaaS-приложения.

Это механизм IPC — inter-process communication.

Архитектурно:

```text
Process №1
Obsidian

       ↓

Process №2
Prometheus Runtime
```

HTTP используется только как удобный транспорт.

---

# 21. Локальная LLM

Для локального inference удобно использовать **Ollama**.

По умолчанию Ollama предоставляет локальный API:

```text
http://localhost:11434/api
```

и взаимодействие с локальной моделью происходит через этот адрес.

Для локального API Ollama отдельная аутентификация не требуется.

В UI расширения пользователь выбирает модель **только из локально установленных** (`ollama list`). Базовый режим не предлагает облачные provider API для генерации ответа.

Получается:

```text
RAG Backend
      │
      │ localhost
      ▼
    Ollama
      │
      ▼
Local LLM (установленная на машине)
```

---

# 22. Какая LLM нужна проекту

Здесь не требуется большая reasoning-модель.

Pipeline уже заранее делает:

```text
question
   ↓
retrieval
   ↓
relevant chunks
```

LLM получает:

```text
Question
+
Context
```

и должна выполнить только:

```text
read
 ↓
summarize / synthesize
 ↓
answer
```

Поэтому модель должна быть:

* сравнительно компактной;
* multilingual;
* хорошо следующей инструкциям;
* способной работать локально;
* достаточно хорошей в summarization и question answering.

---

# 23. Рекомендуемый подход к LLM

Вместо жёсткой зависимости:

```text
Project
  ↓
Qwen3
```

лучше сделать abstraction:

```text
LLMProvider
```

и позволить пользователю выбрать модель Ollama.

Например:

```text
Settings
──────────────────────────

LLM Runtime
Ollama

Model
qwen3:4b

Temperature
0.1

Context
8192
```

Qwen3 доступна в Ollama, включая компактную версию `4b`.

Другой хороший кандидат для слабого оборудования — Gemma 3 4B. Ollama распространяет 4B-вариант примерно в 3.3 GB в Q4-квантизации; семейство поддерживает большое контекстное окно и множество языков.

Поэтому разумная стратегия:

```text
Default:
Qwen 3 / Gemma 3 class 4B

Better hardware:
8B–12B model
```

Но конкретная модель не должна быть частью бизнес-логики приложения.

---

# 24. Embedding model

Для embeddings предлагается использовать **FastEmbed**.

FastEmbed представляет собой лёгкую библиотеку для локальной генерации embeddings и работает поверх ONNX Runtime.

Pipeline:

```text
chunk
 ↓
FastEmbed
 ↓
vector
 ↓
Qdrant
```

В отличие от OpenAI Embeddings API, текст не отправляется в интернет.

---

# 25. Multilingual embeddings

Поскольку заметки потенциально содержат одновременно:

```text
Russian
English
Code
technical terminology
```

embedding model должна быть multilingual.

FastEmbed поддерживает multilingual-модели, включая:

```text
intfloat/multilingual-e5-large
```

и multilingual Sentence Transformers.

Для первой версии желательно протестировать несколько моделей на собственном dataset.

Важно выбирать модель не только по benchmark, но по:

```text
Recall@K
MRR
latency
RAM usage
disk size
```

на реальных пользовательских заметках.

---

# 26. Vector DB — Qdrant

В качестве vector database предлагается **Qdrant**.

Для проекта не обязательно запускать полноценный Docker-сервер.

Qdrant поддерживает локальный embedded/in-process сценарий; документация отдельно указывает возможность запуска без отдельного сервера.

Это особенно удобно для данного проекта.

Архитектура:

```text
Prometheus Runtime
│
├── FastEmbed
│
├── Qdrant Local
│
└── RAG pipeline
```

вместо:

```text
Python
  ↓
Docker
  ↓
Qdrant server
```

---

# 27. Почему Qdrant Local предпочтительнее Qdrant Server

Для нескольких десятков тысяч chunks отдельный сервер избыточен.

Использование Qdrant Local даёт:

* меньше зависимостей;
* отсутствие Docker;
* отсутствие отдельного Qdrant-процесса;
* более простую установку;
* локальное хранение индекса;
* тот же общий подход к vector search.

Qdrant server можно оставить как альтернативный backend для будущих сценариев с очень большими Vault.

---

# 28. Общая архитектура системы

```text
                       USER COMPUTER

┌───────────────────────────────────────────────────┐
│                                                   │
│                    OBSIDIAN                       │
│                                                   │
│ ┌────────────────┐       ┌─────────────────────┐ │
│ │   Chat View    │       │   Vault Watcher     │ │
│ └───────┬────────┘       └──────────┬──────────┘ │
│         │                           │            │
│         └───────────┬───────────────┘            │
│                     │                            │
│               Plugin Service                     │
│                     │                            │
└─────────────────────┼────────────────────────────┘
                      │
                      │ localhost
                      ▼
┌───────────────────────────────────────────────────┐
│                 PROMETHEUS RUNTIME                 │
│                                                   │
│                     API                           │
│                      │                            │
│               Application Layer                   │
│                      │                            │
│                  Domain Layer                     │
│                      │                            │
│        ┌─────────────┼─────────────┐              │
│        ▼             ▼             ▼              │
│    FastEmbed     Qdrant Local    Ollama Client    │
│                                      │            │
└──────────────────────────────────────┼────────────┘
                                       │
                                       │ localhost
                                       ▼
                              ┌────────────────┐
                              │     Ollama     │
                              │                │
                              │   Local LLM    │
                              └────────────────┘

                         ✕ Internet
```
```

---

# 29. Clean Architecture

Проект хорошо подходит для **Clean Architecture**.

Основная идея:

> бизнес-логика RAG не должна зависеть от Obsidian, Qdrant, FastEmbed или Ollama.

Предлагаемая структура backend:

```text
prometheus-runtime/
│
├── domain/
│   │
│   ├── entities/
│   │   ├── document.py
│   │   ├── chunk.py
│   │   ├── search_result.py
│   │   └── answer.py
│   │
│   └── interfaces/
│       ├── vector_store.py
│       ├── embedder.py
│       ├── llm.py
│       └── document_store.py
│
├── application/
│   │
│   ├── use_cases/
│   │   ├── index_document.py
│   │   ├── index_vault.py
│   │   ├── remove_document.py
│   │   ├── search_notes.py
│   │   └── answer_question.py
│   │
│   └── services/
│       ├── chunking.py
│       ├── retrieval.py
│       └── rag.py
│
├── infrastructure/
│   │
│   ├── vector_store/
│   │   └── qdrant_store.py
│   │
│   ├── embeddings/
│   │   └── fastembed_provider.py
│   │
│   ├── llm/
│   │   └── ollama_provider.py
│   │
│   └── parser/
│       └── markdown_parser.py
│
└── presentation/
    │
    └── api/
        ├── app.py
        └── routes/
            ├── chat.py
            ├── search.py
            ├── index.py
            └── status.py
```

---

# 30. Domain Layer

Domain содержит основные сущности.

Например:

```text
Document
```

```python
Document:
    id
    path
    title
    content
    modified_at
```

Chunk:

```python
Chunk:
    id
    document_id
    text
    heading
    chunk_index
```

SearchResult:

```python
SearchResult:
    chunk
    score
```

Domain не знает:

```text
Qdrant
FastEmbed
Ollama
FastAPI
Obsidian
```

---

# 31. Ports / Interfaces

Например:

```python
class VectorStore(Protocol):

    def upsert(
        self,
        chunks: list[Chunk],
        vectors: list[list[float]]
    ) -> None:
        ...

    def search(
        self,
        vector: list[float],
        limit: int
    ) -> list[SearchResult]:
        ...
```

Embedding:

```python
class Embedder(Protocol):

    def embed_documents(
        self,
        texts: list[str]
    ) -> list[list[float]]:
        ...

    def embed_query(
        self,
        query: str
    ) -> list[float]:
        ...
```

LLM:

```python
class LLMProvider(Protocol):

    def generate(
        self,
        question: str,
        context: list[Chunk]
    ) -> str:
        ...
```

---

# 32. Infrastructure implementations

Затем инфраструктура реализует эти interfaces:

```text
VectorStore
     ↓
QdrantVectorStore
```

```text
Embedder
     ↓
FastEmbedProvider
```

```text
LLMProvider
     ↓
OllamaProvider
```

Это позволяет позже заменить:

```text
Ollama
 ↓
llama.cpp
```

или:

```text
Qdrant
 ↓
другая vector DB
```

без изменения use cases.

---

# 33. Prometheus plugin architecture

Отдельно существует TypeScript-плагин Prometheus:

```text
prometheus-plugin/
│
├── src/
│   │
│   ├── main.ts
│   │
│   ├── views/
│   │   ├── ChatView.ts
│   │   └── SearchView.ts
│   │
│   ├── settings/
│   │   └── SettingsTab.ts
│   │
│   ├── vault/
│   │   ├── VaultReader.ts
│   │   └── VaultWatcher.ts
│   │
│   ├── api/
│   │   └── RagClient.ts
│   │
│   ├── runtime/
│   │   ├── RuntimeLocator.ts
│   │   ├── RuntimeDownloader.ts
│   │   ├── RuntimeProcess.ts
│   │   └── RuntimeVersion.ts
│   │
│   └── commands/
│       ├── OpenChatCommand.ts
│       └── ReindexVaultCommand.ts
│
├── manifest.json
└── package.json
```

---

# 34. Распределение ответственности

## Prometheus Plugin

Отвечает за:

```text
UI
Vault access
Vault events
file selection
opening notes
settings
runtime download / locate / spawn / stop
local model selection (Ollama)
communication with runtime
```

## Prometheus Runtime

Отвечает за:

```text
Markdown processing
chunking
embeddings
indexing
retrieval
reranking
prompt construction
LLM
```

---

# 35. Indexing pipeline

Полная первоначальная индексация:

```text
Obsidian Vault
      ↓
Find *.md
      ↓
Read Markdown
      ↓
Normalize
      ↓
Markdown Parser
      ↓
Chunker
      ↓
FastEmbed
      ↓
Vectors
      ↓
Qdrant
```

Для каждого chunk сохраняется:

```json
{
    "document_id": "...",
    "file_path": "Backend/PostgreSQL.md",
    "heading": "Indexes",
    "chunk_index": 4,
    "content": "...",
    "content_hash": "...",
    "modified_at": "..."
}
```

---

# 36. Chunking strategy

Рекомендуемый алгоритм:

```text
Markdown Document
       ↓
split by headings
       ↓
section > max size?
       │
       ├── no → chunk
       │
       └── yes
            ↓
       split paragraphs
            ↓
       still too large?
            ↓
       sentence/token split
```

Стартовые параметры:

```text
Chunk:
500–800 tokens

Overlap:
50–100 tokens
```

Однако их необходимо рассматривать как гипотезу.

Правильные значения должны определяться экспериментально.

---

# 37. Query pipeline

```text
User Question
      ↓
FastEmbed
      ↓
Query Vector
      ↓
Qdrant
      ↓
Top 10–20 chunks
      ↓
Optional Reranker
      ↓
Top 5–8 chunks
      ↓
Prompt Builder
      ↓
Local LLM
      ↓
Answer
      ↓
Sources
```

---

# 38. Почему retrieval важнее большой LLM

Если retrieval находит неправильные документы:

```text
Question
 ↓
bad retrieval
 ↓
wrong context
 ↓
excellent LLM
 ↓
wrong answer
```

Даже очень хорошая LLM не исправит плохой контекст.

Поэтому качество системы определяется прежде всего:

```text
Parser
+
Chunking
+
Embeddings
+
Retrieval
+
Reranking
```

а не размером LLM.

---

# 39. Retrieval v1

Для MVP:

```text
Question
 ↓
Dense embedding
 ↓
Cosine similarity
 ↓
Top-K
```

Этого достаточно для первой работающей версии.

---

# 40. Retrieval v2 — Hybrid Search

Позже желательно добавить:

```text
                  ┌── Dense semantic search
Query ────────────┤
                  └── lexical search / BM25
                         ↓
                       Fusion
                         ↓
                       Top-K
```

Это особенно полезно для запросов:

```text
CVE-2026-1234
```

```text
docker compose --profile
```

```text
PostgreSQL pg_stat_statements
```

Dense search хорошо работает по смыслу, но lexical search лучше обнаруживает точные технические термины.

---

# 41. Retrieval v3 — Reranking

После первого retrieval:

```text
Top 20
```

может выполняться локальный reranker:

```text
20 chunks
    ↓
reranker
    ↓
5 best chunks
```

FastEmbed поддерживает не только embedding-модели, но и варианты моделей для более продвинутого retrieval.

---

# 42. API между Obsidian и Prometheus Runtime

Минимальный API:

```text
GET  /health

POST /index/vault

POST /index/document

DELETE /documents/{id}

POST /search

POST /chat
```

Например:

```http
POST http://127.0.0.1:8765/search
```

Request:

```json
{
    "query": "Как я оптимизировал PostgreSQL?",
    "limit": 10
}
```

Response:

```json
{
    "results": [
        {
            "path": "Database/PostgreSQL.md",
            "heading": "Optimization",
            "text": "...",
            "score": 0.89
        }
    ]
}
```

---

# 43. Chat request

```http
POST /chat
```

```json
{
    "query": "Какие варианты индексов PostgreSQL я описывал?"
}
```

Backend:

```text
query
 ↓
embed
 ↓
search
 ↓
rerank
 ↓
build prompt
 ↓
Ollama
 ↓
answer
```

Response:

```json
{
    "answer": "...",
    "sources": [
        {
            "path": "Database/PostgreSQL.md",
            "heading": "Indexes"
        }
    ]
}
```

---

# 44. Управление локальным runtime

С точки зрения пользователя приложение должно ощущаться как единое расширение.

Не стоит заставлять пользователя каждый раз вручную выполнять:

```bash
python rag.py
```

Идеальная схема:

```text
Obsidian starts
      ↓
Plugin resolves runtime binary
      ↓
binary missing? → предложить Download / указать custom path
      ↓
Plugin checks runtime HTTP
      ↓
runtime unavailable?
      ↓
start local process (spawn owned binary)
```

При закрытии Obsidian:

```text
Plugin unload
      ↓
stop owned runtime
```

При этом Ollama потенциально может работать как отдельная системная служба.

Выбор LLM в UI — только из **локально установленных** моделей Ollama (`ollama list`). Облачные provider API для генерации ответа в базовом режиме не используются.

---

# 45. Упаковка и доставка Prometheus Runtime

Community Plugin в каталоге Obsidian содержит только TypeScript-артефакты (`main.js`, `manifest.json`, стили). Prometheus Runtime — отдельный OS-специфичный процесс.

## Рекомендуемая модель: managed sidecar + optional custom path

| Режим | Назначение |
| ----- | ---------- |
| **Managed (основной)** | Плагин при первой настройке скачивает frozen binary runtime в каталог пользователя вне Vault и далее сам стартует/останавливает его |
| **Custom path (дополнительный)** | Пользователь или разработчик указывает путь к уже установленному `prometheus-runtime` |
| **In-plugin bundle** | **Не использовать** как основной канал: binary внутри `.obsidian/plugins/…` раздувает релиз, копируется на каждый Vault и рискует уехать в Obsidian Sync / Git |

Это согласуется с offline-first: сеть нужна один раз для скачивания runtime (и при необходимости embedding-модели / Ollama-модели). После установки базовый режим работает без интернета и без внешних LLM API.

## Пользовательский сценарий установки

```text
1. Установить Community Plugin
2. (один раз, при наличии сети) Download Prometheus Runtime
3. Установить Ollama и скачать локальную LLM
4. В settings выбрать модель из списка локальных
5. Дальше — полностью локальная работа
```

## Формат артефакта runtime

Runtime поставляется как **frozen binary** (PyInstaller / Nuitka или аналог) для:

```text
Windows x64
Linux x64
macOS x64
macOS arm64
```

CLI-контракт, например:

```text
prometheus-runtime serve --host 127.0.0.1 --port <port> --data-dir <prometheus>
```

Плагин при spawn передаёт data-dir и при необходимости одноразовый session token для localhost API.

## Сравнение отклонённых и принятых вариантов

```text
Managed download вне Vault     ← принять (продуктовый путь)
Custom / уже установленный     ← принять (advanced + разработка)
Binary внутри папки плагина    ← отклонить как основной канал
Docker для runtime             ← избыточно для desktop UX
Ручной python -m каждый раз    ← против требования единого расширения
```

Разработка может использовать monorepo-spawn из исходников `prometheus-runtime/` без freeze; продуктовый UX при этом остаётся managed sidecar.

## Ориентир по реализации в плагине

```text
prometheus-plugin/src/
├── runtime/
│   ├── RuntimeLocator.ts      # AppData bin / custom path
│   ├── RuntimeDownloader.ts   # first-run download + checksum
│   ├── RuntimeProcess.ts      # spawn / stop / health
│   └── RuntimeVersion.ts      # semver / совместимость с плагином
└── api/
    └── RagClient.ts
```

Релизы runtime версионируются отдельно от плагина; плагин хранит `requiredRuntimeVersion` (или диапазон) и при несовместимости предлагает обновление sidecar.

---

# 46. Состояние приложения

Plugin должен отображать:

```text
Prometheus

● Prometheus runtime: Installed (v1.2.0)
● Prometheus service: Running
● Vector index: Ready
● Ollama: Running
● LLM: qwen3:4b   (local)
● Documents: 4,169
● Chunks: 27,481

Last indexed:
2 minutes ago
```

Отдельно полезны промежуточные состояния установки:

```text
● Prometheus runtime: Downloading… 45%
● Prometheus runtime: Verifying…
● Prometheus runtime: Missing — Download required
```

Это позволит пользователю понимать состояние локального RAG.

---

# 47. Ошибки

Система должна корректно обрабатывать:

```text
Prometheus runtime not installed

Prometheus runtime download failed

Prometheus runtime checksum mismatch

Prometheus runtime version incompatible

Ollama not installed

Model not downloaded

Prometheus runtime stopped

Index corrupted

Embedding model unavailable

Insufficient RAM

Vault not indexed
```

Например:

```text
Local LLM is unavailable.

Ollama is running, but model qwen3:4b
is not installed.
```

Или:

```text
Prometheus runtime is not installed.

Download the Prometheus runtime to enable
indexing and chat. No cloud API is used.
```

---

# 48. Настройки

Пример:

```text
Prometheus Settings

Runtime
────────────────────────
Prometheus Runtime
Managed (downloaded)

Custom binary path
(optional)

Runtime version
1.2.0


Indexing
────────────────────────
Automatic indexing       ✓

Ignored folders
.attachments/
Templates/

Chunk size
700 tokens

Overlap
80 tokens


Embeddings
────────────────────────
Provider
FastEmbed

Model
multilingual model


Vector storage
────────────────────────
Qdrant Local

Path
~/.local/share/prometheus/


LLM
────────────────────────
Runtime
Ollama

Model
qwen3:4b          ← только из локально установленных

Address
127.0.0.1:11434


Privacy
────────────────────────
Network access
Updates only / Disabled
```

Список моделей LLM строится из локального Ollama, а не из каталога облачных API. После первичной установки runtime и моделей Network access может быть отключён.

---

# 49. Хранение данных

Не рекомендуется размещать Qdrant database и binary runtime непосредственно внутри:

```text
Vault/
```

или внутри:

```text
Vault/.obsidian/plugins/prometheus/
```

иначе Obsidian Sync / Git могут случайно начать синхронизировать индекс или OS-специфичный binary.

Лучше:

```text
Linux:
~/.local/share/prometheus/

macOS:
~/Library/Application Support/Prometheus/

Windows:
%LOCALAPPDATA%\Prometheus\
```

Например:

```text
prometheus/
│
├── bin/
│   └── prometheus-runtime          # managed frozen binary
│
├── models/                  # embeddings / кэши моделей
│
├── indexes/
│   └── <vault-id>/
│
├── state/
│   ├── index.json
│   └── runtime.json         # port, pid, version
│
└── logs/
```

---

# 50. Идентификация Vault

Следует поддерживать несколько Vault.

Например:

```text
Vault A
University

Vault B
Work

Vault C
Personal
```

У каждого должен быть собственный индекс:

```text
indexes/
├── 041ace.../
├── 193fcb.../
└── 451afd.../
```

Чтобы содержимое разных Vault случайно не смешивалось.

---

# 51. Безопасность localhost API

Несмотря на локальный характер приложения, backend лучше привязывать только к:

```text
127.0.0.1
```

а не:

```text
0.0.0.0
```

То есть сервис не должен быть доступен другим устройствам в локальной сети.

При необходимости plugin и runtime могут дополнительно использовать случайный session token.

---

# 52. Что считается частью системы

В рамках проекта:

```text
Prometheus Plugin
        +
Prometheus Runtime
        +
Vector Store
        +
Embedding Model
        +
LLM integration
```

Ollama можно рассматривать как внешний локальный runtime.

Доставка Prometheus Runtime:

```text
Community Plugin (тонкий TS-клиент)
        +
managed frozen Prometheus Runtime (first-run download вне Vault)
        или
custom path к уже установленному binary
```

То есть архитектурно:

```text
System
│
├── Prometheus Plugin
│     └── Runtime manager (download / spawn)
├── Prometheus Runtime (local binary)
├── Qdrant Local
├── FastEmbed
│
└── adapter → Ollama (выбор только локальных моделей)
```

---

# 53. Что не входит в первую версию

Для MVP не нужны:

```text
Cloud backend
User accounts
Authentication server
Subscriptions
Cloud vector DB
Cloud / provider LLM APIs as default generation path
Multi-agent system
Web search
Graph RAG
Knowledge graph
Agent tool calling
Complex reasoning
Remote synchronization
Bundling RAG binary inside .obsidian/plugins (in-vault install)
```

Это позволит сосредоточиться именно на качестве retrieval.

---

# 54. MVP

Первая версия должна включать:

```text
Prometheus (Obsidian Community Plugin)

Managed Prometheus Runtime delivery (first-run download)

Optional custom runtime binary path

AI Chat

Semantic Search

Markdown indexing

Markdown-aware chunking

FastEmbed

Multilingual embeddings

Qdrant Local

Dense vector search

Local LLM through Ollama

Model picker from locally installed Ollama models

Answer grounded in retrieved chunks

Links to source notes

Automatic incremental indexing

Offline operation after runtime and model install
```

---

# 55. Этап 2

После MVP:

```text
Hybrid Search
Dense + BM25

↓

Local reranker

↓

Folder filters

↓

Current-note mode

↓

Search scopes

↓

Better citations
```

---

# 56. Этап 3

Далее:

```text
Multiple embedding models

Multiple local LLM runtimes

llama.cpp support

Advanced retrieval settings

Performance profiling

RAG evaluation framework

Optional encrypted chat history
```

---

# 57. Ключевая архитектурная схема проекта

```text
┌──────────────────────────────────────────────────┐
│              Prometheus Plugin                   │
│                                                  │
│ Chat │ Search │ Settings │ VaultWatcher          │
└───────────────────────┬──────────────────────────┘
                        │
                        │ localhost
                        ▼
┌──────────────────────────────────────────────────┐
│              Prometheus Runtime                   │
│                                                  │
│                 Application                      │
│                      │                           │
│       ┌──────────────┼──────────────┐            │
│       │              │              │            │
│       ▼              ▼              ▼            │
│    Parser         Retrieval        RAG           │
│       │              │              │            │
│       ▼              ▼              ▼            │
│    Chunker       VectorStore    LLMProvider      │
│                      │              │            │
│                      ▼              ▼            │
│               Qdrant Local       Ollama          │
│                      ▲              │            │
│                      │              ▼            │
│                  FastEmbed       Local LLM        │
└──────────────────────────────────────────────────┘

                  No Internet Required
```

---

# 58. Основной архитектурный принцип

Приложение следует строить вокруг use case:

```text
AnswerQuestion
```

а не вокруг конкретных технологий.

То есть неправильно:

```text
QdrantService
    ↓
FastEmbedService
    ↓
OllamaService
```

как основа бизнес-логики.

Правильнее:

```text
AnswerQuestion
       │
       ├── Embedder
       ├── VectorStore
       └── LLMProvider
```

а уже инфраструктура решает:

```text
Embedder
   → FastEmbed

VectorStore
   → Qdrant

LLMProvider
   → Ollama
```

Именно это позволяет полноценно применить Clean Architecture.

---

# 59. Итоговые бизнес-требования

Система должна:

1. работать полностью локально;
2. не требовать интернета после установки runtime и моделей;
3. не отправлять пользовательские заметки сторонним сервисам;
4. не использовать облачные LLM API как базовый путь генерации — только локально установленные модели;
5. индексировать Markdown Vault;
6. выполнять semantic search;
7. отвечать на вопросы через локальную LLM;
8. основывать ответы только на найденных заметках;
9. показывать источники;
10. поддерживать переход к исходной заметке;
11. автоматически обновлять индекс;
12. работать с Vault из нескольких тысяч файлов;
13. корректно обрабатывать очень большие Markdown-документы;
14. поддерживать русский и английский языки;
15. предоставлять обычный semantic search без LLM;
16. доставлять Prometheus Runtime как managed sidecar вне Vault (с optional custom path);
17. обеспечивать возможность последующего расширения retrieval pipeline.

---

# 60. Итоговый рекомендуемый стек

```text
Prometheus Plugin
│
└── TypeScript
    Obsidian API
    Runtime manager (download / locate / spawn)

        ↓ localhost

Prometheus Runtime (frozen binary, managed sidecar)
│
├── FastAPI
├── Pydantic
│
├── Markdown Parser
├── Chunker
│
├── FastEmbed
│
├── Qdrant Local
│
├── Retrieval
│
└── Ollama Client

        ↓ localhost

Ollama
│
└── Local LLM (выбор из установленных моделей)
```

Упаковка: Community Plugin остаётся тонким; Prometheus Runtime доставляется first-run download во вне-Vault каталог пользователя; custom binary path — для advanced/dev. In-vault bundle binary не используется.

В качестве стартовой LLM имеет смысл рассматривать компактную multilingual instruct-модель порядка **4B**, например Qwen3 4B или Gemma 3 4B, а само приложение не связывать с конкретной моделью.

---

# 61. Итог

Для данного проекта наиболее подходящей является концепция:

> **Prometheus — local-first RAG assistant for Obsidian**

Вся пользовательская база знаний остаётся на компьютере:

```text
Markdown Notes
      ↓
Local Parser
      ↓
Local Chunking
      ↓
Local FastEmbed
      ↓
Local Qdrant
      ↓
Local Retrieval
      ↓
Local LLM
      ↓
Answer + Sources
```

При предполагаемом объёме около **4 169 Markdown-файлов и ~66 МБ исходного текста** нет необходимости создавать облачную или распределённую инфраструктуру.

Qdrant может работать локально без отдельного сервера, FastEmbed позволяет генерировать embeddings локально через ONNX, а Ollama предоставляет localhost API для локальных LLM. Модель выбирается из уже установленных локальных; облачные LLM API в базовом режиме не используются.

Prometheus Runtime доставляется как managed frozen sidecar (first-run download во вне-Vault каталог) с optional custom binary path; binary внутри папки Community Plugin не кладётся.

Главная инженерная задача проекта заключается не в выборе максимально мощной LLM, а в построении качественного pipeline:

```text
Markdown parsing
        ↓
Chunking
        ↓
Embedding
        ↓
Retrieval
        ↓
Reranking
        ↓
Context construction
        ↓
Local LLM
```

Поэтому **Clean Architecture здесь оправдана**: она позволит независимо развивать алгоритмы поиска, менять embedding-модели, Qdrant, способы chunking и локальные LLM, не переписывая центральные use cases приложения.

Итоговую архитектуру проекта можно сформулировать так:

```text
Prometheus (Obsidian Plugin)
        +
Managed Local Prometheus Runtime (sidecar)
        +
FastEmbed
        +
Qdrant Local
        +
Ollama
        +
Compact Local LLM
```

Такой вариант одновременно удовлетворяет требованиям приватности, автономности, расширяемости и производительности и хорошо подходит для реализации Prometheus как полноценного локального RAG-инструмента поверх Obsidian.
