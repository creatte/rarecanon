import re
import os


def clean_image(input_file, output_file):
    """删除图片引用：![](xxx.jpg) 及图片说明文字"""
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. 删除图片引用 ![](images/xxx.jpg)
    content = re.sub(r'!\[\]\(images/[^\)]+\)\n?', '', content)

    # 2. 删除"诊疗流程（图 x-x）"整行（含标题行）
    content = re.sub(r'.*诊疗流程.*（图\s*\d+[-–—]\d+）.*\n?', '', content)

    # 3. 删除"图 x-x xxx"图片说明行（图片上方或下方的caption）
    content = re.sub(r'^图\s*\d+[-–—]\d+.*\n?', '', content, flags=re.MULTILINE)

    # 4. 删除内联图片引用，如"（图9-2）"
    content = re.sub(r'（图\s*\d+[-–—]\d+）', '', content)

    # 5. 被删除后产生的连续空行压缩为单个空行
    content = re.sub(r'\n{3,}', '\n\n', content)
    # 开头空行去掉
    content = content.lstrip('\n')

    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"完成，输出到 {output_file}")


if __name__ == "__main__":
    input_file = r"backend\data\processed\1\Chinese_Rare_Disease_Guidelines_2025_clean.md"
    output_file = r"backend\data\processed\2\Chinese_Rare_Disease_Guidelines_2025_noimg.md"
    clean_image(input_file, output_file)
