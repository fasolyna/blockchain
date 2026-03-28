"""
GeoCoin Node — REST API
Запуск: python node.py --port 5000
"""

import argparse
import json
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from blockchain import Blockchain, Transaction, Wallet

app = Flask(__name__)
CORS(app)

# Стан ноди
blockchain = Blockchain()
node_wallet = Wallet()
peers: set = set()  # адреси інших нод


# ─── БЛОКЧЕЙН ────────────────────────────

@app.route("/chain", methods=["GET"])
def get_chain():
    return jsonify(blockchain.to_dict())


@app.route("/stats", methods=["GET"])
def get_stats():
    return jsonify(blockchain.stats())


@app.route("/balance/<address>", methods=["GET"])
def get_balance(address):
    return jsonify({
        "address": address,
        "balance": blockchain.get_balance(address)
    })


# ─── ТРАНЗАКЦІЇ ──────────────────────────

@app.route("/transactions/pending", methods=["GET"])
def pending_transactions():
    return jsonify([t.to_dict() for t in blockchain.pending_transactions])


@app.route("/transactions/new", methods=["POST"])
def new_transaction():
    data = request.get_json()
    required = ["sender", "recipient", "amount", "signature", "public_key", "tx_id", "timestamp"]
    if not all(k in data for k in required):
        return jsonify({"error": "Відсутні поля транзакції"}), 400

    tx = Transaction(
        sender=data["sender"],
        recipient=data["recipient"],
        amount=float(data["amount"]),
        timestamp=float(data["timestamp"]),
        tx_id=data["tx_id"],
        signature=data["signature"],
        public_key=data["public_key"],
    )
    try:
        blockchain.add_transaction(tx)
        # Розповсюдити транзакцію на пірів
        for peer in peers:
            try:
                requests.post(f"{peer}/transactions/new", json=data, timeout=2)
            except Exception:
                pass
        return jsonify({"message": "Транзакцію додано до пулу", "tx_id": tx.tx_id})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ─── МАЙНІНГ ─────────────────────────────

@app.route("/mine", methods=["POST"])
def mine():
    data = request.get_json() or {}
    miner = data.get("miner_address", node_wallet.address)

    block = blockchain.mine_block(miner)

    # Синхронізувати новий блок з пірами
    for peer in peers:
        try:
            requests.post(f"{peer}/blocks/receive", json=block.to_dict(), timeout=2)
        except Exception:
            pass

    return jsonify({
        "message": "Блок успішно знайдено!",
        "block": block.to_dict(),
        "reward": blockchain.MINING_REWARD,
        "miner": miner,
    })


# ─── НОДА / P2P ──────────────────────────

@app.route("/node/info", methods=["GET"])
def node_info():
    return jsonify({
        "address": node_wallet.address,
        "public_key": node_wallet.public_key_hex,
        "peers": list(peers),
        "chain_length": len(blockchain.chain),
    })


@app.route("/node/peers", methods=["POST"])
def register_peer():
    data = request.get_json()
    peer_url = data.get("url")
    if not peer_url:
        return jsonify({"error": "Потрібен url"}), 400
    peers.add(peer_url)
    return jsonify({"message": f"Пір {peer_url} зареєстровано", "peers": list(peers)})


@app.route("/blocks/receive", methods=["POST"])
def receive_block():
    """Отримати новий блок від іншої ноди"""
    # Спрощена логіка: якщо ланцюг піра довший — синхронізуватись
    _sync_with_peers()
    return jsonify({"message": "Отримано"})


@app.route("/node/sync", methods=["GET"])
def sync():
    _sync_with_peers()
    return jsonify({"message": "Синхронізовано", "chain_length": len(blockchain.chain)})


def _sync_with_peers():
    """Замінити ланцюг на найдовший валідний серед пірів"""
    global blockchain
    longest = len(blockchain.chain)
    new_chain_data = None

    for peer in peers:
        try:
            resp = requests.get(f"{peer}/chain", timeout=3)
            data = resp.json()
            peer_length = len(data["chain"])
            if peer_length > longest:
                longest = peer_length
                new_chain_data = data["chain"]
        except Exception:
            pass

    if new_chain_data:
        # TODO: десеріалізувати та валідувати новий ланцюг
        pass


# ─── ГАМАНЕЦЬ НОДИ ───────────────────────

@app.route("/wallet", methods=["GET"])
def wallet_info():
    return jsonify({
        "address": node_wallet.address,
        "balance": blockchain.get_balance(node_wallet.address),
        "public_key": node_wallet.public_key_hex,
    })


if __name__ == "__main__":
    import os
    parser = argparse.ArgumentParser(description="GeoCoin Node")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)))
    args = parser.parse_args()
    print(f"🚀 GeoCoin нода запущена на порту {args.port}")
    print(f"📬 Адреса гаманця: {node_wallet.address}")
    app.run(host="0.0.0.0", port=args.port, debug=False)
