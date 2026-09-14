import re
import socket
import time
import requests
from concurrent.futures import ThreadPoolExecutor

# ---------------- 公开印度 IP / 节点数据源 ----------------
PUBLIC_SOURCES = [
    # ProxyScrape 动态印度 IP 接口
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=all&timeout=5000&country=IN&ssl=all&anonymity=all",
    # 开源项目实时更新的印度节点/IP列表
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-india.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxystream/main/India.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/in.txt"
]

TIMEOUT = 3            # 握手超时时间（秒）
MAX_THREADS = 30       # 并发测速线程数
OUTPUT_FILE = "india_nodes.txt"

def fetch_public_ips():
    """从多个公开源收集印度 IP:PORT 数据"""
    raw_candidates = set()
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in PUBLIC_SOURCES:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                lines = resp.text.splitlines()
                for line in lines:
                    line = line.strip()
                    # 匹配标准的 IPv4:PORT 格式
                    match = re.search(r'(\d{1,3}(?:\.\d{1,3}){3}):(\d+)', line)
                    if match:
                        raw_candidates.add((match.group(1), int(match.group(2))))
        except Exception as e:
            print(f"[!] 抓取源失败 [{url}]: {e}")
            
    return list(raw_candidates)

def test_tcp_latency(ip, port):
    """测试 TCP 握手延迟"""
    start = time.time()
    try:
        sock = socket.create_connection((ip, port), timeout=TIMEOUT)
        sock.close()
        return round((time.time() - start) * 1000, 2)
    except Exception:
        return None

def main():
    print("[*] 正在从公开节点库抓取印度 IP 列表中...")
    candidates = fetch_public_ips()
    print(f"[*] 共收集到 {len(candidates)} 个候选印度 IP:PORT，开始并行验证与测速...")

    if not candidates:
        print("[!] 未获取到有效的候选 IP，请检查网络联通性。")
        return

    valid_results = []
    
    def worker(item):
        ip, port = item
        lat = test_tcp_latency(ip, port)
        if lat is not None:
            return (lat, f"{ip}:{port}")
        return None

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(worker, c) for c in candidates]
        for f in futures:
            res = f.result()
            if res:
                valid_results.append(res)
                
    # 按延迟升序排序
    valid_results.sort(key=lambda x: x[0])
    print(f"[✓] 测试完成！最终可用印度 IP 数量: {len(valid_results)}")
    
    # 写入结果
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for lat, entry in valid_results:
            f.write(f"{entry} # 延迟:{lat}ms\n")
            
    print(f"[✓] 优选印度 IP 已输出至当前目录下的 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
