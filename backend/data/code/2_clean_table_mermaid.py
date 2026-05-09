"""
清洗 HTML 表格 和 Mermaid 流程图
- 表格: HTML → Markdown 管表（rowspan/colspan 拆开填充）
- Mermaid: 提取节点文本，转流程描述
"""
import re
import os
from html.parser import HTMLParser


# ──────────────────── 表格清洗 ────────────────────

class TableParser(HTMLParser):
    """解析单个 <table> 为二维网格"""

    def __init__(self):
        super().__init__()
        self.rows = []          # 最终网格: list[list[str]]
        self._cur_row = []      # 当前行: list[str]
        self._cur_cell = ""     # 当前单元格文本
        self._in_td = False
        self._cell_attrs = {}   # 当前单元格属性
        self._col = 0           # 当前列位置

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._cur_row = []
            self._col = 0
        elif tag in ("td", "th"):
            self._in_td = True
            self._cur_cell = ""
            self._cell_attrs = dict(attrs)

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._in_td = False
            # 跳过已有内容的位置(colspan填充)
            while self._col < len(self._cur_row) and self._cur_row[self._col]:
                self._col += 1
            # colspan, rowspan 默认 1
            cs = int(self._cell_attrs.get("colspan", 1))
            rs = int(self._cell_attrs.get("rowspan", 1))
            # 填充当前位置
            cell_text = self._cur_cell.strip()
            # 补齐当前行列数
            while len(self._cur_row) < self._col + cs:
                self._cur_row.append("")
            for c in range(cs):
                idx = self._col + c
                if idx >= len(self._cur_row):
                    self._cur_row.append("")
                self._cur_row[idx] = cell_text
            self._col += cs
        elif tag == "tr":
            self.rows.append(self._cur_row)

    def handle_data(self, data):
        if self._in_td:
            self._cur_cell += data

    def get_grid(self):
        """返回展开 rowspan 后的网格"""
        if not self.rows:
            return []
        # 先展开 colspan（已在逐行解析时处理），再找最大列数
        max_cols = max(len(r) for r in self.rows) if self.rows else 0
        # 对齐所有行
        for r in self.rows:
            while len(r) < max_cols:
                r.append("")
        # 展开 rowspan：从上到下扫描，将 rowspan 内容复制到后续行
        for ri, row in enumerate(self.rows):
            for ci, cell in enumerate(row):
                if cell and cell != "":
                    # 这里只处理了 td 级别的 rowspan 展开
                    # 简单方案：从上往下，空单元格从上找非空填充
                    pass
        # 更稳健的做法：重新解析一次，记住 rowspan 信息
        return self.rows


def parse_table_with_spans(html_text):
    """解析含 rowspan/colspan 的 HTML 表格，返回展开后的网格"""
    # 先用简单方式收集所有行和 rowspan 信息
    # 返回 (colspanned_rows, rowspan_info)
    grid = []
    span_map = []  # (ri, ci) -> (rs_remaining, text)

    # 提取所有 <tr> 块
    tr_blocks = re.findall(r'<tr>(.*?)</tr>', html_text, re.DOTALL)

    for ri, tr_html in enumerate(tr_blocks):
        cells = re.findall(r'<(td|th)([^>]*)>(.*?)</\1>', tr_html, re.DOTALL)
        row = []
        ci = 0
        # 先跳过之前 rowspan 遗留的位置
        while any((ri, ci) in dict(sm) for sm in [span_map[-1]] if span_map):
            pass
        # 简化处理
        for tag, attrs_str, text in cells:
            text = text.strip()
            cs = int(re.search(r'colspan=["\']?(\d+)', attrs_str).group(1)
                     ) if re.search(r'colspan=["\']?(\d+)', attrs_str) else 1
            rs = int(re.search(r'rowspan=["\']?(\d+)', attrs_str).group(1)
                     ) if re.search(r'rowspan=["\']?(\d+)', attrs_str) else 1
            # 跳过已有内容的位置
            while ci < len(row) and row[ci] is not None:
                ci += 1
            # 确保行够长
            while len(row) < ci + cs:
                row.append(None)
            for c in range(cs):
                row[ci + c] = text
            ci += cs
        grid.append(row)
        span_map.append({})

    # 简化：用两次扫描处理 rowspan
    # 第一次：收集所有 rowspan 信息
    rowspans = []  # list of (ri, ci, rs, text)
    for ri, tr_html in enumerate(tr_blocks):
        cells = re.findall(r'<(td|th)([^>]*)>(.*?)</\1>', tr_html, re.DOTALL)
        ci = 0
        for tag, attrs_str, text in cells:
            rs = int(re.search(r'rowspan=["\']?(\d+)', attrs_str).group(1)
                     ) if re.search(r'rowspan=["\']?(\d+)', attrs_str) else 1
            cs = int(re.search(r'colspan=["\']?(\d+)', attrs_str).group(1)
                     ) if re.search(r'colspan=["\']?(\d+)', attrs_str) else 1
            if rs > 1:
                rowspans.append((ri, ci, rs, cs, text.strip()))
            ci += cs

    # 第二次：填充 rowspan
    for ri, ci, rs, cs, text in rowspans:
        for r in range(1, rs):
            target_ri = ri + r
            if target_ri < len(grid):
                while len(grid[target_ri]) < ci + cs:
                    grid[target_ri].append(None)
                # 在 ci 位置插入
                for c in range(cs):
                    # 找插入位置
                    insert_at = ci + c
                    while insert_at < len(grid[target_ri]) and grid[target_ri][insert_at] is not None:
                        insert_at += 1
                    while len(grid[target_ri]) <= insert_at:
                        grid[target_ri].append(None)
                    grid[target_ri][insert_at] = text

    # 找最大列数，对齐，None → ""
    max_cols = max(len(r) for r in grid) if grid else 0
    for r in grid:
        while len(r) < max_cols:
            r.append(None)
        for ci in range(len(r)):
            if r[ci] is None:
                r[ci] = ""

    return grid


