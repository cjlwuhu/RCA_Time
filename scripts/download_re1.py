"""Download the three RE1 archives from the official Zenodo record.

No RCAEval installation is required. Existing extracted datasets are skipped.
"""

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile


@dataclass(frozen=True)
class ArchiveSpec:
    key: str
    directory: str
    url: str
    size: int
    md5: str


ARCHIVES = {
    "ob": ArchiveSpec(
        key="RE1-OB.zip",
        directory="RE1-OB",
        url="https://zenodo.org/api/records/14590730/files/RE1-OB.zip/content",
        size=30_966_778,
        md5="47cce26ed24140e8974e68f9db2a5e9c",
    ),
    "ss": ArchiveSpec(
        key="RE1-SS.zip",
        directory="RE1-SS",
        url="https://zenodo.org/api/records/14590730/files/RE1-SS.zip/content",
        size=79_089_075,
        md5="d2b15cbd3bb3cf6ec5f3cc65f7fac225",
    ),
    "tt": ArchiveSpec(
        key="RE1-TT.zip",
        directory="RE1-TT",
        url="https://zenodo.org/api/records/14590730/files/RE1-TT.zip/content",
        size=279_663_965,
        md5="48a26925ce47fd4bcfbedbae4f31475b",
    ),
}


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(spec: ArchiveSpec, archive_path: Path) -> None:
    partial_path = archive_path.with_suffix(archive_path.suffix + ".part")
    downloaded = 0
    with urllib.request.urlopen(spec.url) as response, partial_path.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            downloaded += len(chunk)
            percent = downloaded / spec.size * 100
            print(f"\r{spec.key}: {percent:5.1f}%", end="", flush=True)
    print()
    partial_path.replace(archive_path)


def safe_extract(archive_path: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            member_path = (destination / member.filename).resolve()
            if destination_resolved not in member_path.parents and member_path != destination_resolved:
                raise ValueError(f"unsafe path in ZIP archive: {member.filename}")
        archive.extractall(destination)


def install_archive(spec: ArchiveSpec, target_dir: Path, download_dir: Path) -> None:
    extracted_path = target_dir / spec.directory
    if extracted_path.is_dir():
        print(f"SKIP {spec.directory}: already exists at {extracted_path}")
        return

    download_dir.mkdir(parents=True, exist_ok=True)
    archive_path = download_dir / spec.key
    if archive_path.is_file() and md5_file(archive_path) != spec.md5:
        raise ValueError(
            f"existing archive checksum mismatch: {archive_path}; "
            "remove the incomplete archive before retrying"
        )
    if not archive_path.is_file():
        print(f"Downloading {spec.key} ({spec.size / 1024 / 1024:.1f} MiB)")
        download_file(spec, archive_path)

    actual_md5 = md5_file(archive_path)
    if actual_md5 != spec.md5:
        raise ValueError(
            f"checksum mismatch for {archive_path}: expected {spec.md5}, got {actual_md5}"
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target_dir) as temp_name:
        temp_dir = Path(temp_name)
        safe_extract(archive_path, temp_dir)
        source = temp_dir / spec.directory
        if not source.is_dir():
            raise ValueError(f"archive does not contain {spec.directory}")
        shutil.move(str(source), str(extracted_path))
    print(f"READY {spec.directory}: {extracted_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download RCAEval RE1 datasets.")
    parser.add_argument(
        "--systems",
        nargs="+",
        choices=["ob", "ss", "tt", "all"],
        default=["all"],
        help="systems to download; default: all",
    )
    parser.add_argument("--target", type=Path, default=Path("data/RE1"))
    parser.add_argument("--download-dir", type=Path, default=Path("data/.downloads"))
    parser.add_argument(
        "--download",
        action="store_true",
        help="perform downloads; without this flag only show status",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    systems = list(ARCHIVES) if "all" in args.systems else args.systems
    for system in systems:
        spec = ARCHIVES[system]
        extracted_path = args.target / spec.directory
        status = "present" if extracted_path.is_dir() else "missing"
        print(
            f"{spec.directory}: {status}; archive size "
            f"{spec.size / 1024 / 1024:.1f} MiB"
        )
        if args.download:
            install_archive(spec, args.target, args.download_dir)


if __name__ == "__main__":
    main()
