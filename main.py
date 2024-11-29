import os
import json
import socket
import requests
import threading
import http.client
from github import Github
from datetime import datetime
from bs4 import BeautifulSoup
from queue import Queue, Empty
from playwright.sync_api import sync_playwright
import re
import random
import time


def read_json_file(file_path):
    """
    读取 JSON 文件内容并返回字典数据。
    如果文件不存在，返回 None。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None

def write_json_file(file_path, data, overwrite=False):
    """
    写入 JSON 数据到文件。
    参数：
    - file_path: JSON 文件路径。
    - data: 要写入的字典数据。
    - overwrite: 为 True 时覆盖文件，为 False 时追加数据。
    """
    if overwrite:
        # 如果需要覆盖文件，直接写入数据
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            print(f"数据已覆盖写入到 {file_path}")
        except Exception as e:
            print(f"覆盖写入文件失败: {e}")
    else:
        # 如果需要追加数据，先读取现有文件
        existing_data = read_json_file(file_path)
        
        if not existing_data:
            # 如果文件为空或不存在，初始化数据结构
            existing_data = {"详情": {"iptv": 0, "ip": []}, "直播": {}}

        # 处理 IP 地址
        new_ips = [ip for ip in data["详情"]["ip"] if ip not in existing_data["详情"]["ip"]]
        existing_data["详情"]["ip"].extend(new_ips)
        existing_data["详情"]["iptv"] += data["详情"]["iptv"]

        # 处理频道数据，避免重复添加
        for ip, channels in data["直播"].items():
            if ip not in existing_data["直播"]:
                existing_data["直播"][ip] = channels
            else:
                existing_data["直播"][ip].extend([channel for channel in channels if channel not in existing_data["直播"][ip]])

        # 写入合并后的数据
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(existing_data, file, ensure_ascii=False, indent=4)
            print(f"数据已追加写入到 {file_path}")
        except Exception as e:
            print(f"追加写入文件失败: {e}")

def check_ip_port(ip_port):
    """检查 IP 和端口是否可连接，并尝试访问 /status/，返回 True 表示可用，False 表示不可用。"""
    ip, port = ip_port.split(":")
    try:
        conn = http.client.HTTPConnection(ip, int(port), timeout=5)
        conn.request("GET", "/status/")
        response = conn.getresponse()
        
        # 检查状态码是否为 200 和网页内容中是否包含 "udpxy"
        if response.status == 200:
            # 读取网页内容
            body = response.read().decode()
            if "udpxy" in body:
                return True
        return False
    except (socket.timeout, socket.error, http.client.HTTPException):
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def playwright_get_ip(area, page_number=0):
    ip_list = set()  # 使用集合去重
    url = "http://tonkiang.us/hoteliptv.php"

    with sync_playwright() as p:
        # 启动浏览器并设置无头模式
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # 访问目标网站
            page.goto(url)

            # 循环处理每个地区
            for area_name in area:
                try:
                    # 定位到搜索框并输入地区名称
                    search_box = page.locator('#search')
                    search_box.fill(area_name)  # 输入地区名
                    search_box.press('Enter')  # 模拟按下 Enter 键提交

                    # 等待搜索结果加载完成
                    page.wait_for_selector('#search')  # 等待输入框回到可用状态或根据页面元素变化

                    # 提取第一页的 IP 地址
                    html_content = page.content()
                    pattern = r"(\d+\.\d+\.\d+\.\d+:\d+)"
                    ip_ports = re.findall(pattern, html_content)
                    ip_list.update(ip_ports)  # 将提取到的 IP:端口加入到集合中，自动去重
                    print(f"第1页提取的 IP 地址：", ip_ports)
                    # 处理分页（如果页数大于1）
                    if page_number > 1:
                        for page_num in range(2, page_number + 1):  # 从第 2 页开始
                            try:
                                print(f"尝试获取第 {page_num} 页的翻页按钮...")

                                # 更新 XPath，按区域和页面匹配 href
                                # 这里直接传入 area_name 作为字符串

                                page_button = page.locator(
                                    f"a[href*='?page={page_num}&iphone={area_name}&code=']:has(div:has-text('{page_num}'))")
                                print(f"找到第 {page_num} 页的翻页按钮，正在点击...")
                                page_button.click()

                                delay = random.uniform(2, 5)  # 随机延时
                                print(f"等待 {delay:.2f} 秒")
                                time.sleep(delay)

                                # 等待新页面加载并检测内容变化
                                page.wait_for_selector('.result')

                                # 获取并提取新页面的 IP 地址
                                html_content = page.content()
                                ip_ports = re.findall(pattern, html_content)
                                ip_list.update(ip_ports)  # 将提取到的 IP:端口加入到集合中，自动去重
                                print(f"第 {page_num} 页提取的 IP 地址：", ip_ports)

                            except Exception as e:
                                print(f"处理第 {page_num} 页时发生错误: {e}")
                                break  # 出现问题停止处理分页

                except Exception as e:
                    print(f"Error while processing area {area_name}: {e}")

        finally:
            browser.close()

    print(ip_list)
    return {'ip_list': list(ip_list), 'error': None}

def get_iptv(ip_list, output_file="data/Origfile.json", overwrite=False):
    """爬取频道信息，并返回按 IP 分组的频道数据"""
    
    ip_data = {"详情": {"iptv": 0,"ip": []}, "直播": {}}

    for ip in ip_list:
        existing_data = read_json_file(output_file)
        if ip in existing_data["详情"]["ip"]:
            print(f"IP {ip} 已存在，跳过爬取。")
            continue

        if not check_ip_port(ip): 
            print(f"IP {ip} 无法连接，跳过爬取。")
            continue

        url = f"http://tonkiang.us/allllist.php?s={ip}&c=false"
        headers = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "proxy-connection": "keep-alive",
            "x-requested-with": "XMLHttpRequest",
            "cookie": "REFERER2=Over; REFERER1=NzDbYr1aObDckO0O0O",
            "Referer": f"http://tonkiang.us/hotellist.html?s={url}",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
        response = requests.get(url, headers=headers)
        channels = []

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.find_all(class_='result')

            for result in results:
                channel_name = result.find('div', style='float: left;')
                m3u8_url = result.find('td', style='padding-left: 6px;')

                if channel_name and m3u8_url:
                    channels.append([channel_name.get_text(strip=True), m3u8_url.get_text(strip=True), 0])

            if channels:
                ip_data["详情"]["ip"].append(ip)
                ip_data["直播"][ip] = channels
                ip_data["详情"]["iptv"] += len(channels)
                print(f"IP {ip} 爬取了 {len(channels)} 个频道。")
        else:
            print(f"请求失败，状态码: {response.status_code}，IP: {ip}")

    write_json_file(output_file, ip_data, overwrite=overwrite)
    return ip_data

def filter_and_process_channel_data(ip_data, output_file="data/itv.json"):
    """对频道数据进行过滤和处理，并将结果写入到指定文件"""

    db_config = read_json_file("data/db.json")["data"]

    if not db_config or "keywords" not in db_config or "discard_keywords" not in db_config or "replace_keywords" not in db_config:
        print("错误：db_config 配置缺失必要字段")
        return None

    try:
        keywords = [kw.lower() for kw in db_config["keywords"]]
        discard_keywords = [dk.lower() for dk in db_config["discard_keywords"]]
        replace_keywords = {k.lower(): v for k, v in db_config["replace_keywords"].items()}

        processed_data = {"详情": {"iptv": 0,"ip": []}, "直播": {}}
        channel_count = 0  

        for ip, channels in ip_data["直播"].items():
            ip_channels = [] 

            for channel in channels:
                if len(channel) == 3:
                    channel_name, url, speed = channel

                    for k, v in replace_keywords.items():
                        channel_name = re.sub(k, v, channel_name, flags=re.IGNORECASE)

                    channel_name = channel_name.upper()

                    if any(dk in channel_name.lower() for dk in discard_keywords):
                        continue

                    if keywords and not any(kw in channel_name.lower() for kw in keywords):
                        continue

                    url = re.sub(r"(^http://|[ #])", "", url)
                    url = "http://" + url if not url.startswith("http://") else url

                    ip_channels.append([channel_name, url, speed])
                    channel_count += 1  

            if ip_channels:
                processed_data["直播"][ip] = ip_channels
                processed_data["详情"]["ip"].append(ip)  

        processed_data["详情"]["iptv"] = channel_count  

        if "iptv" in processed_data["详情"]:
            processed_data["详情"]["iptv"] = str(processed_data["详情"]["iptv"])  # 示例修改：将频道总数转换为字符串

        write_json_file("data/itv.json", processed_data, True)
        
        return processed_data

    except Exception as e:
        print(f"处理失败: {e}")
        return None

def test_download_speed(url, test_duration=3):
    """
    测试下载速度，固定访问时间为 test_duration 秒，并加入速度阈值。
    如果下载速度低于阈值，返回 0。
    """
    try:
        start_time = time.time()
        response = requests.get(url, timeout=test_duration + 5, stream=True)
        response.raise_for_status()

        downloaded = 0
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time >= test_duration:
                break

            for chunk in response.iter_content(chunk_size=4096):
                downloaded += len(chunk)
                elapsed_time = time.time() - start_time
                if elapsed_time >= test_duration:
                    break

        speed = downloaded / test_duration if test_duration > 0 else 0 
        speed_mb_s = round(speed / (1024 * 1024), 2)  

        return speed_mb_s

    except requests.RequestException:
        return 0

def measure_download_speed_parallel(data, MinSpeed=0.3, Vmax=1.4):
    """
    并行测量多个 IP 地址下的频道下载速度，
    每个 IP 使用一个线程，且每个线程内串行测试该 IP 下的频道。
    在测试频道速度之前，首先检查 IP 地址和端口是否可连接，
    如果无法连接，则跳过该 IP 地址的测速。
    MinSpeed 是最小速度。
    Vmax 是最大速度。
    """
    queue = Queue()
    results = {"详情": {"iptv": sum(len(channels) for channels in data.values()), "ip": list(data.keys())}, "直播": {}}

    total_channels = results["详情"]["iptv"]  # 统计总频道数
    completed_channels = 0  # 记录已完成的频道数

    # 保证至少 8 个线程
    max_threads = max(os.cpu_count() or 4, 8)

    # 先对所有 IP 进行连接测试，筛选出可用的 IP
    valid_ips = []
    for ip, channels in data.items():
        if check_ip_port(ip):
            valid_ips.append((ip, channels))

    # 将可用的 IP 和频道添加到队列中
    for ip, channels in valid_ips:
        queue.put((ip, channels))

    def worker():
        nonlocal completed_channels
        thread_id = threading.current_thread().name
        while True:
            try:
                ip, channels = queue.get(timeout=1)
            except Empty:
                break

            channel_speeds = []
            for index, (name, url, _) in enumerate(channels):
                speed = test_download_speed(url)
                speed = round(speed, 2)

                if speed > MinSpeed and speed < Vmax:
                    channel_speeds.append([name, url, speed])

                    # 更新已完成的频道数
                completed_channels += 1

                # 每完成 100 个频道，打印进度百分比
                if completed_channels % 100 == 0 or completed_channels == total_channels:
                    percent_complete = (completed_channels / total_channels) * 100
                    print(f"\r总体进度: {percent_complete:.2f}% ({completed_channels}/{total_channels})", end="")

            if channel_speeds:
                results["直播"][ip] = channel_speeds
            queue.task_done()

    threads = []
    for _ in range(max_threads):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)

    queue.join()

    for thread in threads:
        thread.join()

    write_json_file("data/itv.json", results, overwrite=True)
    return results


def natural_key(string):
    """自然排序的辅助函数"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', string)]

