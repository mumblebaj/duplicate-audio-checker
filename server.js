const express = require("express");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");

const app = express();
const port = process.env.PORT || 3000;

const workspaceRoot = __dirname;
const scriptPath = path.join(workspaceRoot, "find_duplicate_music.py");

function getPythonRuntime() {
  // Prefer an explicit override, but default to Python 3 launcher behavior.
  if (process.env.PYTHON_BIN) {
    return { command: process.env.PYTHON_BIN, preArgs: [] };
  }

  if (process.platform === "win32") {
    const localAppData = process.env.LOCALAPPDATA || "";
    const candidates = [
      path.join(localAppData, "Microsoft", "WindowsApps", "python3.10.exe"),
      path.join(localAppData, "Microsoft", "WindowsApps", "python3.exe"),
      path.join(localAppData, "Microsoft", "WindowsApps", "python.exe"),
      "python"
    ];

    for (const candidate of candidates) {
      if (path.isAbsolute(candidate)) {
        if (fs.existsSync(candidate)) {
          return { command: candidate, preArgs: [] };
        }
      } else {
        return { command: candidate, preArgs: [] };
      }
    }
  }

  return { command: "python3", preArgs: [] };
}

const pythonRuntime = getPythonRuntime();

app.use(express.json());
app.use(express.static(path.join(workspaceRoot, "public")));

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.post("/select-directory", (_req, res) => {
  if (process.platform !== "win32") {
    return res.status(400).json({ error: "Directory dialog is only implemented for Windows." });
  }

  const command = [
    "Add-Type -AssemblyName System.Windows.Forms",
    "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog",
    '$dialog.Description = "Select the root folder to scan"',
    '$dialog.ShowNewFolderButton = $false',
    "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $dialog.SelectedPath }"
  ].join("; ");

  const ps = spawn("powershell", ["-NoProfile", "-STA", "-Command", command], {
    cwd: workspaceRoot,
    windowsHide: true
  });

  let stdout = "";
  let stderr = "";

  ps.stdout.on("data", (chunk) => {
    stdout += chunk.toString();
  });

  ps.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });

  ps.on("close", (code) => {
    if (code !== 0) {
      return res.status(500).json({
        error: "Failed to open directory picker.",
        details: stderr.trim() || `PowerShell exited with code ${code}`
      });
    }

    const selectedPath = stdout.trim();
    if (!selectedPath) {
      return res.status(204).send();
    }

    return res.json({ selectedPath });
  });
});

app.post("/run-scan", (req, res) => {
  const { rootPath, algo = "sha256", deleteMode = "none", confirmDelete = false } = req.body || {};

  if (!rootPath || typeof rootPath !== "string") {
    return res.status(400).json({ error: "rootPath is required." });
  }

  const resolvedRoot = path.resolve(rootPath);

  if (!fs.existsSync(resolvedRoot)) {
    return res.status(400).json({ error: `Directory does not exist: ${resolvedRoot}` });
  }

  const stat = fs.statSync(resolvedRoot);
  if (!stat.isDirectory()) {
    return res.status(400).json({ error: `Path is not a directory: ${resolvedRoot}` });
  }

  const args = [...pythonRuntime.preArgs, scriptPath, resolvedRoot, "--algo", algo];
  if (deleteMode === "oldest") args.push("--delete-oldest");
  if (deleteMode === "newest") args.push("--delete-newest");
  if (deleteMode === "first") args.push("--delete-all-but-first");
  if (deleteMode !== "none" && confirmDelete) args.push("--yes");

  const processRef = spawn(pythonRuntime.command, args, {
    cwd: workspaceRoot,
    windowsHide: true
  });

  let stdout = "";
  let stderr = "";
  let responded = false;

  processRef.stdout.on("data", (chunk) => {
    stdout += chunk.toString();
  });

  processRef.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });

  processRef.on("error", (err) => {
    if (responded) return;
    responded = true;
    return res.status(500).json({
      ok: false,
      error: `Failed to start Python process: ${err.message}`,
      command: pythonRuntime.command,
      args
    });
  });

  processRef.on("close", (code) => {
    if (responded) return;
    responded = true;
    const csvPath = path.join(workspaceRoot, "duplicate_music_report.csv");
    const htmlPath = path.join(workspaceRoot, "duplicate_music_report.html");

    res.json({
      ok: code === 0,
      exitCode: code,
      stdout,
      stderr,
      csvPath,
      htmlPath,
      csvExists: fs.existsSync(csvPath),
      htmlExists: fs.existsSync(htmlPath)
    });
  });
});

app.get("/report/html", (_req, res) => {
  const reportPath = path.join(workspaceRoot, "duplicate_music_report.html");
  if (!fs.existsSync(reportPath)) {
    return res.status(404).send("HTML report not found. Run a scan first.");
  }
  return res.sendFile(reportPath);
});

app.get("/report/csv", (_req, res) => {
  const reportPath = path.join(workspaceRoot, "duplicate_music_report.csv");
  if (!fs.existsSync(reportPath)) {
    return res.status(404).send("CSV report not found. Run a scan first.");
  }
  return res.download(reportPath);
});

app.listen(port, () => {
  console.log(`Duplicate Music UI running at http://localhost:${port}`);
  console.log(`Using Python executable: ${pythonRuntime.command} ${pythonRuntime.preArgs.join(" ")}`.trim());
});
