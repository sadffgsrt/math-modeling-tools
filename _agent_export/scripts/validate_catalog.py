"""
model_catalog.json 结构校验脚本（M6 修复）

校验内容：
1. 必需字段：id / name / applicable_scenarios / pros / cons / complexity
2. 类别级字段：name / description
3. implemented 字段存在
4. 无重复 ID
5. 模型数与 metadata 中声称一致（如存在）

用法：
    python scripts/validate_catalog.py            # 校验
    python scripts/validate_catalog.py --fix      # 校验并尝试修复缺失字段

退出码：
    0 = 通过
    1 = 发现错误
"""
import json
import sys
from pathlib import Path

CATALOG_PATH = Path(__file__).parent.parent / "config" / "model_catalog.json"

REQUIRED_MODEL_FIELDS = {"id", "name", "applicable_scenarios", "pros", "cons", "complexity"}
REQUIRED_CATEGORY_FIELDS = {"name", "description"}
VALID_COMPLEXITY = {"low", "medium", "high"}


def validate(fix: bool = False) -> int:
    if not CATALOG_PATH.exists():
        print(f"[ERROR] catalog 文件不存在: {CATALOG_PATH}")
        return 1

    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败: {e}")
        return 1

    errors = []
    warnings = []
    fixed = []

    # 顶层 metadata 校验
    meta = data.get("metadata", {})
    if "version" not in meta:
        errors.append("metadata 缺少 version 字段")
    if "description" not in meta:
        errors.append("metadata 缺少 description 字段")

    models_section = data.get("models", {})
    if not models_section:
        errors.append("models 段为空")
        return 1

    # 类别级 + 模型级校验
    all_ids = []
    for cat_name, cat_info in models_section.items():
        # 类别必需字段
        for field in REQUIRED_CATEGORY_FIELDS:
            if field not in cat_info:
                errors.append(f"类别 {cat_name} 缺少字段: {field}")
        # 模型列表
        if "models" not in cat_info:
            errors.append(f"类别 {cat_name} 缺少 models 列表")
            continue

        for i, model in enumerate(cat_info["models"]):
            mid = model.get("id", "?")
            # 必需字段
            missing = REQUIRED_MODEL_FIELDS - set(model.keys())
            if missing:
                errors.append(f"{cat_name}[{i}] {mid} 缺少必需字段: {missing}")
            # implemented 字段
            if "implemented" not in model:
                if fix:
                    model["implemented"] = False
                    model["implementation_note"] = "尚未在 model_factory.py 中实现"
                    fixed.append(f"{cat_name}/{mid}: 添加 implemented=false")
                else:
                    errors.append(f"{cat_name}[{i}] {mid} 缺少 implemented 字段")
            # complexity 取值
            comp = model.get("complexity")
            if comp and comp not in VALID_COMPLEXITY:
                warnings.append(f"{cat_name}/{mid} complexity={comp} 不在 {VALID_COMPLEXITY}")
            # ID 唯一性
            all_ids.append(mid)

    # 重复 ID
    duplicates = set([x for x in all_ids if all_ids.count(x) > 1])
    if duplicates:
        errors.append(f"发现重复 ID: {duplicates}")

    # 模型数与 metadata 声称数对比（可选）
    claimed_count = meta.get("model_count")
    actual_count = len(all_ids)
    if claimed_count is not None and claimed_count != actual_count:
        errors.append(
            f"模型数不一致: metadata.model_count={claimed_count}, 实际={actual_count}"
        )

    # 输出
    print("=" * 60)
    print(f"catalog 校验: {CATALOG_PATH.name}")
    print(f"类别数: {len(models_section)}")
    print(f"模型总数: {actual_count}")
    print(f"已实现: {sum(1 for cat in models_section.values() for m in cat.get('models', []) if m.get('implemented'))}")
    print("=" * 60)

    if warnings:
        print(f"\n[警告] {len(warnings)} 项:")
        for w in warnings:
            print(f"  - {w}")

    if fixed:
        print(f"\n[修复] {len(fixed)} 项:")
        for f in fixed:
            print(f"  + {f}")
        CATALOG_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    if errors:
        print(f"\n[错误] {len(errors)} 项:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    print("\n[OK] 校验通过")
    return 0


if __name__ == "__main__":
    fix = "--fix" in sys.argv
    sys.exit(validate(fix=fix))