def group_and_sort_channels(data):
    """根据规则分组并排序频道信息，并保存到 itvlist.txt"""
    channels = []
    for ip, channel_list in data["直播"].items():
        channels.extend(channel_list)

    groups = {
        '央视频道': [],
        '卫视频道': [],
        '其他频道': []
    }

    for name, url, speed in channels:
        if 'cctv' in name.lower():
            groups['央视频道'].append((name, url, speed))
        elif '卫视' in name or '凤凰' in name:
            groups['卫视频道'].append((name, url, speed))
        else:
            groups['其他频道'].append((name, url, speed))

    for group in groups.values():
        group.sort(key=lambda x: ( natural_key(x[0]), -x[2] if x[2] is not None else float('-inf') ))

    with open('itvlist.txt', 'w', encoding='utf-8') as file:
        for group_name, channel_list in groups.items():
            file.write(f"{group_name},#genre#\n")
            for name, url, speed in channel_list:
                file.write(f"{name},{url},{speed}\n")
            file.write("\n")

        current_time_str = datetime.now().strftime("%m-%d-%H")
        file.write(
            f"{current_time_str},#genre#:\n{current_time_str},https://raw.gitmirror.com/MemoryCollection/IPTV/main/TB/mv.mp4\n"
        )

    print("分组后的频道信息已保存到 itvlist.txt ")
    return groups

