# XGP-save-extractor
Python script to extract/backup savefiles out of Xbox Game Pass for PC games.

## Supported games
- **Yakuza 0** *(confirmed working with the Steam version)*
- **Octopath Traveller** *(not tested with the Steam version, but the save format should be the same)*
- **Just Cause 4** *(not tested with the Steam version, but the save format should be the same)*
- **Hades** *(not tested with the Steam/Epic version, but the save format should be the same)*

## Running
Run `main.py` with Python 3+. The script produces ZIP files for each of the supported games that are installed for the current user.

## Thanks
Thanks to [@snoozbuster](https://github.com/snoozbuster) for figuring out the container format at https://github.com/goatfungus/NMSSaveEditor/issues/306.