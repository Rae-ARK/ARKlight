// Stage 4: the real wizard. Backend contract (command names, args,
// result shapes) is unchanged from Stage 1-2 — see backend/main.py's
// module docstring. What changes here is presentation only: a screen
// per moment instead of hidden <div> panels, the beam rail tracking
// progress, and real explanatory copy for the connectivity-failure and
// repair-pivot moments instead of raw log lines.

// Set once checkInstallState() sees an existing install; drives which
// backend commands Update/Repair call ("system" vs "private").
let currentMode = null;

const content = document.getElementById('content');
const beamEl = document.getElementById('beam');
const modeLabel = document.getElementById('mode-label');

const INSTALL_STAGES = ['Check', 'Connect', 'Runtime', 'Install', 'Done'];

function onWindowClose() {
    Neutralino.app.exit();
}

// Neutralino's own console forwarding stringifies rejection reasons as
// "[object Object]", which is unreadable. Log the actual message/stack
// (or the raw reason for non-Error rejections) so failures here are
// diagnosable instead of just noise.
window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    const detail = reason && (reason.stack || reason.message) || JSON.stringify(reason);
    console.error('Unhandled promise rejection:', detail);
});

// --- Theme -----------------------------------------------------------

function toggleTheme() {
    const root = document.documentElement;
    const current = root.getAttribute('data-theme')
        || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    root.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
}

// --- Beam rail ---------------------------------------------------------

// items: [{label, state}] where state is 'pending' | 'active' | 'done' | 'error'
function renderBeam(items) {
    beamEl.innerHTML = '';
    for (const item of items) {
        const row = document.createElement('div');
        row.className = `beam-step ${item.state}`;
        row.innerHTML = `<span class="track"><span class="beam-dot"></span></span><span class="beam-label">${item.label}</span>`;
        beamEl.appendChild(row);
    }
}

function beamForInstall(activeIndex, errorIndex) {
    renderBeam(INSTALL_STAGES.map((label, i) => ({
        label,
        state: errorIndex === i ? 'error' : i < activeIndex ? 'done' : i === activeIndex ? 'active' : 'pending',
    })));
}

function beamForMaintenance(busy) {
    renderBeam([{ label: 'Installed', state: busy ? 'active' : 'done' }]);
    modeLabel.textContent = currentMode ? `${currentMode} mode` : '';
}

// --- Screen rendering ----------------------------------------------------

function render(html) {
    const screen = document.createElement('div');
    screen.className = 'screen';
    screen.innerHTML = html;
    content.innerHTML = '';
    content.appendChild(screen);
    return screen;
}

function stepListHtml(lines) {
    if (!lines.length) return '';
    const items = lines.map((line, i) =>
        `<li style="animation-delay:${i * 70}ms"><span class="mark">&#10003;</span>${escapeHtml(line)}</li>`
    ).join('');
    return `<ul class="step-list">${items}</ul>`;
}

function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

// --- Backend bridge --------------------------------------------------------

// Runs a backend command, returns { progressLines, result }. Progress
// lines are {"progress": "..."} objects the backend may emit before its
// final result line — see backend/main.py's module docstring.
async function runBackend(args) {
    // NL_PATH is the directory the app itself is installed/running from
    // (where CMakeLists.txt installs backend/ alongside the binary — see
    // installer/CMakeLists.txt). NL_CWD is wherever the user's shell
    // happened to be when they launched the AppImage/binary, which has
    // nothing to do with where backend/ actually lives — using it here
    // was the "can't open file .../backend/main.py" bug. Quote the path:
    // real install locations can contain spaces (e.g. a partition or
    // folder name with a space in it).
    const backendMain = `${NL_PATH}/backend/main.py`;
    const proc = await Neutralino.os.execCommand(
        `python3 "${backendMain}" ${args}`,
        { cwd: NL_PATH }
    );

    if (proc.exitCode !== 0) {
        throw new Error(proc.stdErr || `backend exited ${proc.exitCode}`);
    }

    const lines = proc.stdOut.trim().split('\n').filter(Boolean).map(l => JSON.parse(l));
    const progressLines = lines.filter(l => 'progress' in l).map(l => l.progress);
    const result = lines[lines.length - 1];
    return { progressLines, result };
}

