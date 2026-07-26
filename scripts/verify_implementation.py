# -*- coding: utf-8 -*-
"""
深度核查脚本 v2：验证 catalog 中 implemented=true 的每个模型在代码中确实有真实分支
- 检查 1: model_id (或其别名) 必须出现在 MODEL_CATEGORY_MAP
- 检查 2: 在 dispatcher.py 或 model_factory.py 中必须存在对应的字符串字面量分支引用
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CATALOG = ROOT / "config" / "model_catalog.json"
# 指向活代码（具名 model_solving 包；编号目录 01~12 为死代码副本，已删除）
FACTORY = ROOT / "modules" / "model_solving" / "factories" / "_base.py"
DISPATCHER = ROOT / "modules" / "model_solving" / "dispatcher.py"


def load_catalog_models():
    """返回 [(model_id, category), ...]"""
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    out = []
    for cat, cat_data in data["models"].items():
        for m in cat_data["models"]:
            if m.get("implemented"):
                out.append((m["id"], cat))
    return out


def load_factory_map_and_aliases():
    """从 model_factory.py 解析 MODEL_CATEGORY_MAP 和 CATALOG_ALIASES"""
    src = FACTORY.read_text(encoding="utf-8")

    cat_map = {}
    map_match = re.search(
        r"MODEL_CATEGORY_MAP\s*=\s*\{(.*?)\n    \}",
        src, re.DOTALL,
    )
    if map_match:
        body = map_match.group(1)
        # 使用 findall 捕获所有 "key": "value" 对
        for k, v in re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', body):
            cat_map[k] = v

    aliases = {}
    alias_match = re.search(
        r"CATALOG_ALIASES\s*=\s*\{(.*?)\n    \}",
        src, re.DOTALL,
    )
    if alias_match:
        body = alias_match.group(1)
        for k, v in re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', body):
            aliases[k] = v

    return cat_map, aliases


def find_code_references():
    """返回 dispatcher + factory 中所有字符串字面量 'xxx' / "xxx" 的集合
    （排除纯注释行）"""
    refs = set()
    for fpath in (DISPATCHER, FACTORY):
        for line in fpath.read_text(encoding="utf-8").splitlines():
            # 去掉行尾注释（粗略处理：# 之后视为注释，但不处理字符串内的 #）
            code = re.sub(r'#.*$', '', line)
            # 提取所有双引号字符串
            for m in re.findall(r'"([^"]+)"', code):
                refs.add(m)
            # 提取所有单引号字符串
            for m in re.findall(r"'([^']+)'", code):
                refs.add(m)
    return refs


def main():
    catalog_models = load_catalog_models()
    cat_map, aliases = load_factory_map_and_aliases()
    code_refs = find_code_references()

    print(f"Catalog implemented: {len(catalog_models)}")
    print(f"MODEL_CATEGORY_MAP entries: {len(cat_map)}")
    print(f"CATALOG_ALIASES entries: {len(aliases)}")
    print(f"Code string literals: {len(code_refs)}")
    print("=" * 70)

    failures = []
    for mid, cat in catalog_models:
        # 步骤1: 必须在 MAP 中（直接或别名）
        resolved = mid
        if mid in cat_map:
            resolved = mid
        elif mid in aliases:
            resolved = aliases[mid]
            if resolved not in cat_map:
                failures.append(f"[{mid}] 别名 {resolved} 不在 MODEL_CATEGORY_MAP")
                continue
        else:
            failures.append(f"[{mid}] 既不在 MODEL_CATEGORY_MAP 也无 CATALOG_ALIASES")
            continue

        # 步骤2: model_id 或别名必须在代码字符串字面量中出现
        if mid in code_refs or resolved in code_refs:
            continue
        failures.append(
            f"[{mid}] (cat={cat}, resolved={resolved}) "
            f"在代码中无字符串字面量引用"
        )

    if failures:
        print(f"❌ 发现 {len(failures)} 个问题:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print(f"✅ 所有 {len(catalog_models)} 个 implemented=true 模型都有真实代码引用")
        sys.exit(0)


if __name__ == "__main__":
    main()
