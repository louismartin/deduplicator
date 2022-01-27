from argparse import ArgumentParser
from hashlib import md5
from pathlib import Path
import shutil
from functools import lru_cache
from typing import DefaultDict

from imohash import hashfile
from tqdm import tqdm


def yield_files(directory_path):
    for path in Path(directory_path).rglob("*"):
        if not path.is_file():
            continue
        yield path


@lru_cache(maxsize=100000)
def get_file_hash(filepath):
    try:
        return md5((hashfile(filepath, hexdigest=True) + Path(filepath).name).encode()).hexdigest()
    except OSError as e:
        print(f"Could not hash {filepath}")
        raise e


def get_file_hashes(filepaths):
    return [get_file_hash(path) for path in filepaths]


def get_trash_dir(base_dirpath):
    return base_dirpath / "deduplicator_trash"


def trash_file(path, base_dirpath):
    trash_dir = get_trash_dir(base_dirpath)
    trash_dir.mkdir(exist_ok=True)
    target_path = trash_dir / path.relative_to(base_dirpath)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        raise FileExistsError(f"File already exists: {target_path}")
    shutil.move(path, target_path)


def is_dir_empty(dirpath):
    for path in Path(dirpath).rglob("*"):
        if path.name == ".DS_Store":
            continue
        if not path.is_dir():
            return False
        if not is_dir_empty(path):
            return False
    return True


def remove_empty_dirs(dirpath):
    for path in Path(dirpath).rglob("*"):
        if not path.is_dir():
            continue
        if not is_dir_empty(path):
            continue
        shutil.rmtree(path)


def get_names_to_paths(paths):
    names_to_paths = DefaultDict(list)
    for path in paths:
        names_to_paths[path.name].append(path)
    return names_to_paths


def is_file_in_paths(filepath, paths):
    return get_file_hash(filepath) in get_file_hashes(paths)


def deduplicate_directory(directory_path, reference_filepaths):
    # We will use this mapping as a first quick filter on filenames to avoid computing hashes for all files
    trash_dir = get_trash_dir(directory_path)
    reference_names_to_path = get_names_to_paths(reference_filepaths)
    for filepath in tqdm(yield_files(directory_path), f"Cleaning files in {directory_path}"):
        # Check that path is not a subpath of the trash directory
        if trash_dir in filepath.parents:
            continue
        if filepath.name.startswith("."):
            continue
        if not filepath.name in reference_names_to_path:
            continue
        candidate_reference_filepaths = reference_names_to_path[filepath.name]
        try:
            if is_file_in_paths(filepath, candidate_reference_filepaths):
                trash_file(filepath, directory_path)
        except OSError as e:
            print(f"Could not deduplicate {filepath} due to {e}")


def deduplicate_directories(paths_to_deduplicate, reference_paths):
    """Will go through `paths_to_deduplicate` recursively and move any file present in `reference_paths` to the `trash` directory"""
    paths_to_deduplicate = [Path(path) for path in paths_to_deduplicate]
    reference_paths = [Path(path) for path in reference_paths]
    for path in paths_to_deduplicate + reference_paths:
        assert path.exists(), f'"{path}" does not exist.'
    reference_filepaths = [
        filepath
        for reference_path in reference_paths
        for filepath in tqdm(yield_files(reference_path), f"Getting files from {reference_path}")
    ]
    for path_to_deduplicate in paths_to_deduplicate:
        deduplicate_directory(directory_path=path_to_deduplicate, reference_filepaths=reference_filepaths)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--paths", nargs="+")
    parser.add_argument("--reference-paths", nargs="+")
    args = parser.parse_args()
    deduplicate_directories(paths_to_deduplicate=args.paths, reference_paths=args.reference_paths)
