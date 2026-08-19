// Stage 2: launch-time state check, connectivity pre-flight, the real
// install-system/install-private calls (Stage 1), plus real
// Update/Repair/Uninstall (Stage 2). Still plain scaffolding — no
// styling, no real screen flow or copy for the connectivity/repair-pivot
// moments (that's Stage 4). This file gets replaced by the real wizard
// in Stage 4.

// Set once checkInstallState() sees an existing install; drives which
// backend commands Update/Repair call ("system" vs "private").
let currentMode = null;

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
            currentMode = result.mode;
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

// Shared connectivity pre-flight for Update/Repair, same rule as Install
// (Architecture.md §4): stop before touching the filesystem if this fails.
async function requireConnectivity(logEl) {
    logEl.textContent = 'Checking connectivity…';
    let connResult;
    try {
        ({ result: connResult } = await runBackend('connectivity'));
    } catch (err) {
        logEl.textContent = `Connectivity check failed to run: ${err.message}`;
        return false;
    }
    if (!connResult.reachable) {
        logEl.textContent =
            'No internet connection. This step needs one — the runtime ' +
            'and package are downloaded, not bundled. Retry once connected.';
        return false;
    }
    return true;
}

async function update() {
    const logEl = document.getElementById('maintenance-log');
    if (!(await requireConnectivity(logEl))) return;

    logEl.textContent = 'Updating…\n';
    try {
        const command = currentMode === 'system' ? 'update-system' : 'update-private';
        const { progressLines, result } = await runBackend(command);
        logEl.textContent = progressLines.map(p => `-> ${p}`).join('\n')
            + `\n\nUpdated (${result.mode}). arklight at: ${result.entry}`;
    } catch (err) {
        logEl.textContent = `Update failed: ${err.message}`;
    }
}

async function repair() {
    const logEl = document.getElementById('maintenance-log');
    const statusEl = document.getElementById('repair-status');
    statusEl.innerHTML = '';
    if (!(await requireConnectivity(logEl))) return;

    logEl.textContent = 'Checking install…\n';
    let checkResult;
    try {
        ({ result: checkResult } = await runBackend('check-repair'));
    } catch (err) {
        logEl.textContent = `Repair check failed: ${err.message}`;
        return;
    }

    if (checkResult.mode === 'private') {
        await runRepair('repair-private', logEl);
        return;
    }

    if (checkResult.mode === 'system' && checkResult.interpreter_valid) {
        await runRepair('repair-system', logEl);
        return;
    }

    if (checkResult.mode === 'system' && !checkResult.interpreter_valid) {
        // The interpreter this install's venv depends on is gone —
        // Architecture.md §3's pivot case. Offer, don't just fail.
        statusEl.innerHTML = `
            <p>The Python interpreter this install depends on
            (${checkResult.interpreter || 'unknown path'}) is no longer
            there. Repair can switch this install to a private, self
            contained runtime instead.</p>
            <button onclick="runRepair('repair-pivot', document.getElementById('maintenance-log'));">
                Switch to a private runtime
            </button>
        `;
        logEl.textContent = 'Waiting for a choice above.';
        return;
    }

    logEl.textContent = 'Nothing found to repair.';
}

async function runRepair(command, logEl) {
    logEl.textContent = 'Repairing…\n';
    try {
        const { progressLines, result } = await runBackend(command);
        currentMode = result.mode;
        logEl.textContent = progressLines.map(p => `-> ${p}`).join('\n')
            + `\n\nRepaired (${result.mode}). arklight at: ${result.entry}`;
    } catch (err) {
        logEl.textContent = `Repair failed: ${err.message}`;
    }
}

function confirmUninstall() {
    document.getElementById('uninstall-confirm').hidden = false;
}

async function doUninstall() {
    document.getElementById('uninstall-confirm').hidden = true;
    const logEl = document.getElementById('maintenance-log');
    logEl.textContent = 'Uninstalling…\n';
    try {
        const { progressLines } = await runBackend('uninstall');
        logEl.textContent = progressLines.map(p => `-> ${p}`).join('\n')
            + '\n\nUninstalled.';
        // Installer-binary self-delete isn't wired up yet — there's no
        // packaged single-binary artifact to point it at until Stage 3.
        document.getElementById('btn-update').disabled = true;
        document.getElementById('btn-repair').disabled = true;
        document.getElementById('btn-uninstall').disabled = true;
    } catch (err) {
        logEl.textContent = `Uninstall failed: ${err.message}`;
    }
}

Neutralino.init();
Neutralino.events.on('windowClose', onWindowClose);
checkInstallState();
