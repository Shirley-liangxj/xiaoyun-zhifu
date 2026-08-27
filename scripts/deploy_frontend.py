import paramiko, sys, time

HOST, PORT, USER, PW = "47.116.143.103", 22, "root", "666258Lxj"
LOCAL_TAR = "D:/xiaoyun/_xy_frontend.tar"
REMOTE_TAR = "/tmp/xy_frontend.tar"
CONTAINER = "xiaoyun_frontend"
NGINX_DIR = "/usr/share/nginx/html"

def connect():
    last = None
    for i in range(5):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, port=PORT, username=USER, password=PW, timeout=20,
                      look_for_keys=False, allow_agent=False)
            print(f"[ok] SSH 连接成功 (第{i+1}次)")
            return c
        except Exception as e:
            last = e
            print(f"[retry {i+1}] SSH 失败: {e}")
            time.sleep(2)
    raise last

ssh = connect()

# 通过 stdin 把 tar 流进容器（避免宿主机/容器文件系统不一致）
cmd = f"docker exec -i {CONTAINER} tar -xvf - -C {NGINX_DIR}"
print(f"[1] 流式解包: {cmd}")
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
with open(LOCAL_TAR, "rb") as f:
    while True:
        chunk = f.read(65536)
        if not chunk:
            break
        stdin.write(chunk)
stdin.flush()
stdin.channel.shutdown_write()
out = stdout.read().decode("utf-8", "ignore")
err = stderr.read().decode("utf-8", "ignore")
print("STDOUT:", out[:1500])
if err.strip():
    print("STDERR:", err[:800])

# 清理宿主机可能残留的 tar
try:
    ssh.exec_command("rm -f /tmp/xy_frontend.tar")
except Exception:
    pass

# 确认新 JS 落地
check = "docker exec -i xiaoyun_frontend sh -c 'ls -1 /usr/share/nginx/html/assets/ | head -20 && echo --- && grep -o \"assets/index-[A-Za-z0-9]*\\.js\" /usr/share/nginx/html/index.html'"
stdin, stdout, stderr = ssh.exec_command(check, timeout=30)
print("[2] 容器前端产物:")
print(stdout.read().decode("utf-8","ignore")[:1200])
ssh.close()
print("[done] 部署脚本结束")
