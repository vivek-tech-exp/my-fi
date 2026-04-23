# my-fi

**Your money, your machine, your data.**

A local-first personal banking tool that imports your bank CSV exports into a clean, searchable ledger — entirely on your computer. No cloud. No accounts. No data leaves your machine.

## ⚡ Quickstart

```bash
# 1. Clone the repo
git clone https://github.com/vivek-tech-exp/my-fi.git
cd my-fi

# 2. Run setup (installs everything automatically)
./setup.sh

# 3. Start the app
make run
```

Then open **http://127.0.0.1:8000/ui** in your browser. That's it.

> **First time?** The setup script checks for Python 3.12+ and `uv`, installs them if needed, and sets up all dependencies. You don't need to install anything manually.

## 📂 Supported Banks

| Bank | CSV Format | Sample File |
|---|---|---|
| HDFC | Debit/Credit statement export | `samples/hdfc_sample.csv` |
| Kotak | Full statement with preamble | `samples/kotak_sample.csv` |
| Federal | Standard statement export | `samples/federal_sample.csv` |

More banks can be added — see [CONTRIBUTING.md](CONTRIBUTING.md).

## 🧪 Try It Out

After running `make run`:

1. Open **http://127.0.0.1:8000/ui** in your browser
2. Select a bank (e.g., `hdfc`)
3. Upload the sample file from `samples/hdfc_sample.csv`
4. See your transactions parsed and displayed instantly

The sample CSVs contain **completely synthetic data** — fake transactions, fake amounts. They exist so you can test the full flow immediately.

## 🔧 Everyday Commands

```bash
make run          # Start the app
make test         # Run the test suite
make lint         # Check code quality (ruff + mypy)
make clean        # Wipe all data (fresh start)
make clean-cache  # Clear tool caches (mypy, ruff, pytest)
make help         # Show all available commands
```

## 📁 Where Is My Data?

All your data lives in **`~/.my-fi/`** on your machine:

```
~/.my-fi/
├── data/
│   ├── uploads/          ← your uploaded bank CSVs
│   └── quarantine/       ← files that couldn't be read
├── storage/
│   ├── my_fi.duckdb      ← your local database
│   ├── logs/             ← import diagnostic logs
│   └── upload-staging/   ← temporary upload chunks
```

- **Your data never leaves your computer.** There is no cloud, no telemetry, no external calls.
- **Data is separate from code.** You can update or re-clone the repo without losing anything.
- **Want data inside the repo instead?** Set `MY_FI_DATA_DIR=./data` in your `.env` file.

## 🧱 How It Works

```
Bank CSV → Upload API → Parser → Canonical Ledger → Local UI
                                      ↓
                              DuckDB (on disk)
```

- **FastAPI** serves the API and a lightweight browser UI
- **Bank-specific parsers** normalize different CSV formats into a canonical schema
- **DuckDB** stores everything locally — no database server needed
- **Validation** checks every import for duplicates, balance mismatches, and suspicious rows

## 🖥 What You Can Do

- Upload CSV files (single or batch) for any supported bank
- Browse your transaction history with filters (bank, account, date range, direction)
- View monthly summaries
- Inspect import reports and raw-row audit trails
- Reprocess a stored import anytime

<details>
<summary><strong>📋 Full API Reference</strong></summary>

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Root |
| `GET` | `/health` | Health check |
| `GET` | `/ui` | Browser-based local console |
| `POST` | `/imports/csv` | Upload a single CSV |
| `POST` | `/imports/csv/batch` | Upload multiple CSVs |
| `GET` | `/imports` | List all imports |
| `GET` | `/imports/{file_id}` | Import details + validation report |
| `GET` | `/imports/{file_id}/report` | Validation report only |
| `GET` | `/imports/{file_id}/rows` | Raw-row audit trail |
| `POST` | `/imports/{file_id}/reprocess` | Re-run parser + validation |
| `GET` | `/transactions` | Query canonical ledger |
| `GET` | `/transactions/summary` | Monthly aggregates |

Interactive API docs available at `http://127.0.0.1:8000/docs` when the server is running.

</details>

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions and guidelines.

## 📄 License

[MIT](LICENSE) — use it however you want.