// --- Launch: state check -----------------------------------------------

async function checkInstallState() {
    beamForInstall(0);
    render(`
        <p class="eyebrow">Starting up</p>
        <h1 class="screen-title">Checking your system</h1>
        <p class="screen-body">Looking for an existing ARKlight install…</p>
    `);

    // Window starts hidden (neutralino.config.json "hidden": true) to avoid
    // the blank/white flash during Neutralino's ~1-1.5s startup (see
    // Neutralino issue #1217). Show it now that the first real screen has
    // actually been painted above, instead of the empty scaffold.
    Neutralino.window.show();

    try {
        const { result } = await runBackend('state');
        if (result.installed) {
            currentMode = result.mode;
            renderMaintenanceHome(result);
        } else {
            await runInstallFlow();
        }
    } catch (err) {
        beamForInstall(0, 0);
        render(`
            <p class="eyebrow">Startup failed</p>
            <h1 class="screen-title">Couldn't check install state</h1>
            <div class="callout callout-warn">
                <p class="callout-title">${escapeHtml(err.message)}</p>
                <p class="callout-body">This runs before anything else — nothing on your system has been touched.</p>
            </div>
            <div class="btn-row">
                <button class="btn btn-primary" onclick="checkInstallState();">Try again</button>
            </div>
        `);
    }
}

// --- Install flow --------------------------------------------------------

// Pre-flight connectivity check per Architecture.md §4: must pass before
// anything below touches the filesystem. On failure, stop here — no
// partial venv, no partially unpacked runtime.
async function runInstallFlow() {
    beamForInstall(1);
    render(`
        <p class="eyebrow">Install &middot; 1 of 3</p>
        <h1 class="screen-title">Checking your connection</h1>
        <div class="status-row"><span class="status-dot busy"></span><span class="screen-body" style="margin:0;">Reaching out to PyPI…</span></div>
    `);

    let connResult;
    try {
        ({ result: connResult } = await runBackend('connectivity'));
    } catch (err) {
        renderConnectivityCheckFailed(err);
        return;
    }

    if (!connResult.reachable) {
        renderNoConnection();
        return;
    }

    await showRuntimeChoice();
}

function renderConnectivityCheckFailed(err) {
    beamForInstall(1, 1);
    render(`
        <p class="eyebrow">Install &middot; 1 of 3</p>
        <h1 class="screen-title">Checking your connection</h1>
        <div class="callout callout-warn">
            <p class="callout-title">The connection check itself didn't run</p>
            <p class="callout-body mono">${escapeHtml(err.message)}</p>
        </div>
        <div class="btn-row">
            <button class="btn btn-primary" onclick="runInstallFlow();">Retry</button>
        </div>
    `);
}

function renderNoConnection() {
    beamForInstall(1, 1);
    render(`
        <p class="eyebrow">Install &middot; 1 of 3</p>
        <h1 class="screen-title">No internet connection</h1>
        <div class="callout callout-warn">
            <p class="callout-title">ARKlight can't be installed offline</p>
            <p class="callout-body">
                The Python runtime and the ARKlight package itself are
                downloaded during install, not bundled into this installer —
                that's what keeps it small. Reconnect, then retry.
            </p>
        </div>
        <div class="btn-row">
            <button class="btn btn-primary" onclick="runInstallFlow();">Retry</button>
        </div>
    `);
}

