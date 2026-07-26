# HMML 方法库专家字段补全工具（维护性脚本，可复跑）
#
# 对齐 MM-Agent 的 HMML 三字段结构：
#   <modeling_method>  → 方法的数学本质（本库已由 description 承载）
#   <core_idea>        → 方法背后的元认知：专家「何时该选它」的判断依据
#   <application>      → 实际领域映射：问题 → 方法的记忆结构
#
# 用法：
#   python tools/enrich_hmml_fields.py
# 仅向缺失字段写入，不破坏既有内容；纯自研、MIT，不复制任何 CC BY-NC 文本。

import json
from pathlib import Path

HMML_PATH = Path(__file__).resolve().parent.parent / "config" / "hmml_method_library.json"

# model_id -> {core_idea, application}
ENRICH = {
    # ── 评价与决策 ──
    "ahp": {
        "core_idea": "当决策含多个定性准则且需把主观经验量化成权重时，用成对比较矩阵把「重要性」转成可计算的相对权重。",
        "application": "供应商优选、方案排序、风险等级评估、设施选址打分。",
    },
    "topsis": {
        "core_idea": "有多方案与多维指标、需要「离最优最近、离最差最远」的直观排序时，贴近度比逐对比较更易解释。",
        "application": "产品综合排名、投资方案优选、城市宜居度评价。",
    },
    "entropy_weight": {
        "core_idea": "希望赋权尽量客观、避免人为主观偏差时，用指标变异信息量定权——数据越离散权重越大。",
        "application": "与 AHP/TOPSIS 组合的客观赋权、绩效指标加权。",
    },
    "grey_relational": {
        "core_idea": "样本极少、信息不完全（灰）时，用序列几何相似度代替分布假设做关联评价，不要求大样本。",
        "application": "小样本因素关联评价、农业/环境因子分析。",
    },
    "comprehensive_evaluation": {
        "core_idea": "指标高度共线、需降维提炼主成分再综合时，避免多重共线性放大估计误差。",
        "application": "区域综合实力评价、教学质量/绩效评估。",
    },
    "fuzzy_evaluation": {
        "core_idea": "准则含「较好/一般」等边界不清的模糊语义时，用隶属度把定性判断转定量更贴合人类认知。",
        "application": "服务质量评价、生态环境模糊评级。",
    },
    # ── 回归预测 ──
    "linear_regression": {
        "core_idea": "变量间近似线性且需强解释性（系数即贡献）时首选，便于显著性与残差诊断。",
        "application": "影响因素量化、成本/销量拟合、敏感性分析基线。",
    },
    "ridge": {
        "core_idea": "自变量高度共线、普通回归系数震荡时，L2 收缩稳定估计、降低方差。",
        "application": "高维共线数据回归、房价预测。",
    },
    "lasso": {
        "core_idea": "希望模型同时做变量选择与稀疏化（剔除无关特征）时，L1 惩罚产生零系数。",
        "application": "特征筛选回归、指标/基因降维。",
    },
    "logistic_regression": {
        "core_idea": "结局是二分类/概率且要可解释的概率边界时，用对数几率建模。",
        "application": "信用违约预测、疾病风险概率、客户流失预警。",
    },
    # ── 时间序列预测 ──
    "arima": {
        "core_idea": "单变量时序、平稳（或差分后平稳）、关心自相关结构时经典稳健、理论基础扎实。",
        "application": "GDP/销量/客流单变量预测。",
    },
    "exponential_smoothing": {
        "core_idea": "无明显趋势季节、只需对近期观测加权做短期平滑预测时，轻量快速。",
        "application": "库存短期需求、平稳指标预警。",
    },
    "grey_prediction": {
        "core_idea": "数据极少（<15 条）且呈指数规律时，生成函数可挖掘少样本趋势。",
        "application": "小样本销量/能耗预测。",
    },
    "prophet": {
        "core_idea": "业务时序含强季节+节假日+趋势突变时，加法分解比 ARIMA 更易融入业务先验。",
        "application": "电商销量、用电负荷、带节假日的流量预测。",
    },
    "lstm": {
        "core_idea": "时序长程依赖强、非线性复杂且数据量充足时，循环网络能捕捉长期时间模式。",
        "application": "长周期时间序列预测、序列异常预警。",
    },
    # ── 优化 ──
    "linear_programming": {
        "core_idea": "目标与约束皆线性、求资源最优配置时，单纯形法高效且解可解释。",
        "application": "生产计划、运输调度、投资组合有效边界。",
    },
    "integer_programming": {
        "core_idea": "决策本质离散（是否建厂/排班）时必须整数/0-1，否则解无物理意义。",
        "application": "设施选址、机组组合、人员排班。",
    },
    "nonlinear_programming": {
        "core_idea": "目标或约束含非线性（平方成本、曲率）时，需梯度/序列二次规划求解。",
        "application": "工程设计优化、非线性成本最小化。",
    },
    "genetic_algorithm": {
        "core_idea": "解空间多峰、不要求可微、可接受近似全局最优时，进化搜索跳出局部。",
        "application": "复杂调度、参数寻优、组合设计。",
    },
    "pso": {
        "core_idea": "连续优化、参数少、需快速收敛且实现简单时，群体协作寻优。",
        "application": "神经网络训练初值、连续参数调优。",
    },
    "abc": {
        "core_idea": "连续优化需平衡探索与开发、对初值不敏感时，蜂群分工觅食寻优。",
        "application": "函数优化、特征选择。",
    },
    "ant_colony": {
        "core_idea": "问题可表达为「路径构建+信息素正反馈」（组合/图）时尤为适合。",
        "application": "TSP 路径、车间调度、网络路由。",
    },
    "simulated_annealing": {
        "core_idea": "易陷局部最优的离散/连续问题，用概率接受劣解在降温中逃离。",
        "application": "布局优化、VLSI 布线、组合调度。",
    },
    "differential_evolution": {
        "core_idea": "连续黑箱优化、无需梯度且要鲁棒时，差分变异向量进化搜索。",
        "application": "黑箱函数寻优、鲁棒参数校准。",
    },
    # ── 分类与聚类 ──
    "svm": {
        "core_idea": "高维小样本、类别边界靠最大间隔时，核技巧可处理非线性。",
        "application": "文本/影像分类、设备故障诊断。",
    },
    "decision_tree": {
        "core_idea": "需要完全可解释的「如果-则」规则且数据含类别/缺失时。",
        "application": "风控规则、客户分群规则。",
    },
    "random_forest": {
        "core_idea": "单树易过拟合、需稳定提升泛化且仍保留可解释（特征重要度）时。",
        "application": "信用评分、销量预测集成。",
    },
    "knn": {
        "core_idea": "数据分布未知、类别边界不规则、想用「近邻投票」做简单基线时。",
        "application": "模式识别、推荐冷启动。",
    },
    "kmeans": {
        "core_idea": "无明显类别标签、想把样本聚成球形簇做探索性分群时。",
        "application": "客户分群、图像压缩、异常初筛。",
    },
    "dbscan": {
        "core_idea": "簇形状任意、且要自动识别噪声点（离群）而非强制球形划分时。",
        "application": "地理热点、离群检测。",
    },
    # ── 降维 ──
    "factor_analysis": {
        "core_idea": "变量间有潜在公共因子、想用少数因子解释相关结构时（比 PCA 更强调潜变量）。",
        "application": "问卷量表降维、指标体系浓缩。",
    },
    # ── 图与网络/仿真 ──
    "dijkstra": {
        "core_idea": "边权非负、求单源最短路且要最优保证时，贪心松弛高效。",
        "application": "路网导航、物流配送路径。",
    },
    "max_flow": {
        "core_idea": "资源在网络中从源到汇的「最大可输送量」是瓶颈问题时。",
        "application": "管网输配、通信带宽、交通容量。",
    },
    "queueing_theory": {
        "core_idea": "系统含「到达-服务」随机过程、关心等待时间/队列长度/吞吐时。",
        "application": "客服中心、医院急诊、服务器容量规划。",
    },
    "system_dynamics": {
        "core_idea": "变量间存在反馈环（正/负）、关心长期动态与政策效应时。",
        "application": "经济-环境耦合、供应链库存、传染病传播。",
    },
    "cellular_automata": {
        "core_idea": "空间离散网格上局部规则演化出宏观模式（涌现）时。",
        "application": "城市扩张、森林火灾、交通流。",
    },
    "monte_carlo": {
        "core_idea": "解析难求、需通过大量随机抽样估计分布/概率/积分时。",
        "application": "风险价值、期权定价、可靠性评估。",
    },
    "discrete_event": {
        "core_idea": "系统状态仅在离散事件（到达/离开/故障）瞬间改变、关心资源利用时。",
        "application": "制造车间、港口装卸、呼叫中心仿真。",
    },
    "agent_based": {
        "core_idea": "宏观现象由异质个体交互涌现、需刻画个体异质性与适应行为时。",
        "application": "市场博弈、交通行为、疫情扩散。",
    },
    "game_theory": {
        "core_idea": "多方决策相互依赖、需找均衡（纳什）或最优策略时。",
        "application": "竞价、谈判、资源竞合。",
    },
    "anova": {
        "core_idea": "比较≥3 组均值、判断某因素是否显著影响结果时。",
        "application": "实验方案对比、工艺参数显著性。",
    },
    "correlation_test": {
        "core_idea": "需先判断两变量是否显著相关、相关方向与强度再建模时。",
        "application": "特征筛选、假设验证前置。",
    },
    # ── 神经网络 ──
    "mlp": {
        "core_idea": "数据非线性、需通用函数逼近且数据量中等时，前馈网络做深度模型基线。",
        "application": "回归/分类通用拟合。",
    },
    "cnn": {
        "core_idea": "输入具网格局部结构（图像/序列局部窗）、靠卷积提取局部特征时。",
        "application": "图像分类、时空格点预测。",
    },
    # ── 模糊逻辑 ──
    "fuzzy_inference": {
        "core_idea": "专家知识是「若A且B则C」的模糊规则、数据不足或机理不清时，用推理而非数据拟合。",
        "application": "控制决策、风险评估规则。",
    },
    "fuzzy_clustering": {
        "core_idea": "样本隶属多个簇（软划分）比硬划分更合理时，FCM 给出隶属度。",
        "application": "重叠客户群、模式软分群。",
    },
}


def main() -> None:
    data = json.loads(HMML_PATH.read_text(encoding="utf-8"))
    total = 0
    updated = 0
    for dom in data.get("domains", []):
        for sd in dom.get("subdomains", []):
            for m in sd.get("methods", []):
                total += 1
                mid = m.get("model_id")
                rule = ENRICH.get(mid)
                if not rule:
                    continue
                changed = False
                for fld in ("core_idea", "application"):
                    if fld not in m or not m.get(fld):
                        m[fld] = rule[fld]
                        changed = True
                if changed:
                    updated += 1
    HMML_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"HMML 方法节点总数={total}，本次补全字段节点数={updated}")


if __name__ == "__main__":
    main()
