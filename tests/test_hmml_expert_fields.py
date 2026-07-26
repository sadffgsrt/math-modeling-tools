# 测试：HMML 方法库专家字段（core_idea/application）补全与选择器透出
import json
from pathlib import Path

from modules.model_selection import HierarchicalMethodSelector

HMML = Path(__file__).resolve().parent.parent / "config" / "hmml_method_library.json"


class TestHMMLExpertFields:
    def test_all_methods_have_expert_fields(self):
        d = json.loads(HMML.read_text(encoding="utf-8"))
        nodes = [m for dom in d["domains"] for sd in dom["subdomains"] for m in sd["methods"]]
        assert len(nodes) >= 40
        for m in nodes:
            assert m.get("core_idea"), f"{m.get('method')} 缺 core_idea"
            assert m.get("application"), f"{m.get('method')} 缺 application"

    def test_selector_surfaces_core_idea(self):
        sel = HierarchicalMethodSelector()
        res = sel.retrieve("建立区域科技成果转化能力综合评价模型", data_features={"is_evaluation": True}, top_k=3)
        assert res.ranked_methods
        rm = res.ranked_methods[0]
        assert rm.core_idea, "RankedMethod 应透出 core_idea"
        assert rm.application, "RankedMethod 应透出 application"
        # 理由中应包含专家提示
        assert "专家提示" in rm.reason

    def test_method_tree_includes_expert_fields(self):
        sel = HierarchicalMethodSelector()
        tree = sel.get_method_tree()
        leaf = tree[0]["children"][0]["children"][0]
        assert "core_idea" in leaf and "application" in leaf
