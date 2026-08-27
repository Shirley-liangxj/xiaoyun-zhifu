import os

src = "D:/xiaoyun/docs/面试备战总集-豆包上传版.md"
out_dir = "D:/xiaoyun/docs/_split"
os.makedirs(out_dir, exist_ok=True)

with open(src, encoding="utf-8") as f:
    lines = f.readlines()

markers = [
    "## 小云智服（作品集通用备战）",
    "## 海洋无限（武汉）· HR面最终安全版",
    "## 海洋无限（武汉）· 面试实录复盘",
    "## 爱帮智汇（西安）· 面试复盘",
    "## 广东国科（惠州）· 面经",
    "## 猎豹移动（北京，9-01）· 面经",
    "## 智书 qtech（8-27 19:00）· AI面试备战",
]

idx = []
for i, l in enumerate(lines):
    s = l.strip()
    if s in markers:
        idx.append((i, s))
idx.sort()

chunks = {}
for j, (start, m) in enumerate(idx):
    end = idx[j + 1][0] if j + 1 < len(idx) else len(lines)
    chunks[m] = "".join(lines[start:end])

# 合并海洋无限两个章节
hy_hr = chunks.pop("## 海洋无限（武汉）· HR面最终安全版")
hy_rec = chunks.pop("## 海洋无限（武汉）· 面试实录复盘")
hy = hy_hr + "\n" + hy_rec

out_map = {
    "01_小云智服.md": ("小云智服（作品集通用备战）", chunks["## 小云智服（作品集通用备战）"]),
    "02_海洋无限.md": ("海洋无限（武汉）", hy),
    "03_爱帮智汇.md": ("爱帮智汇（西安）", chunks["## 爱帮智汇（西安）· 面试复盘"]),
    "04_广东国科.md": ("广东国科（惠州）", chunks["## 广东国科（惠州）· 面经"]),
    "05_猎豹移动.md": ("猎豹移动（北京）", chunks["## 猎豹移动（北京，9-01）· 面经"]),
    "06_智书qtech.md": ("智书 qtech（8-27 19:00）", chunks["## 智书 qtech（8-27 19:00）· AI面试备战"]),
}

for fn, (title, content) in out_map.items():
    header = f"# {title}\n\n"
    with open(os.path.join(out_dir, fn), "w", encoding="utf-8") as f:
        f.write(header + content)
    print(f"written {fn}  title={title}  chars={len(content)}")
