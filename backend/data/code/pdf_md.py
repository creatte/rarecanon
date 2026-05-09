import os
import fitz  # PyMuPDF
import pdfplumber

# ========== 配置 ==========
PDF_PATH = "./backend/data/raw/Chinese_Rare_Disease_Guidelines_2019.pdf"
OUTPUT_MD = "./backend/data/processed/Chinese_Rare_Disease_Guidelines_2019.md"
IMAGE_DIR = "./backend/data/images"
os.makedirs(IMAGE_DIR, exist_ok=True)

md_content = ""

# ========== 第一步：PyMuPDF 提取所有图片 ==========
print("=" * 50)
print("阶段 1/2: PyMuPDF 提取图片...")
print("=" * 50)

doc = fitz.open(PDF_PATH)
# page_images[页码] = [(img_index, xref, 文件名), ...]
page_images = {}

for page_num in range(len(doc)):
    page = doc[page_num]
    image_list = page.get_images(full=True)
    page_images[page_num + 1] = []

    for idx, img_info in enumerate(image_list):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image["ext"]  # png / jpeg
            filename = f"page{page_num + 1}_img{idx + 1}_xref{xref}.{ext}"
            filepath = os.path.join(IMAGE_DIR, filename)

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            page_images[page_num + 1].append((idx + 1, xref, filename))
            print(f"  第{page_num + 1}页 img{idx + 1} → {filename} ({len(image_bytes)} bytes)")
        except Exception as e:
            print(f"  第{page_num + 1}页 img{idx + 1} 提取失败: {e}")

doc.close()
total_images = sum(len(v) for v in page_images.values())
print(f"\n共提取 {total_images} 张图片\n")

# ========== 第二步：pdfplumber 提取文字 + 表格 ==========
print("=" * 50)
print("阶段 2/2: pdfplumber 提取文字 & 表格...")
print("=" * 50)

with pdfplumber.open(PDF_PATH) as pdf:
    for page_num, page in enumerate(pdf.pages, 1):
        print(f"  正在处理第 {page_num} 页...")

        md_content += f"\n\n# 第{page_num}页\n\n"

        # 提取纯文本
        text = page.extract_text()
        if text:
            md_content += text + "\n"

        # 提取表格 → Markdown 表格
        tables = page.extract_tables()
        for table in tables:
            if not table or not table[0]:
                continue
            md_content += "\n"
            # 表头 (None → 空字符串)
            header = [str(c) if c is not None else "" for c in table[0]]
            md_content += "| " + " | ".join(header) + " |\n"
            # 分隔线
            md_content += "| " + " | ".join(["---"] * len(header)) + " |\n"
            # 内容行
            for row in table[1:]:
                cells = [str(c) if c is not None else "" for c in row]
                md_content += "| " + " | ".join(cells) + " |\n"

        # 该页的图片引用
        if page_num in page_images and page_images[page_num]:
            md_content += "\n**本页图片：**\n\n"
            for img_idx, xref, filename in page_images[page_num]:
                # 占位描述，后续 ingest_docs.py 会用多模态模型替换
                md_content += (
                    f"![图{page_num}-{img_idx}(待多模态描述)]"
                    f"(images/{filename})\n\n"
                )

# 保存
with open(OUTPUT_MD, "w", encoding="utf-8") as f:
    f.write(md_content)

print(f"\n{'=' * 50}")
print(f"转换完成！")
print(f"  Markdown: {OUTPUT_MD}")
print(f"  图片目录: {IMAGE_DIR}/ (共 {total_images} 张)")
print(f"{'=' * 50}")
