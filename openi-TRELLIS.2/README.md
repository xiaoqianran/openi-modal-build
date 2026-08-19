# OpenI TRELLIS.2 预编译 Wheel 构建

目标环境：

- OpenI 镜像：`ubuntu22.04-cuda12.4.0-py310-torch2.6.0`
- Ubuntu 22.04
- Python 3.10
- CUDA Toolkit 12.4.0
- PyTorch 2.6.0 + cu124
- NVIDIA A100 40GB / sm_80

`modal_build.py` 会在 Modal 的 `A100-40GB` 上构建并验证 TRELLIS.2 需要的预编译 wheel，然后自动发布到本仓库的 GitHub Release。

## 为什么不用 OpenI 的原始镜像

OpenI 镜像地址：

```text
192.168.192.180:1443/default-workspace/2a72307689ae49758c80c896fffda0a1/image:ubuntu22.04-cuda12.4.0-py310-torch2.6.0
```

这是私有网段地址，Modal 无法假定能够直接访问，因此构建脚本使用公开的：

```text
nvidia/cuda:12.4.0-devel-ubuntu22.04
```

再安装 Python 3.10、PyTorch 2.6.0/cu124，并固定 `TORCH_CUDA_ARCH_LIST=8.0`，尽量匹配 OpenI 的 ABI、CUDA 和 GPU 架构。

## 构建内容

按照 TRELLIS.2 官方 `setup.sh` 构建：

- `utils3d`：固定官方 setup 使用的 commit
- `flash-attn==2.7.3`
- `nvdiffrast==v0.4.0`
- `nvdiffrec` 的 `renderutils` 分支
- `CuMesh`
- `FlexGEMM`
- `TRELLIS.2/o-voxel`
- `pillow-simd`

CUDA 扩展均以 A100 `sm_80` 为目标构建。构建结束后，会在同一个 Modal A100 环境中重新安装这些 wheel，并加载编译扩展进行验证。

FlexGEMM 的 `setup.py` 还会写入 `~/.flex_gemm/autotune_cache.json`。因为直接安装 wheel 不会再次执行这个 setup-time 行为，构建包会额外保存该 cache，并由 OpenI 安装脚本恢复。

## 1. 准备 uv 和 Modal

在仓库目录中创建 Python 3.12 虚拟环境，并安装带 API Proxy 支持的 Modal：

```bash
cd openi-TRELLIS.2
uv venv --python 3.12
uv add 'modal[api-proxy-support]'
uv run modal token set
```

## 2. 创建 Modal GitHub Secret

为 `xiaoqianran/openi-modal-build` 创建一个可写 Release 的 GitHub fine-grained token，然后：

```bash
uv run modal secret create github-openi-build GITHUB_TOKEN=你的_token
```

不要把 token 写进仓库或脚本。

## 3. 开始构建

在仓库根目录执行：

```bash
cd openi-TRELLIS.2
uv run modal run modal_build.py
```

Modal 会申请：

```text
A100-40GB
Ubuntu 22.04
CUDA 12.4.0 devel
Python 3.10
PyTorch 2.6.0 + cu124
sm_80
```

首次构建会比较慢，因为 `flash-attn / nvdiffrast / nvdiffrec / CuMesh / FlexGEMM / o-voxel` 都需要编译。

## 4. GitHub Release 输出

构建成功后会创建或更新 Release：

```text
trellis2-cu124-torch2.6.0-py310-sm80
```

Release 中包含：

```text
trellis2-openi-cu124-torch260-py310-sm80.tar.gz
manifest.json
SHA256SUMS
```

压缩包内部：

```text
wheelhouse/
requirements-openi.txt
install_openi.sh
manifest.json
flex_gemm_autotune_cache.json
```

二进制放 GitHub Release，而不是直接提交到 Git 历史，避免大型 wheel 污染仓库。

## 5. OpenI 安装

把 Release 中的 `trellis2-openi-cu124-torch260-py310-sm80.tar.gz` 上传到 OpenI，例如放在 `/tmp`：

```sh
mkdir -p /tmp/trellis2-prebuilt
```

```sh
tar -xzf /tmp/trellis2-openi-cu124-torch260-py310-sm80.tar.gz -C /tmp/trellis2-prebuilt
```

```sh
sh /tmp/trellis2-prebuilt/install_openi.sh
```

这个阶段不会重新编译 TRELLIS.2 的 CUDA 扩展，核心 wheel 直接安装。

安装脚本会先检查：

```text
Python == 3.10
Torch == 2.6.0
Torch CUDA == 12.4
```

然后安装普通 Python runtime 依赖，再以 `--no-deps` 安装已经构建好的 CUDA wheel，避免 pip 替换 OpenI 镜像自带的 PyTorch。

## 6. 成功标志

最后应输出：

```text
TRELLIS.2 prebuilt dependencies: OK
```

之后即可在 OpenI 的 TRELLIS.2 仓库目录中直接加载：

```text
/tmp/pretrainmodel/TRELLIS.2-4B
```

进行推理。
