# Atraxis Python SDK

Официальный SDK для владельцев гильдий и лавок Atraxis. Он помогает подключить к гильдии
своего бота, сайт или учётную систему: посмотреть склад, работать с внутренними валютами,
выдавать ценности игрокам и получать историю операций.

```bash
pip install atraxis-sdk
```

Требуется Python 3.10 или новее. Перед началом лидер гильдии выпускает приватный токен
в разделе «Интеграции гильдии». Храните его как пароль: токен даёт доступ к операциям
вашей гильдии.

## Быстрый старт

```python
from atraxis import AtraxisClient, CurrencyTransfer

with AtraxisClient("agk_example.redacted") as client:
    for item in client.iter_warehouse():
        print(item.warehouse_item_id, item.name, item.quantity)

        if item.instance and item.instance.kind == "equipment":
            print(item.instance.level, item.instance.quality, item.instance.combat_stats)

    result = client.transfer(
        [CurrencyTransfer.to_player("TOKEN", player_id=100001, amount=25)],
        idempotency_key="order-2026-09-12-0001",
    )
    print(result.operation_id)
```

Асинхронный клиент имеет те же методы:

```python
import asyncio
from atraxis import AsyncAtraxisClient


async def main() -> None:
    async with AsyncAtraxisClient("agk_example.redacted") as client:
        async for event in client.iter_activity():
            print(event.occurred_at, event.kind, event.deposit_method, event.net)


asyncio.run(main())
```

Токен и адрес можно передать через `ATRAXIS_API_TOKEN` и `ATRAXIS_API_BASE_URL`.
По умолчанию SDK обращается к основному серверу Atraxis. Токен не включается в `repr`,
исключения или логи самого SDK.

## Что умеет SDK

- `get_warehouse`, `iter_warehouse` — склад гильдии;
- `list_currencies`, `upsert_currency` — внутренние валюты;
- `get_balances` — балансы игрока;
- `transfer` — единая операция из 1–10 переводов;
- `get_activity`, `iter_activity` — история операций гильдии и последовательное получение новых записей.

Все суммы представлены в Python как `int`, а по сети передаются десятичными строками. Модели
неизменяемы. Новые необязательные поля ответа не ломают клиент, но обязательные поля всегда
проверяются.

У предмета на складе два идентификатора: `item_id` обозначает общий тип предмета,
а `warehouse_item_id` — конкретную позицию, которую нужно передать при выдаче. Для
уникальной позиции `is_unique` равен `True`, а `instance` содержит характеристики именно
этого экземпляра: боевые параметры и улучшения экипировки, бонусы инструментов и удочек,
умения щита, свойства улова, состояние артефакта или журнала. В `condition` указаны
прочность и её единица — `percent` или `points`. Поля `durability` и `max_durability`
сохранены для совместимости со старыми подключениями.

### Переводы

```python
from atraxis import CurrencyTransfer, ItemTransfer

parts = [
    ItemTransfer(warehouse_item_id=700001, player_id=100001, amount=1),
    CurrencyTransfer.issue("TOKEN", amount=100),
    CurrencyTransfer.retire("TOKEN", amount=10),
    CurrencyTransfer.to_player("TOKEN", player_id=100001, amount=25),
    CurrencyTransfer.from_player("TOKEN", player_id=100001, amount=5),
    CurrencyTransfer.between_players(
        "TOKEN",
        from_player_id=100001,
        to_player_id=100002,
        amount=3,
    ),
]
```

Передавайте в `idempotency_key` постоянный идентификатор перевода или заказа. Если ключ не
задан, SDK создаст UUID и вернёт его в `TransferResult.idempotency_key`. Повторный `POST` внутри
SDK использует тот же ключ.

Транспортные ошибки, `429`, `502`, `503` и `504` повторяются не более двух раз. При `429`
учитывается `Retry-After`. Ошибки API представлены `AtraxisAPIError`; в них доступны безопасный
problem response и `request_id`.

