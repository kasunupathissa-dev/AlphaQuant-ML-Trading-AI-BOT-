# AlphaQuant Release Checklist

This checklist must be completed before deploying any new version to the production server.

---

### **Release Version: `vX.X.X`**

### **Release Date: `YYYY-MM-DD`**

---

### Pre-Deployment

-   [ ] **Code Review:** All new code has been reviewed and approved by the Lead Architect.
-   [ ] **Local Testing:** The entire system (live engine + daemon) has been run successfully on a local machine.
-   [ ] **Validation Suite:** The `run_full_pipeline_v7.py` script has been executed successfully, and the walk-forward validation results meet the minimum performance criteria.
-   [ ] **Documentation Updated:**
    -   [ ] `CHANGELOG.md` has been updated with all new features and bug fixes.
    -   [ ] `README.md` has been updated if there are any changes to installation or execution.
    -   [ ] All other relevant documentation (`ARCHITECTURE.md`, `FEATURES.md`, etc.) is up-to-date.
-   [ ] **Dependencies Updated:** The `requirements.txt` file includes any new libraries.
-   [ ] **Git Tag:** The release commit has been tagged with the new version number (e.g., `git tag -a v7.7 -m "Release notes"`).
-   [ ] **Rollback Plan:** The commit hash of the *previous* stable version has been noted down in case a rollback is needed.

### Deployment

-   [ ] **Stop Production Services:** All running `screen` sessions (`v6_live`, `v6_daemon`) on the server have been terminated (`sudo killall -9 screen; screen -wipe`).
-   [ ] **Deploy Code:** The latest version has been pulled from the `main` branch of the Git repository (`git pull origin main`).
-   [ ] **Install Dependencies:** `pip install -r requirements.txt` has been run inside the server's virtual environment.
-   [ ] **Database Migration:** (If applicable) Any necessary database schema changes have been applied.
-   [ ] **Environment Variables:** All required environment variables on the server have been set and verified.
-   [ ] **Launch Services:** The `main_v7.py` and `auto_trainer_daemon.py` scripts have been launched in new `screen` sessions.

### Post-Deployment

-   [ ] **Service Verification:** `screen -ls` confirms that both services are running and `(Detached)`.
-   [ ] **Health Check:** `htop` and `df -h` show that server resources are stable.
-   [ ] **Monitoring Enabled:** The initial startup notifications have been received on Telegram.
-   [ ] **Initial Inference Cycle:** The first 3-minute inference cycle has completed successfully without errors in the live console (`screen -r v6_live`).
-   [ ] **Final Sign-off:** The system has been monitored for at least 1 hour post-deployment and is confirmed to be stable.
