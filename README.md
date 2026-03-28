# GeoCoin — Власний блокчейн з нуля

## Структура проекту

```
blockchain/
├── blockchain.py     # Ядро: Block, Transaction, Blockchain, Wallet
├── node.py           # REST API нода (Flask)
├── requirements.txt
└── README.md
```

## Встановлення

```bash
pip install flask flask-cors cryptography requests
python node.py --port 5000
```

## API Endpoints

| Метод | Шлях | Опис |
|-------|------|------|
| GET | /chain | Повний ланцюг |
| GET | /stats | Статистика |
| GET | /balance/\<address\> | Баланс адреси |
| POST | /transactions/new | Нова транзакція |
| GET | /transactions/pending | Пул транзакцій |
| POST | /mine | Майнінг блоку |
| GET | /wallet | Гаманець ноди |
| POST | /node/peers | Додати пір |
| GET | /node/sync | Синхронізація |

## Приклад використання (Python)

```python
from blockchain import Blockchain, Wallet, Transaction

# Створити блокчейн
bc = Blockchain()

# Створити гаманці
alice = Wallet()
bob = Wallet()

print(f"Alice: {alice.address}")
print(f"Bob:   {bob.address}")

# Видобути першу монети для Alice
bc.mine_block(alice.address)
print(f"Баланс Alice: {bc.get_balance(alice.address)} GEO")

# Alice надсилає Bob 5 GEO
tx = Transaction(
    sender=alice.address,
    recipient=bob.address,
    amount=5.0
)
tx.sign(alice)
bc.add_transaction(tx)

# Підтвердити транзакцію в блоці
bc.mine_block(alice.address)

print(f"Alice: {bc.get_balance(alice.address)} GEO")
print(f"Bob:   {bc.get_balance(bob.address)} GEO")
print(f"Ланцюг валідний: {bc.is_valid_chain()}")
print(f"Статистика: {bc.stats()}")
```

## Як працює Proof of Work

1. Збираємо транзакції з пулу
2. Додаємо нагороду майнеру (10 GEO)
3. Перебираємо `nonce` поки SHA-256 хеш не починається з `0000`
4. Готовий блок додається до ланцюга

## P2P мережа (запуск кількох нод)

```bash
# Термінал 1
python node.py --port 5000

# Термінал 2
python node.py --port 5001

# Підключити ноди одна до одної
curl -X POST http://localhost:5000/node/peers -H "Content-Type: application/json" -d '{"url": "http://localhost:5001"}'
curl -X POST http://localhost:5001/node/peers -H "Content-Type: application/json" -d '{"url": "http://localhost:5000"}'
```

## Ключові концепції реалізовані

- **SHA-256 хешування** — кожен блок має унікальний fingerprint
- **Proof of Work** — складність майнінгу регулюється кількістю нулів
- **ECDSA підписи** (secp256k1) — той самий алгоритм що у Bitcoin
- **Незмінність** — зміна будь-якого блоку робить весь ланцюг невалідним
- **UTXO-like баланс** — підраховується з усіх транзакцій ланцюга
- **Coinbase транзакції** — нагорода майнеру за знайдений блок
- **P2P синхронізація** — правило найдовшого ланцюга
