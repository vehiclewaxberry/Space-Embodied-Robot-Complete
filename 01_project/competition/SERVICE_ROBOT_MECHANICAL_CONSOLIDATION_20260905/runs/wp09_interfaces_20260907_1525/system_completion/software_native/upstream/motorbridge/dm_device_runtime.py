from __future__ import annotations

import argparse
import os
import platform
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from ._version import VERSION

SDK_VERSION = "v1.1.0"
_REPO = "motorbridge/motorbridge"


@dataclass(frozen=True)
class DmDeviceRuntime:
    relpath: str
    lib_name: str


def _truthy(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "off", "no"}


def _platform_runtime() -> DmDeviceRuntime:
    machine = platform.machine().lower()
    if sys.platform.startswith("linux"):
        if machine in {"x86_64", "amd64"}:
            return DmDeviceRuntime("linux/x86_64/libdm_device.so", "libdm_device.so")
        if machine in {"aarch64", "arm64"}:
            return DmDeviceRuntime("linux/arm64/libdm_device.so", "libdm_device.so")
    if sys.platform == "darwin":
        if machine in {"arm64", "aarch64"}:
            return DmDeviceRuntime("macos/arm64/libdm_device.dylib", "libdm_device.dylib")
        if machine in {"x86_64", "amd64"}:
            return DmDeviceRuntime("macos/x86_64/libdm_device.dylib", "libdm_device.dylib")
    if sys.platform.startswith("win") and machine in {"x86_64", "amd64"}:
        return DmDeviceRuntime("windows/msvc/dm_device.dll", "dm_device.dll")
    raise RuntimeError(f"DM_Device runtime is not available for {sys.platform}/{machine}")


def _cache_root() -> Path:
    env = os.getenv("MOTOR_DM_DEVICE_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    xdg = os.getenv("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg).expanduser() / "motorbridge" / "dm_device"
    return Path.home() / ".cache" / "motorbridge" / "dm_device"


def _packaged_runtime_path(runtime: DmDeviceRuntime) -> Path:
    return Path(__file__).resolve().parent / "lib" / "dm_device" / runtime.lib_name


def _cache_runtime_path(runtime: DmDeviceRuntime) -> Path:
    return _cache_root() / SDK_VERSION / runtime.relpath


def _source_runtime_path(runtime: DmDeviceRuntime) -> Path | None:
    try:
        repo_root = Path(__file__).resolve().parents[4]
    except IndexError:
        return None
    third_party_root = repo_root / "third_party" / "dm_device"
    if not third_party_root.exists():
        return None
    return third_party_root / SDK_VERSION / runtime.relpath


def _download_base_urls() -> list[str]:
    override = os.getenv("MOTOR_DM_DEVICE_DOWNLOAD_BASE_URL")
    if override:
        return [override.rstrip("/")]
    return [
        f"https://raw.githubusercontent.com/{_REPO}/v{VERSION}/third_party/dm_device/{SDK_VERSION}",
        f"https://raw.githubusercontent.com/{_REPO}/main/third_party/dm_device/{SDK_VERSION}",
    ]


def _url_for(base_url: str, relpath: str) -> str:
    return f"{base_url.rstrip('/')}/{relpath}"


def _download_runtime(runtime: DmDeviceRuntime, dst: Path, quiet: bool) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for base_url in _download_base_urls():
        url = _url_for(base_url, runtime.relpath)
        if not quiet:
            print(f"[motorbridge] downloading DM_Device runtime: {url}", file=sys.stderr)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{runtime.lib_name}.", dir=str(dst.parent))
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            with urlopen(url, timeout=30) as resp, tmp.open("wb") as out:
                shutil.copyfileobj(resp, out)
            try:
                mode = tmp.stat().st_mode
                tmp.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass
            tmp.replace(dst)
            return dst
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url}: {exc}")
            try:
                tmp.unlink()
            except OSError:
                pass

    raise RuntimeError(
        "Failed to download DM_Device runtime for this platform.\n"
        + "\n".join(f"- {err}" for err in errors)
        + "\nSet MOTOR_DM_DEVICE_LIB=/path/to/libdm_device if you installed the DaMiao SDK manually, "
        "or set MOTOR_DM_DEVICE_DOWNLOAD_BASE_URL to an internal mirror."
    )


