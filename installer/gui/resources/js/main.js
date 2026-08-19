// Stage 1: launch-time state check, connectivity pre-flight, and the
// real install-system/install-private calls. Still plain scaffolding —
// no styling, no real screens for Update/Repair/Uninstall (those are
// Stage 2). This file gets replaced by the real wizard in Stage 4.

function onWindowClose() {
    Neutralino.app.exit();
}

// Runs a backend command, returns { progressLines, result }. Progress
// lines are {"progress": "..."} objects the backend may emit before its
// final result line — see backend/main.py's module docstring.
async function runBackend(args) {
    const proc = await Neutralino.os.execCommand(
        `python3 backend/main.py ${args}`,
        { cwd: NL_CWD }
    );

    if (proc.exitCode !== 0) {
        throw new Error(proc.stdErr || `backend exited ${proc.exitCode}`);
    }

    const lines = proc.stdOut.trim().split('\n').filter(Boolean).map(l => JSON.parse(l));
    const progressLines = lines.filter(l => 'progress' in l).map(l => l.progress);
    const result = lines[lines.length - 1];
    return { progressLines, result };
}

async function checkInstallState() {
    const statePanel = document.getElementById('state-panel');
    try {
        const { result } = await runBackend('state');
        if (result.installed) {
            statePanel.hidden = true;
            document.getElementById('maintenance-panel').hidden = false;
            document.getElementById('maintenance-summary').textContent =
                `ARKlight is installed (${result.mode} mode) at ${result.entry}.`;
        } else {
            statePanel.hidden = true;
            document.getElementById('install-panel').hidden = false;
            await runInstallFlow();
        }
    } catch (err) {
        statePanel.textContent = `State check failed: ${err.message}`;
    }
}

// Pre-flight connectivity check per Architecture.md §4: must pass before
// anything below touches the filesystem. On failure, stop here — no
// partial venv, no partially unpacked runtime.
async function runInstallFlow() {
    const connEl = document.getElementById('connectivity-status');
    connEl.textContent = 'Checking connectivity…';

    let connResult;
    try {
        ({ result: connResult } = await runBackend('connectivity'));
    } catch (err) {
        connEl.textContent = `Connectivity check failed to run: ${err.message}`;
        return;
    }

    if (!connResult.reachable) {
        connEl.innerHTML = `
            <strong>No internet connection.</strong>
            ARKlight can't be installed, updated, or repaired without one —
            the Python runtime and package are downloaded, not bundled.
            <br/>
            <button onclick="runInstallFlow();">Retry</button>
        `;
        return;
    }
    connEl.textContent = 'Connected.';

    const choicesEl = document.getElementById('python-choices');
    choicesEl.textContent = 'Looking for a system Python…';
    let pyResult;
    try {
        ({ result: pyResult } = await runBackend('list-pythons'));
    } catch (err) {
        choicesEl.textContent = `Python detection failed: ${err.message}`;
        return;
    }

    choicesEl.innerHTML = '';
    for (const candidate of pyResult.candidates) {
        const btn = document.createElement('button');
        btn.textContent = `Use system Python ${candidate.version} (${candidate.path})`;
        btn.onclick = () => install('install-system', candidate.path);
        choicesEl.appendChild(btn);
        choicesEl.appendChild(document.createElement('br'));
    }
    const privateBtn = document.createElement('button');
    privateBtn.textContent = 'Use a private runtime instead';
    privateBtn.onclick = () => install('install-private');
    choicesEl.appendChild(privateBtn);
}

async function install(command, pythonPath) {
    const logEl = document.getElementById('install-log');
    logEl.textContent = 'Starting install…\n';

    try {
        const args = pythonPath ? `${command} ${pythonPath}` : command;
        const { progressLines, result } = await runBackend(args);
        logEl.textContent = progressLines.map(p => `-> ${p}`).join('\n')
            + `\n\nInstalled (${result.mode}). arklight at: ${result.wrapper}`
            + (result.path_needs_update
                ? `\n\n${result.wrapper} is not on PATH yet.`
                : '');
    } catch (err) {
        logEl.textContent = `Install failed: ${err.message}`;
    }
}

Neutralino.init();
Neutralino.events.on('windowClose', onWindowClose);
checkInstallState();
