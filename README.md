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
    warehouse = client.get_warehouse()
    for item in warehouse.items:
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

- `get_warehouse`, `iter_warehouse` — весь склад гильдии одним запросом;
- `list_currencies`, `upsert_currency` — внутренние валюты;
- `resolve_player_identities` — все подтверждённые ID одного игрока по игровому или платформенному ID;
- `get_balances` — балансы игрока;
- `transfer` — единая операция из 1–10 переводов;
- `get_activity`, `iter_activity`, `iter_new_activity` — история операций гильдии и последовательное получение новых записей.

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
Для `/activity` доступно до 300 запросов в минуту с одного IP и 60 на гильдию. Остальные методы
имеют отдельный лимит: до 100 запросов с IP и 60 на гильдию.

Полная интерактивная документация: <https://atraxisonline.com/developers/api>.

### Кроссплатформенные идентификаторы

Лавке не нужно отдельно просить покупателя зарегистрировать ID в Telegram, VK или на другой платформе.
Передайте любой известный идентификатор, и API вернёт игровой ID вместе со всеми текущими
подтверждёнными привязками:

```python
with AtraxisClient("agk_example.redacted") as client:
    identities = client.resolve_player_identities("telegram", "987654321")
    game_id = int(identities.by_platform["game"])
```

`platform` — строковый slug платформы: `game` либо значение `provider` из `/api/providers`. Это не
закрытый список, поэтому новые платформы начинают работать без обновления SDK. Внешний
`player_id` считается непрозрачной строкой и передаётся без преобразований.

## Как пополняется склад и выдаются предметы

Свой склад пополняют на странице гильдии или через основной бот. В привязанном чате
гильдии используйте `Внести …`. Участник с правом брать предметы со склада может там же
использовать `Забрать …`. Обе команды принимают до 10 позиций через точку с запятой:

```text
Внести Стабилизатор - 2 штуки; 1000 кредитов
Забрать Стабилизатор - 2 штуки; номер 4
```

`Номер N` относится к последнему списку соответствующего раздела склада в основном боте.
Права, принадлежность к гильдии привязанного чата, доступность предмета и место в сумке
проверяются заново при каждой команде. Повтор одного события чата не выдаёт предметы дважды.

В любом чате Авроры, где работает обычное `Передать`, можно выбрать склад любой гильдии
по её уникальному тегу:

```text
Передать ТЕГ Стабилизатор - 2 штуки
Передать ТЕГ 1000 кредитов; номер 4 - 2 штуки
```

Тег указывается первым аргументом без скобок. Команда с тегом не работает в общем чате.
Для неё не нужны reply, пересланное сообщение
или членство в выбранной гильдии.

Через API их можно только выдавать со склада игрокам. Списать их у игрока через API нельзя.

Для учёта пополнений читайте `iter_activity()`. В новых операциях `warehouse_deposit`
поле `deposit_method` равно `guild_deposit` для обычного пополнения, в том числе команды
«Внести», и `tagged_transfer` для команды «Передать ТЕГ». Поле `source` уточняет канал:
`chat` — чат Авроры, `game` — страница гильдии или основной бот. Поле
`source_identity` содержит фактические `platform` и `player_id`, с которых пришло новое
пополнение; у старых и системных записей оно отсутствует. Поле
`warehouse_item` сохраняет характеристики конкретного экземпляра и количество в позиции до и
после передачи, даже если позднее предмет исчезнет со склада. В старых записях этого поля нет:
SDK не подставляет вместо исторических данных текущее состояние.
Новая выдача через `Забрать …` записывается как `warehouse_withdrawal` с `source="chat"`;
метод `iter_activity()` получает её без отдельного SDK-вызова.

Для регулярного получения новых операций достаточно хранить один `event_id`. При первом
подключении запрос без `after_event_id` возвращает историю от новых записей к старым. Если
нужно начать следить только за будущими операциями, сохраните идентификатор самой новой записи:

```python
with AtraxisClient("agk_example.redacted") as client:
    page = client.get_activity(page_size=1)
    last_event_id = page.items[0].event_id if page.items else None
```

При следующих проверках передавайте сохранённый идентификатор. `iter_new_activity` явно запрашивает
порядок от старых к новым и проходит все страницы одной выборки. Сохраняйте новый идентификатор
после успешной обработки каждой записи — список прежних операций и собственная проверка дублей
не нужны:

```python
if last_event_id is not None:
    with AtraxisClient("agk_example.redacted") as client:
        for event in client.iter_new_activity(after_event_id=last_event_id):
            process(event)
            last_event_id = event.event_id
```

`after_event_id` только исключает указанную и более старые записи и не меняет сортировку.
`get_activity` принимает `order="desc"` или `order="asc"`; `cursor` можно передавать вместе с
`after_event_id`, если он получен для тех же параметров. `available_since` показывает начало
истории, которая ещё доступна на сервере.
Если сохранённая запись уже вышла за этот срок, API попросит начать без `after_event_id` и
сохранить новый идентификатор. У старых и системных пополнений `deposit_method` может
отсутствовать. Налоговые начисления учитываются отдельно и в этой истории операций не
возвращаются.

Для первоначальной сверки вызовите `get_warehouse()`: метод возвращает весь склад без пагинации.
В ответе доступен `activity_checkpoint`. Передайте его в `iter_new_activity`, чтобы затем получать
операции, появившиеся после этой сверки. Налоги и системные механики могут менять склад без записи
в истории передач, поэтому периодически запрашивайте склад заново.

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
