# 需安装：pip install requests beautifulsoup4
import requests
from bs4 import BeautifulSoup
import os

# 1. 把你要抓的Orphanet中文版疾病链接放这
urls = [
    "https://www.chard.org.cn/orphanet/disease1",  # 替换成真实链接
    "https://www.chard.org.cn/orphanet/disease2"
]

# 2. 保存目录
save_dir = "orphanet_zh"
os.makedirs(save_dir, exist_ok=True)

# 3. 批量抓取
for url in urls:
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 只抓正文（根据页面结构调整，只留疾病内容）
        content = soup.find("div", class_="main-content").get_text(strip=True, separator="\n")
        
        # 保存为txt
        name = url.split("/")[-1] + ".txt"
        with open(os.path.join(save_dir, name), "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 已保存：{name}")
    except Exception as e:
        print(f"❌ 失败：{url}，{e}")