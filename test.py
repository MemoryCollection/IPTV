import re
import random
import time
from playwright.sync_api import sync_playwright

# 防止被封禁的 User-Agent 列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:64.0) Gecko/20100101 Firefox/64.0",
    "Mozilla/5.0 (Windows NT 6.3; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:79.0) Gecko/20100101 Firefox/79.0"
]

# 请求 URL 列表
urls = [
    "https://www.zoomeye.org/searchResult?q=%2Fiptv%2Flive%2Fzh_cn.js%20%2Bcountry%3A%22CN%22%20%2Bsubdivisions%3A%22hebei%22",
    "https://www.zoomeying.com/searchResult?q=%2Fiptv%2Flive%2Fzh_cn.js%20%2Bcountry%3A%22CN%22%20%2Bsubdivisions%3A%22beijing%22",
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0iSGViZWki",
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0iYmVpamluZyI%3D",
]

# 匹配 IP 地址和端口的正则表达式
pattern = r"http://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+"

# 随机选择一个 User-Agent
def get_random_user_agent():
    return random.choice(USER_AGENTS)

# 发送请求并处理响应
def extract_info(page, url):
    ip_ports = []
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": url,
    }

    try:
        # 访问 URL 并等待加载完成
        page.goto(url)
        page.wait_for_load_state("networkidle")  # 等待页面加载完成

        # 获取页面内容
        page_content = page.content()

        # 使用正则表达式匹配 IP 地址和端口
        urls_found = re.findall(pattern, page_content)
        unique_urls = set(urls_found)  # 保证 URL 唯一性

        # 将 IP + 端口直接加入列表
        ip_ports.extend(unique_urls)
        print(unique_urls)
        # 进一步处理每个 IP 地址获取数据
        for ip_url in unique_urls:
            new_url = f"{ip_url}/iptv/live/1000.json?key=txiptv"
            try:
                page.goto(new_url)
                page.wait_for_load_state("networkidle")
                response = page.content()  # 获取响应内容
                data = page.evaluate("""() => JSON.parse(document.querySelector('body').innerText)""")

                for item in data.get("data", []):
                    typename = item.get("typename")
                    url = item.get("url")
                    if typename and url:
                        ip_ports.append(f"{ip_url} - {typename}，{url}")
            except Exception as e:
                print(f"Error fetching data from {new_url}: {e}")

    except Exception as e:
        print(f"Error while fetching {url}: {e}")

    return ip_ports

# 主函数
def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        with open("i.txt", "w", encoding="utf-8") as f:
            for url in urls:
                print(f"Processing: {url}")
                ip_ports = extract_info(page, url)
                for ip_port in ip_ports:
                    f.write(ip_port + "\n")  # 保存 IP + 端口信息
                # 请求之间添加随机延迟，确保每个 URL 提取完成后再处理下一个
                time.sleep(random.uniform(1, 3))  # 延迟 1 到 3 秒

        browser.close()

if __name__ == "__main__":
    main()
