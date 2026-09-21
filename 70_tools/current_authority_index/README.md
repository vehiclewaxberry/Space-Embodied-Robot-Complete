# Current authority index builder

该工具为 `01_project/current/` 生成只导航的当前来源索引。输出不复制工程资产，
不改写任何 Gate，不升级科学结论，也不执行删除、移动或归档。

`DELETE_CANDIDATES_V1.csv` 只有在同哈希、无活动引用、权威副本、冷备恢复和
非受保护证据五项都被证明后才允许出现数据行；空表表示当前没有合格删除项。

复现：

```powershell
python -B 70_tools/current_authority_index/build_current_authority_index.py --repo-root .
python -B -m pytest -p no:cacheprovider 70_tools/current_authority_index/tests
```
