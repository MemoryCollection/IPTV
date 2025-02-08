import requests
import m3u8
import time
from urllib.parse import urljoin
from io import BytesIO
import av
import re
import os
import json
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional

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


def analyze_video_resolution(content):
    """使用PyAV库分析视频分辨率"""
    try:
        buffer = BytesIO(content)
        with av.open(buffer, format='mpegts') as container:
            for stream in container.streams:
                if stream.type == 'video':
                    return (stream.width, stream.height)
            return "0x0"
    except Exception:
        return "0x0"


def get_m3u8_info(m3u8_url):
    """获取m3u8分片信息和视频参数"""
    try:
        # 获取m3u8文件内容
        response = session.get(m3u8_url, timeout=2)
        response.raise_for_status()
        playlist = m3u8.loads(response.text)

        if not playlist.segments:
            return 0, "0x0"

        # 获取第一个分片URL
        first_segment = playlist.segments[0]
        segment_url = urljoin(m3u8_url, first_segment.uri)

        # 尝试获取分片时长
        segment_duration = first_segment.duration
        if segment_duration is None:
            segment_duration = 10  # 默认时长为10秒

        # 计算2秒数据的大致字节数
        start_time = time.time()
        try:
            # 发送HEAD请求获取分片大小
            head_response = session.head(segment_url, timeout=2)
            head_response.raise_for_status()
            segment_size = int(head_response.headers.get('Content-Length', 0))
            data_to_download = int(segment_size * (2 / segment_duration))
        except (requests.exceptions.RequestException, ValueError):
            data_to_download = None

        if data_to_download is not None:
            headers = {'Range': f'bytes=0-{data_to_download - 1}'}
            seg_response = session.get(segment_url, headers=headers, timeout=2)
        else:
            seg_response = session.get(segment_url, timeout=2)
        seg_response.raise_for_status()
        download_time = time.time() - start_time

        content = seg_response.content
        file_size = len(content)

        # 计算下载速度（MB/s）
        speed_mbp = (file_size / (1024 ** 2)) / download_time if download_time > 0 else 0
        # 获取分辨率
        resolution = analyze_video_resolution(content)

        return round(speed_mbp, 2), resolution
    except requests.exceptions.RequestException:
        return 0, "0x0"


def update_json_file(new_data: Dict, key: str = 'hotel') -> None:
    file_path = 'data/iptv.json'
    try:
        existing_data = read_json_file()
        existing_data[key] = new_data
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"更新 JSON 文件时出错: {e}")


def read_json_file() -> Dict:
    file_path = 'data/iptv.json'
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'hotel': [], 'hotel_channels': {}}


def make_request(url: str, method: str = 'get', headers: Optional[Dict] = None, json_data: Optional[Dict] = None,
                 timeout: int = 10) -> Optional[Dict]:
    try:
        response = session.request(method, url, headers=headers, json=json_data, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None


def fetch_ips_360(query: str, size: int = 10) -> List[str]:
    token = os.getenv("TOKEN_360")
    if not token:
        print("请设置 TOKEN_360 环境变量")
        return []

    headers = {"X-QuakeToken": token, "Content-Type": "application/json"}
    data = {"query": query, "start": 0, "size": size, "ignore_cache": False, "latest": True,
            "shortcuts": ["610ce2adb1a2e3e1632e67b1"]}

    response = make_request(url="https://quake.360.net/api/v3/search/quake_service", method='post', headers=headers,
                            json_data=data, timeout=10)

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
            "家庭电影": "家庭影院",
            "PLUS": "+",
            "高清": "",
            "超高": "",
            "超清": "",
            "HD": "",
            "标清": "",
            "频道": "",
            "台": "",
            "套": "",
            "第1": "1",
            "CCTVCCTV": "CCTV",
            "CHCCHC": "CHC",
            "移动": ""
        }
        # 按键长度降序处理其他规则
        if "高清电影" not in name:
            for old, new in sorted(other_replacements.items(), key=lambda x: (-len(x[0]), x[0])):
                name = name.replace(old, new)
        if name == "家庭影院":
            name = "CHC家庭影院"
        if name == "动作电影":
            name = "CHC动作电影"

        return name
    except Exception:
        return name