async function showRuntimeChoice() {
    beamForInstall(2);
    render(`
        <p class="eyebrow">Install &middot; 2 of 3</p>
        <h1 class="screen-title">Choose a Python runtime</h1>
        <div class="status-row"><span class="status-dot busy"></span><span class="screen-body" style="margin:0;">Looking for a system Python…</span></div>
    `);

    let pyResult;
    try {
        ({ result: pyResult } = await runBackend('list-pythons'));
    } catch (err) {
        beamForInstall(2, 2);
        render(`
            <p class="eyebrow">Install &middot; 2 of 3</p>
            <h1 class="screen-title">Python detection failed</h1>
            <div class="callout callout-warn">
                <p class="callout-title">${escapeHtml(err.message)}</p>
            </div>
            <div class="btn-row">
                <button class="btn btn-primary" onclick="showRuntimeChoice();">Try again</button>
            </div>
        `);
        return;
    }

    const choices = pyResult.candidates.map(c => `
        <button class="choice" onclick="beginInstall('install-system', '${escapeHtml(c.path).replace(/'/g, "\\'")}');">
            <span class="choice-title">System Python ${escapeHtml(c.version)}</span>
            <span class="choice-sub">${escapeHtml(c.path)}</span>
        </button>
    `).join('');

    render(`
        <p class="eyebrow">Install &middot; 2 of 3</p>
        <h1 class="screen-title">Choose a Python runtime</h1>
        <p class="screen-body">
            ${pyResult.candidates.length
                ? 'Use an interpreter already on your system, or install a private one just for ARKlight.'
                : "No system Python was found — a private runtime downloaded just for ARKlight is the way to go."}
        </p>
        <div class="choice-list">
            ${choices}
            <button class="choice" onclick="beginInstall('install-private');">
                <span class="choice-title">Private runtime</span>
                <span class="choice-sub">downloads its own Python, self-contained</span>
            </button>
        </div>
    `);
}

async function beginInstall(command, pythonPath) {
    beamForInstall(3);
    render(`
        <p class="eyebrow">Install &middot; 3 of 3</p>
        <h1 class="screen-title">Installing ARKlight</h1>
        <div class="status-row"><span class="status-dot busy"></span><span class="screen-body" style="margin:0;">This takes a moment…</span></div>
    `);

    try {
        const args = pythonPath ? `${command} ${pythonPath}` : command;
        const { progressLines, result } = await runBackend(args);
        currentMode = result.mode;
        beamForInstall(4);
        render(`
            <p class="eyebrow">Install &middot; 3 of 3</p>
            <h1 class="screen-title">Installing ARKlight</h1>
            ${stepListHtml(progressLines)}
            <div class="card">
                <p class="card-title">Installed (${escapeHtml(result.mode)} mode)</p>
                <p class="card-body">Run <span class="entry-path">arklight</span> from
                <span class="entry-path">${escapeHtml(result.wrapper)}</span></p>
            </div>
            ${result.path_needs_update ? `
                <div class="callout callout-info" style="margin-top:10px;">
                    <p class="callout-title">One more step</p>
                    <p class="callout-body">
                        <code>${escapeHtml(result.wrapper)}</code> isn't on your
                        PATH yet — add its folder to your shell's PATH to run
                        <code>arklight</code> directly.
                    </p>
                </div>
            ` : ''}
            <div class="btn-row">
                <button class="btn btn-primary" onclick="checkInstallState();">Continue</button>
            </div>
        `);
    } catch (err) {
        beamForInstall(3, 3);
        render(`
            <p class="eyebrow">Install &middot; 3 of 3</p>
            <h1 class="screen-title">Install failed</h1>
            <div class="callout callout-warn">
                <p class="callout-title">${escapeHtml(err.message)}</p>
            </div>
            <div class="btn-row">
                <button class="btn btn-primary" onclick="showRuntimeChoice();">Back to runtime choice</button>
            </div>
        `);
    }
}

// --- Maintenance mode: Update / Repair / Uninstall -----------------------

function renderMaintenanceHome(stateResult) {
    beamForMaintenance(false);
    render(`
        <p class="eyebrow">${escapeHtml(currentMode)} mode</p>
        <h1 class="screen-title">ARKlight is installed</h1>
        <div class="card" style="margin-bottom:20px;">
            <p class="card-title">Entry point</p>
            <p class="card-body"><span class="entry-path">${escapeHtml(stateResult.entry)}</span></p>
        </div>
        <div class="btn-row">
            <button class="btn btn-primary" onclick="runUpdate();">Update</button>
            <button class="btn" onclick="runRepairCheck();">Repair</button>
            <button class="btn btn-danger" onclick="showUninstallConfirm();">Uninstall</button>
        </div>
    `);
}

