# Duplicate Music Finder Web App

This project wraps `find_duplicate_music.py` in a small local web app.

You can:
- Select a folder from a browser UI
- Run duplicate scan for audio files
- Generate CSV and HTML reports
- Optionally run deletion modes after explicit confirmation

## What The App Does

The Python scanner finds exact duplicate audio files by:
1. Recursively scanning a root folder
2. Grouping files by size
3. Hashing candidate files (`sha256` by default)
4. Treating files with same size + same hash as duplicates

Supported audio extensions:
- `.mp3`, `.flac`, `.m4a`, `.aac`, `.ogg`, `.wav`, `.wma`, `.opus`, `.alac`

Outputs:
- `duplicate_music_report.csv`
- `duplicate_music_report.html`

## Project Structure

- `find_duplicate_music.py` - scanner and report generation
- `server.js` - Express backend that runs Python script
- `public/index.html` - UI page
- `public/app.js` - UI logic and API calls
- `package.json` - npm scripts and dependencies

## Requirements

- Windows (directory picker is implemented for Windows)
- Node.js and npm
- Python 3.10+

## Install

From project folder:

```bash
npm install
```

## Run

### Recommended (Windows with explicit Python path)

```bash
npm run start:py
```

This uses:
- `PYTHON_BIN=C:/Users/User/AppData/Local/Microsoft/WindowsApps/python3.10.exe`

### Standard

```bash
npm start
```

If `npm start` picks the wrong Python interpreter, use `npm run start:py`.

## Use The Web UI

1. Open `http://localhost:3000`
2. Click **Pick Directory** and choose the folder to scan
3. (Optional) Select a delete mode:
   - `none` (safe)
   - `oldest` (keep oldest, delete newer duplicates)
   - `newest` (keep newest, delete older duplicates)
   - `first` (keep alphabetically first path, delete others)
4. Click **Run Scan**
5. Review script output in the page
6. Open/download reports using:
   - **Open HTML report**
   - **Download CSV report**

## Delete Mode Safety

Delete modes are destructive.

Browser flow behavior:
- UI asks for confirmation before running delete mode
- Backend passes explicit `--yes` flag to Python only when confirmed
- No terminal prompt is needed in browser mode

CLI behavior:
- Without `--yes`, script asks:
  - `Type YES to continue with delete mode ...`
- With `--yes`, script proceeds non-interactively

Examples:

```bash
# Safe scan only
./find_duplicate_music.py "C:/Music"

# Delete mode with interactive confirmation
./find_duplicate_music.py "C:/Music" --delete-oldest

# Delete mode without interactive prompt
./find_duplicate_music.py "C:/Music" --delete-oldest --yes
```

## API Endpoints (Local)

- `GET /health` - health check
- `POST /select-directory` - opens native Windows folder picker
- `POST /run-scan` - runs python scan
- `GET /report/html` - serves html report
- `GET /report/csv` - downloads csv report

`POST /run-scan` body fields:
- `rootPath` (string, required)
- `algo` (string, optional, default `sha256`)
- `deleteMode` (`none|oldest|newest|first`)
- `confirmDelete` (boolean, required for non-interactive delete flow)

## Troubleshooting

### `PYTHON_BIN is not recognized`
Use the provided script:

```bash
npm run start:py
```

### Python syntax error from old interpreter
If you see syntax errors around type annotations, wrong Python version is being used. Run with:

```bash
npm run start:py
```

### Port 3000 already in use
Stop the process using port 3000, then run again.

## Notes

- This tool finds exact duplicates by content hash, not similar audio.
- Scan/deletion speed depends on number and size of files.
- Keep backups before using delete modes.
