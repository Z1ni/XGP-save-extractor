# XGP-save-extractor
Python script to extract/backup savefiles out of Xbox Game Pass for PC games.

When run, the script produces a ZIP file for each supported game save found in the system.

In most cases the files in the ZIP can be copied to the save directory of the Steam/Epic version of the game. To find out the save file location, check [PCGamingWiki](https://www.pcgamingwiki.com/).

## ⚠️ If you want the script to support another game, please open an issue [here](https://github.com/Z1ni/XGP-save-extractor/issues/new/choose). ⚠️

## Supported games
If you migrate a save to Steam/Epic version that's listed with ❔ below, please open an issue and confirm whether it worked, so the table can be updated.

Legend: ✅ Confirmed working, ❔ Unconfirmed, - Not available in the store

| Game | Tested w/ Steam | Tested w/ Epic |
|-|-|-|
| A Plague Tale: Requiem | ❔ | ❔ |
| Arcade Paradise | ✅ | ❔ |
| Atomic Heart | ✅ | - |
| Celeste | ❔ | ❔ |
| Chained Echoes | ❔ | ❔ |
| Chorus | ✅ | ❔ |
| Control | ❔ | ✅ |
| Final Fantasy XV | ✅ | - |
| Forza Horizon 5 | ❔ | - |
| Hades | ❔ | ❔ |
| High on Life | ✅ | ❔ |
| Hi-Fi RUSH | ❔ | ❔ |
| Just Cause 4 | ❔ | ❔ |
| Lies of P | ✅ | - |
| Like a Dragon Gaiden: The Man Who Erased His Name | ❔ | - |
| Like a Dragon: Ishin! | ❔ | - |
| Monster Train | ✅ | - |
| Octopath Traveller | ❔ | ❔ |
| Palworld | ✅ | - |
| Persona 5 Royal | ✅ | - |
| Persona 5 Tactica | ✅ | - |
| Remnant 2 | ✅ | ❔ |
| Remnant: From the Ashes | ❔ | ❔ |
| Starfield | ✅ | - |
| Totally Accurate Battle Simulator | ✅ | - |
| Wo Long: Fallen Dynasty | ❔ | - |
| Yakuza 0 | ✅ | - |
| Yakuza: Like a Dragon | ❔ | - |

## Incompatible games
These games use different save formats than the Steam/Epic version that can't be easily converted.

| Game | Issue |
|-|-|
| Chivarly 2 | [#39](https://github.com/Z1ni/XGP-save-extractor/issues/39) |
| Forza Horizon 4 | [#71](https://github.com/Z1ni/XGP-save-extractor/issues/71) |
| Tinykin | [#28](https://github.com/Z1ni/XGP-save-extractor/issues/28) |

### Possibly incompatible (needs testing)
Please test these and report back to the issue if the extracted saves work or not.

| Game | Issue |
|-|-|
| Forza Horizon 5 | [#81](https://github.com/Z1ni/XGP-save-extractor/issues/81) |

## Running
⚠️ **NOTE**: If the save file extraction fails, wait for a bit and try again. The Xbox cloud save sync can take some time and produce invalid files while syncing is in progress.

Download the latest release for an one-file executable: https://github.com/Z1ni/XGP-save-extractor/releases

⚠️ **NOTE**: Some anti-virus/anti-malware software can flag the executable as malicious. The executable is produced with [PyInstaller](https://pyinstaller.org/) and contains the Python interpreter alongside with the same `main.py` script as in this repo.

*Or*

Run `main.py` with Python 3.10+. The script produces ZIP files for each of the supported games that are installed for the current user.

## Thanks
Thanks to [@snoozbuster](https://github.com/snoozbuster) for figuring out the container format at https://github.com/goatfungus/NMSSaveEditor/issues/306.
