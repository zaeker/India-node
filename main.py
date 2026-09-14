import os
import re
import urllib.parse
import base64
import socket
import time
import requests
from concurrent.futures import ThreadPoolExecutor

# ---------------- 全网免费节点聚合源 (每日更新数万节点) ----------------
SUB_SOURCES = [
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription2",
    "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription8",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray"
]

# 印度节点关键词字典
IN_KEYWORDS = ["印度", "孟买", "india", "mumbai", " in ", "-in-"]

TIMEOUT = 3            # 握手超时时间（秒）
MAX_THREADS = 50       # 提高并发数以加快测速
OUTPUT_FILE = "india_nodes.txt"

def decode_base64_content(content):
    """尝试解码 Base64 订阅内容"""
    try:
        # 补齐等号
        missing_padding = len(content) % 4
        if missing_padding:
            content += '=' * (4 - missing_padding)
        return base64.b64decode(content).decode('utf-8', errors='ignore')
    except Exception:
        return content # 如果不是 Base64 则返回原文本

def fetch_and_filter_nodes():
    """抓取聚合订阅并利用关键词筛选印度节点"""
    india_candidates = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    for url in SUB_SOURCES:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                raw_text = resp.text.strip()
                decoded_text = decode_base64_content(raw_text)
                
                for line in decoded_text.splitlines():
                    line_lower = urllib.parse.unquote(line).lower()
                    # 判断是否包含印度特征词
                    if any(kw in line_lower for kw in IN_KEYWORDS):
                        # 解析出 Host/IP 和 Port
                        # 兼容 vless://uuid@host:port 或 vmess://(base64)
                        match = re.search(r'@([\w\.-]+):(\d+)', line)
                        if match:
                            india_candidates.append({
                                "host": match.group(1),
                                "port": int(match.group(2)),
                                "raw": line
                            })
        except Exception as e:
            print(f"[!] 源抓取失败 [{url}]: {e}")
            
    # 去重处理
    unique_candidates = {f"{c['host']}:{c['port']}": c for c in india_candidates}.values()
    return list(unique_candidates)

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
    print("[*] 正在从全网节点聚合池拉取并筛选印度节点...")
    candidates = fetch_and_filter_nodes()
    print(f"[*] 初步匹配到 {len(candidates)} 个印度节点，开始并发连通性测速...")

    if not candidates:
        print("[!] 未筛选出任何印度节点，程序退出。")
        return

    valid_results = []
    
    def worker(item):
        lat = test_tcp_latency(item["host"], item["port"])
        if lat is not None:
            return (lat, item["raw"])
        return None

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(worker, c) for c in candidates]
        for f in futures:
            res = f.result()
            if res:
                valid_results.append(res)
                
    # 按延迟从小到大排序
    valid_results.sort(key=lambda x: x[0])
    print(f"[✓] 测速完成！最终高可用印度节点数量: {len(valid_results)}")
    
    # 将测速成功的原始节点链接写入文件（Base64编码，标准订阅格式）
    if valid_results:
        final_nodes = "\n".join([raw for _, raw in valid_results])
        base64_nodes = base64.b64encode(final_nodes.encode('utf-8')).decode('utf-8')
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(base64_nodes)
            
        print(f"[✓] 优选结果已输出至 {OUTPUT_FILE} (已打包为标准 Base64 订阅格式)")
    else:
        print("[!] 测试后无可用节点存活。")

if __name__ == "__main__":
    main()
