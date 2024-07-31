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

filetime_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
packages_root = Path(os.path.expandvars(f"%LOCALAPPDATA%\\Packages"))


def read_game_list() -> Dict[str, Any] | None:
    try:
        # Search for the games JSON in the script directory
        games_json_path = Path("games.json")
        if not games_json_path.exists():
            # Search for the games JSON in the bundle directory
            games_json_path = Path(__file__).resolve().with_name("games.json")
        if not games_json_path.exists():
            return None
        with games_json_path.open("r") as f:
            without_comments = "\n".join(
                [l for l in f.readlines() if not l.lstrip().startswith("//")]
            )
        j = json.loads(without_comments)
        # Create a dict with the package name as the key
        games: Dict[str, Any] = {}
        for entry in j["games"]:
            games[entry["package"]] = {
                "name": entry["name"],
                "handler": entry["handler"],
                "handler_args": entry.get("handler_args") or {}
            }
        return games
    except:
        return None


def discover_games(supported_games: Dict[str, Any]) -> List[str]:
    found_games = []
    for pkg_name in supported_games.keys():
        pkg_path = packages_root / pkg_name
        if pkg_path.exists():
            found_games.append(pkg_name)
    return found_games


def read_utf16_str(f, str_len=None) -> str:
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
        live_gamer_path = (
            packages_root / xbox_app_package / "LocalState/XboxLiveGamer.xml"
        )
        with live_gamer_path.open("r", encoding="utf-8") as f:
            gamer = json.load(f)
        known_user_id = gamer.get("XboxUserId")
        if known_user_id != user_id:
            return None
        return gamer.get("Gamertag")
    except:
        return None


def find_user_containers(pkg_name: str) -> List[Tuple[int | str, Path]]:
    # Find container dir
    wgs_dir = packages_root / pkg_name / "SystemAppData/wgs"
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

        # Package display name seems to be available only on console saves
        pkg_display_name = read_utf16_str(f)

        store_pkg_name = read_utf16_str(f).split("!")[0]

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
                print_sync_warning(f'Missing container "{container_name}"')
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
                            print_sync_warning(
                                f'Two files exist for container "{container_name}" file "{file_name}": {file_guid} and {file_guid_2}, can\'t choose one'
                            )
                            continue
                        else:
                            print_sync_warning(
                                f'Missing file "{file_name}" inside container "{container_name}"'
                            )
                            continue

                    files.append(
                        {
                            "name": file_name,
                            # "guid": file_guid,
                            "path": file_path,
                        }
                    )

            containers.append(
                {
                    "name": container_name,
                    "number": container_num,
                    # "guid": container_guid,
                    "files": files,
                }
            )

    return (store_pkg_name, containers)


