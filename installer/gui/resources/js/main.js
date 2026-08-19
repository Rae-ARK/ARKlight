// Stage 0: shell scaffolding. Proves the Neutralino shell can call out
// to the Python backend and get structured output back. Everything here
// gets replaced by real detection/install/lifecycle logic in later
// stages — this file is not meant to survive Stage 1 in its current form.

function onWindowClose() {
    Neutralino.app.exit();
}

async function pingBackend() {
    const resultEl = document.getElementById('result');
    resultEl.textContent = 'running...';

    try {
        // Backend is a plain Python script for now (Stage 0). Stage 1
        // wires this same call shape to detect.py / install.py instead.
        const proc = await Neutralino.os.execCommand(
            'python3 backend/main.py ping',
            { cwd: NL_CWD }
        );

        if (proc.exitCode !== 0) {
            resultEl.textContent = `backend exited ${proc.exitCode}\n${proc.stdErr}`;
            return;
        }

        const parsed = JSON.parse(proc.stdOut);
        resultEl.textContent = JSON.stringify(parsed, null, 2);
    } catch (err) {
        resultEl.textContent = `call failed: ${err.message || err}`;
    }
}

Neutralino.init();
Neutralino.events.on('windowClose', onWindowClose);
