import json
import os
import struct
import sys
import tempfile
import traceback
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePath
from typing import Any, Dict, List, Tuple

# Xbox Game Pass for PC savefile extractor

# Running: Just run the script with Python 3 to create ZIP files that contain the save files

# Thanks to @snoozbuster for figuring out the container format at https://github.com/goatfungus/NMSSaveEditor/issues/306

# List of supported Game Pass games and their UWP package names
supported_xgp_apps = {
    "Yakuza 0": "SEGAofAmericaInc.Yakuza0PC_s751p9cej88mt",
    "Yakuza Like a Dragon": "SEGAofAmericaInc.Yazawa_s751p9cej88mt",
    "Octopath Traveller": "39EA002F.FrigateMS_n746a19ndrrjg",
    "Just Cause 4": "39C668CD.JustCause4-BaseGame_r7bfsmp40f67j",
    "Hades": "SupergiantGamesLLC.Hades_q53c1yqmx7pha",
    "Control": "505GAMESS.P.A.ControlPCGP_tefn33qh9azfc",
    "Atomic Heart": "FocusHomeInteractiveSA.579645D26CFD_4hny5m903y3g0",
    "Chorus": "DeepSilver.UnleashedGoF_hmv7qcest37me",
    "Final Fantasy XV": "39EA002F.FINALFANTASYXVforPC_n746a19ndrrjg",
    "Starfield": "BethesdaSoftworks.ProjectGold_3275kfvn8vcwc",
    "A Plague Tale: Requiem": "FocusHomeInteractiveSA.APlagueTaleRequiem-Windows_4hny5m903y3g0"
}

filetime_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)


def discover_games():
    found_games = []
    for game_name, pkg_name in supported_xgp_apps.items():
        pkg_path = Path(os.path.expandvars(f"%LOCALAPPDATA%\\Packages\\{pkg_name}"))
        if pkg_path.exists():
            found_games.append(game_name)
    return found_games


def read_utf16_str(f, str_len=None):
    if not str_len:
        str_len = struct.unpack("<i", f.read(4))[0]
    return f.read(str_len * 2).decode("utf-16").rstrip("\0")


def read_filetime(f) -> datetime:
    filetime = struct.unpack("<Q", f.read(8))[0]
    filetime_seconds = filetime / 10_000_000
    return filetime_epoch + timedelta(seconds=filetime_seconds)


def print_sync_warning(title: str):
    print()
    print(f"  !! {title} !!")
    print("     Xbox cloud save syncing might not be complete, try again later.")
    print("     Extracted saves for this game might be corrupted!")
    print("     Press enter to skip and continue.")
    input()


def get_xbox_user_name(user_id: int) -> str | None:
    xbox_app_package = "Microsoft.XboxApp_8wekyb3d8bbwe"
    try:
        live_gamer_path = Path(os.path.expandvars(f"%LOCALAPPDATA%\\Packages\\{xbox_app_package}\\LocalState\\XboxLiveGamer.xml"))
        with live_gamer_path.open("r", encoding="utf-8") as f:
            gamer = json.load(f)
        known_user_id = gamer.get("XboxUserId")
        if known_user_id != user_id:
            return None
        return gamer.get("Gamertag")
    except:
        return None


def find_user_containers(pkg_name) -> List[Tuple[int | str, Path]]:
    # Find container dir
    wgs_dir = Path(os.path.expandvars(f"%LOCALAPPDATA%\\Packages\\{pkg_name}\\SystemAppData\\wgs"))
    if not wgs_dir.is_dir():
        return []
    # Get the correct user directory
    has_backups = False
    valid_user_dirs = []
    for entry in wgs_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name == "t":
            continue
        if "backup" in entry.name:
            has_backups = True
            continue
        if len(entry.name.split("_")) == 2:
            valid_user_dirs.append(entry)

    if has_backups:
        print("  !! The save directory contains backups !!")
        print("     This script will currently skip backups made by the Xbox app.")
        print("     Press enter to continue.")
        input()

    if len(valid_user_dirs) == 0:
        # No saves for any users
        return []

    user_dirs = []

    for valid_user_dir in valid_user_dirs:
        user_id_hex, title_id_hex = valid_user_dir.name.split("_", 1)
        user_id = int(user_id_hex, 16)
        user_name = get_xbox_user_name(user_id)
        user_dirs.append((user_name or user_id, valid_user_dir))

    return user_dirs


