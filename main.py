09.14 21:27
import os
import re
import json
import base64
import socket
import time
import requests
from concurrent.futures import ThreadPoolExecutor

# ---------------- 配置选项 ----------------
# 可通过环境变量获取，默认填入你的节点订阅或IP列表地址
SUB_URL = os.getenv("SUBSCRIPTION_URL", "https://your-subscription-link.com/sub")
TARGET_COUNTRY = "IN"  # 印度国家代码
MAX_THREADS = 20       # 并发测速线程数
TIMEOUT = 3            # 超时时间（秒）
OUTPUT_FILE = "india_nodes.txt"

def fetch_sub_content(url):
    """获取并解码订阅链接内容"""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        content = resp.text.strip()
        try:
            decoded = base64.b64decode(content).decode('utf-8')
            return [line.strip() for line in decoded.splitlines() if line.strip()]
        except Exception:
            return [line.strip() for line in content.splitlines() if line.strip()]
    except Exception as e:
        print(f"[!] 获取订阅内容失败: {e}")
        return []

def extract_host_port(line):
    """解析节点/条目中的 Host 与 Port"""
    # 匹配普通 IP:PORT 格式
    match_ip = re.match(r'^(\d{1,3}(?:\.\d{1,3}){3}):(\d+)$', line)
    if match_ip:
        return match_ip.group(1), int(match_ip.group(2))
    
    # 匹配 vless://, vmess://, trojan://, ss:// 等协议节点
    match_protocol = re.search(r'@([^:\s/]+):(\d+)', line)
    if match_protocol:
        return match_protocol.group(1), int(match_protocol.group(2))
    
    return None, None

def batch_geoip_check(hosts):
    """批量查询 GeoIP 识别印度 IP (使用 ip-api 批量接口)"""
    india_hosts = set()
    unique_hosts = list(set(hosts))
    chunk_size = 100  # ip-api batch 单次上线 100 条
    
    for i in range(0, len(unique_hosts), chunk_size):
        chunk = unique_hosts[i:i + chunk_size]
        payload = [{"query": h} for h in chunk]
        try:
            res = requests.post("http://ip-api.com/batch?fields=query,countryCode,status", json=payload, timeout=10)
            data = res.json()
            for item in data:
                if item.get("status") == "success" and item.get("countryCode") == TARGET_COUNTRY:
                    india_hosts.add(item.get("query"))
        except Exception as e:
            print(f"[!] GeoIP 批量查询发生异常: {e}")
            
    return india_hosts

def test_tcp_latency(host, port):
    """测试 TCP 握手延迟"""
    start = time.time()
    try:
        sock = socket.create_connection((host, port), timeout=TIMEOUT)
        sock.close()
        return round((time.time() - start) * 1000, 2)
    except Exception:
        return None

def main():
    print("[*] 正在拉取订阅数据...")
    raw_lines = fetch_sub_content(SUB_URL)
    if not raw_lines:
        print("[!] 未获取到任何节点数据，程序退出。")
        return

    parsed_items = []
    hosts_to_check = []
    
    for line in raw_lines:
        host, port = extract_host_port(line)
        if host and port:
            parsed_items.append({"raw": line, "host": host, "port": port})
            hosts_to_check.append(host)
            
    print(f"[*] 解析到 {len(parsed_items)} 条有效条目，开始校验地理位置...")
    india_hosts = batch_geoip_check(hosts_to_check)
    
    india_items = [item for item in parsed_items if item["host"] in india_hosts]
    print(f"[*] 筛选完成：匹配到 {len(india_items)} 个印度 (IN) 节点/IP")
    
    if not india_items:
        print("[!] 未筛选出任何印度 IP，更新空文件。")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("")
        return

    print("[*] 开始并发测试连通性与延迟...")
    valid_results = []
    
    def worker(item):
        lat = test_tcp_latency(item["host"], item["port"])
        if lat is not None:
            return (lat, item["raw"])
        return None

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(worker, item) for item in india_items]
        for f in futures:
            res = f.result()
            if res:
                valid_results.append(res)
                
    # 按照延迟从低到高排序
    valid_results.sort(key=lambda x: x[0])
    print(f"[✓] 测速完成，最终可用印度节点数: {len(valid_results)}")
    
    # 写入文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join([raw for _, raw in valid_results]))
    print(f"[✓] 优选结果已保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

