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
            print(event.occurred_at, event.kind, event.net)


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
- `get_activity`, `iter_activity` — история операций гильдии.

Все суммы представлены в Python как `int`, а по сети передаются десятичными строками. Модели
неизменяемы. Новые необязательные поля ответа не ломают клиент, но обязательные поля всегда
проверяются.

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

Предметы, кредиты и Эхоны кладут на склад на странице гильдии, через основной бот
или командой `Внести …` в привязанном чате с Авророй.

Через API их можно только выдавать со склада игрокам. Списать их у игрока через API нельзя.

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