def upload_file_to_github(token, repo_name, file_path, folder='', branch='main'):
    """
    将结果上传到 GitHub，并指定文件夹
    """
    g = Github(token)
    repo = g.get_user().get_repo(repo_name)
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    git_path = f"{folder}/{file_path.split('/')[-1]}" if folder else file_path.split('/')[-1]

    try:
        contents = repo.get_contents(git_path, ref=branch)
    except:
        contents = None

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if contents:
            repo.update_file(contents.path, current_time, content, contents.sha, branch=branch)
            print("文件已更新")
        else:
            repo.create_file(git_path, current_time, content, branch=branch)
            print("文件已创建")
    except Exception as e:
        print("文件上传失败:", e)


if __name__ == "__main__":

    ip_data = read_json_file("data/itv.json")
    if int(ip_data["详情"]["iptv"]) <600:
        area = ["北京", "辽宁"]
        # page_number>1则进行翻页
        get_iptv(playwright_get_ip(area,page_number=3)["ip_list"])
        filter_and_process_channel_data(read_json_file("data/Origfile.json"))
    iptv_data = read_json_file("data/itv.json")
    results = measure_download_speed_parallel(iptv_data["直播"])
    group_and_sort_channels(results)
    token = os.getenv("GITHUB_TOKEN")
    if token:
        upload_file_to_github(token, "IPTV", "itvlist.txt")
        upload_file_to_github(token, "IPTV", "data/itv.json", folder="data")




