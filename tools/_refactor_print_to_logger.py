"""一次性重构：将模块内的裸 print() 收口为项目统一 logger（mathmodeling）。

仅作用于 modules/ 下 6 个仍有裸 print 的文件；__main__ 演示块额外注入
logging.basicConfig 以保证直接运行脚本时日志仍可见。可重复运行安全。
"""
import logging
import re
import pathlib

TARGETS = [
    "modules/data_processing/processor.py",
    "modules/model_selection/selector.py",
    "modules/model_solving/solver.py",
    "modules/paper_writing/writer.py",
    "modules/validation/validator.py",
    "modules/visualization/visualizer.py",
]

LOGGER_LINE = 'logger = logging.getLogger("mathmodeling")'


def refactor(rel: str) -> None:
    p = pathlib.Path(rel)
    src = p.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)

    has_logging_import = any(re.match(r"^\s*import logging\b", line) for line in lines)
    has_logger = LOGGER_LINE in src

    out = []
    inserted = False
    for line in lines:
        out.append(line)
        # 在第一条 import/from 语句之后插入 logging 导入与 logger（若缺）
        if not inserted and re.match(r"^\s*(import|from)\s", line) and not line.lstrip().startswith("#"):
            if not has_logging_import:
                out.append("import logging\n")
                has_logging_import = True
            if not has_logger:
                out.append(LOGGER_LINE + "\n")
                has_logger = True
            inserted = True

    # 行级替换：无参 print() -> logger.info("")；其余 print( -> logger.info(
    new_lines = []
    for line in out:
        if "print(" in line:
            line = re.sub(r"\bprint\(\)", 'logger.info("")', line)
            line = re.sub(r"\bprint\(", "logger.info(", line)
        new_lines.append(line)
    out = new_lines

    # 在 __main__ 块首行注入 basicConfig，保证 demo 运行时日志可见
    final = []
    injected = False
    for line in out:
        final.append(line)
        if not injected and re.match(r'^\s*if\s+__name__\s*==\s*["\']__main__["\']\s*:', line):
            indent = re.match(r"^(\s*)", line).group(1)
            final.append(indent + '    logging.basicConfig(level=logging.INFO, format="%(message)s")\n')
            injected = True

    p.write_text("".join(final), encoding="utf-8")
    print(f"refactored: {rel}")


if __name__ == "__main__":
    for t in TARGETS:
        refactor(t)
    print("done")