def get_save_paths(
    supported_games: Dict[str, Any],
    store_pkg_name: str,
    containers: List[Dict[str, Any]],
    temp_dir: tempfile.TemporaryDirectory,
) -> List[Tuple[str, Path]]:
    save_meta = []

    handler_name = supported_games[store_pkg_name]["handler"]
    handler_args = supported_games[store_pkg_name].get("handler_args") or {}

    if handler_name == "1c1f":
        # "1 container, 1 file" (1c1f). Each container contains only one file which name will be the name of the container.
        file_suffix = handler_args.get("suffix")
        for container in containers:
            fname = container["name"]
            if file_suffix is not None:
                # Add a suffix to the file name if configured
                fname += file_suffix
            fpath = container["files"][0]["path"]
            save_meta.append((fname, fpath))

    elif handler_name == "1cnf":
        # "1 container, n files" (1cnf). There's only one container that contains all the savefiles.
        file_suffix = handler_args.get("suffix")
        container = containers[0]
        for c_file in container["files"]:
            final_filename = c_file["name"]
            if file_suffix is not None:
                # Add a suffix to the file name if configured
                final_filename += file_suffix
            save_meta.append((final_filename, c_file["path"]))

    elif handler_name == "1cnf-folder":
        # Each container represents one folder
        for container in containers:
            folder_name: str = container["name"]
            for file in container["files"]:
                fname = file["name"]
                zip_fname = f"{folder_name}/{fname}"
                fpath = file["path"]
                save_meta.append((zip_fname, fpath))

    elif handler_name == "control":
        # Handle Control saves
        # Control uses container in a "n containers, n files" manner (ncnf),
        # where the container represents a folder that has named files.
        # Epic Games Store (and Steam?) use the same file names, but with a ".chunk" file extension.
        # TODO: Are files named "meta" unnecessary?
        for container in containers:
            path = PurePath(container["name"])

            # Create "--containerDisplayName.chunk" that contains the container name
            # TODO: Does Control _need_ "--containerDisplayName.chunk"?
            temp_container_disp_name_path = (
                Path(temp_dir.name)
                / f"{container['name']}_--containerDisplayName.chunk"
            )
            with temp_container_disp_name_path.open("w") as f:
                f.write(container["name"])
            save_meta.append(
                (path / "--containerDisplayName.chunk", temp_container_disp_name_path)
            )

            for file in container["files"]:
                save_meta.append((path / f"{file['name']}.chunk", file["path"]))

    elif handler_name == "starfield":
        # Starfield
        # The Steam version uses SFS ("Starfield save"?) files, whereas the Store version splits the SFS files into multiple files inside the containers.
        # One container is one save.
        # It seems that the "BETHESDAPFH" file is a header which is padded to the next 16 byte boundary with the string "padding\0", where \0 is NUL.
        # The other files ("PnP", where n is a number starting from 0) are then concatenated into the SFS file, also with padding.

        # As of at least Starfield version 1.9.51.0, the containers contain "toc" and one or more "BlobDataN" files (where N is a number starting from 0).
        # The new format seems to already include the padding.

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
            # Arrange the files: header as index 0, P0P as 1, P1P as 2, etc. (or BlobData0, ... for the new format)
            parts = {}

            is_new_format = "toc" in [f["name"] for f in container["files"]]

            for file in container["files"]:
                if file["name"] == "toc":
                    continue
                if is_new_format:
                    idx = int(file["name"].removeprefix("BlobData"))
                else:
                    if file["name"] == "BETHESDAPFH":
                        idx = 0
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

    elif handler_name == "lies-of-p":
        # Lies of P
        for container in containers:
            fname: str = container["name"]
            # Lies of P prefixes the save file names with a numeric ID
            # Filter the numbers out
            for i, c in enumerate(fname):
                if c.isdigit():
                    continue
                fname = fname[i:]
                break

            # The names also need a ".sav" suffix
            fname += ".sav"
            fpath = container["files"][0]["path"]

            save_meta.append((fname, fpath))

    elif handler_name == "palworld":
        for container in containers:
            fname = container["name"]
            # Each "-" in the name is a directory separator
            fname = fname.replace("-", "/")
            fname += ".sav"
            fpath = container["files"][0]["path"]
            save_meta.append((fname, fpath))

    elif handler_name == "like-a-dragon":
        for container in containers:
            path = PurePath(container["name"])
            if path.name == "datasav":
                fpath = path.with_name("data.sav")
            elif path.name == "datasys":
                fpath = path.with_name("data.sys")
            else:
                fpath = path

            for file in container["files"]:
                if file["name"].lower() == "data":
                    save_meta.append((str(fpath), file["path"]))
                elif file["name"].lower() == "icon":
                    icon_format = handler_args.get("icon_format")
                    if icon_format is None:
                        continue
                    save_meta.append(
                        (
                            str(
                                fpath.with_name(
                                    f"{fpath.parent.name}_icon.{icon_format}"
                                )
                            ),
                            file["path"],
                        )
                    )

    elif handler_name == "cricket-24":
        # 1cnf-folder, but with a file suffix and "CHUNK" suffix removal
        # TODO: Can there be more than one chunk?
        # Each container represents one folder
        for container in containers:
            folder_name: str = container["name"]
            for file in container["files"]:
                fname = file["name"]
                fname = fname.removesuffix(".CHUNK0")
                if "CHUNK" in fname:
                    raise Exception(
                        f"Unexpected chunk name in {file['name']}! Please report this issue on the GitHub repository!"
                    )
                fname += ".SAV"
                zip_fname = f"{folder_name}/{fname}"
                fpath = file["path"]
                save_meta.append((zip_fname, fpath))

    elif handler_name == "forza":
        # Container name is the filename prefix, file names inside container are appended to that after "."
        for container in containers:
            for file in container["files"]:
                fname = f"{container['name']}.{file['name']}"
                save_meta.append((fname, file["path"]))

    elif handler_name == "arcade-paradise":
        # Arcade Paradise seems to save to one container with one file, which should be renamed to "RATSaveData.dat" for Steam
        fpath = containers[0]["files"][0]["path"]
        save_meta.append(("RATSaveData.dat", fpath))

    elif handler_name == "state-of-decay-2":
        # This is otherwise identical to 1cnf, but we ignore the path in the file names
        for file in containers[0]["files"]:
            fname = file["name"].split("/")[-1] + ".sav"
            save_meta.append((fname, file["path"]))

    elif handler_name == "railway-empire-2":
        # Each container is one file.
        # The files inside the container are "savegame" and "description". It seems that we can ignore "description".
        for container in containers:
            for file in container["files"]:
                if file["name"] != "savegame":
                    continue
                save_meta.append((container["name"], file["path"]))

    elif handler_name == "coral-island":
        # 1c1f with ".sav" suffix, but if the file name is prefixed with "Backup", we place it in a folder
        # without the prefix.
        for container in containers:
            fname = f"{container['name']}.sav"
            if fname.startswith("Backup"):
                fname = f"Backup/{fname.removeprefix('Backup')}"
            fpath = container["files"][0]["path"]
            save_meta.append((fname, fpath))

    else:
        raise Exception('Unsupported XGP app "%s"' % store_pkg_name)

    return save_meta


