# iCloud sync with systemd --user

This repo contains a small `systemd --user` setup that watches a local folder and syncs it bidirectionally with an rclone iCloud Drive remote using `rclone bisync`.

## 1. Install the right rclone for iCloud

iCloud Drive support is sensitive to Apple's authentication changes. In rclone issue [#8587](https://github.com/rclone/rclone/issues/8587), users hit `Invalid Session Token` with normal releases such as `v1.70.x` through `v1.72.x`. The rclone maintainer merged the iCloud SRP authentication fix in PR [#9209](https://github.com/rclone/rclone/pull/9209) on 2026-04-02 and asked users to test the latest beta.

As of 2026-04-26, the stable download page lists `v1.73.5`, which predates that merge. For iCloud, install the latest beta unless stable rclone has moved past the fix:

```sh
sudo -v
curl https://rclone.org/install.sh | sudo bash -s beta
rclone version
```

If rclone is already installed:

```sh
sudo rclone selfupdate --beta
rclone version
```

If you do not want to replace the system rclone, download a beta binary manually from <https://beta.rclone.org/>, put it somewhere like `~/.local/bin/rclone`, and set this in `config.json`:

```json
"rclone_bin": "/home/linanw/.local/bin/rclone"
```

After installing the beta, create an iCloud Drive remote:

```sh
rclone config
rclone lsd icloud:
```

If your remote is not named `icloud`, edit `config.json`.

## 2. Edit paths

Edit `config.json`:

```json
{
  "local_path": "~/#icloud_sync",
  "icloud_path": "icloud:#icloud_sync"
}
```

`config.json` is the source of truth. The installer copies it to `~/.config/icloud-sync/config.json`, installs app code to `~/.local/share/icloud-sync`, and writes matching systemd user units.

## 3. Install the user units

```sh
./install.sh
```

Re-run this after changing `local_path` in `config.json`:

```sh
./install.sh
```

After first installation, edit the deployed config directly:

```sh
$EDITOR ~/.config/icloud-sync/config.json
./install.sh
```

To overwrite the deployed config from this repo's `config.json`:

```sh
./install.sh --force-config
```

## 4. First bisync run

Bisync must be initialized once with `--resync`. Start with a dry run:

```sh
python3 ~/.local/share/icloud-sync/icloud-bisync.py dry-run-resync --config ~/.config/icloud-sync/config.json
```

If the output looks correct, run the real resync once:

```sh
python3 ~/.local/share/icloud-sync/icloud-bisync.py resync --config ~/.config/icloud-sync/config.json
```

Do not use `--resync` for normal runs. After initialization, deletes and renames are handled by normal bisync:

```sh
systemctl --user start icloud-sync.service
```

## 5. Enable watching

```sh
systemctl --user enable --now icloud-sync.path
systemctl --user enable --now icloud-sync.timer
```

Trigger a sync manually:

```sh
systemctl --user start icloud-sync.service
```

Check status and logs:

```sh
systemctl --user status icloud-sync.path icloud-sync.timer icloud-sync.service
journalctl --user -u icloud-sync.service -f
```

The installed `.path` unit reacts to local changes at the `local_path` configured in `config.json`. The `.timer` runs a regular reconciliation so remote-only changes and deeper nested local changes are also picked up.

## Notifications

The sync wrapper sends desktop notifications when a sync starts and when it finishes. If sync fails, the finish notification is sent with critical urgency.

Notifications use `notify-send`; install it if your desktop does not already provide it. To disable notifications, set this in `config.json`:

```json
"notifications": false
```

## Notes

- The base directories on both sides must exist before bisync runs.
- The first run can sync one empty side, but normal non-resync runs intentionally fail if either side is unexpectedly empty.
- The default flags include `--resilient --recover --max-lock 2m --conflict-resolve newer` for unattended runs.
- For extra safety, consider adding rclone's `--check-access` flow after creating matching `RCLONE_TEST` files on both sides.
