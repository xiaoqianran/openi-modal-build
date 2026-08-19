from __future__ import annotations

import modal

APP_NAME = "openi-trellis2-wheel-builder"
GITHUB_REPO = "xiaoqianran/openi-modal-build"
RELEASE_TAG = "trellis2-cu124-torch2.6.0-py310-sm80"

# Pin every Git source so rerunning a fixed Release tag cannot silently build a
# different ABI or dependency set after an upstream branch moves.
TRELLIS_REF = "75fbf0183001ed9876c8dbb35de6b68552ee08bd"
UTILS3D_REF = "9a4eb15e4021b67b12c460c7057d642626897ec8"
NVDIFFRAST_REF = "253ac4fcea7de5f396371124af597e6cc957bfae"
NVDIFFREC_REF = "b296927cc7fd01c2ac1087c8065c4d7248f72da4"
CUMESH_REF = "12289e1062f0603f2f0d0771b02e1395d247f26f"
FLEXGEMM_REF = "6dd94a859c26ee8246888502eada3dd8ad85532e"

# OpenI target:
#   Ubuntu 22.04
#   CUDA Toolkit 12.4.0
#   Python 3.10
#   PyTorch 2.6.0 + cu124
#   NVIDIA A100 40GB (sm_80)
#
# The OpenI registry address supplied by the user is a private 192.168.x.x
# address, so Modal cannot be expected to pull it directly. Reproduce its
# relevant ABI/toolchain stack with NVIDIA's public CUDA devel image instead.
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.0-devel-ubuntu22.04",
        add_python="3.10",
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
    .pip_install(
        "pip==25.2",
        "setuptools>=75",
        "wheel>=0.45",
        "packaging",
        "ninja",
        "psutil",
        "requests",
    )
    .run_commands(
        "python -m pip install torch==2.6.0 torchvision==0.21.0 "
        "--index-url https://download.pytorch.org/whl/cu124"
    )
    .env(
        {
            # Modal's standalone Python is built with Clang and its sysconfig
            # therefore defaults C++ extension linking to clang++. The CUDA
            # image only provides GCC via build-essential, and PyTorch's Linux
            # wheels are built with GCC, so force one consistent toolchain.
            "CC": "/usr/bin/gcc",
            "CXX": "/usr/bin/g++",
            "CUDAHOSTCXX": "/usr/bin/g++",
            "CUDA_HOME": "/usr/local/cuda",
            "BUILD_TARGET": "cuda",
            "TORCH_CUDA_ARCH_LIST": "8.0",
            # The nvdiffrec extension links against libcuda/libnvrtc.
            "LIBRARY_PATH": "/usr/local/cuda/lib64/stubs:/usr/local/cuda/lib64",
            "MAX_JOBS": "8",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
)

app = modal.App(APP_NAME, image=image)

# Create this once on Modal with a fine-grained GitHub token that can write
# releases/content to xiaoqianran/openi-modal-build.
github_secret = modal.Secret.from_name(
    "github-openi-build",
    required_keys=["GITHUB_TOKEN"],
)


@app.function(
    gpu="A100-40GB",
    cpu=16.0,
    memory=32768,
    timeout=2 * 60 * 60,
    secrets=[github_secret],
)
def build_and_release() -> dict[str, object]:
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

    import requests
    import torch

    root = pathlib.Path("/tmp/trellis2-build")
    src = root / "src"
    wheels = root / "wheelhouse"
    dist = root / "dist"

    shutil.rmtree(root, ignore_errors=True)
    src.mkdir(parents=True)
    wheels.mkdir()
    dist.mkdir()

    env = os.environ.copy()
    env.update(
        {
            "CC": "/usr/bin/gcc",
            "CXX": "/usr/bin/g++",
            "CUDAHOSTCXX": "/usr/bin/g++",
            "CUDA_HOME": "/usr/local/cuda",
            "BUILD_TARGET": "cuda",
            "TORCH_CUDA_ARCH_LIST": "8.0",
            "LIBRARY_PATH": "/usr/local/cuda/lib64/stubs:/usr/local/cuda/lib64",
            "MAX_JOBS": "8",
        }
    )

    def run(
        cmd: list[str],
        *,
        cwd: pathlib.Path | None = None,
        capture: bool = False,
    ) -> str:
        print("+", " ".join(cmd), flush=True)
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.STDOUT if capture else None,
            check=True,
        )
        return p.stdout.strip() if capture and p.stdout else ""

    def clone(
        name: str,
        url: str,
        *,
        ref: str | None = None,
        recursive: bool = False,
    ) -> tuple[pathlib.Path, str]:
        dst = src / name
        cmd = ["git", "clone"]
        if recursive:
            cmd.append("--recursive")
        cmd.extend([url, str(dst)])
        run(cmd)
        if ref:
            run(["git", "checkout", ref], cwd=dst)
            if recursive:
                run(
                    ["git", "submodule", "update", "--init", "--recursive"],
                    cwd=dst,
                )
        sha = run(["git", "rev-parse", "HEAD"], cwd=dst, capture=True)
        return dst, sha

    def build_wheel(source: pathlib.Path | str, label: str) -> None:
        print(f"\n===== BUILD {label} =====", flush=True)
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                "-w",
                str(wheels),
                str(source),
            ]
        )

    def sha256_file(path: pathlib.Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    print("===== BUILD ENVIRONMENT =====")
    print("Python:", sys.version)
    print("Platform:", platform.platform())
    print("Torch:", torch.__version__)
    print("Torch CUDA:", torch.version.cuda)
    print("CUDA available:", torch.cuda.is_available())
    print("GPU:", torch.cuda.get_device_name(0))
    print("Capability:", torch.cuda.get_device_capability(0))
    print("CC:", env["CC"])
    print("CXX:", env["CXX"])
    print("CUDAHOSTCXX:", env["CUDAHOSTCXX"])
    run([env["CXX"], "--version"])
    run(["nvcc", "--version"])

    if sys.version_info[:2] != (3, 10):
        raise RuntimeError(f"Expected Python 3.10, got {sys.version}")
    if torch.__version__.split("+", 1)[0] != "2.6.0":
        raise RuntimeError(f"Expected torch 2.6.0, got {torch.__version__}")
    if torch.version.cuda != "12.4":
        raise RuntimeError(f"Expected torch CUDA 12.4, got {torch.version.cuda}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available inside the Modal function")
    if torch.cuda.get_device_capability(0) != (8, 0):
        raise RuntimeError(
            "Expected A100 compute capability 8.0, got "
            f"{torch.cuda.get_device_capability(0)}"
        )

    sources: dict[str, str] = {}

    trellis, sources["TRELLIS.2"] = clone(
        "TRELLIS.2",
        "https://github.com/microsoft/TRELLIS.2.git",
        ref=TRELLIS_REF,
        recursive=True,
    )
    utils3d, sources["utils3d"] = clone(
        "utils3d",
        "https://github.com/EasternJournalist/utils3d.git",
        ref=UTILS3D_REF,
    )
    nvdiffrast, sources["nvdiffrast"] = clone(
        "nvdiffrast",
        "https://github.com/NVlabs/nvdiffrast.git",
        ref=NVDIFFRAST_REF,
    )
    nvdiffrec, sources["nvdiffrec"] = clone(
        "nvdiffrec",
        "https://github.com/JeffreyXiang/nvdiffrec.git",
        ref=NVDIFFREC_REF,
    )
    cumesh, sources["CuMesh"] = clone(
        "CuMesh",
        "https://github.com/JeffreyXiang/CuMesh.git",
        ref=CUMESH_REF,
        recursive=True,
    )
    flexgemm, sources["FlexGEMM"] = clone(
        "FlexGEMM",
        "https://github.com/JeffreyXiang/FlexGEMM.git",
        ref=FLEXGEMM_REF,
        recursive=True,
    )

    # These are normal runtime dependencies. Keep them separate from the
    # custom wheels so pip cannot replace the target image's torch build.
    # Because the custom wheels are installed with --no-deps, this list also
    # includes their non-torch dependencies that the upstream installers would
    # otherwise resolve automatically.
    basic_requirements = """\
imageio
imageio-ffmpeg
tqdm
easydict
opencv-python-headless
ninja
trimesh
# DINOv3ViTModel, imported by TRELLIS.2, was added in Transformers 4.56.
transformers>=4.56.0,<6
gradio==6.0.1
tensorboard
pandas
lpips
zstandard
kornia
timm
torchvision==0.21.0
numpy
plyfile
einops
moderngl
scipy
filelock
triton==3.2.0
"""
    requirements_path = dist / "requirements-openi.txt"
    requirements_path.write_text(basic_requirements, encoding="utf-8")
    constraints_path = dist / "constraints-openi.txt"
    constraints_path.write_text(
        "torch==2.6.0\ntorchvision==0.21.0\ntriton==3.2.0\n",
        encoding="utf-8",
    )

    # Resolve runtime packages before the expensive CUDA builds. This both
    # fails fast on dependency conflicts and makes the build environment match
    # the environment used for validation and OpenI installation.
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_path),
            "-c",
            str(constraints_path),
        ]
    )
    run(
        [
            sys.executable,
            "-c",
            (
                "import torch, torchvision, triton; "
                "assert torch.__version__.split('+', 1)[0] == '2.6.0'; "
                "assert torchvision.__version__.split('+', 1)[0] == '0.21.0'; "
                "assert triton.__version__ == '3.2.0'; "
                "print('constrained torch stack: OK')"
            ),
        ]
    )

    # Build the packages referenced by the official TRELLIS.2 setup.sh.
    # TORCH_CUDA_ARCH_LIST=8.0 makes the CUDA wheels target A100/sm_80.
    build_wheel(utils3d, "utils3d@9a4eb15")
    build_wheel("flash-attn==2.7.3", "flash-attn==2.7.3")
    build_wheel(nvdiffrast, "nvdiffrast@v0.4.0")
    build_wheel(nvdiffrec, "nvdiffrec@renderutils")
    build_wheel(cumesh, "CuMesh")
    build_wheel(flexgemm, "FlexGEMM")
    build_wheel(trellis / "o-voxel", "TRELLIS.2/o-voxel")

    # Official setup.sh installs pillow-simd from source; prebuild it too so
    # OpenI does not need a compiler for that step.
    build_wheel("pillow-simd==9.5.0.post2", "pillow-simd==9.5.0.post2")

    wheel_files = sorted(wheels.glob("*.whl"))
    if not wheel_files:
        raise RuntimeError("No wheels were built")

    # FlexGEMM's setup.py writes its autotune cache into ~/.flex_gemm as a
    # setup-time side effect. Installing from a prebuilt wheel does not rerun
    # setup.py, so ship the cache explicitly and restore it in install_openi.sh.
    flex_cache_src = flexgemm / "autotune_cache.json"
    flex_cache_dst = dist / "flex_gemm_autotune_cache.json"
    shutil.copy2(flex_cache_src, flex_cache_dst)

    # Install every freshly built wheel without dependency resolution, exactly
    # as install_openi.sh will, then validate the resulting environment.
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--force-reinstall",
            *[str(p) for p in wheel_files],
        ]
    )
    run([sys.executable, "-m", "pip", "check"])

    print("\n===== VERIFY RUNTIME DEPENDENCIES =====", flush=True)
    run(
        [
            sys.executable,
            "-c",
            (
                "import cv2, easydict, einops, filelock, gradio, imageio, "
                "imageio_ffmpeg, kornia, lpips, moderngl, ninja, numpy, "
                "pandas, plyfile, scipy, tensorboard, timm, tqdm, "
                "transformers, trimesh, triton, torchvision, zstandard; "
                "from transformers import DINOv3ViTModel; "
                "print('runtime dependency imports: OK')"
            ),
        ]
    )

    extension_checks = [
        ("flash-attn", "import flash_attn, flash_attn_2_cuda"),
        ("nvdiffrast", "import nvdiffrast, _nvdiffrast_c"),
        (
            "nvdiffrec-render",
            "import nvdiffrec_render, nvdiffrec_render.renderutils._C",
        ),
        (
            "CuMesh",
            "import cumesh, cumesh._C, cumesh._cubvh, "
            "cumesh._cumesh_xatlas",
        ),
        ("o-voxel", "import o_voxel, o_voxel._C"),
        ("FlexGEMM", "import flex_gemm, flex_gemm.kernels.cuda"),
        (
            "utils3d",
            "import utils3d, utils3d.io, utils3d.numpy, utils3d.torch",
        ),
        (
            "pillow-simd",
            "from PIL import Image, features; "
            "assert features.check('jpg'); assert features.check('zlib')",
        ),
    ]
    for label, imports in extension_checks:
        print(f"\n===== VERIFY {label} =====", flush=True)
        run([sys.executable, "-c", f"{imports}; print('{label}: OK')"])

    # Import the real TRELLIS.2 entry points from the pinned source tree. This
    # catches integration-level missing dependencies that isolated wheel
    # imports cannot see, while avoiding a model download or inference run.
    print("\n===== VERIFY TRELLIS.2 INTEGRATION =====", flush=True)
    run(
        [
            sys.executable,
            "-c",
            (
                "from trellis2.pipelines import "
                "Trellis2ImageTo3DPipeline, Trellis2TexturingPipeline; "
                "from trellis2.renderers import "
                "MeshRenderer, VoxelRenderer, PbrMeshRenderer; "
                "from trellis2.models import "
                "SparseStructureEncoder, SLatFlowModel, "
                "FlexiDualGridVaeDecoder; "
                "print('TRELLIS.2 integration imports: OK')"
            ),
        ],
        cwd=trellis,
    )

    installer = """#!/bin/sh
set -eu

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

python - <<'PY'
import sys, torch
print("Python:", sys.version)
print("Torch:", torch.__version__)
print("Torch CUDA:", torch.version.cuda)
assert sys.version_info[:2] == (3, 10), "Expected Python 3.10"
assert torch.__version__.split("+", 1)[0] == "2.6.0", "Expected Torch 2.6.0"
assert torch.version.cuda == "12.4", "Expected Torch CUDA 12.4"
PY

# Normal Python dependencies first.
python -m pip install \
  -r "$HERE/requirements-openi.txt" \
  -c "$HERE/constraints-openi.txt"

# All GitHub/CUDA packages are already compiled. --no-deps is deliberate:
# do not let pip replace the OpenI image's torch 2.6.0/cu124.
python -m pip install --no-deps --force-reinstall "$HERE"/wheelhouse/*.whl

# Restore the FlexGEMM setup-time cache that a wheel install would otherwise
# skip.
mkdir -p "$HOME/.flex_gemm"
cp "$HERE/flex_gemm_autotune_cache.json" \
   "$HOME/.flex_gemm/autotune_cache.json"

python - <<'PY'
import torch, torchvision, triton
assert torch.__version__.split("+", 1)[0] == "2.6.0", "Torch changed during install"
assert torch.version.cuda == "12.4", "Torch CUDA changed during install"
assert torchvision.__version__.split("+", 1)[0] == "0.21.0", "torchvision changed during install"
assert triton.__version__ == "3.2.0", "Triton changed during install"

import flash_attn, flash_attn_2_cuda
import nvdiffrast, _nvdiffrast_c
import nvdiffrec_render, nvdiffrec_render.renderutils._C
import cumesh, cumesh._C, cumesh._cubvh, cumesh._cumesh_xatlas
import o_voxel, o_voxel._C
import flex_gemm, flex_gemm.kernels.cuda
import utils3d, utils3d.io, utils3d.numpy, utils3d.torch
import cv2, easydict, einops, filelock, gradio, imageio, imageio_ffmpeg
import kornia, lpips, moderngl, ninja, numpy, pandas, plyfile, scipy
import tensorboard, timm, tqdm, transformers, trimesh, zstandard
from transformers import DINOv3ViTModel
from PIL import features
assert features.check("jpg"), "pillow-simd was built without JPEG support"
assert features.check("zlib"), "pillow-simd was built without zlib support"
print("TRELLIS.2 prebuilt dependencies: OK")
PY
"""
    installer_path = dist / "install_openi.sh"
    installer_path.write_text(installer, encoding="utf-8")
    installer_path.chmod(0o755)

    manifest = {
        "release_tag": RELEASE_TAG,
        "target": {
            "openi_image_reference": (
                "192.168.192.180:1443/default-workspace/"
                "2a72307689ae49758c80c896fffda0a1/"
                "image:ubuntu22.04-cuda12.4.0-py310-torch2.6.0"
            ),
            "os": "Ubuntu 22.04",
            "python": "3.10",
            "cuda_toolkit": "12.4.0",
            "torch": "2.6.0",
            "torch_cuda": "12.4",
            "gpu": "NVIDIA A100 40GB",
            "compute_capability": "8.0",
        },
        "modal_build": {
            "python": sys.version,
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "compute_capability": torch.cuda.get_device_capability(0),
        },
        "sources": sources,
        "wheels": [p.name for p in wheel_files],
        "created_unix": int(time.time()),
    }
    manifest_path = dist / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    archive = dist / "trellis2-openi-cu124-torch260-py310-sm80.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(wheels, arcname="wheelhouse")
        tf.add(dist / "requirements-openi.txt", arcname="requirements-openi.txt")
        tf.add(dist / "constraints-openi.txt", arcname="constraints-openi.txt")
        tf.add(installer_path, arcname="install_openi.sh")
        tf.add(manifest_path, arcname="manifest.json")
        tf.add(
            flex_cache_dst,
            arcname="flex_gemm_autotune_cache.json",
        )

    archive_sha256 = sha256_file(archive)
    sums = dist / "SHA256SUMS"
    sums.write_text(
        f"{archive_sha256}  {archive.name}\n",
        encoding="utf-8",
    )

    print("Archive:", archive)
    print("SHA256:", archive_sha256)
    print("Size:", archive.stat().st_size)

    # Publish binaries as GitHub Release assets instead of committing them into
    # Git history. This also keeps the source repository small.
    token = os.environ["GITHUB_TOKEN"]
    api = f"https://api.github.com/repos/{GITHUB_REPO}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    release_resp = requests.get(
        f"{api}/releases/tags/{RELEASE_TAG}",
        headers=headers,
        timeout=60,
    )
    if release_resp.status_code == 404:
        release_resp = requests.post(
            f"{api}/releases",
            headers=headers,
            json={
                "tag_name": RELEASE_TAG,
                "target_commitish": "main",
                "name": "TRELLIS.2 OpenI A100/cu124/torch2.6 wheelhouse",
                "body": (
                    "Prebuilt TRELLIS.2 dependencies for Ubuntu 22.04, "
                    "Python 3.10, CUDA 12.4, PyTorch 2.6.0 and A100 sm_80. "
                    "Built and compiled-extension-validated on Modal "
                    "A100-40GB."
                ),
                "draft": False,
                "prerelease": False,
            },
            timeout=60,
        )
    release_resp.raise_for_status()
    release = release_resp.json()

    assets_resp = requests.get(
        f"{api}/releases/{release['id']}/assets",
        headers=headers,
        timeout=60,
    )
    assets_resp.raise_for_status()
    existing_assets = {
        asset["name"]: asset
        for asset in assets_resp.json()
    }

    assets = [archive, manifest_path, sums]
    upload_url = release["upload_url"].split("{", 1)[0]

    for asset_path in assets:
        if asset_path.name in existing_assets:
            delete_resp = requests.delete(
                existing_assets[asset_path.name]["url"],
                headers=headers,
                timeout=60,
            )
            delete_resp.raise_for_status()

        print(f"Uploading {asset_path.name} ...", flush=True)
        with asset_path.open("rb") as f:
            upload_resp = requests.post(
                upload_url,
                headers={
                    **headers,
                    "Content-Type": "application/octet-stream",
                },
                params={"name": asset_path.name},
                data=f,
                timeout=60 * 30,
            )
        upload_resp.raise_for_status()

    release_url = release["html_url"]
    print("Published:", release_url)

    return {
        "release_url": release_url,
        "archive": archive.name,
        "sha256": archive_sha256,
        "wheels": [p.name for p in wheel_files],
        "sources": sources,
    }


@app.local_entrypoint()
def main():
    result = build_and_release.remote()
    print(result)
