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

game = {"Starfield": "BethesdaSoftworks.ProjectGold_3275kfvn8vcwc"}

filetime_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
packages_root = Path(os.path.expandvars(f"%LOCALAPPDATA%\\Packages"))

def discover_games():
    found_games = []
    for game_name, pkg_name in game.items():
        pkg_path = packages_root / pkg_name
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
    print()
    print("     Xbox cloud save syncing might not be complete, try again later.")
    print("     Extracted saves for this game might be corrupted!")
    print()
    print("     Press enter to skip and continue.")
    input()

def get_xbox_user_name(user_id: int) -> str | None:
    xbox_app_package = "Microsoft.XboxApp_8wekyb3d8bbwe"
    try:
        live_gamer_path = packages_root / xbox_app_package / "LocalState/XboxLiveGamer.xml"
        with live_gamer_path.open("r", encoding="utf-8") as f:
            gamer = json.load(f)
        known_user_id = gamer.get("XboxUserId")
        if known_user_id != user_id:
            return None
        return gamer.get("Gamertag")
    except:
        return None

def find_user_containers(pkg_name) -> List[Tuple[int | str, Path]]:
    wgs_dir = packages_root / pkg_name / "SystemAppData/wgs"
    if not wgs_dir.is_dir():
        return []
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

    with containers_idx_path.open("rb") as f:
        f.read(4)
        container_count = struct.unpack("<i", f.read(4))[0]
        f.read(4)

        store_pkg_name = read_utf16_str(f).split("!")[0]

        creation_date = read_filetime(f)
        print()
        print(f"  Most recent synced save was created at {creation_date}")
        
        f.read(4)
        read_utf16_str(f)
        f.read(8)

        for _ in range(container_count):
            
            container_name = read_utf16_str(f)
            read_utf16_str(f)
            read_utf16_str(f)
            container_num = struct.unpack("B", f.read(1))[0]
            f.read(4)
            container_guid = uuid.UUID(bytes_le=f.read(16))
            container_creation_date = read_filetime(f)
            f.read(16)

            files = []

            container_path = containers_dir / container_guid.hex.upper()
            container_file_path = container_path / f"container.{container_num}"

            if not container_file_path.is_file():
                print_sync_warning(f"Missing container \"{container_name}\"")
                continue

            with container_file_path.open("rb") as cf:
                cf.read(4)
                file_count = struct.unpack("<i", cf.read(4))[0]
                for _ in range(file_count):
                    file_name = read_utf16_str(cf, 64)
                    file_guid = uuid.UUID(bytes_le=cf.read(16))
                    file_guid_2 = uuid.UUID(bytes_le=cf.read(16))
                    if file_guid == file_guid_2:
                        file_path = container_path / file_guid.hex.upper()
                    else:
                        file_guid_1_path = container_path / file_guid.hex.upper()
                        file_guid_2_path = container_path / file_guid_2.hex.upper()

                        file_1_exists = file_guid_1_path.is_file()
                        file_2_exists = file_guid_2_path.is_file()

                        if file_1_exists and not file_2_exists:
                            file_path = file_guid_1_path
                        elif not file_1_exists and file_2_exists:
                            file_path = file_guid_2_path
                        elif file_1_exists and file_2_exists:
                            print_sync_warning(f"Two files exist for container \"{container_name}\" file \"{file_name}\": {file_guid} and {file_guid_2}, can't choose one")
                            continue
                        else:
                            print_sync_warning(f"Missing file \"{file_name}\" inside container \"{container_name}\"")
                            continue

                    files.append({
                        "name": file_name,
                        "guid": file_guid,
                        "path": file_path
                    })

            containers.append({
                "name": container_name,
                "number": container_num,
                "guid": container_guid,
                "files": files
            })

    return (store_pkg_name, containers)


def get_save_paths(store_pkg_name, containers, temp_dir):
    save_meta = []

    if store_pkg_name in [game["Starfield"], game["Starfield"]]:
                          
        for container in containers:
            fname = container["name"]
            if store_pkg_name == game["Starfield"]:
                fname += ".sav"
            fpath = container["files"][0]["path"]
            save_meta.append((fname, fpath))

    elif store_pkg_name in [game["Starfield"]]:

        temp_folder = Path(temp_dir.name) / "Starfield"
        temp_folder.mkdir()

        pad_str = "padding\0" * 2

        for container in containers:
            path = PurePath(container["name"])
            if path.parent.name != "Saves":
                continue
            sfs_name = path.name
            parts = {}
            for file in container["files"]:
                if file["name"] == "BETHESDAPFH":
                    parts[0] = file["path"]
                else:
                    idx = int(file["name"].strip("P")) + 1
                    parts[idx] = file["path"]
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
    print()
    print("  Starfield Xbox to Steam Save Extractor")
    print("  ======================================")

    found_games = discover_games()

    if len(found_games) == 0:
        print("No save detected")
        sys.exit(1)
    
    for name in found_games:

        try:
            user_containers = find_user_containers(game[name])
            if len(user_containers) == 0:
                print("  No containers found. Resync save files and verify game files")
                print()
                continue

            for xbox_username_or_id, container_dir in user_containers:
                read_result = read_user_containers(container_dir)
                store_pkg_name, containers = read_result

                temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

                save_paths = get_save_paths(store_pkg_name, containers, temp_dir)
                print()
                print(f"  Converting save files for user {xbox_username_or_id}:")
                print()
                for file_name, _ in save_paths:
                    print(f"  - {file_name}")

                formatted_game_name = name.replace(" ", "_").replace(":", "_").replace("'", "").lower()
                timestamp = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
                zip_name = "{}_{}_{}.zip".format(formatted_game_name, xbox_username_or_id, timestamp)
                with zipfile.ZipFile(zip_name, "x") as save_zip:
                    for file_name, file_path in save_paths:
                        save_zip.write(file_path, arcname=file_name)

                temp_dir.cleanup()

                print()
                print("  Converted save files written to \"%s\"" % zip_name)
                print()
        except Exception:
            print(f"  Failed to extract saves:")
            traceback.print_exc()
            print()
	    
    print("  Press enter to exit")
    input()

if __name__ == "__main__":
    main()
