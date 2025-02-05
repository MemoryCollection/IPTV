import json
import os
from typing import List, Dict
import requests

# 写入 JSON 文件（仅更新酒店 IPTV 部分）
def update_json_file(file_path: str, new_data: Dict, key: str = 'multicast_channels') -> None:
    """更新 JSON 文件中的特定部分，而不是覆盖整个文件"""
    try:
        existing_data = read_json_file(file_path)
        existing_data[key] = new_data
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"更新 JSON 文件时出错: {e}")


# 读取 JSON 文件
def read_json_file(file_path: str) -> Dict:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"文件未找到: {file_path}")
    except Exception as e:
        print(f"读取 JSON 文件时出错: {e}")
    return {'multicast_channels': {}, 'multicast': []}


def fetch_ips(token: str) -> Dict:
    """根据城市和运营商信息，从 API 获取对应 IP 和端口"""
    result_data = {}
    headers = {"X-QuakeToken": token, "Content-Type": "application/json"}
    CITY_LIST = ["北京"]
    ISP_LIST = ["电信", "联通"]
    IP_FETCH_COUNT = 20

    for city in CITY_LIST:
        for isp in ISP_LIST:
            query = f'((country: "china" AND app:"udpxy") AND province_cn: "{city}") AND isp: "中国{isp}"'
            data = {
                "query": query,
                "start": 0,
                "size": IP_FETCH_COUNT,
                "ignore_cache": False,
                "latest": True,
                "shortcuts": ["610ce2adb1a2e3e1632e67b1"]
            }

            try:
                response = requests.post(
                    url="https://quake.360.net/api/v3/search/quake_service",
                    headers=headers,
                    json=data,
                    timeout=10
                )

                if response.status_code == 200:
                    ip_data = response.json().get("data", [])
                    urls = [f"http://{entry.get('ip')}:{entry.get('port')}" for entry in ip_data if 'ip' in entry and 'port' in entry]
                    if urls:
                        result_data[f"{city}{isp}"] = urls
                        print(f"成功获取 {city}, {isp} 的 IP 地址！")
                        print(f"可用 IP 地址：{urls}")
                else:
                    print(f"城市 {city}, 运营商 {isp} 查询失败，状态码：{response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"查询城市 {city}, 运营商 {isp} 时出错：{e}")

    return result_data


def process_channels(ip_url: str, channels: List[List[str]]) -> Dict:
    """处理单个 IP 地址的组播 URL"""
    output_data = {}
    try:
        response = requests.get(f"{ip_url}/status/", timeout=3)
        if response.status_code == 200:
            for name, multicast_url in channels:
                output_data[name] = f"{ip_url}{multicast_url}"
    except requests.exceptions.RequestException as e:
        pass
    return output_data


if __name__ == "__main__":
    token_360 = os.getenv("token_360")
    if not token_360:
        exit("未设置：token_360，程序无法执行")

    ip_list = fetch_ips(token_360)

    if not ip_list:
        exit("未获取到有效的 IP 地址，程序无法执行")

    print(f"可用 IP 地址：{ip_list}")

    multicast_channels = {}
    multicast = {}

    for province, ip_urls in ip_list.items():
        print(f"正在处理 {province} 的 IP 地址...")
        multicast_file_path = os.path.join("data/udp/", f"{province}.txt")
        try:
            with open(multicast_file_path, 'r', encoding='utf-8') as multicast_file:
                channels = [line.strip().split(',') for line in multicast_file if len(line.strip().split(',')) == 2]

                multicast.setdefault(province, [])

                for ip_url in ip_urls:
                    try:
                        output_data = process_channels(ip_url, channels)
                        if output_data:
                            multicast_channels[ip_url] = {'speed': 0, 'data': output_data}
                            multicast[province].append(ip_url)
                    except Exception as e:
                        print(f"处理 {ip_url} 时出错: {e}")

        except FileNotFoundError:
            print(f"未找到 {province} 的 UDP 组播文件，请检查文件路径是否正确！")
        except Exception as e:
            print(f"读取 {province} 的 UDP 组播文件时出错: {e}")


    update_json_file("data/iptv.json", multicast_channels, key='multicast_channels')
    update_json_file("data/iptv.json", multicast, key='multicast')




    # existing_ips = read_json_file('data/iptv.json')['multicast']
    # ip_list = list(set(ip_list + existing_ips))
    # print(f"可用 IP 地址：{ip_list}")


    # ip_list = merge_and_deduplicate(ip_list, read_json_file("data/multicast.json"))
    # ip_list = read_json_file("data/multicast.json")
    # ip_list = asyncio.run(test_and_get_working_ips(ip_list))
    # write_json_file("data/multicast.json", ip_list)
    # ip_list = process_ip_list(ip_list)
    # ip_list = test_download_speed(ip_list)
    # group_and_sort_channels(ip_list)