def read_user_containers(user_wgs_dir: Path) -> Tuple[str, List[Dict[str, Any]]]:

    containers_dir = user_wgs_dir
    containers_idx_path = containers_dir / "containers.index"

    containers = []

    # Read the index file
    with containers_idx_path.open("rb") as f:
        # Unknown
        f.read(4)

        container_count = struct.unpack("<i", f.read(4))[0]

        # Unknown
        f.read(4)

        store_pkg_name = read_utf16_str(f).split("!Game")[0].split("!Retail")[0].split("!AppChorusShipping")[0].split("!App")[0]

        # Creation date, FILETIME
        creation_date = read_filetime(f)
        # print(f"  Container index created at {creation_date}")
        # Unknown
        f.read(4)
        read_utf16_str(f)

        # Unknown
        f.read(8)

        for _ in range(container_count):
            # Container name
            container_name = read_utf16_str(f)
            # Duplicate of the file name
            read_utf16_str(f)
            # Unknown quoted hex number
            read_utf16_str(f)
            # Container number
            container_num = struct.unpack("B", f.read(1))[0]
            # Unknown
            f.read(4)
            # Read container (folder) GUID
            container_guid = uuid.UUID(bytes_le=f.read(16))
            # Creation date, FILETIME
            container_creation_date = read_filetime(f)
            # print(f"Container created at {container_creation_date}")
            # Unknown
            f.read(16)

            files = []

            # Read the container file in the container directory
            container_path = containers_dir / container_guid.hex.upper()
            container_file_path = container_path / f"container.{container_num}"

            if not container_file_path.is_file():
                print_sync_warning(f"Missing container \"{container_name}\"")
                continue

            with container_file_path.open("rb") as cf:
                # Unknown (always 04 00 00 00 ?)
                cf.read(4)
                # Number of files in this container
                file_count = struct.unpack("<i", cf.read(4))[0]
                for _ in range(file_count):
                    # File name, 0x80 (128) bytes UTF-16 = 64 characters
                    file_name = read_utf16_str(cf, 64)
                    # Read file GUID
                    file_guid = uuid.UUID(bytes_le=cf.read(16))
                    # Read the copy of the GUID
                    file_guid_2 = uuid.UUID(bytes_le=cf.read(16))

                    if file_guid == file_guid_2:
                        file_path = container_path / file_guid.hex.upper()
                    else:
                        # Check if one of the file paths exist
                        file_guid_1_path = container_path / file_guid.hex.upper()
                        file_guid_2_path = container_path / file_guid_2.hex.upper()

                        file_1_exists = file_guid_1_path.is_file()
                        file_2_exists = file_guid_2_path.is_file()

                        if file_1_exists and not file_2_exists:
                            file_path = file_guid_1_path
                        elif not file_1_exists and file_2_exists:
                            file_path = file_guid_2_path
                        elif file_1_exists and file_2_exists:
                            # Which one to use?
                            print_sync_warning(f"Two files exist for container \"{container_name}\" file \"{file_name}\": {file_guid} and {file_guid_2}, can't choose one")
                            continue
                        else:
                            print_sync_warning(f"Missing file \"{file_name}\" inside container \"{container_name}\"")
                            continue

                    files.append({
                        "name": file_name,
                        # "guid": file_guid,
                        "path": file_path
                    })

            containers.append({
                "name": container_name,
                "number": container_num,
                # "guid": container_guid,
                "files": files
            })

    return (store_pkg_name, containers)


