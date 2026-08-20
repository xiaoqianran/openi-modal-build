from __future__ import annotations

import modal

APP_NAME = "v3-openi-trellis2-wheel-builder-py311"
GITHUB_REPO = "xiaoqianran/openi-modal-build"
RELEASE_TAG = "v3-trellis2-cu124-torch2.6.0-py311-sm80"
CACHE_VOLUME_NAME = "openi-trellis2-wheel-cache-py311"
CACHE_SCHEMA = "v4-003-py311"
UV_VERSION = "0.12.3"
MODAL_GPU = "A100-40GB"
RELEASE_ARCHIVE = "v3-trellis2-openi-cu124-torch260-py311-sm80.tar.gz"
RELEASE_CACHE_DIR = "release-v3"
# The py310 private OpenI registry image ID is intentionally not reused here.
# This value is a target ABI label for the manifest; the installer enforces Python 3.11 at runtime.
OPENI_IMAGE_REFERENCE = (
    "ubuntu22.04-cuda12.4.0-py311-torch2.6.0"
)

# Target ABI/runtime: OpenI ubuntu22.04-cuda12.4.0-py311-torch2.6.0 + A100/sm_80.
PYTHON_MINOR = "3.11"
TORCH_VERSION = "2.6.0"
TORCHVISION_VERSION = "0.21.0"
TORCH_CUDA_VERSION = "12.4"
CUDA_TOOLKIT_VERSION = "12.4.0"
CUDA_ARCH = "8.0"
FLASH_ATTN_VERSION = "2.7.3"
ACCELERATE_VERSION = "1.7.0"

# Pin every Git source. A fixed release tag must never silently rebuild against
# a moving upstream branch.
TRELLIS_REF = "75fbf0183001ed9876c8dbb35de6b68552ee08bd"
UTILS3D_REF = "9a4eb15e4021b67b12c460c7057d642626897ec8"
NVDIFFRAST_REF = "253ac4fcea7de5f396371124af597e6cc957bfae"
NVDIFFREC_REF = "b296927cc7fd01c2ac1087c8065c4d7248f72da4"
CUMESH_REF = "12289e1062f0603f2f0d0771b02e1395d247f26f"
FLEXGEMM_REF = "6dd94a859c26ee8246888502eada3dd8ad85532e"

SOURCE_SPECS = {
    "TRELLIS.2": ("https://github.com/microsoft/TRELLIS.2.git", TRELLIS_REF, True),
    "utils3d": ("https://github.com/EasternJournalist/utils3d.git", UTILS3D_REF, False),
    "nvdiffrast": ("https://github.com/NVlabs/nvdiffrast.git", NVDIFFRAST_REF, False),
    "nvdiffrec": ("https://github.com/JeffreyXiang/nvdiffrec.git", NVDIFFREC_REF, False),
    "CuMesh": ("https://github.com/JeffreyXiang/CuMesh.git", CUMESH_REF, True),
    "FlexGEMM": ("https://github.com/JeffreyXiang/FlexGEMM.git", FLEXGEMM_REF, True),
}

# Normal runtime dependencies are deliberately separate from custom CUDA wheels.
# Keep torch/torchvision/triton constrained so dependency resolution cannot replace
# the OpenI base image's CUDA stack. Transformers stays on the 4.x line because
# TRELLIS.2 needs DINOv3ViTModel but there is no reason to absorb a future major API.
# Direct runtime versions below are the exact versions observed in the final
# successful Modal validation run. Pinning them prevents a future PyPI resolver
# run from silently changing the OpenI environment under the same release tag.
BUILD_RUNTIME_REQUIREMENTS = """\
imageio==2.37.4
imageio-ffmpeg==0.6.0
tqdm==4.70.0
easydict==1.13
opencv-python-headless==5.0.0.93
ninja==1.13.0
trimesh==5.0.0
transformers==4.57.6
gradio==6.0.1
tensorboard==2.21.0
pandas==2.3.3
lpips==0.1.4
zstandard==0.25.0
kornia==0.8.2
timm==1.0.28
torchvision==0.21.0
pillow==12.3.0
numpy==2.2.6
plyfile==1.1.5
einops==0.8.2
moderngl==5.12.0
scipy==1.15.3
filelock==3.32.3
triton==3.2.0
"""

# Runtime-only compatibility pins are intentionally excluded from the CUDA wheel
# build cache identity. They affect the final OpenI Python runtime, not compiled
# extension ABI/artifacts, so adding/changing them must not force an expensive
# rebuild of already validated CUDA wheels.
RUNTIME_ONLY_REQUIREMENTS = f"""\
accelerate=={ACCELERATE_VERSION}
"""

RUNTIME_REQUIREMENTS = BUILD_RUNTIME_REQUIREMENTS + RUNTIME_ONLY_REQUIREMENTS

RUNTIME_CONSTRAINTS = """\
torch==2.6.0
torchvision==0.21.0
triton==3.2.0
"""

