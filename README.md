# Dataset Hygiene

离线优先的 **机器学习数据集审计工具**。扫描目录、计算校验和、发现精确重复与空文件，并输出适合 CI 的 JSON / Markdown / HTML 报告。

无需云端、无需数据库；**运行时零硬依赖**（Pillow 仅为可选图像近重复检测）。

## 为什么需要它

训练与评估失败常常来自隐蔽的数据问题：

- 不同文件名但内容完全相同的拷贝
- 空标签 / 占位文件
- 合并后意外混入的扩展名与可疑文件
- 同名不同内容（basename 冲突）导致的标注错位
- 审计结果无法跨环境复现

`dataset-hygiene` 把一个目录变成可审计清单，可在本地或 CI 中于每次训练前运行。

## 功能一览

- 递归清单与扩展名直方图、体积分桶直方图
- 流式 SHA-256（大文件友好）
- 精确重复分组
- 可疑模式：空文件、超小文件阈值、可疑扩展名、损坏符号链接、同名不同内容
- Manifest JSON 导出 / 校验（可复现审计）
- 对比两次审计报告或两个目录（added / removed / changed）
- 可选图像感知哈希近重复检测（需安装 Pillow；未安装则优雅跳过）
- 可选粗略可压缩性采样（zlib）
- TOML 配置：`.dataset-hygiene.toml`
- `--exclude` glob 排除
- JSON / Markdown / HTML 报告
- 子命令：`audit` / `diff` / `manifest`
- `--fail-on-issues` / `--fail-on-diff` 便于流水线闸门

## 环境要求

- Python 3.10+
- 可选：`Pillow`（图像近重复）、`tomli`（仅在 Python 3.10 且需要 TOML 配置时）

## 安装

```bash
pip install -e ".[dev]"

# 如需图像近重复检测
pip install -e ".[images]"
```

## 快速开始

```bash
# 向 stdout 打印 Markdown 报告
dataset-hygiene audit ./my-dataset

# 同时写出机器可读与人类可读报告
dataset-hygiene audit ./my-dataset \
  --json reports/audit.json \
  --markdown reports/audit.md \
  --html reports/audit.html \
  --fail-on-issues

# 导出可复现清单
dataset-hygiene manifest export ./my-dataset -o reports/manifest.json

# 对比两次审计 / 两个目录
dataset-hygiene diff reports/audit-a.json reports/audit-b.json --fail-on-diff
```

退出码：

| Code | Meaning |
| --- | --- |
| `0` | 成功 |
| `2` | 发现问题且启用了 `--fail-on-issues` / `--fail-on-diff` |
| `1` | 参数错误 / 路径错误 / 配置错误 |

## 库用法

```python
from dataset_hygiene import audit_path, diff_sources, export_manifest

report = audit_path("./my-dataset", exclude_patterns=["*.tmp"], tiny_threshold=64)
print(report.summary())
print(report.duplicate_groups)

manifest = export_manifest("./my-dataset")
diff = diff_sources("./dataset-v1", "./dataset-v2")
```

## CLI 概览

| Command | Description |
| --- | --- |
| `audit ROOT` | 扫描数据集并生成报告 |
| `diff LEFT RIGHT` | 对比两个目录或两份 JSON（审计/清单） |
| `manifest export ROOT -o PATH` | 导出 Manifest |
| `manifest verify MANIFEST ROOT` | 用 Manifest 校验目录 |
| `--version` | 打印版本 |

常用 `audit` 选项：`--json` / `--markdown` / `--html` / `--exclude` / `--include-hidden` / `--tiny-threshold` / `--perceptual-hash` / `--compressibility` / `--config` / `--fail-on-issues`。

完整说明见 [使用指南](docs/usage.md)。

## 项目结构

```text
src/dataset_hygiene/   # 库与 CLI
tests/                 # pytest
docs/                  # 文档（中文）
examples/              # 示例数据集与配置
```

## 运行测试

```bash
pytest -q
```

## 文档

- [使用指南](docs/usage.md)
- [架构说明](docs/architecture.md)

## License

MIT
