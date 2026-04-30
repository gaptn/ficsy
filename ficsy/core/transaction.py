"""
FICSY — Transaction Layer
"""

from datetime import datetime
from uuid import uuid4

import ficsy.core.config as cfg
from ficsy.core.storage   import storage_load, storage_save
from ficsy.core.ai_tagger import ai_tag, ai_tag_manual, TagStatus


class TransactionError(Exception):
    pass


def add_transaction(
    description:       str,
    amount:            float,
    tx_type:           str,
    category_override: str = None,
    on_uncertain=None,
) -> dict:
    amount      = float(amount)
    tx_type     = tx_type.lower().strip()
    description = description.strip()

    if amount <= 0:
        raise TransactionError("Amount harus lebih dari 0.")
    if not description:
        raise TransactionError("Deskripsi tidak boleh kosong.")
    if tx_type not in ("income", "expense"):
        raise TransactionError("Type harus 'income' atau 'expense'.")

    tag_result     = None
    user_confirmed = False

    if tx_type == "expense":
        if category_override:
            tag_result     = ai_tag_manual(category_override, description)
            user_confirmed = True
        else:
            tag_result = ai_tag(description)
            if tag_result.status == TagStatus.AUTO:
                user_confirmed = False
            else:
                if on_uncertain is None:
                    raise TransactionError(
                        "AI ragu dengan kategori ini. Sediakan on_uncertain callback."
                    )
                chosen         = on_uncertain(tag_result)
                tag_result     = ai_tag_manual(chosen, description)
                user_confirmed = True

    tx = {
        "id":             str(uuid4()),
        "description":    description,
        "amount":         amount,
        "type":           tx_type,
        "auto_category":  tag_result.category.value if tag_result else None,
        "ai_confidence":  tag_result.confidence     if tag_result else None,
        "user_confirmed": user_confirmed,
        "date":           datetime.now().isoformat(),
    }

    data = storage_load()
    if tx_type == "expense":
        data["profile"]["current_balance"] -= amount
    else:
        data["profile"]["current_balance"] += amount
    data["transactions"].append(tx)
    storage_save(data)
    return tx


def get_transactions(
    limit:   int  = None,
    tx_type: str  = None,
) -> list:
    limit = limit or cfg.LIST_TX_LIMIT
    data  = storage_load()
    txs   = data.get("transactions", [])
    if tx_type:
        txs = [t for t in txs if t.get("type") == tx_type]
    txs = sorted(txs, key=lambda x: x.get("date", ""), reverse=True)
    return txs[:limit] if limit else txs


def get_balance() -> float:
    return float(storage_load()["profile"].get("current_balance", 0.0))


def get_summary() -> dict:
    data = storage_load()
    txs  = data.get("transactions", [])
    ti = te = tn = tw = 0.0
    ic = ec = 0
    for tx in txs:
        a = float(tx.get("amount", 0))
        if tx.get("type") == "income":
            ti += a; ic += 1
        elif tx.get("type") == "expense":
            te += a; ec += 1
            cat = tx.get("auto_category")
            if cat == "Needs":   tn += a
            elif cat == "Wants": tw += a
    return {
        "total_income":      ti,
        "total_expense":     te,
        "total_needs":       tn,
        "total_wants":       tw,
        "needs_pct":         round(tn / te * 100, 1) if te else 0.0,
        "wants_pct":         round(tw / te * 100, 1) if te else 0.0,
        "transaction_count": len(txs),
        "income_count":      ic,
        "expense_count":     ec,
        "current_balance":   float(data["profile"].get("current_balance", 0)),
    }
