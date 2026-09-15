# 架构说明

```text
CLI (cli.py)
  ├── audit
  │     -> config.load_config()
  │     -> scan.audit_path()
  │          -> iter_paths() + exclude globs
  │          -> hashutil.sha256_file()
  │          -> suspicion.* / stats.* / phash.*（可选）
  │          -> AuditReport
  │     -> report.write_reports()  # JSON / Markdown / HTML
  ├── diff
  │     -> diff.diff_sources()     # 目录或 JSON
  │     -> DiffReport
  └── manifest
        -> manifest.export_manifest() / verify_manifest()
```

## 模块划分

| Module | Responsibility |
| --- | --- |
| `models.py` | `FileRecord` / `AuditReport` / `DiffReport` / `Manifest` |
| `config.py` | TOML 配置发现与加载 |
| `hashutil.py` | 流式 SHA-256、目录跳过规则 |
| `scan.py` | 目录遍历、审计编排 |
| `suspicion.py` | 超小文件、可疑扩展名、同名冲突 |
| `stats.py` | 体积直方图、扩展名 Top-N、粗略可压缩性 |
| `phash.py` | 可选感知哈希（Pillow） |
| `manifest.py` | Manifest 导出与校验 |
| `diff.py` | 报告/目录差分 |
| `report.py` | Markdown / HTML / JSON 写出 |
| `cli.py` | 子命令入口 |

## 设计取舍

1. **运行时零硬依赖**  
   需能在隔离训练机上稳定安装。Pillow 仅作为 `[images]` extra；无 Pillow 时近重复检测自动关闭。

2. **流式哈希**  
   默认 1 MiB 分块，避免大媒体文件撑爆内存。

3. **报告使用相对路径**  
   便于跨机器、跨挂载点对比与归档。

4. **确定性输出**  
   文件遍历与分组排序固定，同一棵目录树应生成稳定报告。

5. **配置可选且可覆盖**  
   默认开箱即用；`.dataset-hygiene.toml` 方便团队统一闸门阈值，CLI 参数优先生效。

## 扩展点

- 在 `phash.py` 中替换平均哈希为更强算法，而不改动 SHA-256 主路径。
- 在 `diff.py` 上叠加 split 感知检查（train/val 泄漏），消费 Manifest JSON。
- 在 `suspicion.py` 增加更多启发式规则（例如魔数与扩展名不一致）。
