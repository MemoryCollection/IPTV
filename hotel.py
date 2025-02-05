import requests
import re
import os
import json
import time
import m3u8
from concurrent.futures import ThreadPoolExecutor
import random
from typing import List, Dict, Any, Optional

def make_request(url: str, method: str = 'get', headers: Optional[Dict] = None, json_data: Optional[Dict] = None, timeout: int = 10) -> Optional[Dict]:
    try:
        response = requests.request(method, url, headers=headers, json=json_data, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        return None

def update_json_file(file_path: str, new_data: Dict, key: str = 'hotel_channels') -> None:
    try:
        existing_data = read_json_file(file_path)
        existing_data[key] = new_data
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"更新 JSON 文件时出错: {e}")

def read_json_file(file_path: str) -> Dict:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {'hotel': [], 'hotel_channels': {}}

def fetch_ips_360(query: str, size: int = 10) -> List[str]:
    token = os.getenv("TOKEN_360")
    if not token:
        print("请设置 TOKEN_360 环境变量")
        return []
    
    headers = {"X-QuakeToken": token, "Content-Type": "application/json"}
    data = {"query": query, "start": 0, "size": size, "ignore_cache": False, "latest": True, "shortcuts": ["610ce2adb1a2e3e1632e67b1"]}
    
    response = make_request(url="https://quake.360.net/api/v3/search/quake_service", method='post', headers=headers, json_data=data, timeout=10)
    
    if response:
        ip_data = response.get("data", [])
        urls = [f"{entry.get('ip')}:{entry.get('port')}" for entry in ip_data if entry.get('ip') and entry.get('port')]
        print("360IP搜索成功" if urls else "未找到匹配的 IP 数据")
        return urls
    return []

def clean_channel_name(name: str) -> str:
    try:
        # 移除所有非单词字符并转为大写（保留汉字）
        name = re.sub(r'[^\w]', '', name).upper()
        
        # 第一阶段：处理数字和符号替换
        digit_replacements = {
            "十七": "17",
            "十六": "16",
            "十五": "15",
            "十四": "14",
            "十三": "13",
            "十二": "12",
            "十一": "11",
            "十": "10",
            "一": "1",
            "二": "2",
            "三": "3",
            "四": "4",
            "五": "5",
            "六": "6",
            "七": "7",
            "八": "8",
            "九": "9",
            "＋": "+",
            "—": "",
        }
        # 按键长度降序排序，优先处理长数字（如“十一”在“十”之前）
        for old, new in sorted(digit_replacements.items(), key=lambda x: (-len(x[0]), x[0])):
            name = name.replace(old, new)
        
        other_replacements = {
            "上海东方卫视": "东方卫视",
            "上海卫视": "东方卫视",
            "中央": "CCTV",
            "央视": "CCTV",
            "CCTV5+体育赛事": "CCTV5+",
            "CCTV5赛事": "CCTV5+",
            "CCTV5+体育": "CCTV5+",
            "CCTV1综合": "CCTV1",
            "CCTV2财经": "CCTV2",
            "CCTV3综艺": "CCTV3",
            "CCTV4中文国际": "CCTV4",
            "CCTV4国际": "CCTV4",
            "CCTV5体育": "CCTV5",
            "CCTV6电影": "CCTV6",
            "CCTV7军事农业": "CCTV7",
            "CCTV7国防军事": "CCTV7",
            "CCTV7军农": "CCTV7",
            "CCTV7军事": "CCTV7",
            "CCTV17农业农村": "CCTV17",
            "CCTV17军农": "CCTV17",
            "CCTV17农业": "CCTV17",
            "CCTV8电视剧": "CCTV8",
            "CCTV9纪录": "CCTV9",
            "CCTV10科教": "CCTV10",
            "CCTV11戏曲": "CCTV11",
            "CCTV12社会与法": "CCTV12",
            "CCTV13新闻": "CCTV13",
            "CCTV新闻": "CCTV13",
            "CCTV14少儿": "CCTV14",
            "CCTV少儿": "CCTV14",
            "CCTV15音乐": "CCTV15",
            "CCTV音乐": "CCTV15",
            "金鹰卡通卫视": "金鹰卡通",
            "3沙卫视": "三沙卫视",
            "4川卫视": "四川卫视",
            "广东大湾区卫视": "大湾区卫视",
            "内蒙古卫视": "内蒙卫视",
            "CHC电影": "CHC高清电影",
            "动作电影": "CHC动作电影",
            "家庭电影": "家庭影院",
            "PLUS": "+",
            "高清": "",
            "超高": "",
            "HD": "",
            "标清": "",
            "频道": "",
            "台": "",
            "套": "",
            "第1": "1",
            "CCTVCCTV": "CCTV",
            "CHCCHC": "CHC",
            "移动": "",
            "CHC电影":"CHC高清电影"
        }
        # 按键长度降序处理其他规则
        for old, new in sorted(other_replacements.items(), key=lambda x: (-len(x[0]), x[0])):
            name = name.replace(old, new)
        if name == "家庭影院":
            name = "CHC家庭影院"
        return name
    except Exception as e:
        print(f"清理频道名称时出错: {e}")
        return name

