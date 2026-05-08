import re
import os


def clean_raw_data(input_file, output_file):
    """ 
    2019年罕见病指南的markdown文件
    数据清洗步骤：
    1. 删除目录（# 目录到 # 1.）
    2. 标题规范化（数字标题1级，其余2级）
    3. 压缩连续空行
    4. 删除参考文献（## 参考文献 到下一个 #）
    5. 修复OCR错误（字符替换 + 合并断行）
    6. 正文去空格
    
    """
    new_lines = []
    with open(input_file, "r", encoding="utf-8") as f:
        f = f.readlines()
        f = clean_directory(f)
        f = change_title(f)
        f = clean_blank_lines(f)
        f = remove_references(f)
        f = fix_ocr_error(f)
        f = remove_spaces_except_headers(f)
        new_lines = f
        print(new_lines[10:15])

    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def clean_directory(f_lines):
    """删除目录（从 # 罕见病诊疗指南 到正文第一个 # 1.）"""
    lines = []
    skip = False
    for line in f_lines:
        # if line.strip().startswith("# 罕见病诊疗指南"):
        if line.strip().startswith("# 86 个罕见病"):
            skip = True
            continue
        if skip and line.strip().startswith("# 1."):
            skip = False
        if not skip:
            lines.append(line)
    return lines


def change_title(f_lines):
    """数字标题保留为1级标题(# 1.)，其余降为2级标题(##)"""
    lines = []
    for line in f_lines:
        if not re.match(r'# \d+\.', line):
            line = line.replace("# ", "## ")
        lines.append(line)
    return lines


def clean_blank_lines(f_lines):
    """压缩连续空行：连续空行只保留一个"""
    lines = []
    prev_empty = True  # 开头多余空行也一并干掉
    for line in f_lines:
        cur_empty = (line.strip() == "")
        if cur_empty and prev_empty:
            continue
        lines.append(line)
        prev_empty = cur_empty
    return lines

def remove_spaces_except_headers(lines):
    """
    规则：
    1. 以 # 开头的【标题】：保留所有空格
    2. 其他【正文】：删除所有空格
    """
    result = []
    
    for line in lines:
        # 如果是标题（# 开头），直接保留，不动空格
        if line.strip().startswith("#"):
            result.append(line)
        
        # 如果是正文，删除里面所有空格（包括中间、前后）
        else:
            # 删除所有空格：普通空格 + 全角空格
            cleaned = line.replace(" ", "").replace("　", "")
            result.append(cleaned)
    
    return result

def remove_references(f_lines):
    """删除参考文献：从 ## 参考文献 到下一个 # 标题"""
    lines = []
    skip = False
    for line in f_lines:
        stripped = line.strip()
        if stripped.startswith("## 参考文献") or stripped.startswith("# 参考文献"):
            skip = True
            continue
        if skip and stripped.startswith("# "):
            skip = False
        if not skip:
            lines.append(line)
    return lines


def fix_ocr_error(f_lines):
    """修复OCR识别错误：字符替换 + 合并断行"""
    lines = []
    for line in f_lines:
        line = line.replace("", "μ")
        lines.append(line)

    # 合并OCR断行：不以句末标点结尾的行，尝试与后续正文拼接
    # 单个空行在正文续行之间也视为OCR噪声，一并跳过
    def is_content_line(s):
        """非空、非标题、非特殊标记的正文行"""
        return s and not s.startswith(("#", "- ", "* ", "```", "!", "["))

    def is_sentence_end(s):
        """行尾是否为句末标点"""
        return s and s[-1] in "。！？；—…》」』）)"

    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            result.append(line)
            i += 1
            continue

        # 尝试向后合并
        while True:
            nxt_idx = i + 1
            merged_blank = False
            # 跳过单个空行(OCR噪声)
            if nxt_idx < len(lines) and not lines[nxt_idx].strip():
                if nxt_idx + 1 < len(lines) and is_content_line(lines[nxt_idx + 1].strip()):
                    nxt_idx += 1  # 跳过空行
                    merged_blank = True
            if nxt_idx >= len(lines):
                break

            nxt_stripped = lines[nxt_idx].strip()
            if not is_content_line(nxt_stripped):
                break

            tail = line.rstrip("\n")
            if is_sentence_end(tail):
                break

            # 拼接
            line = tail + nxt_stripped + "\n"
            i = nxt_idx
            if merged_blank:
                # 空行已被跳过消费，后续不再保留
                pass

        result.append(line)
        i += 1
    return result


if __name__ == "__main__":
    input_file = r"backend\data\mineru\Chinese_Rare_Disease_Guidelines_2025\hybrid_auto\Chinese_Rare_Disease_Guidelines_2025.md"
    output_file = r"backend/data/processed/1/Chinese_Rare_Disease_Guidelines_2025_clean.md"
    clean_raw_data(input_file, output_file)
