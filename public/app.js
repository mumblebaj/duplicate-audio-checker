const rootPathInput = document.getElementById("rootPath");
const pickButton = document.getElementById("pickButton");
const runButton = document.getElementById("runButton");
const statusEl = document.getElementById("status");
const outputEl = document.getElementById("output");
const deleteModeEl = document.getElementById("deleteMode");

function setStatus(message, variant = "") {
  statusEl.textContent = message;
  statusEl.classList.remove("ok", "bad");
  if (variant) statusEl.classList.add(variant);
}

function appendOutput(text) {
  outputEl.value = text;
  outputEl.scrollTop = outputEl.scrollHeight;
}

pickButton.addEventListener("click", async () => {
  pickButton.disabled = true;
  setStatus("Opening folder picker...");

  try {
    const response = await fetch("/select-directory", {
      method: "POST"
    });

    if (response.status === 204) {
      setStatus("No directory selected.");
      return;
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: "Failed to open picker." }));
      throw new Error(err.error || "Failed to open picker.");
    }

    const data = await response.json();
    rootPathInput.value = data.selectedPath;
    setStatus("Directory selected.", "ok");
  } catch (error) {
    setStatus(error.message, "bad");
  } finally {
    pickButton.disabled = false;
  }
});

runButton.addEventListener("click", async () => {
  const rootPath = rootPathInput.value.trim();
  const deleteMode = deleteModeEl.value;
  let confirmDelete = false;

  if (!rootPath) {
    setStatus("Please choose or enter a directory first.", "bad");
    return;
  }

  const isDangerousMode = deleteMode !== "none";
  if (isDangerousMode) {
    confirmDelete = window.confirm(
      "Delete mode is selected. This will permanently delete files. Continue?"
    );
    if (!confirmDelete) {
      setStatus("Run cancelled.");
      return;
    }
  }

  runButton.disabled = true;
  setStatus("Running scan...");
  appendOutput("");

  try {
    const response = await fetch("/run-scan", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ rootPath, deleteMode, confirmDelete })
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Scan failed.");
    }

    const combinedOutput = [
      data.stdout?.trim() || "",
      data.stderr?.trim() ? `\n[stderr]\n${data.stderr.trim()}` : ""
    ].join("\n").trim();

    appendOutput(combinedOutput || "No output.");

    if (data.ok) {
      setStatus("Scan completed successfully.", "ok");
    } else {
      setStatus(`Scan ended with exit code ${data.exitCode}.`, "bad");
    }
  } catch (error) {
    appendOutput(String(error));
    setStatus(error.message, "bad");
  } finally {
    runButton.disabled = false;
  }
});
