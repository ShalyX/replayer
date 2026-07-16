# RepLayer V3.0 Release Proof

## Current implementation proof

- Contract AST parse: passed on 2026-07-14.
- GenVM AST lint: passed 3 checks on 2026-07-14.
- Deterministic V3 smoke command: `npm run smoke:v3.0`.
- Result: a 30/70 shared-responsibility event produced distinct principal and worker Passport impacts, then rebuilt identically after deleting all agent projections.
- SDK TypeScript build: passed.

## GenVM semantic-lint exception

Command run on 2026-07-14:

```powershell
& 'C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\Scripts\genvm-lint.exe' check contracts/agent_reputation_ledger_v2.py --json
```

Exact failing artifact URL:

```text
https://github.com/genlayerlabs/genvm/releases/download/v0.3.0-rc7/genvm-universal.tar.xz
```

Exact result:

```json
{"ok":false,"lint":{"ok":true,"passed":3},"validate":{"ok":false,"errors":[{"code":"E101","msg":"Failed to load SDK: HTTP Error 404: Not Found"}]}}
```

Semantic lint is not marked successful. Live V3 contract deployment, responsibility transaction hashes, contract readback, indexer health, and no-mock acceptance evidence must be added here after deployment.