# Modal cannot reach the user's private 192.168.x.x OpenI registry, so recreate
# the ABI-relevant public stack: Ubuntu 22.04 + CUDA 12.4 devel + CPython 3.11 +
# PyTorch 2.6/cu124. uv is used for image dependency installation and retained in
# the image for runtime dependency installation/building.
build_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.0-devel-ubuntu22.04",
        add_python=PYTHON_MINOR,
    )
    .entrypoint([])
    .apt_install(
        "build-essential",
        "cmake",
        "git",
        "git-lfs",
        "libjpeg-dev",
        "zlib1g-dev",
        "ninja-build",
        "pkg-config",
    )
    .uv_pip_install(
        f"uv=={UV_VERSION}",
        "setuptools>=75,<81",
        "wheel>=0.45,<0.46",
        "packaging>=24,<26",
        "ninja>=1.11,<2",
        "psutil>=6,<8",
        "requests>=2.32,<3",
        uv_version=UV_VERSION,
    )
    .uv_pip_install(
        f"torch=={TORCH_VERSION}",
        f"torchvision=={TORCHVISION_VERSION}",
        index_url="https://download.pytorch.org/whl/cu124",
        uv_version=UV_VERSION,
    )
    .env(
        {
            "CC": "/usr/bin/gcc",
            "CXX": "/usr/bin/g++",
            "CUDAHOSTCXX": "/usr/bin/g++",
            "CUDA_HOME": "/usr/local/cuda",
            "BUILD_TARGET": "cuda",
            "TORCH_CUDA_ARCH_LIST": CUDA_ARCH,
            "LIBRARY_PATH": "/usr/local/cuda/lib64/stubs:/usr/local/cuda/lib64",
            "MAX_JOBS": "8",
            "UV_LINK_MODE": "copy",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
)

publish_image = (
    modal.Image.debian_slim(python_version=PYTHON_MINOR)
    .uv_pip_install("requests>=2.32,<3", uv_version=UV_VERSION)
)

app = modal.App(APP_NAME)
build_cache = modal.Volume.from_name(CACHE_VOLUME_NAME, create_if_missing=True)
github_secret = modal.Secret.from_name(
    "github-openi-build",
    required_keys=["GITHUB_TOKEN"],
)


def _cache_identity() -> dict[str, object]:
    return {
        "schema": CACHE_SCHEMA,
        "python": PYTHON_MINOR,
        "torch": TORCH_VERSION,
        "torchvision": TORCHVISION_VERSION,
        "torch_cuda": TORCH_CUDA_VERSION,
        "cuda_toolkit": CUDA_TOOLKIT_VERSION,
        "cuda_arch": CUDA_ARCH,
        "flash_attn": FLASH_ATTN_VERSION,
        "sources": {name: spec[1] for name, spec in SOURCE_SPECS.items()},
        "runtime_requirements": BUILD_RUNTIME_REQUIREMENTS,
        "runtime_constraints": RUNTIME_CONSTRAINTS,
    }


def _cache_key() -> str:
    import hashlib
    import json

    payload = json.dumps(_cache_identity(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


@app.function(
    image=build_image,
    gpu=MODAL_GPU,
    cpu=16.0,
    memory=32768,
    timeout=3 * 60 * 60,
    max_containers=1,
    retries=1,
    volumes={"/cache": build_cache},
)
def build_wheelhouse(force_rebuild: bool = False) -> dict[str, object]:
    """Compile and persist all custom wheels. Expensive work lives only here."""
    import hashlib
    import json
    import os
    import pathlib
    import platform
    import shutil
    import subprocess
    import sys
    import zipfile

    import torch

    key = _cache_key()
    root = pathlib.Path("/tmp/trellis2-build")
    src_root = root / "src"
    wheelhouse = root / "wheelhouse"
    cache_root = pathlib.Path("/cache/trellis2-py311") / key
    cache_wheels = cache_root / "wheelhouse"
    cache_meta = cache_root / "build-meta.json"
    cache_flex = cache_root / "flex_gemm_autotune_cache.json"

    shutil.rmtree(root, ignore_errors=True)
    src_root.mkdir(parents=True)
    wheelhouse.mkdir(parents=True)
    cache_root.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    torch_lib = pathlib.Path(torch.__file__).resolve().parent / "lib"
    env.update(
        {
            "CC": "/usr/bin/gcc",
            "CXX": "/usr/bin/g++",
            "CUDAHOSTCXX": "/usr/bin/g++",
            "CUDA_HOME": "/usr/local/cuda",
            "BUILD_TARGET": "cuda",
            "TORCH_CUDA_ARCH_LIST": CUDA_ARCH,
            "LIBRARY_PATH": "/usr/local/cuda/lib64/stubs:/usr/local/cuda/lib64",
            "LD_LIBRARY_PATH": (
                f"{torch_lib}:/usr/local/cuda/lib64:/usr/local/cuda/lib64/stubs:"
                + env.get("LD_LIBRARY_PATH", "")
            ),
            "MAX_JOBS": "8",
            "UV_CACHE_DIR": "/tmp/uv-cache",
            "UV_LINK_MODE": "copy",
        }
    )

    def run(
        cmd: list[str],
        *,
        cwd: pathlib.Path | None = None,
        capture: bool = False,
        check: bool = True,
    ) -> str:
        print("+", " ".join(str(x) for x in cmd), flush=True)
        proc = subprocess.run(
            [str(x) for x in cmd],
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            check=check,
        )
        if capture and proc.stderr:
            print(proc.stderr, file=sys.stderr, end="" if proc.stderr.endswith("\n") else "\n", flush=True)
        return proc.stdout.strip() if capture and proc.stdout else ""

    def valid_wheel(path: pathlib.Path) -> bool:
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                return (
                    bool(names)
                    and any(n.endswith(".dist-info/WHEEL") for n in names)
                    and zf.testzip() is None
                )
        except (OSError, zipfile.BadZipFile):
            return False

    def clone(name: str) -> tuple[pathlib.Path, str]:
        url, ref, recursive = SOURCE_SPECS[name]
        dst = src_root / name
        # Checkout the pinned superproject first, then initialize submodules.
        # This avoids cloning submodules for a moving default branch only to
        # immediately replace them after checkout.
        run(["git", "clone", url, str(dst)])
        run(["git", "-c", "advice.detachedHead=false", "checkout", "--detach", ref], cwd=dst)
        if recursive:
            run(["git", "submodule", "update", "--init", "--recursive"], cwd=dst)
        sha = run(["git", "rev-parse", "HEAD"], cwd=dst, capture=True)
        if sha != ref:
            raise RuntimeError(f"{name}: expected {ref}, checked out {sha}")
        return dst, sha

    def component_cache_dir(name: str) -> pathlib.Path:
        safe = name.lower().replace(".", "-").replace("/", "-")
        return cache_wheels / safe

    def restore_component(name: str) -> list[pathlib.Path]:
        if force_rebuild:
            return []
        cdir = component_cache_dir(name)
        cached = sorted(cdir.glob("*.whl")) if cdir.exists() else []
        if not cached or not all(valid_wheel(p) for p in cached):
            return []
        restored: list[pathlib.Path] = []
        for wheel in cached:
            dst = wheelhouse / wheel.name
            shutil.copy2(wheel, dst)
            restored.append(dst)
        print(f"===== CACHE HIT {name}: {[p.name for p in restored]} =====", flush=True)
        return restored

    def persist_component(name: str, paths: list[pathlib.Path]) -> None:
        cdir = component_cache_dir(name)
        tmp = cdir.with_name(cdir.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True, exist_ok=True)
        for wheel in paths:
            if not valid_wheel(wheel):
                raise RuntimeError(f"Invalid wheel produced: {wheel}")
            shutil.copy2(wheel, tmp / wheel.name)
        shutil.rmtree(cdir, ignore_errors=True)
        tmp.rename(cdir)
        # Persist each expensive component immediately. A later validation or
        # publication failure must not throw away minutes of CUDA compilation.
        build_cache.commit()

    def build_component(
        name: str,
        source: pathlib.Path | str,
        *,
        backend: str = "uv",
    ) -> list[pathlib.Path]:
        restored = restore_component(name)
        if restored:
            return restored
        print(f"\n===== BUILD {name} [{backend}] =====", flush=True)
        before = {p.name for p in wheelhouse.glob("*.whl")}
        if backend == "uv":
            run(
                [
                    "uv",
                    "build",
                    "--wheel",
                    "--no-build-isolation",
                    "--out-dir",
                    str(wheelhouse),
                    str(source),
                ]
            )
        elif backend == "pip-wheel":
            # uv has no wheel-artifact equivalent that is as reliable for these
            # legacy setup.py/sdist packages. Keep pip only for artifact creation;
            # resolution and installation elsewhere use uv.
            run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    "--no-build-isolation",
                    "--wheel-dir",
                    str(wheelhouse),
                    str(source),
                ]
            )
        else:
            raise ValueError(f"Unknown backend: {backend}")

        built = [p for p in wheelhouse.glob("*.whl") if p.name not in before]
        if not built:
            raise RuntimeError(f"{name}: build produced no new wheel")
        persist_component(name, sorted(built))
        return sorted(built)

    def sha256_file(path: pathlib.Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    print("===== BUILD ENVIRONMENT =====", flush=True)
    print("Python:", sys.version)
    print("Platform:", platform.platform())
    print("Torch:", torch.__version__)
    print("Torch CUDA:", torch.version.cuda)
    print("CUDA available:", torch.cuda.is_available())
    print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE")
    print("Capability:", torch.cuda.get_device_capability(0) if torch.cuda.is_available() else None)
    print("uv:", run(["uv", "--version"], capture=True))
    run([env["CXX"], "--version"])
    run(["nvcc", "--version"])

    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(f"Expected Python 3.11, got {sys.version}")
    if torch.__version__.split("+", 1)[0] != TORCH_VERSION:
        raise RuntimeError(f"Expected torch {TORCH_VERSION}, got {torch.__version__}")
    if torch.version.cuda != TORCH_CUDA_VERSION:
        raise RuntimeError(f"Expected torch CUDA {TORCH_CUDA_VERSION}, got {torch.version.cuda}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable inside the Modal A100 builder")
    if torch.cuda.get_device_capability(0) != (8, 0):
        raise RuntimeError(f"Expected A100 sm_80, got {torch.cuda.get_device_capability(0)}")

    # Fast path: a complete keyed wheelhouse survives previous runs. This is the
    # most important cache because it avoids all CUDA compilation and source clones.
    flat_cache = cache_root / "wheelhouse-flat"
    if not force_rebuild and cache_meta.exists() and cache_flex.exists() and flat_cache.is_dir():
        cached_flat = sorted(flat_cache.glob("*.whl"))
        if len(cached_flat) >= 7 and all(valid_wheel(p) for p in cached_flat):
            metadata = json.loads(cache_meta.read_text(encoding="utf-8"))
            expected_wheels = {
                item["name"]: (item.get("size"), item.get("sha256"))
                for item in metadata.get("wheels", [])
                if isinstance(item, dict) and item.get("name")
            }
            actual_names = {p.name for p in cached_flat}
            hashes_match = bool(expected_wheels) and actual_names == set(expected_wheels)
            if hashes_match:
                for wheel in cached_flat:
                    expected_size, expected_sha = expected_wheels[wheel.name]
                    if wheel.stat().st_size != expected_size or sha256_file(wheel) != expected_sha:
                        hashes_match = False
                        break
            if metadata.get("cache_key") == key and hashes_match:
                print(f"===== COMPLETE WHEELHOUSE CACHE HIT {key} =====", flush=True)
                return {
                    "cache_key": key,
                    "wheels": [p.name for p in cached_flat],
                    "sources": metadata.get("sources", {}),
                    "cache_hit_allowed": True,
                    "complete_cache_hit": True,
                }
            print("===== COMPLETE CACHE REJECTED: metadata/hash mismatch =====", flush=True)

    # o-voxel declares several Python packages as build requirements. With
    # --no-build-isolation those requirements must already exist in the build
    # environment, so prepare the same constrained runtime stack with uv before
    # compiling. This also avoids any build backend attempting to replace torch.
    build_requirements = root / "requirements-build.txt"
    build_constraints = root / "constraints-build.txt"
    build_requirements.write_text(BUILD_RUNTIME_REQUIREMENTS, encoding="utf-8")
    build_constraints.write_text(RUNTIME_CONSTRAINTS, encoding="utf-8")
    run(["uv", "pip", "uninstall", "--python", sys.executable, "pillow-simd", "Pillow"], check=False)
    run(
        [
            "uv", "pip", "install", "--python", sys.executable,
            "-r", str(build_requirements),
            "-c", str(build_constraints),
        ]
    )

    sources: dict[str, str] = {}
    paths: dict[str, pathlib.Path] = {}
    for name in SOURCE_SPECS:
        paths[name], sources[name] = clone(name)

    # Modern pyproject/PEP-517 projects use uv build. flash-attn 2.7.3 and the
    # pinned nvdiffrec renderutils source are legacy setup.py paths, so use the
    # compatibility artifact builder only for those two.
    build_component("utils3d", paths["utils3d"], backend="uv")
    build_component(
        "flash-attn",
        f"flash-attn=={FLASH_ATTN_VERSION}",
        backend="pip-wheel",
    )
    build_component("nvdiffrast", paths["nvdiffrast"], backend="uv")
    build_component("nvdiffrec-render", paths["nvdiffrec"], backend="pip-wheel")
    build_component("CuMesh", paths["CuMesh"], backend="uv")
    build_component("FlexGEMM", paths["FlexGEMM"], backend="uv")
    build_component("o-voxel", paths["TRELLIS.2"] / "o-voxel", backend="uv")

    wheels = sorted(wheelhouse.glob("*.whl"))
    stale_abi = [p.name for p in wheels if "cp310" in p.name or "py310" in p.name]
    if stale_abi:
        raise RuntimeError(f"Python 3.10 wheel contamination detected: {stale_abi}")
    if len(wheels) < 7:
        raise RuntimeError(f"Expected at least 7 wheels, found {len(wheels)}: {wheels}")

    cache_wheels.mkdir(parents=True, exist_ok=True)
    # Also keep a flat canonical wheelhouse for the clean validation stage.
    flat = cache_root / "wheelhouse-flat"
    shutil.rmtree(flat, ignore_errors=True)
    flat.mkdir(parents=True)
    for wheel in wheels:
        shutil.copy2(wheel, flat / wheel.name)

    flex_src = paths["FlexGEMM"] / "autotune_cache.json"
    if not flex_src.exists():
        raise RuntimeError(f"FlexGEMM autotune cache missing: {flex_src}")
    shutil.copy2(flex_src, cache_flex)

    metadata = {
        "cache_key": key,
        "cache_identity": _cache_identity(),
        "sources": sources,
        "build": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "gpu_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "uv": run(["uv", "--version"], capture=True),
            "gcc": run([env["CXX"], "-dumpfullversion"], capture=True),
        },
        "wheels": [
            {
                "name": p.name,
                "size": p.stat().st_size,
                "sha256": sha256_file(p),
            }
            for p in wheels
        ],
    }
    cache_meta.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    build_cache.commit()

    return {
        "cache_key": key,
        "wheels": [p.name for p in wheels],
        "sources": sources,
        "cache_hit_allowed": not force_rebuild,
    }


@app.function(
    image=build_image,
    gpu=MODAL_GPU,
    cpu=8.0,
    memory=24576,
    timeout=60 * 60,
    max_containers=1,
    retries=1,
    volumes={"/cache": build_cache},
)
def validate_and_package(cache_key: str) -> dict[str, object]:
    """Install the cached artifacts into a clean A100 container, smoke-test them,
    then create the exact OpenI installer/archive. No source compilation occurs here.
    """
    import hashlib
    import json
    import os
    import pathlib
    import platform
    import shutil
    import subprocess
    import sys
    import tarfile
    import time
    import zipfile

    import torch

    expected_key = _cache_key()
    if cache_key != expected_key:
        raise RuntimeError(f"Cache key mismatch: caller={cache_key}, expected={expected_key}")

    build_cache.reload()
    cache_root = pathlib.Path("/cache/trellis2-py311") / cache_key
    source_wheels = cache_root / "wheelhouse-flat"
    source_meta = cache_root / "build-meta.json"
    source_flex = cache_root / "flex_gemm_autotune_cache.json"
    if not source_wheels.is_dir() or not source_meta.exists() or not source_flex.exists():
        raise RuntimeError(f"Incomplete wheel cache at {cache_root}")

    root = pathlib.Path("/tmp/trellis2-validate")
    dist = root / "dist"
    wheels = dist / "wheelhouse"
    bootstrap = dist / "bootstrap"
    trellis = root / "TRELLIS.2"
    shutil.rmtree(root, ignore_errors=True)
    wheels.mkdir(parents=True)
    bootstrap.mkdir(parents=True)
    for wheel in source_wheels.glob("*.whl"):
        shutil.copy2(wheel, wheels / wheel.name)

    wheel_files = sorted(wheels.glob("*.whl"))
    stale_abi = [p.name for p in wheel_files if "cp310" in p.name or "py310" in p.name]
    if stale_abi:
        raise RuntimeError(f"Python 3.10 wheel contamination detected during validation: {stale_abi}")
    if len(wheel_files) < 7:
        raise RuntimeError(f"Cached wheelhouse is incomplete: {[p.name for p in wheel_files]}")
    for wheel in wheel_files:
        try:
            with zipfile.ZipFile(wheel) as zf:
                if not any(n.endswith(".dist-info/WHEEL") for n in zf.namelist()):
                    raise RuntimeError(f"Malformed wheel: {wheel}")
                bad_member = zf.testzip()
                if bad_member is not None:
                    raise RuntimeError(f"Wheel CRC failure: {wheel.name}: {bad_member}")
        except zipfile.BadZipFile as exc:
            raise RuntimeError(f"Corrupt wheel: {wheel}") from exc

    env = os.environ.copy()
    torch_lib = pathlib.Path(torch.__file__).resolve().parent / "lib"
    env.update(
        {
            "CUDA_HOME": "/usr/local/cuda",
            "TORCH_CUDA_ARCH_LIST": CUDA_ARCH,
            "UV_CACHE_DIR": "/tmp/uv-cache",
            "UV_LINK_MODE": "copy",
            # Critical OpenI invariant: validation is not allowed to hide a missing
            # wheel by compiling an sdist. If a binary is unavailable, fail here.
            "UV_NO_BUILD": "1",
            "LD_LIBRARY_PATH": (
                f"{torch_lib}:/usr/local/cuda/lib64:/usr/local/cuda/lib64/stubs:"
                + env.get("LD_LIBRARY_PATH", "")
            ),
        }
    )

    def run(
        cmd: list[str],
        *,
        cwd: pathlib.Path | None = None,
        capture: bool = False,
        check: bool = True,
    ) -> str:
        print("+", " ".join(str(x) for x in cmd), flush=True)
        proc = subprocess.run(
            [str(x) for x in cmd],
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            check=check,
        )
        if capture and proc.stderr:
            print(proc.stderr, file=sys.stderr, end="" if proc.stderr.endswith("\n") else "\n", flush=True)
        return proc.stdout.strip() if capture and proc.stdout else ""

    def sha256_file(path: pathlib.Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    print("===== CLEAN VALIDATION ENVIRONMENT =====", flush=True)
    print("Python:", sys.version)
    print("Platform:", platform.platform())
    print("Torch:", torch.__version__)
    print("Torch CUDA:", torch.version.cuda)
    print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE")
    print("uv:", run(["uv", "--version"], capture=True))

    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(f"Expected Python 3.11, got {sys.version}")
    if torch.__version__.split("+", 1)[0] != TORCH_VERSION:
        raise RuntimeError(f"Expected torch {TORCH_VERSION}, got {torch.__version__}")
    if torch.version.cuda != TORCH_CUDA_VERSION:
        raise RuntimeError(f"Expected torch CUDA {TORCH_CUDA_VERSION}, got {torch.version.cuda}")
    if not torch.cuda.is_available() or torch.cuda.get_device_capability(0) != (8, 0):
        raise RuntimeError("Clean validation requires a Modal A100/sm_80")

    requirements_path = dist / "requirements-openi.txt"
    constraints_path = dist / "constraints-openi.txt"
    resolved_constraints_path = dist / "constraints-openi.resolved.txt"
    requirements_path.write_text(RUNTIME_REQUIREMENTS, encoding="utf-8")
    constraints_path.write_text(RUNTIME_CONSTRAINTS, encoding="utf-8")

    # Pillow-SIMD and Pillow share PIL. Clean both package records/namespaces first.
    run(["uv", "pip", "uninstall", "--python", sys.executable, "pillow-simd", "Pillow"], check=False)
    run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "-r",
            str(requirements_path),
            "-c",
            str(constraints_path),
        ]
    )

    # Keep a diagnostic snapshot of the exact registry environment validated on Modal.
    # IMPORTANT: this file is NOT consumed by install_openi.sh. It is metadata only.
    # `uv` writes status messages such as "Using Python ..." to stderr, so run() keeps
    # stderr separate. Parse every stdout line as a PEP 508 requirement as a second
    # guard against future uv output-format changes or accidental log contamination.
    from packaging.requirements import InvalidRequirement, Requirement
    from packaging.utils import canonicalize_name

    resolved_lines: list[str] = []
    rejected_freeze_lines: list[str] = []
    for line in run(["uv", "pip", "freeze", "--python", sys.executable], capture=True).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            req = Requirement(stripped)
        except InvalidRequirement:
            rejected_freeze_lines.append(stripped)
            continue
        normalized = canonicalize_name(req.name)
        # The OpenI image owns the CUDA-sensitive torch stack.
        if normalized in {"torch", "torchvision", "triton"}:
            continue
        resolved_lines.append(stripped)

    if rejected_freeze_lines:
        print(
            "WARNING: ignored non-requirement lines from `uv pip freeze`: "
            + repr(rejected_freeze_lines),
            file=sys.stderr,
            flush=True,
        )
    if not resolved_lines:
        raise RuntimeError("uv pip freeze produced no valid resolved requirements")

    resolved_constraints_path.write_text(
        "\n".join(sorted(set(resolved_lines), key=str.lower)) + "\n",
        encoding="utf-8",
    )

    # Fail packaging immediately if the diagnostic snapshot itself is malformed.
    # This catches regressions during Modal validation, before anything reaches OpenI.
    for line_no, line in enumerate(resolved_constraints_path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            Requirement(line)
        except InvalidRequirement as exc:
            raise RuntimeError(
                f"Malformed generated constraint at {resolved_constraints_path}:{line_no}: {line!r}"
            ) from exc

    # Install the exact wheelhouse without dependency resolution. --reinstall makes
    # validation deterministic even if a container happens to be reused.
    run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            "--reinstall",
            *[str(p) for p in wheel_files],
        ]
    )
    run(["uv", "pip", "check", "--python", sys.executable])

    # Verify every direct exact pin against installed distribution metadata. This is
    # important for OpenI-like pre-populated environments: a successful resolver run
    # is not enough if an unexpected preinstalled version survives.
    run(
        [
            sys.executable,
            "-c",
            (
                "from importlib.metadata import version; "
                "from packaging.requirements import Requirement; "
                "from pathlib import Path; "
                "p=Path(__import__('sys').argv[1]); "
                "reqs=[Requirement(x.strip()) for x in p.read_text().splitlines() "
                "if x.strip() and not x.lstrip().startswith('#')]; "
                "bad=[(r.name, str(r.specifier), version(r.name)) for r in reqs "
                "if not r.specifier.contains(version(r.name), prereleases=True)]; "
                "assert not bad, f'direct runtime pin mismatch: {bad}'; "
                "print('direct runtime pins: OK')"
            ),
            str(requirements_path),
        ]
    )

    run(
        [
            sys.executable,
            "-c",
            (
                "import torch, torchvision, triton; "
                f"assert torch.__version__.split('+', 1)[0] == '{TORCH_VERSION}'; "
                f"assert torch.version.cuda == '{TORCH_CUDA_VERSION}'; "
                f"assert torchvision.__version__.split('+', 1)[0] == '{TORCHVISION_VERSION}'; "
                "assert triton.__version__ == '3.2.0'; "
                "print('torch stack: OK')"
            ),
        ]
    )

    print("\n===== VERIFY RUNTIME DEPENDENCIES =====", flush=True)
    run(
        [
            sys.executable,
            "-c",
            (
                "import accelerate, cv2, easydict, einops, filelock, gradio, imageio, "
                "imageio_ffmpeg, kornia, lpips, moderngl, ninja, numpy, pandas, "
                "plyfile, scipy, tensorboard, timm, tqdm, transformers, trimesh, "
                "triton, torchvision, zstandard; "
                f"assert accelerate.__version__ == '{ACCELERATE_VERSION}', accelerate.__version__; "
                "assert transformers.__version__ == '4.57.6', transformers.__version__; "
                "from transformers import DINOv3ViTModel; "
                "from PIL import Image, features; Image.init(); "
                "assert features.check('jpg'); assert features.check('zlib'); "
                "assert features.check('webp'); "
                "print('runtime dependencies: OK, accelerate=', accelerate.__version__, "
                "'transformers=', transformers.__version__)"
            ),
        ]
    )

    # Always import torch before private torch-extension DSOs. nvdiffrast's public
    # torch API itself follows this order; importing _nvdiffrast_c first can report a
    # false libc10.so failure even when the wheel is valid.
    extension_checks = [
        ("flash-attn", "import torch; import flash_attn, flash_attn_2_cuda"),
        (
            "nvdiffrast",
            "import torch; import nvdiffrast.torch as dr; import _nvdiffrast_c; "
            "assert dr.RasterizeCudaContext is not None",
        ),
        (
            "nvdiffrec-render",
            "import torch; import nvdiffrec_render, nvdiffrec_render.renderutils._C",
        ),
        (
            "CuMesh",
            "import torch; import cumesh, cumesh._C, cumesh._cubvh, cumesh._cumesh_xatlas",
        ),
        ("o-voxel", "import torch; import o_voxel, o_voxel._C"),
        ("FlexGEMM", "import torch; import flex_gemm, flex_gemm.kernels.cuda"),
        ("utils3d", "import utils3d, utils3d.io, utils3d.numpy, utils3d.torch"),
    ]
    for label, imports in extension_checks:
        print(f"\n===== VERIFY {label} =====", flush=True)
        run([sys.executable, "-c", f"{imports}; print('{label}: OK')"])

    # Exercise nvdiffrast on the actual GPU instead of validating only imports.
    print("\n===== NVDIFFRAST CUDA SMOKE TEST =====", flush=True)
    run(
        [
            sys.executable,
            "-c",
            (
                "import torch; import nvdiffrast.torch as dr; "
                "ctx=dr.RasterizeCudaContext(); "
                "pos=torch.tensor([[[-0.5,-0.5,0.,1.],[0.5,-0.5,0.,1.],"
                "[0.,0.5,0.,1.]]],device='cuda',dtype=torch.float32); "
                "tri=torch.tensor([[0,1,2]],device='cuda',dtype=torch.int32); "
                "rast,_=dr.rasterize(ctx,pos,tri,(16,16)); torch.cuda.synchronize(); "
                "assert rast.is_cuda and rast.shape==(1,16,16,4); "
                "print('nvdiffrast CUDA smoke: OK')"
            ),
        ]
    )

    # Import the exact TRELLIS.2 source revision against the prebuilt wheelhouse.
    run(["git", "clone", SOURCE_SPECS["TRELLIS.2"][0], str(trellis)])
    run(["git", "-c", "advice.detachedHead=false", "checkout", "--detach", TRELLIS_REF], cwd=trellis)
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=trellis)
    actual_trellis = run(["git", "rev-parse", "HEAD"], cwd=trellis, capture=True)
    if actual_trellis != TRELLIS_REF:
        raise RuntimeError(f"TRELLIS.2 checkout mismatch: {actual_trellis}")

    print("\n===== VERIFY TRELLIS.2 INTEGRATION =====", flush=True)
    run(
        [
            sys.executable,
            "-c",
            (
                "from trellis2.pipelines import Trellis2ImageTo3DPipeline, Trellis2TexturingPipeline; "
                "from trellis2.renderers import MeshRenderer, VoxelRenderer, PbrMeshRenderer; "
                "from trellis2.models import SparseStructureEncoder, SLatFlowModel, FlexiDualGridVaeDecoder; "
                "print('TRELLIS.2 integration imports: OK')"
            ),
        ],
        cwd=trellis,
    )

    # Bundle uv itself so OpenI does not need network access merely to bootstrap
    # the package manager. pip is used only to download/install this one wheel.
    run(
        [
            sys.executable, "-m", "pip", "download",
            "--only-binary=:all:", "--no-deps",
            "--dest", str(bootstrap), f"uv=={UV_VERSION}",
        ]
    )
    uv_bootstrap = sorted(bootstrap.glob("uv-*.whl"))
    if len(uv_bootstrap) != 1:
        raise RuntimeError(f"Expected one uv bootstrap wheel, got {uv_bootstrap}")

    # The OpenI installer prefers uv. If the image does not already have it,
    # bootstrap from the bundled wheel without contacting PyPI.
    installer = f'''#!/bin/sh
set -eu

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="$(command -v python)"

"$PYTHON_BIN" - <<'PY_CHECK'
import sys, torch, torchvision, triton
print("Python:", sys.version)
print("Torch:", torch.__version__)
print("Torch CUDA:", torch.version.cuda)
print("Torchvision:", torchvision.__version__)
print("Triton:", triton.__version__)
assert sys.version_info[:2] == (3, 11), "Expected Python 3.11"
assert torch.__version__.split("+", 1)[0] == "{TORCH_VERSION}", "Expected Torch {TORCH_VERSION}"
assert torch.version.cuda == "{TORCH_CUDA_VERSION}", "Expected Torch CUDA {TORCH_CUDA_VERSION}"
assert torchvision.__version__.split("+", 1)[0] == "{TORCHVISION_VERSION}", "Expected Torchvision {TORCHVISION_VERSION}"
assert triton.__version__ == "3.2.0", "Expected Triton 3.2.0"
PY_CHECK

# Always use the bundled uv wheel with the current Notebook Python. Do not trust
# an arbitrary system uv version on OpenI, because resolver/log behavior can drift.
"$PYTHON_BIN" -m pip install --no-deps --force-reinstall "$HERE"/bootstrap/uv-*.whl
UV_BIN="$(dirname -- "$PYTHON_BIN")/uv"
if [ ! -x "$UV_BIN" ]; then
  echo "Bundled uv executable not found next to $PYTHON_BIN: $UV_BIN" >&2
  exit 1
fi
UV_ACTUAL="$("$UV_BIN" --version)"
case "$UV_ACTUAL" in
  "uv {UV_VERSION}"*) ;;
  *) echo "Expected uv {UV_VERSION}, got: $UV_ACTUAL" >&2; exit 1 ;;
esac

export UV_LINK_MODE=copy
# Never compile on OpenI. A missing binary wheel must fail loudly instead of
# consuming GPU job time building CUDA/C++ extensions again.
export UV_NO_BUILD=1

if command -v sha256sum >/dev/null 2>&1 && [ -f "$HERE/SHA256SUMS.contents" ]; then
  (cd "$HERE" && sha256sum -c SHA256SUMS.contents)
fi

"$UV_BIN" pip uninstall --python "$PYTHON_BIN" pillow-simd Pillow >/dev/null 2>&1 || true
# OpenI deliberately uses only the hand-written ABI constraints.
# constraints-openi.resolved.txt is packaged for diagnostics/reproducibility only;
# it must never be able to block installation because of resolver/log-format drift.
"$UV_BIN" pip install --python "$PYTHON_BIN" \
  -r "$HERE/requirements-openi.txt" \
  -c "$HERE/constraints-openi.txt"
"$UV_BIN" pip install --python "$PYTHON_BIN" --no-deps --reinstall "$HERE"/wheelhouse/*.whl
# Do NOT run a whole-environment `uv pip check` on OpenI: its /usr/local Python is
# pre-populated with hundreds of unrelated packages, and an unrelated legacy conflict
# must not block TRELLIS.2. The clean Modal validation already runs uv pip check; here
# we verify every direct pin plus the actual TRELLIS/runtime imports below.

mkdir -p "$HOME/.flex_gemm"
cp "$HERE/flex_gemm_autotune_cache.json" "$HOME/.flex_gemm/autotune_cache.json"

"$PYTHON_BIN" - "$HERE/requirements-openi.txt" <<'PY_VERIFY'
import sys
from importlib.metadata import version as dist_version
from packaging.requirements import Requirement

with open(sys.argv[1], encoding="utf-8") as fh:
    direct_requirements = [
        Requirement(line.strip())
        for line in fh
        if line.strip() and not line.lstrip().startswith("#")
    ]

bad_pins = []
for req in direct_requirements:
    installed = dist_version(req.name)
    if not req.specifier.contains(installed, prereleases=True):
        bad_pins.append((req.name, str(req.specifier), installed))
assert not bad_pins, f"Direct runtime pin mismatch: {{bad_pins}}"
print("Direct runtime pins: OK")

import accelerate, torch, torchvision, transformers, triton
assert torch.__version__.split("+", 1)[0] == "{TORCH_VERSION}"
assert torch.version.cuda == "{TORCH_CUDA_VERSION}"
assert torchvision.__version__.split("+", 1)[0] == "{TORCHVISION_VERSION}"
assert triton.__version__ == "3.2.0"
assert accelerate.__version__ == "{ACCELERATE_VERSION}", accelerate.__version__
assert transformers.__version__ == "4.57.6", transformers.__version__
print("Accelerate:", accelerate.__version__)
print("Transformers:", transformers.__version__)

# torch must be imported before torch-linked private extension DSOs.
import flash_attn, flash_attn_2_cuda
import nvdiffrast.torch as dr
import _nvdiffrast_c
import nvdiffrec_render, nvdiffrec_render.renderutils._C
import cumesh, cumesh._C, cumesh._cubvh, cumesh._cumesh_xatlas
import o_voxel, o_voxel._C
import flex_gemm, flex_gemm.kernels.cuda
import utils3d, utils3d.io, utils3d.numpy, utils3d.torch
from transformers import DINOv3ViTModel
from PIL import Image, features
Image.init()
assert features.check("jpg") and features.check("zlib") and features.check("webp")
print("TRELLIS.2 prebuilt dependencies: OK")
PY_VERIFY
'''
    # This is the exact regression guard for the OpenI failure that motivated v2/v3.
    # The resolved snapshot may remain in the archive, but the installer must never
    # pass it to uv as a constraints file.
    forbidden_resolved_arg = '-c "$HERE/constraints-openi.resolved.txt"'
    if forbidden_resolved_arg in installer:
        raise RuntimeError(
            "Regression: install_openi.sh must not consume constraints-openi.resolved.txt"
        )

    installer_path = dist / "install_openi.sh"
    installer_path.write_text(installer, encoding="utf-8")
    installer_path.chmod(0o755)
    shutil.copy2(source_flex, dist / "flex_gemm_autotune_cache.json")

    build_metadata = json.loads(source_meta.read_text(encoding="utf-8"))
    manifest = {
        "release_tag": RELEASE_TAG,
        "cache_key": cache_key,
        "target": {
            "openi_image_reference": OPENI_IMAGE_REFERENCE,
            "os": "Ubuntu 22.04",
            "python": PYTHON_MINOR,
            "cuda_toolkit": CUDA_TOOLKIT_VERSION,
            "torch": TORCH_VERSION,
            "torch_cuda": TORCH_CUDA_VERSION,
            "gpu": "NVIDIA A100 40GB target",
            "compute_capability": CUDA_ARCH,
        },
        "build": build_metadata,
        "clean_validation": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "gpu_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "uv": run(["uv", "--version"], capture=True),
            "trellis_ref": actual_trellis,
            "nvdiffrast_cuda_smoke": True,
            "uv_bootstrap_wheel": uv_bootstrap[0].name,
            "resolved_constraints_sha256": sha256_file(resolved_constraints_path),
            "source_builds_disabled": True,
            "accelerate": ACCELERATE_VERSION,
            # Packaging returns successfully only after the archived installer itself runs.
            "packaged_installer_smoke": True,
        },
        "created_unix": int(time.time()),
    }
    manifest_path = dist / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    archive = dist / RELEASE_ARCHIVE
    # Hash every payload inside the archive as well as the archive itself. OpenI's
    # installer verifies SHA256SUMS.contents before touching the environment.
    content_sums = dist / "SHA256SUMS.contents"
    content_entries = []
    content_entries.extend((p, f"wheelhouse/{p.name}") for p in wheel_files)
    content_entries.extend((p, f"bootstrap/{p.name}") for p in sorted(bootstrap.glob("*.whl")))
    content_entries.extend(
        [
            (requirements_path, "requirements-openi.txt"),
            (constraints_path, "constraints-openi.txt"),
            (resolved_constraints_path, "constraints-openi.resolved.txt"),
            (installer_path, "install_openi.sh"),
            (manifest_path, "manifest.json"),
            (dist / "flex_gemm_autotune_cache.json", "flex_gemm_autotune_cache.json"),
        ]
    )
    content_sums.write_text(
        "\n".join(f"{sha256_file(path)}  {rel}" for path, rel in content_entries) + "\n",
        encoding="utf-8",
    )

    with tarfile.open(archive, "w:gz") as tf:
        tf.add(wheels, arcname="wheelhouse")
        tf.add(bootstrap, arcname="bootstrap")
        tf.add(requirements_path, arcname="requirements-openi.txt")
        tf.add(constraints_path, arcname="constraints-openi.txt")
        tf.add(resolved_constraints_path, arcname="constraints-openi.resolved.txt")
        tf.add(installer_path, arcname="install_openi.sh")
        tf.add(manifest_path, arcname="manifest.json")
        tf.add(content_sums, arcname="SHA256SUMS.contents")
        tf.add(dist / "flex_gemm_autotune_cache.json", arcname="flex_gemm_autotune_cache.json")

    # Final package-level gate: extract the exact tar.gz that will be published and
    # execute its installer. This catches archive-layout, shell quoting, checksum,
    # PATH/Python selection, uv invocation, and wheel-install regressions that the
    # earlier in-process validation cannot detect.
    package_smoke = root / "package-smoke"
    shutil.rmtree(package_smoke, ignore_errors=True)
    package_smoke.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(package_smoke)

    smoke_installer = package_smoke / "install_openi.sh"
    if not smoke_installer.is_file():
        raise RuntimeError("Packaged install_openi.sh is missing after archive extraction")

    print("\n===== VERIFY PACKAGED OPENI INSTALLER =====", flush=True)
    run(["bash", str(smoke_installer)], cwd=package_smoke)
    print("packaged install_openi.sh: OK", flush=True)

    sums = dist / "SHA256SUMS"
    sum_lines = [
        f"{sha256_file(archive)}  {archive.name}",
        f"{sha256_file(manifest_path)}  {manifest_path.name}",
    ]
    sums.write_text("\n".join(sum_lines) + "\n", encoding="utf-8")

    release_cache = cache_root / RELEASE_CACHE_DIR
    tmp_release = cache_root / f"{RELEASE_CACHE_DIR}.tmp"
    shutil.rmtree(tmp_release, ignore_errors=True)
    tmp_release.mkdir(parents=True)
    for path in (archive, manifest_path, sums):
        shutil.copy2(path, tmp_release / path.name)
    shutil.rmtree(release_cache, ignore_errors=True)
    tmp_release.rename(release_cache)
    build_cache.commit()

    return {
        "cache_key": cache_key,
        "archive": archive.name,
        "sha256": sha256_file(archive),
        "wheels": [p.name for p in wheel_files],
        "validated": True,
    }