def _install_hint(runtime: DmDeviceRuntime) -> str:
    repo_url = f"https://github.com/{_REPO}/tree/main/third_party/dm_device/{SDK_VERSION}"
    raw_url = _url_for(
        f"https://raw.githubusercontent.com/{_REPO}/main/third_party/dm_device/{SDK_VERSION}",
        runtime.relpath,
    )
    cache_path = _cache_runtime_path(runtime)
    source_path = _source_runtime_path(runtime)
    source_line = f"\n- Source checkout path: {source_path}" if source_path is not None else ""
    dep_note = ""
    if runtime.relpath.startswith("linux/x86_64/"):
        dep_note = (
            "\nLinux x86_64 dependency note: install libusb-1.0-0 and make sure "
            "libstdc++.so.6 provides GLIBCXX_3.4.32."
        )
    elif runtime.relpath.startswith("linux/arm64/"):
        dep_note = (
            "\nLinux arm64 dependency note: install libusb-1.0-0; this runtime "
            "requires GLIBC_2.17 and GLIBCXX_3.4.22 or newer."
        )
    elif runtime.relpath.startswith("windows/"):
        dep_note = (
            "\nWindows dependency note: install the USB driver/libusb runtime and "
            "the Microsoft Visual C++ runtime if the DLL loader reports missing MSVC DLLs."
        )
    return (
        "DM_Device runtime is not installed for this platform.\n"
        f"Required runtime: {runtime.relpath}\n"
        f"Download page: {repo_url}\n"
        f"Direct file URL: {raw_url}\n"
        "Install options:\n"
        f"- Set MOTOR_DM_DEVICE_LIB=/absolute/path/to/{runtime.lib_name}\n"
        f"- Or place the file at the motorbridge cache path: {cache_path}"
        f"{source_line}\n"
        "- Or run: motorbridge-install-dm-device --download\n"
        "Reference: third_party/dm_device/README.md"
        f"{dep_note}"
    )


def ensure_dm_device_runtime(*, auto_download: bool | None = None, quiet: bool = False, force: bool = False) -> Path:
    env_lib = os.getenv("MOTOR_DM_DEVICE_LIB")
    if env_lib and not force:
        path = Path(env_lib).expanduser()
        if path.exists():
            return path
        raise RuntimeError(f"MOTOR_DM_DEVICE_LIB points to a missing file: {path}")

    runtime = _platform_runtime()

    packaged = _packaged_runtime_path(runtime)
    if packaged.exists() and not force:
        os.environ["MOTOR_DM_DEVICE_LIB"] = str(packaged)
        return packaged

    source_path = _source_runtime_path(runtime)
    if source_path is not None and source_path.exists() and not force:
        os.environ["MOTOR_DM_DEVICE_LIB"] = str(source_path)
        return source_path

    cached = _cache_runtime_path(runtime)
    if cached.exists() and not force:
        os.environ["MOTOR_DM_DEVICE_LIB"] = str(cached)
        return cached

    if auto_download is None:
        auto_download = _truthy(os.getenv("MOTOR_DM_DEVICE_AUTO_DOWNLOAD"), False)
    if not auto_download:
        raise RuntimeError(_install_hint(runtime))

    downloaded = _download_runtime(runtime, cached, quiet)
    os.environ["MOTOR_DM_DEVICE_LIB"] = str(downloaded)
    return downloaded


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Inspect or install the DaMiao DM_Device runtime used by motorbridge.")
    parser.add_argument("--download", action="store_true", help="download the matching runtime into the user cache")
    parser.add_argument("--force", action="store_true", help="download again even if a cached runtime exists")
    parser.add_argument("--print-path", action="store_true", help="print only the installed runtime path")
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="only resolve an existing runtime; fail if one is not already installed",
    )
    args = parser.parse_args(argv)

    try:
        path = ensure_dm_device_runtime(
            auto_download=args.download and not args.no_download,
            quiet=args.print_path,
            force=args.force,
        )
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from None
    if args.print_path:
        print(path)
    else:
        print(f"DM_Device runtime ready: {path}")


if __name__ == "__main__":
    main()
