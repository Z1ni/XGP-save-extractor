# XGP-save-extractor
Python script to extract/backup savefiles out of Xbox Game Pass for PC games.

When run, the script produces a ZIP file for each supported game save found in the system.

In most cases the files in the ZIP can be copied to the save directory of the Steam/Epic version of the game. To find out the save file location, check [PCGamingWiki](https://www.pcgamingwiki.com/).

## Supported games
If you migrate a save to Steam/Epic version that's listed with ❔ below, please open an issue and confirm whether it worked, so the table can be updated.

If you want the script to support another game, please open an issue.

Legend: ✅ Confirmed working, ❔ Unconfirmed, - Not available in the store

| Game | Tested w/ Steam | Tested w/ Epic |
|-|-|-|
| Starfield | ✅ | - |
| High on Life | ❔ | ❔ |
| A Plague Tale: Requiem | ❔ | ❔ |
| Yakuza 0 | ✅ | - |
| Yakuza: Like a Dragon | ❔ | - |
| Octopath Traveller | ❔ | ❔ |
| Just Cause 4 | ❔ | ❔ |
| Hades | ❔ | ❔ |
| Control | ❔ | ✅ |
| Final Fantasy XV | ✅ | - |
| Atomic Heart | ✅ | - |
| Chorus | ✅ | ❔ |

## Running
⚠️ **NOTE**: If the save file extraction fails, wait for a bit and try again. The Xbox cloud save sync can take some time and produce invalid files while syncing is in progress.

Download the latest release for an one-file executable: https://github.com/Z1ni/XGP-save-extractor/releases

⚠️ **NOTE**: Some anti-virus/anti-malware software can flag the executable as malicious. The executable is produced with [PyInstaller](https://pyinstaller.org/) and contains the Python interpreter alongside with the same `main.py` script as in this repo.

*Or*

Run `main.py` with Python 3.10+. The script produces ZIP files for each of the supported games that are installed for the current user.

## Thanks
Thanks to [@snoozbuster](https://github.com/snoozbuster) for figuring out the container format at https://github.com/goatfungus/NMSSaveEditor/issues/306.
