import contextlib
import itertools
import json
import os
import pathlib
import platform
import shutil
import subprocess
import tarfile
import tempfile

import requests
import semantic_version as semver
import tqdm


class VersionManager:
    HUFFC_DIR = pathlib.Path.home() / ".huffc"

    def __init__(self):
        self.session = None
        self.HUFFC_DIR.mkdir(exist_ok=True)

    @classmethod
    def get_executable(cls, version):
        if (path := cls.HUFFC_DIR / f"huffc-{version}").exists():
            return path

    def fetch_remote_versions(self):
        versions = []
        for page in itertools.count(1):
            r = self.session.get(
                "https://api.github.com/repos/huff-language/huff-rs/releases",
                params={"per_page": 100, "page": page},
            )

            for release in (releases := r.json()):
                with contextlib.suppress(ValueError):
                    versions.append(semver.Version(release["name"].removeprefix("v")))

            if len(releases) < 100:
                break

        return versions

    @classmethod
    def fetch_local_versions(cls):
        versions = []
        if cls.HUFFC_DIR.exists():
            for binary in cls.HUFFC_DIR.iterdir():
                versions.append(semver.Version(binary.name.removeprefix("huffc-")))

        return versions

    def install(self, version, overwrite=False, silent=False):
        assert semver.Version(version) in self.fetch_remote_versions()

        if not overwrite:
            assert semver.Version(version) not in self.fetch_local_versions()

        r = self.session.get(
            f"https://api.github.com/repos/huff-language/huff-rs/releases/tags/{version}"
        )

        system = platform.system().lower()
        match platform.machine().lower():
            case "amd64" | "x86_64" | "i386" | "i586" | "i686":
                machine = "amd64"
            case "aarch64_be" | "aarch64" | "armv8b" | "armv8l" | "arm64":
                machine = "arm64"
            case _:
                raise Exception("Platform is not supported.")

        for asset in (release := r.json())["assets"]:
            if not all((val in asset["name"].lower() for val in (system, machine))):
                continue

            with tempfile.NamedTemporaryFile() as tmp:
                with self.session.get(asset["browser_download_url"], stream=True) as resp:
                    resp.raise_for_status()

                    with tqdm.tqdm(
                        desc=f"huffc v{version}",
                        total=int(resp.headers.get("content-length", 0)),
                        disable=silent,
                        unit="b",
                        unit_scale=True,
                    ) as pbar:
                        for chunk in resp.iter_content(None):
                            tmp.write(chunk)
                            pbar.update(len(chunk))
                        tmp.flush()

                with tarfile.open(tmp.name, "r:gz") as tar:
                    tar.extract("huffc", self.HUFFC_DIR)

            (self.HUFFC_DIR / "huffc").rename(self.HUFFC_DIR / f"huffc-{version}")
            return

        if (tool := shutil.which("cargo")) is None:
            raise Exception("Build tool 'cargo' could not be located.")

        with tempfile.NamedTemporaryFile() as tmp:
            with self.session.get(release["tarball_url"], stream=True) as resp:
                resp.raise_for_status()

                with tqdm.tqdm(
                    desc=resp.headers["content-disposition"].split("=")[-1],
                    total=int(resp.headers.get("content-length", 0)),
                    disable=silent,
                    unit="b",
                    unit_scale=True,
                ) as pbar:
                    for chunk in resp.iter_content(None):
                        tmp.write(chunk)
                        pbar.update(len(chunk))
                    tmp.flush()

            with tempfile.TemporaryDirectory(dir=self.HUFFC_DIR) as tmpdir:
                with tarfile.open(tmp.name) as tar:
                    tar.extractall(tmpdir)

                args = [tool, "build", "-r", "--locked", "--bin", "huffc"]
                if silent:
                    args += ["--quiet"]

                subprocess.run(args, cwd=(repo := next(pathlib.Path(tmpdir).iterdir())), check=True)
                shutil.copyfile(
                    repo / "target/release/huffc", (binary := self.HUFFC_DIR / f"huffc-{version}")
                )
                binary.chmod(755)

    @classmethod
    def uninstall(cls, version):
        if binary := cls.get_executable(version):
            binary.unlink()

    def __enter__(self):
        session = requests.Session()
        session.headers.update({"Accept": "application/json", "X-GitHub-Api-Version": "2022-11-28"})

        if token := os.getenv("GITHUB_TOKEN"):
            session.headers.update({"Authorization": f"token {token}"})

        self.session = session
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()
        self.session = None


def compile(files, /, version=None):
    if version is None:
        try:
            version = max(VersionManager.fetch_local_versions())
        except ValueError:
            raise Exception("A Huff compiler has not been installed.")
    else:
        assert semver.Version(version) in VersionManager.fetch_local_versions()

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [VersionManager.get_executable(version), "-ad", tmpdir, *files],
            check=True,
            capture_output=True,
        )

        artifacts = {}
        for root, _, files in os.walk(tmpdir):
            for file in files:
                with pathlib.Path(root).joinpath(file).open() as f:
                    artifact = json.load(f)
                    artifacts[artifact["file"]["path"]] = artifact

    return artifacts
