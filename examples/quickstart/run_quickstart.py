"""
数学建模竞赛工作流 - 快速启动示例
演示如何使用工作流处理一个数学建模问题

工作流模式：
- 人工参与模式：每个阶段执行前询问用户确认
- 可视化阶段：用户主导，AI仅提供数据和指引
- 图表生成：用户操作权威在线工具完成
"""

import sys
import argparse
from pathlib import Path

# 添加工作流目录到路径
workflow_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(workflow_dir))

from main import MathModelingWorkflow


def main():
    """运行快速启动示例"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="数学建模竞赛工作流 - 快速启动示例")
    parser.add_argument("--project", help="自定义项目目录")
    args = parser.parse_args()

    print("=" * 60)
    print("数学建模竞赛工作流 - 快速启动示例")
    print("（人工参与模式）")
    print("=" * 60)

    # 设置项目目录
    if args.project:
        project_dir = Path(args.project)
    else:
        project_dir = workflow_dir / "examples" / "quickstart" / "project"
    project_dir.mkdir(parents=True, exist_ok=True)

    # 复制示例文件到项目目录
    import shutil
    source_dir = workflow_dir / "examples" / "quickstart"
    dest_dirs = ["problem_files", "raw_data"]

    for d in dest_dirs:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    # 复制题目文件
    problem_file = source_dir / "problem.txt"
    if problem_file.exists():
        shutil.copy(problem_file, project_dir / "problem_files" / "problem.txt")
        print(f"已复制题目文件: problem.txt")

    # 复制数据文件
    data_file = source_dir / "data.csv"
    if data_file.exists():
        shutil.copy(data_file, project_dir / "raw_data" / "data.csv")
        print(f"已复制数据文件: data.csv")

    print(f"\n项目目录: {project_dir}")
    print("-" * 60)

    # 初始化工作流
    workflow = MathModelingWorkflow(str(project_dir))

    # 运行所有阶段（人工参与模式）
    print("\n开始运行工作流...")
    print("-" * 60)
    print("人工参与模式：每个阶段执行前将询问您的确认")
    print("图片绘制阶段支持人工全程参与协作")
    print("输入 'y' 或回车执行阶段，'n' 跳过，'q' 中止工作流")
    print("-" * 60)

    results = workflow.run_all()

    # 打印结果摘要
    print("\n" + "=" * 60)
    print("运行完成！结果摘要:")
    print("=" * 60)

    for stage, result in results.items():
        if isinstance(result, dict) and "error" not in result:
            status = result.get("status", "completed")
            if status == "skipped":
                print(f"\n[SKIP] {stage}: 用户跳过")
            else:
                print(f"\n[OK] {stage}:")
                for key, value in result.items():
                    if isinstance(value, (str, int, float)):
                        print(f"   {key}: {value}")
        else:
            print(f"\n[FAIL] {stage}: {result.get('error', '未知错误')}")

    # 打印输出文件位置
    print("\n" + "=" * 60)
    print("输出文件:")
    print("=" * 60)

    # 检查文件是否存在
    paper_md = project_dir / 'paper' / 'paper_draft.md'
    paper_docx = project_dir / 'paper' / 'paper_draft.docx'
    solving_result = project_dir / 'results' / 'solving_result.json'
    figures_dir = project_dir / 'figures'
    validation_json = project_dir / 'results' / 'validation.json'

    if paper_md.exists():
        print(f"  论文草稿: {paper_md}")
    else:
        print(f"  论文草稿: 未生成")

    if paper_docx.exists():
        print(f"  Word文档: {paper_docx}")
    else:
        print(f"  Word文档: 未生成")

    if solving_result.exists():
        print(f"  模型结果: {solving_result}")
    else:
        print(f"  模型结果: 未生成")

    if figures_dir.exists() and any(figures_dir.iterdir()):
        print(f"  可视化图: {figures_dir}")
    else:
        print(f"  可视化图: 未生成")

    if validation_json.exists():
        print(f"  验证报告: {validation_json}")
    else:
        print(f"  验证报告: 未生成")

    # 打印状态
    print("\n" + "=" * 60)
    workflow.print_status()


if __name__ == "__main__":
    main()
