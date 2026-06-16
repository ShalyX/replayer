import json
import os
import re
import subprocess

from .config import settings


class GenLayerClient:
    def __init__(self) -> None:
        self.contract_address = settings.genlayer_contract_address
        self.mode = settings.genlayer_mode
        self.password = settings.genlayer_account_password

    def enabled(self) -> bool:
        return self.mode == "live"

    def _run(self, args: list[str], password: bool = False) -> str:
        stdin = f"{self.password}\n" if password and self.password else None
        command = ["genlayer", *args]
        if os.name == "nt":
            command = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                os.path.join(os.environ.get("APPDATA", ""), "npm", "genlayer.ps1"),
                *args,
            ]
        completed = subprocess.run(
            command,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
            timeout=240,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode != 0 and not self._accepted_receipt(output) and not self._parse_tx_hash(output):
            raise RuntimeError(output)
        return output

    def write(self, method: str, args: list[str]) -> dict:
        if not self.enabled():
            return {"mode": "mock", "method": method, "tx_id": f"mock-{method}"}
        output = self._run(["write", self.contract_address, method, "--args", *[str(arg) for arg in args]], password=True)
        tx_id = self._parse_tx_hash(output)
        if tx_id and self._rpc_fetch_failed(output):
            return {
                "mode": "live",
                "method": method,
                "tx_id": tx_id,
                "contract_address": self.contract_address,
                "verify_url": self.verify_url(tx_id),
                "warning": "GenLayer transaction was submitted, but RPC readback timed out.",
            }
        if self._accepted_receipt(output) and tx_id:
            return {
                "mode": "live",
                "method": method,
                "tx_id": tx_id,
                "contract_address": self.contract_address,
                "verify_url": self.verify_url(tx_id),
            }
        if self._contract_failed(output):
            raise RuntimeError(output)
        return {
            "mode": "live",
            "method": method,
            "tx_id": tx_id,
            "contract_address": self.contract_address,
            "verify_url": self.verify_url(tx_id),
        }

    def call_json(self, method: str, args: list[str]) -> dict | str | None:
        if not self.enabled():
            return None
        output = self._run(["call", self.contract_address, method, "--args", *[str(arg) for arg in args]])
        marker = "Result:"
        if marker not in output:
            return None
        payload = output.split(marker, 1)[1].strip().splitlines()[0]
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload

    def verify_url(self, tx_id: str) -> str:
        if not tx_id:
            return ""
        return f"{settings.genlayer_explorer_base_url.rstrip('/')}/{tx_id}"

    @staticmethod
    def _parse_tx_hash(output: str) -> str:
        clean_output = re.sub(r"\x1b\[[0-9;]*m", "", output)
        patterns = [
            r"Write Transaction Hash:\s*[\r\n]+\s*(0x[a-fA-F0-9]{64})",
            r"Transaction Hash:\s*[\r\n]+\s*(0x[a-fA-F0-9]{64})",
            r"transaction_hash:\s*'?(0x[a-fA-F0-9]{64})'?",
            r"tx_id:\s*'?(0x[a-fA-F0-9]{64})'?",
            r"hash:\s*'?(0x[a-fA-F0-9]{64})'?",
            r"\b(0x[a-fA-F0-9]{64})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, clean_output)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _leader_execution_result(output: str) -> str:
        match = re.search(r"leader_receipt:\s*\[\s*\{\s*execution_result:\s*'([A-Z_]+)'", output, re.S)
        if match:
            return match.group(1)
        match = re.search(r"execution_result:\s*'([A-Z_]+)'", output)
        return match.group(1) if match else "UNKNOWN"

    @staticmethod
    def _contract_failed(output: str) -> bool:
        if "contract_error" in output:
            return True
        if GenLayerClient._accepted_receipt(output):
            return False
        if "TypeError:" in output or "Exception:" in output:
            return True
        return GenLayerClient._leader_execution_result(output) == "ERROR"

    @staticmethod
    def _rpc_fetch_failed(output: str) -> bool:
        return "fetch failed" in output or "UnknownRpcError" in output or "UND_ERR_CONNECT_TIMEOUT" in output

    @staticmethod
    def _accepted_receipt(output: str) -> bool:
        return (
            "status_name: 'ACCEPTED'" in output
            or "status_name: 'FINALIZED'" in output
            or "Write operation successfully executed" in output
        )