// Shared connectivity pre-flight for Update/Repair, same rule as Install
// (Architecture.md §4): stop before touching the filesystem if this fails.
async function requireConnectivity(onFail) {
    beamForMaintenance(true);
    let connResult;
    try {
        ({ result: connResult } = await runBackend('connectivity'));
    } catch (err) {
        onFail(`The connection check itself didn't run: ${err.message}`);
        return false;
    }
    if (!connResult.reachable) {
        onFail(
            "No internet connection. This step needs one — the runtime and " +
            "ARKlight itself are downloaded, not bundled, so there's nothing " +
            "to fall back to offline."
        );
        return false;
    }
    return true;
}

function renderMaintenanceBlocked(eyebrow, title, message) {
    beamForMaintenance(false);
    render(`
        <p class="eyebrow">${escapeHtml(eyebrow)}</p>
        <h1 class="screen-title">${escapeHtml(title)}</h1>
        <div class="callout callout-warn">
            <p class="callout-body" style="margin:0;">${escapeHtml(message)}</p>
        </div>
        <div class="btn-row">
            <button class="btn btn-primary" onclick="renderMaintenanceHomeAgain();">Back</button>
        </div>
    `);
}

async function renderMaintenanceHomeAgain() {
    try {
        const { result } = await runBackend('state');
        renderMaintenanceHome(result);
    } catch (err) {
        renderMaintenanceBlocked('Maintenance', "Couldn't refresh state", err.message);
    }
}

async function runUpdate() {
    let blocked = false;
    const ok = await requireConnectivity((msg) => {
        blocked = true;
        renderMaintenanceBlocked('Update', 'No connection', msg);
    });
    if (!ok) return;

    render(`
        <p class="eyebrow">Update</p>
        <h1 class="screen-title">Updating ARKlight</h1>
        <div class="status-row"><span class="status-dot busy"></span><span class="screen-body" style="margin:0;">Fetching the current release…</span></div>
    `);

    try {
        const command = currentMode === 'system' ? 'update-system' : 'update-private';
        const { progressLines, result } = await runBackend(command);
        beamForMaintenance(false);
        render(`
            <p class="eyebrow">Update</p>
            <h1 class="screen-title">ARKlight is up to date</h1>
            ${stepListHtml(progressLines)}
            <div class="card">
                <p class="card-title">Updated (${escapeHtml(result.mode)} mode)</p>
                <p class="card-body"><span class="entry-path">${escapeHtml(result.entry)}</span></p>
            </div>
            <div class="btn-row">
                <button class="btn btn-primary" onclick="renderMaintenanceHomeAgain();">Back</button>
            </div>
        `);
    } catch (err) {
        renderMaintenanceBlocked('Update', 'Update failed', err.message);
    }
}

