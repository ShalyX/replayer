import json
import os
import re
import shutil
import subprocess

from .config import settings


class GenLayerClient:
    def __init__(self) -> None:
        self.contract_address = settings.genlayer_contract_address
        self.mode = settings.genlayer_mode
        self.password = settings.genlayer_account_password

    def enabled(self) -> bool:
        return self.mode == "live"

    def require_live(self) -> None:
        if not self.enabled() and not settings.allow_test_mocks:
            raise RuntimeError("GENLAYER_MODE=mock is disabled outside automated tests")

    def _run(self, args: list[str], password: bool = False) -> str:
        stdin = f"{self.password}\n" if password and self.password else None
        command = ["genlayer", *args]
        if os.name == "nt":
            launcher = shutil.which("genlayer.cmd") or shutil.which("genlayer.exe") or shutil.which("genlayer")
            ps1 = os.path.join(os.environ.get("APPDATA", ""), "npm", "genlayer.ps1")
            if launcher and launcher.lower().endswith((".cmd", ".bat")):
                command = ["cmd.exe", "/d", "/s", "/c", launcher, *args]
            elif launcher:
                command = [launcher, *args]
            elif os.path.exists(ps1):
                command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, *args]
            else:
                raise RuntimeError(
                    "GenLayer CLI is not installed or is not on PATH. Install it, restart the API process, "
                    "then run npm run indexer:once."
                )
        completed = subprocess.run(
            command,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
            timeout=settings.genlayer_command_timeout_seconds,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        if (
            completed.returncode != 0
            and not self._accepted_receipt(output)
            and not self._parse_tx_hash(output)
            and not self._rpc_fetch_failed(output)
        ):
            raise RuntimeError(output)
        return output

    def write(self, method: str, args: list[str]) -> dict:
        if not self.enabled():
            self.require_live()
            return {"mode": "test-mock", "method": method, "tx_id": f"test-mock-{method}"}
        output = self._run(
            ["write", self.contract_address, method, "--args", *[str(arg) for arg in args]],
            password=True,
        )
        tx_id = self._parse_tx_hash(output)
        execution_result = self._leader_execution_result(output)
        contract_error = self._contract_error(output)
        if self._contract_failed(output) and not self._accepted_receipt(output):
            raise RuntimeError(output)
        if self._rpc_fetch_failed(output) and not tx_id:
            raise RuntimeError(output)
        if tx_id and self._rpc_fetch_failed(output):
            return {
                "mode": "live",
                "method": method,
                "tx_id": tx_id,
                "contract_address": self.contract_address,
                "verify_url": self.verify_url(tx_id),
                "warning": "GenLayer transaction was submitted, but RPC readback timed out.",
                "execution_result": execution_result,
                "contract_error": contract_error,
            }
        if self._accepted_receipt(output) and tx_id:
            return {
                "mode": "live",
                "method": method,
                "tx_id": tx_id,
                "contract_address": self.contract_address,
                "verify_url": self.verify_url(tx_id),
                "execution_result": execution_result,
                "contract_error": contract_error,
            }
        return {
            "mode": "live",
            "method": method,
            "tx_id": tx_id,
            "contract_address": self.contract_address,
            "verify_url": self.verify_url(tx_id),
            "execution_result": execution_result,
            "contract_error": contract_error,
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
            parsed = json.loads(payload)
            if isinstance(parsed, str) and parsed.strip().startswith(("{", "[")):
                return json.loads(parsed)
            return parsed
        except json.JSONDecodeError:
            return payload

    def receipt_diagnostics(self, tx_id: str) -> dict:
        if not re.fullmatch(r"0x[a-fA-F0-9]{64}", tx_id):
            raise ValueError("Invalid GenLayer transaction hash")
        output = self._run([
            "receipt", tx_id, "--status", "ACCEPTED", "--stdout", "--stderr",
            "--retries", "1", "--interval", "1000",
        ])
        return {
            "transaction_hash": tx_id,
            "execution_result": self._leader_execution_result(output),
            "contract_error": self._contract_error(output),
            "output": output[-12000:],
        }

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
        if GenLayerClient._leader_execution_result(output) == "ERROR":
            return True
        error = re.search(r"contract_error:\s*['\"]([^'\"]+)['\"]", output)
        if error and error.group(1).strip().lower() not in {"", "none", "null"}:
            return True
        return False

    @staticmethod
    def _contract_error(output: str) -> str:
        error = re.search(r"contract_error:\s*['\"]([^'\"]+)['\"]", output)
        return error.group(1).strip() if error else ""

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
