# Shared Oracle wallet setup

All Oracle passwords are entries in **one shared wallet** owned by Watchword. This application reads the same host directory as the other three apps. Select an existing credential alias; do not create a separate project wallet or store an Oracle password in this application.

For a fresh deployment of all four projects, follow [Watchword installation](https://github.com/oorona/watchword/blob/main/docs/INSTALLATION.md). It creates one `.env` in the Watchword checkout, initializes the shared wallet and adds existing accounts through `wallet add`.

For independent deployment, set `WALLET_HOST_PATH` to the same absolute host wallet root used by Watchword. Use the base Compose wallet mount. Set the same shared registry path and UID/GID. Every target uses `/wallets` plus a lowercase credential alias; arbitrary wallet directories are rejected.

Account creation, grants and existing passwords come from the DBA. Per-project Oracle provisioning/seed commands are disabled. Consumers reject administrative accounts. Verify a real connection and workload after registering access.

See [the wallet contract](SHARED_ORACLE_WALLET.md) and [shared registry](SHARED_DATABASE_REGISTRY.md).
