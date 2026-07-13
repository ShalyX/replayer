from __future__ import annotations

import base58
from eth_account import Account
from eth_account.messages import encode_defunct
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey


def registration_message(agent_id: str, identity: str, nonce: str) -> str:
    return f"RepLayer identity registration\nagent:{agent_id}\nidentity:{normalize_identity(identity)}\nnonce:{nonce}"


def binding_message(source_agent_id: str, target_agent_id: str, nonce: str) -> str:
    return f"RepLayer identity link\nsource:{source_agent_id}\ntarget:{target_agent_id}\nnonce:{nonce}"


def normalize_identity(identity: str) -> str:
    value = identity.strip()
    parts = value.split(":")
    if len(parts) < 2:
        raise ValueError("Identity must be chain-qualified, for example base:0x... or solana:...")
    account = parts[-1]
    namespace = ":".join(parts[:-1]).lower()
    if namespace == "solana":
        if len(base58.b58decode(account)) != 32:
            raise ValueError("Invalid Solana public key")
        return f"solana:{account}"
    if namespace == "base" or namespace.startswith("eip155:"):
        if not account.startswith("0x") or len(account) != 42:
            raise ValueError("Invalid EVM controller address")
        return f"{namespace}:{account.lower()}"
    raise ValueError("Unsupported identity namespace")


def verify_identity_signature(identity: str, message: str, signature: str) -> str:
    normalized = normalize_identity(identity)
    namespace, account = normalized.rsplit(":", 1)
    if namespace == "solana":
        try:
            VerifyKey(base58.b58decode(account)).verify(message.encode("utf-8"), base58.b58decode(signature))
        except (BadSignatureError, ValueError) as exc:
            raise ValueError("Invalid Solana controller signature") from exc
        return account
    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
    except Exception as exc:
        raise ValueError("Invalid EVM controller signature") from exc
    if recovered.lower() != account.lower():
        raise ValueError("Signature does not match the claimed EVM controller")
    return recovered.lower()
