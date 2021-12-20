from argparse import ArgumentParser
from hashlib import md5
from pathlib import Path
import shutil
from functools import lru_cache

from imohash import hashfile
from tqdm import tqdm


def get_files(dirpath):
    paths = []
    for path in tqdm(Path(dirpath).rglob('*'), 'Getting files'):
        if not path.is_file():
            continue
        paths.append(path)
    return paths


@lru_cache(maxsize=100000)
def get_file_hash(filepath):
    return md5((hashfile(filepath, hexdigest=True) + Path(filepath).name).encode()).hexdigest()


@lru_cache()
def get_file_hashes(filepaths):
    return [get_file_hash(path) for path in tqdm(filepaths, desc='Computing hashes')]


def trash(path, trash_path, base_dirpath):
    target_path = trash_path / path.relative_to(base_dirpath)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        raise FileExistsError(f'File already exists: {target_path}')
    shutil.move(path, target_path)


def is_dir_empty(dirpath):
    for path in Path(dirpath).rglob('*'):
        if path.name == '.DS_Store':
            continue
        if not path.is_dir():
            return False
        if not is_dir_empty(path):
            return False
    return True


def remove_empty_dirs(dirpath):
    for path in Path(dirpath).rglob('*'):
        if not path.is_dir():
            continue
        if not is_dir_empty(path):
            continue
        shutil.rmtree(path)


def deduplicate_directories(paths_to_deduplicate, reference_paths):
    '''Will go through `paths_to_deduplicate` recursively and move any file present in `reference_paths` to the `trash` directory'''
    paths_to_deduplicate = [Path(path) for path in paths_to_deduplicate]
    reference_paths = [Path(path) for path in reference_paths]
    for path in paths_to_deduplicate + reference_paths:
        assert path.exists(), f'"{path}" does not exist.'
    reference_hashes = set(
        [filehash for path in reference_paths for filehash in get_file_hashes(tuple(get_files(path)))]
    )
    trash_name = 'deduplicator_trash'
    for path_to_deduplicate in paths_to_deduplicate:
        trash_path = path_to_deduplicate / trash_name
        for filepath in tqdm(get_files(path_to_deduplicate), 'Cleaning'):
            if filepath.name == trash_name:
                continue
            if filepath.name.startswith('.'):
                continue
            if get_file_hash(filepath) in reference_hashes:
                trash(filepath, trash_path, path_to_deduplicate)
        remove_empty_dirs(path_to_deduplicate)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--paths', nargs='+')
    parser.add_argument('--reference-paths', nargs='+')
    args = parser.parse_args()
    deduplicate_directories(paths_to_deduplicate=args.paths, reference_paths=args.reference_paths)