@app.function(
    image=publish_image,
    cpu=1.0,
    memory=1024,
    timeout=30 * 60,
    max_containers=1,
    retries=1,
    volumes={"/cache": build_cache},
    secrets=[github_secret],
)
def publish_release(cache_key: str) -> dict[str, object]:
    """Publish validated binaries from the Volume. No GPU is allocated here."""
    import os
    import pathlib

    import requests

    expected_key = _cache_key()
    if cache_key != expected_key:
        raise RuntimeError(f"Cache key mismatch: caller={cache_key}, expected={expected_key}")

    build_cache.reload()
    release_dir = pathlib.Path("/cache/trellis2-py311") / cache_key / RELEASE_CACHE_DIR
    archive = release_dir / RELEASE_ARCHIVE
    manifest = release_dir / "manifest.json"
    sums = release_dir / "SHA256SUMS"
    for path in (archive, manifest, sums):
        if not path.is_file():
            raise RuntimeError(f"Validated release asset missing: {path}")

    token = os.environ["GITHUB_TOKEN"]
    api = f"https://api.github.com/repos/{GITHUB_REPO}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = requests.get(f"{api}/releases/tags/{RELEASE_TAG}", headers=headers, timeout=60)
    if response.status_code == 404:
        response = requests.post(
            f"{api}/releases",
            headers=headers,
            json={
                "tag_name": RELEASE_TAG,
                "target_commitish": "main",
                "name": "v2 TRELLIS.2 OpenI A100/cu124/torch2.6/Python 3.11 wheelhouse",
                "body": (
                    "Prebuilt TRELLIS.2 dependencies for Ubuntu 22.04, Python 3.11, "
                    "CUDA 12.4, PyTorch 2.6.0 and A100 sm_80. Built on Modal A100, "
                    "then reinstalled and CUDA-smoke-tested in a clean Modal A100 container."
                ),
                "draft": False,
                "prerelease": False,
            },
            timeout=60,
        )
    response.raise_for_status()
    release = response.json()

    assets_response = requests.get(
        f"{api}/releases/{release['id']}/assets",
        headers=headers,
        timeout=60,
    )
    assets_response.raise_for_status()
    existing = {asset["name"]: asset for asset in assets_response.json()}
    upload_url = release["upload_url"].split("{", 1)[0]

    for asset in (archive, manifest, sums):
        old = existing.get(asset.name)
        if old:
            delete_response = requests.delete(old["url"], headers=headers, timeout=60)
            delete_response.raise_for_status()
        print(f"Uploading {asset.name} ({asset.stat().st_size} bytes)...", flush=True)
        with asset.open("rb") as fh:
            upload_response = requests.post(
                upload_url,
                headers={**headers, "Content-Type": "application/octet-stream"},
                params={"name": asset.name},
                data=fh,
                timeout=30 * 60,
            )
        upload_response.raise_for_status()

    print("Published:", release["html_url"], flush=True)
    return {
        "release_url": release["html_url"],
        "release_tag": RELEASE_TAG,
        "archive": archive.name,
        "cache_key": cache_key,
    }


@app.local_entrypoint()
def main(force_rebuild: bool = False, no_publish: bool = False):
    print("[1/3] Build/reuse wheelhouse")
    build_result = build_wheelhouse.remote(force_rebuild)
    print(build_result)

    print("[2/3] Clean A100 validation + OpenI package")
    validate_result = validate_and_package.remote(str(build_result["cache_key"]))
    print(validate_result)

    if no_publish:
        print("[3/3] Publish skipped (--no-publish)")
        return

    print("[3/3] Publish GitHub Release (CPU only)")
    publish_result = publish_release.remote(str(build_result["cache_key"]))
    print(publish_result)
