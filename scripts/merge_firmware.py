# PlatformIO post-build script: merge the environment's flash images into one .bin
# Usage: pio run -t merge -e <environment>

Import("env")

import os
from os.path import join


def _flash_frequency(board):
    frequency_hz = str(board.get("build.f_flash", "40000000L")).rstrip("L")
    return f"{int(frequency_hz) // 1000000}m"


def _flash_mode(board):
    mode = board.get("build.flash_mode", "dio")
    # Match PlatformIO's upload behavior for Arduino QIO/QOUT board definitions.
    return "dio" if mode in ("qio", "qout") else mode


def merge_firmware(source, target, env):
    build_dir = env.subst("$BUILD_DIR")
    progname = env.subst("${PROGNAME}")
    esptool = join(env.PioPlatform().get_package_dir("tool-esptoolpy"), "esptool.py")
    merged = join(build_dir, "firmware-merged.bin")
    board = env.BoardConfig()
    mcu = board.get("build.mcu")
    flash_size = board.get("upload.flash_size", "4MB")
    flash_mode = _flash_mode(board)
    flash_frequency = _flash_frequency(board)
    firmware = join(build_dir, f"{progname}.bin")

    # PlatformIO supplies the target-specific bootloader address and every
    # framework image here (partition table, boot_app0, and any board extras).
    images = [
        (str(offset), env.subst(str(path)))
        for offset, path in env.get("FLASH_EXTRA_IMAGES", [])
    ]
    images.append((env.subst("$ESP32_APP_OFFSET"), firmware))
    images.sort(key=lambda image: int(image[0], 0))

    if not mcu or not images:
        raise RuntimeError("PlatformIO did not provide a flash layout")
    for offset, path in images:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Missing image for {offset}: {path}")

    cmd = [
        env.subst("$PYTHONEXE"),
        esptool,
        "--chip",
        mcu,
        "merge_bin",
        "-o",
        merged,
        "--flash_mode",
        flash_mode,
        "--flash_freq",
        flash_frequency,
        "--flash_size",
        flash_size,
    ]
    for offset, path in images:
        cmd.extend((offset, path))

    print(f"Merging {mcu} flash image -> {merged}")
    print("Flash layout: " + ", ".join(f"{offset}={path}" for offset, path in images))
    env.Execute(" ".join(f'"{c}"' if " " in c else c for c in cmd))
    return None


env.AddCustomTarget(
    name="merge",
    dependencies="${BUILD_DIR}/${PROGNAME}.bin",
    actions=env.Action(merge_firmware, "Merging flash image for web flasher"),
    title="Merge firmware",
    description="Create firmware-merged.bin (bootloader + partitions + app)",
)
