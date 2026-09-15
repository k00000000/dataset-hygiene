# 使用指南

## 典型工作流

1. 用 `audit` 指向数据集根目录（图像、标签、清单等）。
2. 写出 JSON（机器）/ Markdown（人）/ HTML（浏览器）。
3. 用 `manifest export` 固化可复现快照。
4. 后续变更用 `diff` 或 `manifest verify` 对比。
5. 在流水线中开启 `--fail-on-issues` / `--fail-on-diff`。

```bash
dataset-hygiene audit /data/train \
  --json /tmp/train-audit.json \
  --markdown /tmp/train-audit.md \
  --html /tmp/train-audit.html \
  --exclude "*.tmp" \
  --exclude "**/_cache/**" \
  --fail-on-issues
```

## 子命令

### `audit`

扫描目录，计算 SHA-256，汇总重复、空文件、超小文件、可疑扩展名、同名冲突、体积直方图等。

```bash
dataset-hygiene audit ./dataset \
  --tiny-threshold 128 \
  --perceptual-hash \
  --compressibility \
  --summary-only \
  --json out.json
```

未安装 Pillow 时，`--perceptual-hash` 会被忽略（报告中 `perceptual_hash_enabled=false`），不会报错退出。

### `diff`

对比两个目录，或两份含 `files` 数组的审计/Manifest JSON：

```bash
dataset-hygiene diff ./dataset-v1 ./dataset-v2 --markdown diff.md
dataset-hygiene diff audit-old.json audit-new.json --json delta.json --fail-on-diff
```

输出三类差异：

- **added**：右侧新增路径
- **removed**：右侧缺失路径
- **changed**：同路径但 SHA-256 变化

### `manifest`

```bash
# 导出
dataset-hygiene manifest export ./dataset -o manifest.json

# 校验（内容或文件集合发生变化则失败）
dataset-hygiene manifest verify manifest.json ./dataset --fail-on-diff
```

Manifest 适合挂在数据集版本标签旁，作为可复现审计的基线。

## 配置文件

在数据集根目录或当前工作目录放置 `.dataset-hygiene.toml`：

```toml
include_hidden = false
largest = 15
tiny_threshold = 64
exclude = ["*.tmp", "**/cache/**"]
suspicious_extensions = [".exe", ".bat", ".dll", ".ps1"]
perceptual_hash = false
compute_compressibility = false
fail_on_issues = false
summary_only = false
top_extensions = 20
```

也可用 `--config path/to/file.toml` 显式指定。CLI 显式参数会覆盖配置文件中的同名项。

> Python 3.11+ 使用标准库 `tomllib`；Python 3.10 需要可选依赖 `tomli` 才能读取 TOML。

## 如何解读结果

### Duplicate groups

每组包含两个及以上相对路径，且 SHA-256 相同。精确重复浪费空间，也可能造成 train/val 泄漏。

### Tiny / empty files

空文件常见于中断下载或损坏导出；超小文件阈值（默认 64 字节）可捕获“几乎为空”的标签或损坏样本。

### Suspicious extensions

默认关注可执行/脚本类后缀（如 `.exe` / `.bat` / `.dll`）。可在配置中自定义列表。

### Name collisions

相同 basename、不同内容的多路径。对依赖文件名对齐的标注管线尤其危险。

### Near-duplicate groups

在启用感知哈希且安装 Pillow 时出现。用于发现“看起来几乎一样但字节不同”的图像。

### Size histogram

按体积分桶统计，便于发现异常巨大文件或大量极小文件。

## CI 示例（GitHub Actions）

```yaml
- name: Audit dataset
  run: |
    pip install -e .
    dataset-hygiene audit ./examples/sample-dataset --fail-on-issues
```

## 建议

- 把 checksum / manifest 报告与数据集版本标签一起保存。
- 每次 ETL / 标注导出后重跑。
- 千万级文件树若只关心聚合统计与重复组，优先使用 `--summary-only`。
- 用 `diff` 对比训练前后快照，而不是只依赖人工抽查。