def fetch_hotel_iptv(ip_list: List[str]) -> Dict:
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Upgrade-Insecure-Requests': '1'
    })

    filter_keywords = {"4K", "测试", "奥林匹克", "NEWS", "台球", "网球", "足球", "指南", "教育", "高尔夫"}
    results = {}
    ip_list = set(ip_list)

    def fetch_single_ip(ip: str) -> None:
        try:
            response = session.get(f'http://{ip}/iptv/live/1000.json?key=txiptv', timeout=2)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException:
            return

        if 'data' in data:
            channels = []
            for channel in data['data']:
                name = channel.get('name', '').upper()
                if any(keyword in name for keyword in filter_keywords):
                    continue
                name = clean_channel_name(name)
                channel_url = f"http://{ip}{channel.get('url', '')}"
                if "/tsfile/live/1015_1.m3u8?key=txiptv&playlive=1&authid=0" in channel_url:
                    name = "江苏卫视"
                channels.append([name, channel_url, channel.get('typename', '')])

            if channels:
                results[ip] = {'data': channels}
                print(f"获取 {ip} 成功，共 {len(channels)} 个频道")

    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(fetch_single_ip, ip_list)
    print(f"共获取 {len(results)} 个 IP 的 IPTV 频道")
    return results

def download_segment(url: str, duration: int = 5) -> float:
    start_time = time.time()
    try:
        response = requests.get(url, timeout=duration, stream=True)
        response.raise_for_status()

        total_data = 0
        for chunk in response.iter_content(chunk_size=1024*1024):
            total_data += len(chunk)
            if time.time() - start_time >= duration:
                break

        elapsed_time = time.time() - start_time
        return total_data / (elapsed_time * 1024 * 1024) if elapsed_time > 0 else 0
    except requests.exceptions.RequestException:
        return 0

def download_m3u8(url: str, duration: int = 10) -> float:
    start_time = time.time()
    try:
        response = requests.get(url, timeout=duration)
        response.raise_for_status()
        m3u8_obj = m3u8.loads(response.text)

        segment_urls = [seg.uri for seg in m3u8_obj.segments]
        speeds = []

        for segment_url in segment_urls:
            if not segment_url.startswith("http"):
                segment_url = url.rsplit('/', 1)[0] + '/' + segment_url
            speed = download_segment(segment_url, duration=2)
            speeds.append(speed)

            if time.time() - start_time >= duration:
                break

        return sum(speeds) / len(speeds) if speeds else 0
    except requests.exceptions.RequestException:
        return 0