Полная интерактивная документация: <https://atraxisonline.com/developers/api>.

## Как пополняется склад

Свой склад пополняют на странице гильдии или через основной бот. В привязанном чате
гильдии используйте `Внести …`. В любом чате Авроры, где работает обычное `Передать`,
можно выбрать склад любой гильдии по её уникальному тегу:

```text
Передать {ТЕГ} Стабилизатор - 2 штуки
Передать {ТЕГ} 1000 кредитов; номер 4 - 2 штуки
```

Команда с тегом не работает в общем чате. Для неё не нужны reply, пересланное сообщение
или членство в выбранной гильдии.

Через API их можно только выдавать со склада игрокам. Списать их у игрока через API нельзя.

Для учёта пополнений читайте `iter_activity()`. В новых операциях `warehouse_deposit`
поле `deposit_method` равно `guild_deposit` для обычного пополнения, в том числе команды
«Внести», и `tagged_transfer` для команды «Передать {ТЕГ}». Поле `source` уточняет канал:
`chat` — чат Авроры, `game` — страница гильдии или основной бот. Через
`asset.warehouse_item_id` операцию можно связать с позицией из `iter_warehouse()`.

Для регулярного получения новых операций достаточно хранить один `event_id`. При первом
подключении запрос без `after_event_id` возвращает историю от новых записей к старым. Если
нужно начать следить только за будущими операциями, сохраните идентификатор самой новой записи:

```python
with AtraxisClient("agk_example.redacted") as client:
    page = client.get_activity(page_size=1)
    last_event_id = page.items[0].event_id if page.items else None
```

При следующих проверках передавайте сохранённый идентификатор. SDK получит только записи после
него, в порядке от старых к новым. Сохраняйте новый идентификатор после успешной обработки каждой
записи — список прежних операций и собственная проверка дублей не нужны:

```python
if last_event_id is not None:
    with AtraxisClient("agk_example.redacted") as client:
        for event in client.iter_activity(after_event_id=last_event_id):
            process(event)
            last_event_id = event.event_id
```

`cursor` предназначен для просмотра старых страниц и не используется вместе с
`after_event_id`. `available_since` показывает начало истории, которая ещё доступна на сервере.
Если сохранённая запись уже вышла за этот срок, API попросит начать без `after_event_id` и
сохранить новый идентификатор. У старых операций `deposit_method` равен `None`, поскольку раньше
способ пополнения не сохранялся. Налоговые начисления учитываются отдельно и в этой истории
операций не возвращаются.

## Подключение к Codex и Claude Code

```bash
pip install "atraxis-sdk[mcp]"
```

MCP позволяет Codex и Claude Code подсказывать по API и работать с вашей гильдией через SDK.
Без токена помощник отвечает только по документации. С `ATRAXIS_API_TOKEN` он сможет читать
данные гильдии. Команды, которые меняют валюты или передают ценности, доступны только после
запуска с `--allow-writes`; для каждого перевода потребуется `idempotency_key`.

Codex в режиме только для чтения, с уже установленной переменной окружения:

```toml
[mcp_servers.atraxis]
command = "atraxis-mcp"
env_vars = ["ATRAXIS_API_TOKEN"]
```

Или через CLI:

```bash
codex mcp add atraxis --env ATRAXIS_API_TOKEN="$ATRAXIS_API_TOKEN" -- atraxis-mcp
```

Claude Code:

```bash
claude mcp add --transport stdio --env ATRAXIS_API_TOKEN="$ATRAXIS_API_TOKEN" atraxis -- atraxis-mcp
```

Готовые конфигурации без токенов лежат в [`examples/mcp`](examples/mcp). Чтобы разрешить
изменения, добавьте `--allow-writes` в `args` только на своём устройстве и только для помощника,
которому доверяете.

## Лицензия

MIT.