def grid_to_markdown(grid):
    """二维网格 → Markdown 管表"""
    if not grid or not grid[0]:
        return ""
    max_cols = max(len(r) for r in grid)
    lines = []
    # 表头
    header = grid[0]
    lines.append("| " + " | ".join(h if h else " " for h in header) + " |")
    lines.append("| " + " | ".join("---" for _ in range(max_cols)) + " |")
    # 数据行
    for row in grid[1:]:
        cells = [(row[i] if i < len(row) and row[i] else " ") for i in range(max_cols)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def clean_tables(content):
    """替换所有 HTML <table> 为 Markdown 表格"""
    tables = re.findall(r'<table>.*?</table>', content, re.DOTALL)

    for tbl_html in tables:
        try:
            grid = parse_table_with_spans(tbl_html)
            md_table = grid_to_markdown(grid)
            content = content.replace(tbl_html, "\n" + md_table + "\n", 1)
        except Exception:
            # 解析失败，只剥离 HTML 标签保留文字
            text = re.sub(r'<[^>]+>', ' ', tbl_html)
            text = re.sub(r'\s+', ' ', text).strip()
            content = content.replace(tbl_html, "\n" + text + "\n", 1)

    return content


# ──────────────────── Mermaid 清洗 ────────────────────

def mermaid_to_text(mermaid_code):
    """将 mermaid graph TD 代码转为流程描述文本"""
    code = mermaid_code.strip()
    # 去掉 graph TD/LR 前缀
    code = re.sub(r'^graph\s*\w+\s*', '', code)
    # 去掉 style 样式行（行尾带 fill 的那些）
    code = re.sub(r'style\w+fill[^;]*;?', '', code)

    # 按 --> 切分成边
    edges = re.split(r'\s*-->\s*', code)
    texts = []
    for part in edges:
        # 提取节点文本: A["xxx"] 或 B{xxx} 或 C(xxx)
        match = re.search(r'[\[\(\{]"([^"]*)"[\]\)\}]', part)
        if match:
            texts.append(match.group(1))

    if not texts:
        return ""
    # 去重相邻的相同节点（如 B-->B 这种情况跳过重复）
    seen = []
    for t in texts:
        if not seen or t != seen[-1]:
            seen.append(t)

    if len(seen) <= 1:
        return " → ".join(texts)
    return " → ".join(seen)


def clean_mermaid(content):
    """提取 <details> 中 mermaid 内容，转为流程文本"""
    # 匹配整个 details 块（不依赖换行）
    pattern = re.compile(
        r'<details>\s*<summary>flowchart</summary>\s*```mermaid\s*(.*?)```\s*</details>',
        re.DOTALL
    )
    for match in pattern.finditer(content):
        mermaid_code = match.group(1)
        text_desc = mermaid_to_text(mermaid_code)
        replacement = f"\n**诊疗流程:**\n{text_desc}\n"
        content = content.replace(match.group(0), replacement, 1)
    return content


# ──────────────────── 主函数 ────────────────────

def clean_table_and_mermaid(input_file, output_file):
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"原始长度: {len(content)} 字符")

    content = clean_tables(content)
    print("表格转换完成")

    content = clean_mermaid(content)
    print("Mermaid 转换完成")

    # 压缩可能产生的多余空行
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.lstrip('\n')

    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"完成，输出到 {output_file}")


if __name__ == "__main__":
    input_file = r"backend\data\processed\2\Chinese_Rare_Disease_Guidelines_2025_noimg.md"
    output_file = r"backend\data\processed\3\Chinese_Rare_Disease_Guidelines_2025_final.md"
    clean_table_and_mermaid(input_file, output_file)