def process_channel(channel: List, ip: str) -> tuple:
    try:
        name, url, typename = channel
        channel_speed = download_m3u8(url, duration=2)
        return name, channel_speed
    except Exception as e:
        print(f"处理通道时出错: {e}")
        return channel[0], 0

def calculate_ip_speed(ip: str, results: Dict, filtered_ip_list: List, filtered_channels: Dict) -> None:
    if ip not in results:
        return

    channels = results[ip]['data']
    target_channels = [channel for channel in channels if channel[0] in {'CCTV1', 'CCTV2', 'CCTV3'}]

    if len(target_channels) < 3:
        try:
            target_channels = random.sample(channels, 3)
        except Exception as e:
            print(f"随机采样频道时出错: {e}")
            return

    speeds = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for name, channel_speed in executor.map(lambda channel: process_channel(channel, ip), target_channels):
            if channel_speed > 0.2:
                speeds.append(channel_speed)
                if ip not in filtered_ip_list:
                    filtered_ip_list.append(ip)

    if speeds:
        ip_speed = sum(speeds) / len(speeds)
        print(f"{ip} 平均速度为 {ip_speed:.2f} MB/s")
        filtered_channels[ip] = {'speed': round(ip_speed, 2), 'data': channels}

def hotel_iptv(size: int = 10) -> Dict:
    filtered_channels = {}
    filtered_ip_list = []

    query = '((favicon:"6e6e3db0140929429db13ed41a2449cb" OR favicon:"34f5abfd228a8e5577e7f2c984603144" )) AND country_cn: "中国"'
    ip_list = fetch_ips_360(query, size)
    existing_ips = read_json_file('data/iptv.json')['hotel']
    ip_list = list(set(ip_list + existing_ips))

    print(f"去重后还有： {len(ip_list)} 个 IP")
    results = fetch_hotel_iptv(ip_list)

    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(lambda ip: calculate_ip_speed(ip, results, filtered_ip_list, filtered_channels), results.keys())

    update_json_file('data/iptv.json', filtered_channels, key='hotel_channels')
    update_json_file('data/iptv.json', filtered_ip_list, key='hotel')
    return filtered_channels

def extract_cctv_number(name: str) -> float:
    if "CCTV" in name:
        match = re.search(r'CCTV(\d+)', name)
        if match:
            return float(match.group(1))
        return float('inf')
    return float('inf')

def classify_and_sort(data: Dict) -> Dict:
    channel_keywords = {
        '中央频道': {'CCTV'},
        '卫视频道': {'卫视', '凤凰'},
        '影视剧场': {'CHC', '相声小品', '热播剧场', '经典电影', '谍战剧场', '家庭影院', '动作电影'}
    }

    groups = {
        '中央频道': [],
        '卫视频道': [],
        '影视剧场': [],
        '未分组': []
    }

    for ip, info in data.items():
        channels = info['data']
        speed = info['speed']

        for name, url, _ in channels:
            found_group = False
            for group_name, keywords in channel_keywords.items():
                if any(keyword in name for keyword in keywords):
                    groups[group_name].append((name, url, speed))
                    found_group = True
                    break
            
            if not found_group:
                groups['未分组'].append((name, url, speed))

    for group_name, channel_list in groups.items():
        channel_list.sort(key=lambda x: (x[0], -x[2]))

        if group_name == '中央频道':
            channel_list.sort(key=lambda x: (extract_cctv_number(x[0]), x[0], -x[2]))

    with open("hotel.txt", 'w', encoding='utf-8') as file:
        for group_name, channel_list in groups.items():
            file.write(f"{group_name},#genre#\n")
            for name, url, speed in channel_list:
                name = name.replace("CCTVCCTV", "CCTV")
                file.write(f"{name},{url},{speed}\n")
            file.write("\n")
            
    return groups

if __name__ == "__main__":
    ip_list = hotel_iptv(20)
    if ip_list:
        classify_and_sort(read_json_file('data/iptv.json')['hotel_channels'])
    else:
        print("未获取到有效的 IP 列表")