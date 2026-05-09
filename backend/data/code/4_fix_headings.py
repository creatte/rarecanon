"""
修复 final markdown 中的假一级标题：
- 规则：只有紧跟着 ## 概述 的 # N. 才是真疾病名
- 其余 # N. 全部去掉 # 前缀，降为普通编号段落
"""
import re
import os


def fix_headings(input_file: str, output_file: str):
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # ── 第一步：找到所有 # N. 行，判断真假 ──
    h1_lines = {}  # line_index -> True(真疾病) / False(假标题)
    for i, line in enumerate(lines):
        if re.match(r'^# \d+\.', line):
            h1_lines[i] = None  # 待判定

    # 判定：往后扫描，忽略空行，看遇到的第一个 ## 是不是 "## 概述"
    for idx in h1_lines:
        next_h2 = None
        for j in range(idx + 1, len(lines)):
            stripped = lines[j].strip()
            if stripped == "":
                continue
            if stripped.startswith("## "):
                next_h2 = stripped
                break
            # 遇到正文（非空非标题）就继续往后，直到遇到下一个 ##
            if stripped.startswith("# "):
                # 遇到另一个 # N. 且还没找到 ## 概述，说明前一个肯定是假的
                break
        # 只有紧跟着 ## 概述的才是真疾病
        h1_lines[idx] = (next_h2 == "## 概述")

    # ── 第二步：修复 ──
    fixed_lines = []
    for i, line in enumerate(lines):
        if i in h1_lines and not h1_lines[i]:
            # 假标题：去掉 # 前缀，变成普通段落
            fixed_lines.append(line.replace("# ", "", 1))
        else:
            fixed_lines.append(line)

    # ── 第三步：同样处理 ## 表 N-X、## 核心标准、## 排除标准、## 支持标准 ──
    # 这些本质是三级/四级标题，但 mineru 没有更细的层级区分，先不动它们
    # 如果后续需要可以在此扩展

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(fixed_lines)

    # ── 输出变更摘要 ──
    changes = []
    for idx, is_real in h1_lines.items():
        status = "保留" if is_real else "降级→普通段落"
        heading = lines[idx].strip()
        """
        f"  行{idx+1:<6d} {status:<16s} {heading}"                                                                                         
            - idx+1 — 行号（数组索引从 0 开始，+1 变成从 1 开始）                                                                  
            - :<6d — 左对齐，占 6 个字符宽，整数格式
            - :<16s — 左对齐，占 16 个字符宽，字符串格式
            - heading — 原始标题文本，不限制宽度
        """
        changes.append(f"  行{idx+1:<6d} {status:<16s} {heading}")

    print(f"处理: {input_file}")
    print(f"共 {len(h1_lines)} 个 # N. 标题，其中 {sum(1 for v in h1_lines.values() if v)} 个真疾病，{sum(1 for v in h1_lines.values() if not v)} 个假标题")
    for c in changes:
        print(c)

    print(f"\n输出 → {output_file}\n")


if __name__ == "__main__":
    base = os.path.dirname(__file__)

    for name in [
        "Chinese_Rare_Disease_Guidelines_2019_final.md",
        "Chinese_Rare_Disease_Guidelines_2025_final.md",
    ]:
        src = os.path.join(base, "processed", "clear", "3", name)
        dst = os.path.join(base, "processed", name.replace("_final", ""))
        if os.path.exists(src):
            fix_headings(src, dst)
        else:
            print(f"文件不存在: {src}")
