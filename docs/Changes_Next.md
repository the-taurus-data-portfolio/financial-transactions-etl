# Цели изменений (Ingestion & Archiving)

Реализация универсального механизма получения данных (Ingestion) и их архивации, поддерживающего как локальную файловую систему, так и Google Drive. 

**Ключевые возможности:**
1. **Абстракция источника:** Переход от прямой работы с файлами к интерфейсу `SourceProvider`.
2. **Поддержка Google Drive:** Чтение CSV-файлов из облачной папки и их перемещение в облачный архив.
3. **Безопасность:** Использование Service Account с ограниченным доступом (только к конкретным папкам и таблицам).
4. **Централизованная конфигурация:** Единый блок настроек для Google сервисов.

---

# План имплементации

## 1. Подготовка GCP и Безопасность
- **API:** Включить **Google Drive API** в консоли GCP.
- **Доступ:** 
    - Использовать существующий Service Account.
    - **Важно:** Поделиться (Share) с email сервис-аккаунта только двумя конкретными папками (`Input` и `Archive`) с правами "Editor".
    - Это обеспечит принцип минимальных привилегий (доступ только к нужным данным, а не ко всему диску).

## 2. Конфигурация (`config/config.yaml`)
Перенос настроек авторизации в общий блок и разделение источников:

```yaml
google_auth:
  credentials_file: "config/credentials/test-spreadsheet-credentials.json"

source:
  type: "gdrive" # "local" или "gdrive"
  local:
    input_dir: "data/input"
  gdrive:
    input_folder_id: "ID_ПАПКИ_ВХОДА"

archiving:
  enabled: true
  type: "gdrive" # "local" или "gdrive"
  local:
    archive_dir: "data/archive"
    add_timestamp: false
  gdrive:
    archive_folder_id: "ID_ПАПКИ_АРХИВА"
```
Comment: комментарии как в коде, так и в конфигурации должны быть исключительно на английском языке
## 3. Архитектура (Интерфейсы)
В `src/core/interfaces.py` добавим новый интерфейс:

```python
class SourceProvider(ABC):
    @abstractmethod
    def list_files(self) -> List[Dict[str, Any]]:
        """Возвращает список метаданных файлов (имя, ID/путь)."""
        pass

    @abstractmethod
    def get_file_content(self, identifier: Any) -> io.BytesIO:
        """Возвращает содержимое файла для обработки."""
        pass
```

## 4. Имплементация провайдеров
1. **`LocalSourceProvider`**: 
    - Реализация через `pathlib`.
    - Фильтрация по расширениям из конфига (`.csv`).
2. **`GDriveSourceProvider`**:
    - Использует `google-api-python-client`.
    - Поиск файлов в папке `input_folder_id` с фильтром `mimeType = 'text/csv'`.
    - Метод `get_file_content` скачивает файл в `io.BytesIO`.

## 5. Имплементация архиваторов
1. **`LocalFileArchiver`**: (Уже реализован, обновить согласно интерфейсу).
2. **`GDriveFileArchiver`**:
    - Реализует `SourceArchiver`.
    - Использует метод `files().update` для "перемещения": удаляет `input_folder_id` из родителей и добавляет `archive_folder_id`.

## 6. Изменения в Pipeline (`src/core/etl_pipeline.py`)
- Добавить **SourceFactory**, которая на основе `config['source']['type']` создает нужного провайдера.
- Перевести метод `run()` на работу с `SourceProvider`:
    1. Получить список файлов через `provider.list_files()`.
    2. Для каждого файла получить контент через `provider.get_file_content()`.
    3. Отдать контент в `GenericSourceConverter`.
    4. При успехе всей партии вызвать `archiver.archive()`.

---

# Уточняющие вопросы

1. **Библиотеки:** Для GDrive потребуется `google-api-python-client` и `google-auth-httplib2`. Устанавливаем их в `requirements.txt`? - Да
2. **Порядок архивации на GDrive:** В Google Drive один файл может иметь несколько "родителей". При перемещении мы будем строго удалять старую папку и добавлять новую. Это стандартное поведение, согласны? - Согласен
3. **Логирование ID:** В GDrive у файлов могут быть одинаковые имена, но разные ID. Нужно ли в логах выводить ID файла для точности диагностики? - Если это не будет слишком verbose, можно выводить в скобках. Если же слишком verbose, то отдельный лог рекорд (with ID) с уровнем DEBUG. Но первый вариант предпочтительнее 