#
# def selenium_get_ip(area, page_number=0):
#     # 初始化浏览器配置
#     options = webdriver.ChromeOptions()
#     options.add_argument("--headless")  # 无头模式，避免打开浏览器窗口
#     options.add_argument(
#         '--host-resolver-rules=MAP *.googlesyndication.com 127.0.0.1,'
#         'MAP *.googletagmanager.com 127.0.0.1,'
#         'MAP *.histats.com 127.0.0.1,'
#         'MAP *.2mdn-cn.net 127.0.0.1'
#     )
#     options.add_argument('--no-sandbox')  # 禁用沙箱
#     options.add_argument('--disable-dev-shm-usage')  # 禁用 /dev/shm 使用
#     options.add_argument('--disable-gpu')  # 禁用 GPU 加速
#     options.add_argument('--remote-debugging-port=9222')  # 使 DevTools 可用
#     options.add_argument('--disable-software-rasterizer')  # 禁用软件光栅化
#     driver = webdriver.Chrome(options=options)
#
#     ip_list = set()  # 使用集合去重
#     url = "http://tonkiang.us/hoteliptv.php"
#
#     # 访问目标网站
#     driver.get(url)
#
#     try:
#         # 循环处理每个地区
#         for area_name in area:
#             try:
#                 # 定位到搜索框并输入地区名称
#                 search_box = WebDriverWait(driver, 10).until(
#                     EC.presence_of_element_located((By.ID, "search"))
#                 )
#                 search_box.clear()  # 清空输入框
#                 search_box.send_keys(area_name)  # 输入地区名
#                 search_box.send_keys(Keys.RETURN)  # 模拟按下 Enter 键提交
#
#                 # 等待搜索结果加载完成
#                 WebDriverWait(driver, 10).until(
#                     EC.presence_of_element_located((By.ID, "search"))  # 或者根据页面元素的变化来判断
#                 )
#
#                 # 提取第一页的 IP 地址
#                 html_content = driver.page_source
#                 pattern = r"(\d+\.\d+\.\d+\.\d+:\d+)"
#                 ip_ports = re.findall(pattern, html_content)
#                 ip_list.update(ip_ports)  # 将提取到的 IP:端口加入到集合中，自动去重
#
#                 # 处理分页（如果页数大于1）
#                 if page_number > 1:
#                     for page in range(2, page_number + 1):  # 从第 2 页开始
#                         try:
#                             print(f"尝试获取第 {page} 页的翻页按钮...")
#
#                             # 更新 XPath，按区域和页面匹配 href
#                             # 这里直接传入 area_name 作为字符串
#                             page_button = WebDriverWait(driver, 15).until(
#                                 EC.presence_of_element_located(
#                                     (By.XPATH, f"//a[contains(@href, '?page={page}&iphone={area_name}')]"))
#                             )
#                             print(f"找到第 {page} 页的翻页按钮，正在点击...")
#                             page_button.click()  # 点击页码链接
#
#                             delay = random.uniform(2, 5)  # 随机延时
#                             print(f"等待 {delay:.2f} 秒")
#                             time.sleep(delay)
#
#                             # 等待新页面加载并检测内容变化
#                             WebDriverWait(driver, 10).until(
#                                 EC.presence_of_all_elements_located((By.CLASS_NAME, "result"))
#                             )
#
#                             # 获取并提取新页面的 IP 地址
#                             html_content = driver.page_source
#                             ip_ports = re.findall(pattern, html_content)
#                             ip_list.update(ip_ports)  # 将提取到的 IP:端口加入到集合中，自动去重
#                             print(f"第 {page} 页提取的 IP 地址：", ip_ports)
#
#                         except Exception as e:
#                             print(f"处理第 {page} 页时发生错误: {e}")
#                             break  # 出现问题停止处理分页
#
#             except Exception as e:
#                 print(f"Error while processing area {area_name}: {e}")
#
#     finally:
#         driver.quit()
#
#     print(ip_list)
#     return {'ip_list': list(ip_list), 'error': None}
#
