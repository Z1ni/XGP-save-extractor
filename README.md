# XGP-save-extractor
Python script to extract/backup savefiles out of Xbox Game Pass for PC games.

## Supported games
- **Starfield** *(confirmed working with the Steam version)*
- **Yakuza 0** *(confirmed working with the Steam version)*
- **Yakuza Like a Dragon** *(not tested with the Steam version, but the save format should be the same)*
- **Octopath Traveller** *(not tested with the Steam version, but the save format should be the same)*
- **Just Cause 4** *(not tested with the Steam version, but the save format should be the same)*
- **Hades** *(not tested with the Steam/Epic version, but the save format should be the same)*
- **Control** *(confirmed working with the Epic version, save format should be the same with Steam)*
- **Final Fantasy XV** *(confirmed working with the Steam version)*
- **Atomic Heart** *(confirmed working with the Steam version, at least when all fiels where copied before ever launching Steam version)*
- **Chorus** *(confirmed working with the Steam version)*

## Running
Download the latest release for an one-file executable: https://github.com/Z1ni/XGP-save-extractor/releases

*Or*

Run `main.py` with Python 3.10+. The script produces ZIP files for each of the supported games that are installed for the current user.

## Thanks
Thanks to [@snoozbuster](https://github.com/snoozbuster) for figuring out the container format at https://github.com/goatfungus/NMSSaveEditor/issues/306.