async function runRepairCheck() {
    let blocked = false;
    const ok = await requireConnectivity((msg) => {
        blocked = true;
        renderMaintenanceBlocked('Repair', 'No connection', msg);
    });
    if (!ok) return;

    render(`
        <p class="eyebrow">Repair</p>
        <h1 class="screen-title">Checking your install</h1>
        <div class="status-row"><span class="status-dot busy"></span><span class="screen-body" style="margin:0;">Validating the Python interpreter this install depends on…</span></div>
    `);

    let checkResult;
    try {
        ({ result: checkResult } = await runBackend('check-repair'));
    } catch (err) {
        renderMaintenanceBlocked('Repair', 'Repair check failed', err.message);
        return;
    }

    if (checkResult.mode === 'private') {
        await runRepair('repair-private');
        return;
    }

    if (checkResult.mode === 'system' && checkResult.interpreter_valid) {
        await runRepair('repair-system');
        return;
    }

    if (checkResult.mode === 'system' && !checkResult.interpreter_valid) {
        // Architecture.md §3's pivot case: the interpreter this install's
        // venv depends on is gone. Offer the fix, don't just fail.
        beamForMaintenance(false);
        render(`
            <p class="eyebrow">Repair</p>
            <h1 class="screen-title">The original Python is gone</h1>
            <div class="callout callout-info">
                <p class="callout-title">Switch to a private runtime?</p>
                <p class="callout-body">
                    This install depends on
                    <code>${escapeHtml(checkResult.interpreter || 'an interpreter that')}</code>
                    still existing at its original path, and it no longer
                    does — likely removed or upgraded outside ARKlight.
                    Repair can move this install onto a private, self
                    contained Python that only ARKlight uses, so this can't
                    happen again.
                </p>
                <div class="btn-row">
                    <button class="btn btn-primary" onclick="runRepair('repair-pivot');">Switch to a private runtime</button>
                    <button class="btn" onclick="renderMaintenanceHomeAgain();">Cancel</button>
                </div>
            </div>
        `);
        return;
    }

    renderMaintenanceBlocked('Repair', 'Nothing to repair', 'No issue was found with the current install.');
}

async function runRepair(command) {
    beamForMaintenance(true);
    render(`
        <p class="eyebrow">Repair</p>
        <h1 class="screen-title">Repairing ARKlight</h1>
        <div class="status-row"><span class="status-dot busy"></span><span class="screen-body" style="margin:0;">This takes a moment…</span></div>
    `);

    try {
        const { progressLines, result } = await runBackend(command);
        currentMode = result.mode;
        beamForMaintenance(false);
        render(`
            <p class="eyebrow">Repair</p>
            <h1 class="screen-title">Repaired</h1>
            ${stepListHtml(progressLines)}
            <div class="card">
                <p class="card-title">Now running in ${escapeHtml(result.mode)} mode</p>
                <p class="card-body"><span class="entry-path">${escapeHtml(result.entry)}</span></p>
            </div>
            <div class="btn-row">
                <button class="btn btn-primary" onclick="renderMaintenanceHomeAgain();">Back</button>
            </div>
        `);
    } catch (err) {
        renderMaintenanceBlocked('Repair', 'Repair failed', err.message);
    }
}

function showUninstallConfirm() {
    beamForMaintenance(false);
    render(`
        <p class="eyebrow">Uninstall</p>
        <h1 class="screen-title">Remove ARKlight?</h1>
        <div class="callout callout-warn">
            <p class="callout-body" style="margin:0;">
                This removes the ARKlight install and its <code>.ark</code>
                bundle file association. This can't be undone from here.
            </p>
        </div>
        <div class="confirm-actions">
            <button class="btn btn-danger" onclick="doUninstall();">Yes, uninstall</button>
            <button class="btn" onclick="renderMaintenanceHomeAgain();">Cancel</button>
        </div>
    `);
}

async function doUninstall() {
    beamForMaintenance(true);
    render(`
        <p class="eyebrow">Uninstall</p>
        <h1 class="screen-title">Uninstalling ARKlight</h1>
        <div class="status-row"><span class="status-dot busy"></span><span class="screen-body" style="margin:0;">This takes a moment…</span></div>
    `);

    try {
        const { progressLines } = await runBackend('uninstall');
        renderBeam([{ label: 'Uninstalled', state: 'done' }]);
        modeLabel.textContent = '';
        render(`
            <p class="eyebrow">Uninstall</p>
            <h1 class="screen-title">ARKlight has been removed</h1>
            ${stepListHtml(progressLines)}
            <p class="screen-body">
                You can close this window. Run the installer again any time
                to reinstall ARKlight.
            </p>
        `);
        // Installer-binary self-delete isn't wired up yet — there's no
        // packaged single-binary artifact to point it at until Stage 3.
    } catch (err) {
        renderMaintenanceBlocked('Uninstall', 'Uninstall failed', err.message);
    }
}

// --- Boot -----------------------------------------------------------------

Neutralino.init();
Neutralino.events.on('windowClose', onWindowClose);
checkInstallState();
