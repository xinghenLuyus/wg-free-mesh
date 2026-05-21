from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tomllib
from zipfile import ZIP_DEFLATED, ZipFile


TARGETS = (
    ("windows", "amd64"),
    ("windows", "arm64"),
    ("windows", "386"),
    ("linux", "amd64"),
    ("linux", "arm64"),
    ("darwin", "amd64"),
    ("darwin", "arm64"),
)


def project_version(repo_root: Path) -> str:
    pyproject_path = repo_root / "src" / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    version = str(data.get("project", {}).get("version", "")).strip()
    if not version:
        raise RuntimeError("Project version is missing in src/pyproject.toml")
    return version


def parse_target(value: str) -> tuple[str, str]:
    parts = value.strip().split("/")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("target must use GOOS/GOARCH, for example windows/amd64")
    target = (parts[0], parts[1])
    if target not in TARGETS:
        supported = ", ".join(f"{goos}/{goarch}" for goos, goarch in TARGETS)
        raise argparse.ArgumentTypeError(f"unsupported target {value!r}; supported: {supported}")
    return target


def run_go_build(
    client_dir: Path,
    output: Path,
    package: str,
    goos: str,
    goarch: str,
    version: str,
) -> None:
    env = os.environ.copy()
    env["GOOS"] = goos
    env["GOARCH"] = goarch
    env["CGO_ENABLED"] = "0"
    command = [
        "go",
        "build",
        "-trimpath",
        "-ldflags",
        f"-X wfm/client/internal/bind.Version={version}",
        "-o",
        str(output),
        package,
    ]
    result = subprocess.run(command, cwd=client_dir, env=env, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"go build failed for {package} {goos}/{goarch}")


def write_package(
    zip_path: Path,
    ctl_path: Path,
    agent_path: Path,
    version: str,
    goos: str,
    goarch: str,
) -> None:
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        archive.write(ctl_path, arcname=ctl_path.name)
        archive.write(agent_path, arcname=agent_path.name)
        archive.writestr(
            "README.txt",
            "\n".join(
                [
                    "WG Free Mesh client package",
                    f"Version: {version}",
                    f"Target: {goos}/{goarch}",
                    "",
                    "Run wfmctl install from this directory to install and start the system service.",
                ]
            ),
        )


def build_target(client_dir: Path, dist_dir: Path, goos: str, goarch: str, version: str) -> Path:
    suffix = ".exe" if goos == "windows" else ""
    work_dir = dist_dir / "work" / f"{goos}-{goarch}"
    work_dir.mkdir(parents=True, exist_ok=True)
    ctl_path = work_dir / f"wfmctl{suffix}"
    agent_path = work_dir / f"wfm-agent{suffix}"
    run_go_build(client_dir, ctl_path, "./cmd/ctl", goos, goarch, version)
    run_go_build(client_dir, agent_path, "./cmd/agent", goos, goarch, version)
    zip_path = dist_dir / f"wfm-client-{goos}-{goarch}-v{version}.zip"
    write_package(zip_path, ctl_path, agent_path, version, goos, goarch)
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build WG Free Mesh client release packages.")
    parser.add_argument(
        "--target",
        action="append",
        type=parse_target,
        help="Build one target, for example windows/amd64. May be repeated.",
    )
    parser.add_argument("--dist", default="dist", help="Output directory relative to client/.")
    parser.add_argument("--keep-work", action="store_true", help="Keep intermediate binaries under dist/work.")
    args = parser.parse_args()

    client_dir = Path(__file__).resolve().parent
    repo_root = client_dir.parent
    version = project_version(repo_root)
    targets = tuple(args.target or TARGETS)
    dist_dir = client_dir / str(args.dist)
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    built: list[Path] = []
    for goos, goarch in targets:
        built.append(build_target(client_dir, dist_dir, goos, goarch, version))

    if not args.keep_work:
        shutil.rmtree(dist_dir / "work", ignore_errors=True)

    print(f"Built {len(built)} package(s) for version {version}:")
    for path in built:
        print(f"  {path.relative_to(client_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