def get_save_paths(store_pkg_name, containers, temp_dir):
    save_meta = []

    if store_pkg_name in [supported_xgp_apps["Yakuza 0"], supported_xgp_apps["Yakuza Like a Dragon"], supported_xgp_apps["Final Fantasy XV"], supported_xgp_apps["A Plague Tale: Requiem"]]:
        # Handle Yakuza 0, Yakuza Like a Dragon, Final Fantasy XV and A Plague Tale: Requiem saves
        # These all use containers in a "1 container, 1 file" manner (1c1f),
        # where the container includes a file named "data" that is the file named as the container.
        for container in containers:
            fname = container["name"]
            fpath = container["files"][0]["path"]
            save_meta.append((fname, fpath))

    elif store_pkg_name in [supported_xgp_apps["Octopath Traveller"], supported_xgp_apps["Just Cause 4"], supported_xgp_apps["Hades"]]:
        # Handle Octopath Traveller, Just Cause 4 and Hades saves
        # All of these games use containers in a "1 container, n files" manner (1cnf), where there exists only one
        # container that contains all the savefiles.
        # The save files seem to be the same as in the Steam version.
        container = containers[0]
        for c_file in container["files"]:
            save_meta.append((c_file["name"], c_file["path"]))

    elif store_pkg_name in [supported_xgp_apps["Chorus"]]:
        # Handle Chorus saves
        # All of these games use containers in a "1 container, n files" manner (1cnf), where there exists only one
        # container that contains all the savefiles.
        # The save files seem to be the same as in the Steam version.
        container = containers[0]
        for c_file in container["files"]:
            save_meta.append((c_file["name"] + '.sav', c_file["path"]))

    elif store_pkg_name == supported_xgp_apps["Control"]:
        # Handle Control saves
        # Control uses container in a "n containers, n files" manner (ncnf),
        # where the container represents a folder that has named files.
        # Epic Games Store (and Steam?) use the same file names, but with a ".chunk" file extension.
        # TODO: Are files named "meta" unnecessary?
        for container in containers:
            path = PurePath(container["name"])

            # Create "--containerDisplayName.chunk" that contains the container name
            # TODO: Does Control _need_ "--containerDisplayName.chunk"?
            temp_container_disp_name_path = Path(temp_dir.name) / f"{container['name']}_--containerDisplayName.chunk"
            with temp_container_disp_name_path.open("w") as f:
                f.write(container["name"])
            save_meta.append((path / "--containerDisplayName.chunk", temp_container_disp_name_path))

            for file in container["files"]:
                save_meta.append((path / f"{file['name']}.chunk", file['path']))
                
    elif store_pkg_name in [supported_xgp_apps["Atomic Heart"]]:
        # Handle Atomic Heart saves
        # Atomic Heart uses containers in a "1 container, 1 file" manner (1c1f),
        # where the container includes a file named "data" that is the file named as the container. All files need to have ".sav" added as an extension
        for container in containers:
            fname = container["name"] + '.sav'
            fpath = container["files"][0]["path"]
            save_meta.append((fname, fpath))

    elif store_pkg_name in [supported_xgp_apps["Starfield"]]:
        # Starfield
        # The Steam version uses SFS ("Starfield save"?) files, whereas the Store version splits the SFS files into multiple files inside the containers.
        # One container is one save.
        # It seems that the "BETHESDAPFH" file is a header which is padded to the next 16 byte boundary with the string "padding\0", where \0 is NUL.
        # The other files ("PnP", where n is a number starting from 0) are then concatenated into the SFS file, also with padding.

        temp_folder = Path(temp_dir.name) / "Starfield"
        temp_folder.mkdir()

        pad_str = "padding\0" * 2

        for container in containers:
            path = PurePath(container["name"])
            # There can be other files than saves, e.g. files under "Settings/" path. Skip those.
            if path.parent.name != "Saves":
                continue
            # Strip out the parent folder name
            sfs_name = path.name
            # Arrange the files: header as index 0, P0P as 1, P1P as 2, etc.
            parts = {}
            for file in container["files"]:
                if file["name"] == "BETHESDAPFH":
                    parts[0] = file["path"]
                else:
                    idx = int(file["name"].strip("P")) + 1
                    parts[idx] = file["path"]
            # Construct the SFS file
            sfs_path = temp_folder / sfs_name
            with sfs_path.open("wb") as sfs_f:
                for idx, part_path in sorted(parts.items(), key=lambda t: t[0]):
                    with open(part_path, "rb") as part_f:
                        data = part_f.read()
                    size = sfs_f.write(data)
                    pad = 16 - (size % 16)
                    if pad != 16:
                        sfs_f.write(pad_str[:pad].encode("ascii"))

            save_meta.append((sfs_name, sfs_path))

    else:
        raise Exception("Unsupported XGP app \"%s\"" % store_pkg_name)

    return save_meta


def main():
    print("Xbox Game Pass for PC savefile extractor")
    print("========================================")

    # Discover supported games
    found_games = discover_games()

    if len(found_games) == 0:
        print("No supported games installed")
        sys.exit(1)

    print("Installed supported games:")
    for name in found_games:
        print("- %s" % name)

        try:
            user_containers = find_user_containers(supported_xgp_apps[name])
            if len(user_containers) == 0:
                print("  No containers for the game, maybe the game is not installed anymore")
                print()
                continue

            for xbox_username_or_id, container_dir in user_containers:
                read_result = read_user_containers(container_dir)
                store_pkg_name, containers = read_result

                # Create tempfile directory
                # Some save files need this, as we need to create files that do not exist in the XGP save data
                temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

                # Get save file paths
                save_paths = get_save_paths(store_pkg_name, containers, temp_dir)
                print(f"  Save files for user {xbox_username_or_id}:")
                for file_name, _ in save_paths:
                    print(f"  - {file_name}")

                # Create a ZIP file
                formatted_game_name = name.replace(" ", "_").replace(":", "_").replace("'", "").lower()
                timestamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
                zip_name = "{}_{}_{}.zip".format(formatted_game_name, xbox_username_or_id, timestamp)
                with zipfile.ZipFile(zip_name, "x") as save_zip:
                    for file_name, file_path in save_paths:
                        save_zip.write(file_path, arcname=file_name)

                temp_dir.cleanup()

                print()
                print("  Save files written to \"%s\"" % zip_name)

        except Exception:
            print(f"  Failed to extract saves:")
            traceback.print_exc()
            print()

    print()
    print("Press enter to quit")
    input()


if __name__ == "__main__":
    main()
