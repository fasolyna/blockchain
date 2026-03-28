"""
GeoCoin — власний блокчейн з нуля
Ядро: блоки, ланцюг, proof-of-work, транзакції, гаманці
"""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
import base64


# ─────────────────────────────────────────
#  ГАМАНЕЦЬ
# ─────────────────────────────────────────

class Wallet:
    """Криптографічний гаманець на основі ECDSA (secp256k1 — той самий що в Bitcoin)"""

    def __init__(self):
        self._private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
        self._public_key = self._private_key.public_key()

    @property
    def address(self) -> str:
        """Адреса = SHA256 від публічного ключа (скорочено)"""
        pub_bytes = self._public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint
        )
        return "GEO_" + hashlib.sha256(pub_bytes).hexdigest()[:32].upper()

    @property
    def public_key_hex(self) -> str:
        pub_bytes = self._public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint
        )
        return pub_bytes.hex()

    def sign(self, data: str) -> str:
        """Підписати дані приватним ключем"""
        signature = self._private_key.sign(
            data.encode(),
            ec.ECDSA(hashes.SHA256())
        )
        return base64.b64encode(signature).decode()

    def export_private(self) -> str:
        pem = self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        )
        return pem.decode()


# ─────────────────────────────────────────
#  ТРАНЗАКЦІЯ
# ─────────────────────────────────────────

@dataclass
class Transaction:
    sender: str       # адреса відправника (або "COINBASE" для нагороди)
    recipient: str    # адреса отримувача
    amount: float
    timestamp: float = field(default_factory=time.time)
    tx_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signature: str = ""
    public_key: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def signing_string(self) -> str:
        return f"{self.sender}{self.recipient}{self.amount}{self.timestamp}{self.tx_id}"

    def sign(self, wallet: Wallet):
        self.public_key = wallet.public_key_hex
        self.signature = wallet.sign(self.signing_string())

    def is_valid(self) -> bool:
        if self.sender == "COINBASE":
            return True  # coinbase не потребує підпису
        if not self.signature or not self.public_key:
            return False
        try:
            pub_bytes = bytes.fromhex(self.public_key)
            pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_bytes)
            sig_bytes = base64.b64decode(self.signature)
            pub_key.verify(sig_bytes, self.signing_string().encode(), ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            return False


# ─────────────────────────────────────────
#  БЛОК
# ─────────────────────────────────────────

@dataclass
class Block:
    index: int
    transactions: List[Transaction]
    previous_hash: str
    timestamp: float = field(default_factory=time.time)
    nonce: int = 0
    hash: str = ""

    def compute_hash(self) -> str:
        block_data = {
            "index": self.index,
            "transactions": [t.to_dict() for t in self.transactions],
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }
        block_string = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "transactions": [t.to_dict() for t in self.transactions],
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "hash": self.hash,
        }


# ─────────────────────────────────────────
#  БЛОКЧЕЙН
# ─────────────────────────────────────────

class Blockchain:
    DIFFICULTY = 4          # кількість нулів на початку хешу
    MINING_REWARD = 10.0    # нагорода майнеру за блок
    MAX_TX_PER_BLOCK = 10   # максимум транзакцій у блоці

    def __init__(self):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self._create_genesis_block()

    def _create_genesis_block(self):
        genesis = Block(
            index=0,
            transactions=[],
            previous_hash="0" * 64,
            timestamp=1700000000.0,
        )
        genesis.hash = genesis.compute_hash()
        self.chain.append(genesis)

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    @property
    def difficulty_prefix(self) -> str:
        return "0" * self.DIFFICULTY

    # ── Proof of Work ──────────────────────
    def proof_of_work(self, block: Block) -> str:
        block.nonce = 0
        computed = block.compute_hash()
        while not computed.startswith(self.difficulty_prefix):
            block.nonce += 1
            computed = block.compute_hash()
        return computed

    # ── Додати транзакцію до пулу ──────────
    def add_transaction(self, tx: Transaction) -> bool:
        if not tx.is_valid():
            raise ValueError("Невалідна транзакція (підпис не вірний)")
        if tx.sender != "COINBASE":
            balance = self.get_balance(tx.sender)
            if balance < tx.amount:
                raise ValueError(f"Недостатньо коштів: баланс {balance}, потрібно {tx.amount}")
        self.pending_transactions.append(tx)
        return True

    # ── Майнінг нового блоку ────────────────
    def mine_block(self, miner_address: str) -> Block:
        # Нагорода майнеру
        reward_tx = Transaction(
            sender="COINBASE",
            recipient=miner_address,
            amount=self.MINING_REWARD
        )
        txs = [reward_tx] + self.pending_transactions[:self.MAX_TX_PER_BLOCK]

        new_block = Block(
            index=len(self.chain),
            transactions=txs,
            previous_hash=self.last_block.hash,
        )
        new_block.hash = self.proof_of_work(new_block)
        self.chain.append(new_block)
        self.pending_transactions = self.pending_transactions[self.MAX_TX_PER_BLOCK:]
        return new_block

    # ── Баланс адреси ──────────────────────
    def get_balance(self, address: str) -> float:
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.recipient == address:
                    balance += tx.amount
                if tx.sender == address:
                    balance -= tx.amount
        return round(balance, 8)

    # ── Валідація ланцюга ──────────────────
    def is_valid_chain(self) -> bool:
        for i in range(1, len(self.chain)):
            curr = self.chain[i]
            prev = self.chain[i - 1]

            if curr.hash != curr.compute_hash():
                return False
            if curr.previous_hash != prev.hash:
                return False
            if not curr.hash.startswith(self.difficulty_prefix):
                return False
            for tx in curr.transactions:
                if not tx.is_valid():
                    return False
        return True

    # ── Статистика ────────────────────────
    def stats(self) -> dict:
        total_tx = sum(len(b.transactions) for b in self.chain)
        total_coins = sum(
            tx.amount for b in self.chain
            for tx in b.transactions if tx.sender == "COINBASE"
        )
        return {
            "blocks": len(self.chain),
            "pending_transactions": len(self.pending_transactions),
            "total_transactions": total_tx,
            "total_coins_mined": total_coins,
            "difficulty": self.DIFFICULTY,
            "is_valid": self.is_valid_chain(),
        }

    def to_dict(self) -> dict:
        return {
            "chain": [b.to_dict() for b in self.chain],
            "stats": self.stats(),
        }
