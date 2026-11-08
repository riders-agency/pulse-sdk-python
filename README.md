# Pulse SDK · Python

Синхронный клиент API v1 для Python 3.12+. Только стандартная библиотека.
Пакет устанавливается из GitHub; в каталоге PyPI ещё не опубликован:

```bash
python -m pip install "git+https://github.com/riders-agency/pulse-sdk-python.git@v0.1.0"
```

```python
import os
from pulse_sdk import PulseClient

pulse = PulseClient(os.environ["PULSE_URL"], os.environ["PULSE_ACCESS_TOKEN"])
project = os.environ["PULSE_PROJECT_ID"]
tasks = pulse.list_tasks(project, limit=20)
session = pulse.create_session(project)
reply = pulse.send_message(project, session["ai_chat_session_id"],
                           "Создай задачу Подготовить прототип завтра",
                           timezone="Europe/Moscow")
proposals = [call for call in reply.get("tool_calls", [])
             if call["status"] == "pending_approval"]
# Покажите input_json пользователю. Только после его подтверждения:
# pulse.approve_proposal(project, proposals[0]["ai_tool_call_id"])
```

`login(email, password)` хранит access token в памяти; `logout()` отзывает сессию.
Токены не обновляются автоматически. `PulseError.status` и `.request_id` позволяют
обработать ошибку без записи тела ответа и ключа в журнал. Ответы — обычные
словари с исходными JSON-полями. Сессия либо API-ключ должны иметь нужные права;
ИИ-сценарий проверен с пользовательской сессией.

Поддерживаются задачи (список, чтение, создание, изменение, архив, восстановление),
ИИ-сессии и предложения. Другие JSON-маршруты доступны через `request`.
SSE, загрузки и браузерные cookie не входят в эту версию. Таймаут 60 секунд
применяется к операциям сокета, а не ко всему диалогу целиком.

Запросы не повторяются автоматически. После таймаута записи проверьте результат
через `get_task` или `get_session`. HTTPS обязателен вне localhost;
перенаправления запрещены. Храните ключи вне кода и не печатайте ответы авторизации.

[FastAPI, Django и Flask](https://github.com/riders-agency/pulse-open-source/blob/main/sdk/frameworks/python.md)
используют `pulse_sdk.frameworks.from_request` — отдельный клиент для каждого
запроса. Для разработки из папки SDK: `python -m pip install .`, затем
`PYTHONPATH=src python -m unittest discover -s tests -v`.