def fetch_hotel_iptv(ip_list: List[str]) -> Dict:
    filter_keywords = {"4K", "测试", "奥林匹克", "NEWS", "台球", "网球", "足球", "指南", "教育", "高尔夫"}
    channels = []
    hotel_s = []
    ip_list = set(ip_list)

    def fetch_single_ip(ip: str) -> None:
        try:
            response = session.get(f'http://{ip}/iptv/live/1000.json?key=txiptv', timeout=2)
            response.raise_for_status()
            data = response.json()
            
        except requests.exceptions.RequestException:
            return

        if 'data' in data:
            hotel_s.append(ip)
            for channel in data['data']:
                name = channel.get('name', '').upper()
                if any(keyword in name for keyword in filter_keywords):
                    continue
                name = clean_channel_name(name)
                channel_url = f"http://{ip}{channel.get('url', '')}"
                if "/tsfile/live/1015_1.m3u8?key=txiptv&playlive=1&authid=0" in channel_url:
                    name = "江苏卫视"
                if 'udp://@' not in channel_url:
                    channels.append([name, channel_url])

    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(fetch_single_ip, ip_list)
    update_json_file(hotel_s, key='hotel')
    print(f"共获取 {len(channels)} 个 IPTV 频道")
    return channels


def extract_cctv_number(name: str) -> float:
    if "CCTV" in name:
        match = re.search(r'CCTV(\d+)', name)
        if match:
            return float(match.group(1))
        return float('inf')
    return float('inf')


def classify_and_sort(data: List[Dict]) -> Dict:
    channel_keywords = {
        '中央频道': {'CCTV'},
        '卫视频道': {'卫视', '凤凰'},
        '影视剧场': {'CHC', '相声小品', '热播剧场', '经典电影', '谍战剧场', '家庭影院', '动作电影', '亚洲电影'}
    }

    groups = {
        '中央频道': [],
        '卫视频道': [],
        '影视剧场': [],
        '未分组': []
    }

    for entry in data:
        name = entry["name"]
        url = entry.get("url", "")  # 假设原代码里后续能补充这里的 url 逻辑
        speed = entry["speed"]
        resolution = entry["resolution"]

        found_group = False
        for group_name, keywords in channel_keywords.items():
            if any(keyword in name for keyword in keywords):
                groups[group_name].append((name, url, speed, resolution))
                found_group = True
                break

        if not found_group:
            groups['未分组'].append((name, url, speed, resolution))

    def custom_sort_key(item):
        name = item[0]
        resolution_str = item[3]
        speed = item[2]
        try:
            width, height = map(int, resolution_str.split('x'))
            resolution = width * height
        except ValueError:
            resolution = 0
        cctv_num = extract_cctv_number(name)
        return (cctv_num if "CCTV" in name else float('inf'), name, -resolution, -speed)

    for group_name, channel_list in groups.items():
        channel_list.sort(key=custom_sort_key)

    with open("hotel.txt", 'w', encoding='utf-8') as file:
        for group_name, channel_list in groups.items():
            file.write(f"{group_name},#genre#\n")
            for name, url, speed, resolution in channel_list:
                if speed > 0.3:  # 速度过滤
                    name = name.replace("CCTVCCTV", "CCTV")
                    file.write(f"{name},{url},{speed},{resolution}\n")
            file.write("\n")

    return groups


def process_iptv(iptv):
    global processed_count, iptv_m
    processed_count += 1
    
    name, url = iptv
    speed, resolution = get_m3u8_info(url)
    if resolution:
        resolution_str = f"{resolution[0]}x{resolution[1]}"
    else:
        resolution_str = '0x0'
    print(f"第 {processed_count}/{iptv_m} 个 IPTV 频道: {name} - {speed} MB/s - {resolution_str}")
    return {
        "name": name,
        "url": url,
        "speed": speed,
        "resolution": resolution_str
    }


if __name__ == '__main__':
    global iptv_m,processed_count
    # 360IP搜索
    query = '((favicon:"6e6e3db0140929429db13ed41a2449cb" OR favicon:"34f5abfd228a8e5577e7f2c984603144" )) AND country_cn: "中国"'
    existing_ips = read_json_file()['hotel']
    ip_list = list(set(fetch_ips_360(query, size=10) + existing_ips))
    print(f"合并后共获取 {len(ip_list)} 个 IP 地址")
    iptv_list = fetch_hotel_iptv(ip_list)
    iptv_m = len(iptv_list)
    processed_count = 0
    with ThreadPoolExecutor(max_workers=16) as executor:
        iptv_list_dict = list(executor.map(process_iptv, iptv_list))

    result = classify_and_sort(iptv_list_dict)
    print("IPTV 信息处理完成")
