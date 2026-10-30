# Test minidb-journal

## From a phone or computer

1. Sign in to GitHub and open this repository.
2. Open **Actions** and choose the test workflow in the left sidebar.
3. Tap **Run workflow**, select **main**, then tap the green **Run workflow** button.
4. Open the new run. Each version-matrix job must finish successfully.
5. Expand the test step for individual test results and **Run sample scenario** for the demo output.

Tests and the sample scenario run on GitHub's runner, not on your device. No service credentials are needed. A green result verifies the checks implemented in this repository; it does not establish untested hardware or live-service behavior.

## Locally

Follow README.md for the supported runtime and test command. The manual scenario runs these commands in a fresh checkout:

```bash
python -m minidb --db demo.journal set profile '{"name":"Synthetic demo","active":true}'
python -m minidb --db demo.journal compact
python -m minidb --db demo.journal inspect
```

Demo inputs are synthetic and local. Keep the documented platform and verification limits in mind.
