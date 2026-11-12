# 在自己的电脑构建 H700 Android 镜像

本入口用于从 H616 Android 10 基础源码编译 ROC OS 的 **ARM64 user Android 用户空间**，随后生成包含启动区、system、vendor 和空 userdata 的完整 `.img.gz`。H700 bootloader、kernel、DTB 和 ramdisk 基础运行环境沿用 0.0.1，不声称从源码重编所有启动组件。

当前入口不依赖作者的 `/home/lpf` 路径、历史 `out` 收据或生产签名备份。构建者使用自己的五组密钥，生成的镜像不会与官方签名镜像具有相同 SHA256，也不能直接覆盖安装官方平台签名的应用。

公共输入闭合检查和工具验证记录见 [PUBLIC_BUILD_STATUS.md](PUBLIC_BUILD_STATUS.md)。独立环境完整编译、烧录和实机验收是不同阶段；有构建脚本不等于已完成这些验收。全 H700 面板兼容仍未完成。

## 1. 下载外部大文件

| 输入 | 获取方式 | 用途 |
| --- | --- | --- |
| `android.tar.gz` | [H700_Android_Example](https://pan.baidu.com/s/1carfBOv4uB0bM9LoRLqmrw?pwd=H616)，提取码 `H616` | 完整 Android 基础树、厂商 HAL 与工具链 |
| `ROC_OS_ARM64_ver0.0.1.img.gz` | [H700_Android](https://pan.baidu.com/s/12mIL9R38oy65ldhGujHWuw?pwd=H700)，提取码 `H700` | 提取确定版本的 H700 启动资产和必要二进制输入 |
| `longan.tar.gz` | 上述 H616 分享 | 内核/BSP 参考；本用户空间构建入口不编内核，无须先构建 Longan |

源码包位置：`H700_Android_Example/Orange Pi Zero 2（H616）/H616_Android_Source_Code/`。大小、哈希和镜像分区范围固定在 [external-inputs.json](../build-support/public/external-inputs.json)，既有来源见 [H616 来源记录](H616_ANDROID10_PROVENANCE_20260902.md)。不要使用名称相似的其他版本代替。

0.0.1 gzip 为 **591,043,813 字节**，SHA256：

```text
e72580e8c4e4afc8b08b50570ad6beebf46a435ee6e8b32b7a943f21786a6346
```

镜像和大型上游源码留在网盘，Git 只保存必要修改、复制配方、工具和校验清单。

## 2. 准备 Linux 环境

使用 x86_64 Linux；作者保留环境为 Ubuntu 24.04 / WSL2。WSL 应启用 systemd，源码和输出放在 Linux ext4 文件系统，避免 NTFS 大小写、权限和符号链接差异。以下命令在 Linux bash 中执行，示例路径均可替换，工具处理的路径不要包含空格。

基础软件：

```sh
sudo apt update
sudo apt install build-essential gcc-multilib g++-multilib bc bison flex gperf libtool \
  git curl rsync zip unzip xz-utils lzop m4 patch \
  libssl-dev libxml2-utils zlib1g-dev lib32z1-dev libncurses-dev \
  python3 openssl e2fsprogs util-linux sudo systemd qemu-user
```

Python 需 3.11+。Android JDK、交叉编译器和旧 Python 工具优先使用基础源码包自带版本；不要求把 Android 10 改成当前系统 JDK。RenderScript 旧主机 Clang 需要真正的 `libncurses.so.5` / `libtinfo.so.5`，脚本会从已校验的 GCC sysroot 复制到独立兼容目录，不将 ABI6 软链冒充 ABI5。

源码树已有记录约 48.4GB 普通文件载荷，此外还需保存下载包、编译输出和整卡打包文件。每个整卡 raw 逻辑长度约 32.43GB；应使用支持稀疏文件的文件系统，不能用旧脚本的空闲空间阈值推断完整构建只需要 40GB。

## 3. 克隆与解压

```sh
git clone https://github.com/LPF970915/H700Android.git
cd H700Android
REPO=$(pwd)
WORK="$HOME/roc-community-work"
mkdir -p "$WORK"

# 替换为实际下载位置。先核对 external-inputs.json 中的大小和哈希。
ANDROID_ARCHIVE=/path/to/android.tar.gz
REFERENCE_IMAGE=/path/to/ROC_OS_ARM64_ver0.0.1.img.gz
sudo -v
bash "$REPO/tools/public_build/run-limited.sh" \
  python3 "$REPO/tools/public_build/verify_downloads.py" \
  --android "$ANDROID_ARCHIVE" --image "$REFERENCE_IMAGE"
tar --no-same-owner -xzf "$ANDROID_ARCHIVE" -C "$WORK"

SOURCE="$WORK/android"
INPUTS="$WORK/image-inputs"
BUILD_OUT="$WORK/android-out"
KEYS="$HOME/.roc-community-keys/v1"
```

不要把这一流程应用到仍在使用的作者工作树，也不要按日期重放历史 `prepare_*` 脚本。`tools/public_build/` 是本指南的独立入口。

## 4. 提取必要输入，生成自己的签名

```sh
# 有 sudo 的普通构建用户先在交互终端刷新授权，包装器不会等待输入密码。
sudo -v
bash "$REPO/tools/public_build/run-limited.sh" \
  python3 "$REPO/tools/public_build/extract.py" \
  --image "$REFERENCE_IMAGE" --output "$INPUTS"

# 仅首次生成。已有身份应继续使用，不要每次编译重新生成。
python3 "$REPO/tools/public_build/keys.py" --output "$KEYS"
```

提取器校验完整 gzip/raw 身份及分区哈希，从普通镜像文件提取必要驱动、固件、壁纸和 AT4K。它不访问物理磁盘，不提取 userdata。原镜像中的工作站 ADB 授权不会带到新镜像。

五组签名为 `releasekey / platform / shared / media / networkstack`，每组有 `.pk8` 和 `.x509.pem`。私钥保留在仓库和源码树外，妥善备份。此流程不需要、也不分发项目官方私钥。

## 5. 应用最终修改层

```sh
# 默认只校验和列出计划。
python3 "$REPO/tools/public_build/prepare.py" \
  --source "$SOURCE" --inputs "$INPUTS" --keys "$KEYS"

python3 "$REPO/tools/public_build/prepare.py" \
  --source "$SOURCE" --inputs "$INPUTS" --keys "$KEYS" --apply
```

[source-manifest.json](../build-support/public/source-manifest.json) 固定输出路径、权限与 SHA256。每个文件来自 Git 覆盖层、基础源码树中的已有文件，或已校验镜像输入。未修改的 Services/Vold/Resize 等源码由复制清单复用，不重复上传完整树。

替换的原文件保存在新源码树 `.roc-public/before/`；签名只创建指向外部目录的链接。准备成功后保留该树和输出用于增量构建，不再次运行首次准备步骤。

## 6. 编译 Android 分区

```sh
sudo -v
bash "$REPO/tools/public_build/run-limited.sh" \
  bash "$REPO/tools/public_build/build.sh" "$SOURCE" "$BUILD_OUT"
```

入口执行 `lunch roc_os_release_candidate-user` 与 `m -j1 systemimage vendorimage ramdisk`。资源限制为一个 CPU 的合计配额、CPU0–1 亲和性、6GiB RAM、512MiB swap、nice19、idle I/O 和单批三小时上限，并与项目已有构建共用互斥锁。宿主至少需要两个可用逻辑 CPU 以符合该亲和性设置。

成功产物在：

```text
$BUILD_OUT/target/product/roc_os_source64/system.img
$BUILD_OUT/target/product/roc_os_source64/vendor.img
$BUILD_OUT/target/product/roc_os_source64/ramdisk.img
```

超时后先查看实际退出与日志；确认没有构建进程仍在运行，再在相同树、输出和签名身份上续编。失败不可视为成功，也不要清除唯一源码或切换签名来掩盖错误。

## 7. 生成可烧录整卡镜像

```sh
sudo -v
bash "$REPO/tools/public_build/run-limited.sh" \
  python3 "$REPO/tools/public_build/pack.py" \
  --inputs "$INPUTS" \
  --product "$BUILD_OUT/target/product/roc_os_source64" \
  --output "$WORK/community-card-v1"
```

打包器展开新编译的 system/vendor，检查文件系统与 user/认证 ADB 属性，从新 system 更新三项静态扩容工具，保留已知 H700 kernel/DTB，重新创建空 userdata，再组装 GPT 整卡文件。分区写入读回和完整 gzip 解压哈希通过后才写入 `result.json`。

输出为 `ROC_OS_ARM64_community.img.gz`，**不是官方签名 0.0.1 的逐字节复刻**。它不会导入已有个人数据或预授权 ADB 主机；首次 ADB 连接需在设备界面授权。打包器只写新目录中的普通文件，不自动烧录。

自编成功不证明其他 H700 型号的显示、电源或 USB 已兼容。实际烧录应按适用机型使用独立测试 TF1 并核对目标卡；现有 Wi-Fi、合盖唤醒、USB 恢复、焦点问题和面板边界不会因重新签名自动解决。