def main():
    print("Xbox Game Pass for PC savefile extractor")
    print("========================================")

    games = read_game_list()
    if games is None:
        print("Failed to read game list. Check that games.json exists and is valid.")
        print()
        print("Press enter to quit")
        input()
        sys.exit(1)

    # Discover supported games
    found_games = discover_games(games)

    if len(found_games) == 0:
        print("No supported games installed")
        print()
        print("Press enter to quit")
        input()
        sys.exit(1)

    print("Installed supported games:")
    for package_name in found_games:
        name: str = games[package_name]["name"]
        print("- %s" % name)

        try:
            user_containers = find_user_containers(package_name)
            if len(user_containers) == 0:
                print(
                    "  No containers for the game, maybe the game is not installed anymore"
                )
                print()
                continue

            for xbox_username_or_id, container_dir in user_containers:
                read_result = read_user_containers(container_dir)
                store_pkg_name, containers = read_result

                # Create tempfile directory
                # Some save files need this, as we need to create files that do not exist in the XGP save data
                temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

                # Get save file paths
                save_paths = get_save_paths(games, store_pkg_name, containers, temp_dir)
                if len(save_paths) == 0:
                    continue
                print(f"  Save files for user {xbox_username_or_id}:")
                for file_name, _ in save_paths:
                    print(f"  - {file_name}")

                # Create a ZIP file
                formatted_game_name = (
                    name.replace(" ", "_")
                    .replace(":", "_")
                    .replace("'", "")
                    .replace("!", "")
                    .lower()
                )
                timestamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
                zip_name = "{}_{}_{}.zip".format(
                    formatted_game_name, xbox_username_or_id, timestamp
                )
                with zipfile.ZipFile(zip_name, "x", zipfile.ZIP_DEFLATED) as save_zip:
                    for file_name, file_path in save_paths:
                        save_zip.write(file_path, arcname=file_name)

                temp_dir.cleanup()

                print()
                print('  Save files written to "%s"' % zip_name)
                print()

        except Exception:
            print(f"  Failed to extract saves:")
            traceback.print_exc()
            print()

    print()
    print("Press enter to quit")
    input()


if __name__ == "__main__":
    main()
