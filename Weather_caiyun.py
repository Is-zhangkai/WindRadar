#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@Project        ：WindRadar 
@File           ：Weather_caiyun.py
@Author         ：zhangkai
@Date           ：2026/5/8 14:05 
@Version        : 1.0.0
@Description    : 通过彩云天气API获取天气和空气质量，保存到数据库和csv
@Record         :

@Issue          : 20260508能见度数值异常，aqi不稳定
"""

import requests
import sqlite3
import logging
from datetime import datetime
import signal
import csv
import threading
import os
from zoneinfo import ZoneInfo

# ========== 配置==========
# 经纬度配置
# LATITUDE = "43.85"  # 纬度
# LONGITUDE = "125.41"  # 经度
LOCATION = "125.41,43.85"
API_KEY = "BjtegIGBc0vMHwqJ"  # 演示密钥，仅用于测试

INTERVAL = 3600  # 采集间隔（秒）
# 彩云天气API接口
url = f"https://api.caiyunapp.com/v2.6/{API_KEY}/{LOCATION}/realtime"

# 当前使用的数据表名，改名修改这里(数据库表名,-log,csv文件名)
# CURRENT_TABLE = "weather_records_20260508"
# 按日期命名
today = datetime.now().strftime("%Y%m%d")
CURRENT_TABLE = f"weather_records_{today}"
# CURRENT_TABLE = f"weather_records"
"""

"""
# 数据保存路径
Data_DIR = "weather_data_caiyun"  # 文件目录
# log_dir = os.path.join(Data_DIR, "log")

os.makedirs(Data_DIR, exist_ok=True)  # 确保目录存在
# os.makedirs(log_dir, exist_ok=True)          # 如果目录不存在则创建
DB_FILENAME = "weather_data_caiyun.db"  # SQLite数据库文件路径
CSV_FILENAME = f"{CURRENT_TABLE}_caiyun.csv"  # CSV文件名
# LOG_FILENAME = f"{CURRENT_TABLE}.log"  # log文件名
LOG_FILENAME = "weather_fetcher_caiyun.log"  # 日志文件名
DB_PATH = os.path.join(Data_DIR, DB_FILENAME)
csv_path = os.path.join(Data_DIR, CSV_FILENAME)
log_path = os.path.join(Data_DIR, LOG_FILENAME)

# ========== 设置日志 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),  # 输出到文件
        logging.StreamHandler()  # 同时输出到控制台
    ]
)


# ========== CSV文件配置 ==========
# # 按日期新建文件
# def get_csv_path():
#     """获取CSV文件路径（按日期分文件）"""
#     os.makedirs(Data_DIR, exist_ok=True)
#     today = datetime.now().strftime("%Y%m%d")
#     return os.path.join(Data_DIR, f"weather_{today}.csv")


# ========== 初始化数据库 ==========
def init_db():
    """创建SQLite数据表（如果不存在）"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA auto_vacuum = FULL")
    cursor = conn.cursor()

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {CURRENT_TABLE}  (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            fetch_time TEXT NOT NULL,      -- 采集时间（ISO格式）
            text TEXT,                  -- 天气描述
            obsTime TEXT,                  -- 数据观测时间
            temp TEXT,                     -- 温度
            feels_like TEXT,               -- 体感温度
            humidity TEXT,                 -- 相对湿度，百分比数值
            wind_speed TEXT,               -- 风速
            wind_dir TEXT,                 -- 风向
            wind360 TEXT,                  -- 风向角
            windScale TEXT,                -- 风力等级
            pressure TEXT,                 -- 气压 默认单位：百帕
            visibility TEXT,               -- 能见度默认单位：公里

            -- 空气质量数据（新增）
            aqi REAL,                 -- AQI指数

            -- 污染物浓度（新增）
            pm2p5 REAL,                    -- PM2.5浓度 (μg/m3)
            pm10 REAL,                     -- PM10浓度 (μg/m3)
            no2 REAL,                      -- 二氧化氮浓度 (ppb)
            o3 REAL,                       -- 臭氧浓度 (ppb)
            co REAL,                       -- 一氧化碳浓度 (ppm)

            raw_response TEXT              -- 天气原始返回数据（备用）
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("数据库初始化完成")
    logging.info(f"文件保存目录:{os.path.join(Data_DIR, CSV_FILENAME)} ")

# ========== 转换中文天气描述 ==========
def convert_skycon_to_weather(skycon_code):
    """
    将彩云天气的skycon代码转换为中文天气描述
    Args:
        skycon_code (str): 彩云API返回的天气代码，如 "PARTLY_CLOUDY_DAY"
    Returns:
        str: 中文天气描述，如 "多云"
    """
    if not skycon_code:
        return None

    weather_map = {
        "CLEAR_DAY": "晴",
        "CLEAR_NIGHT": "晴",
        "PARTLY_CLOUDY_DAY": "多云",
        "PARTLY_CLOUDY_NIGHT": "多云",
        "CLOUDY": "阴",
        "LIGHT_HAZE": "轻度雾霾",
        "MODERATE_HAZE": "中度雾霾",
        "HEAVY_HAZE": "重度雾霾",
        "LIGHT_RAIN": "小雨",
        "MODERATE_RAIN": "中雨",
        "HEAVY_RAIN": "大雨",
        "STORM_RAIN": "暴雨",
        "FOG": "雾",
        "LIGHT_SNOW": "小雪",
        "MODERATE_SNOW": "中雪",
        "HEAVY_SNOW": "大雪",
        "STORM_SNOW": "暴雪",
        "DUST": "浮尘",
        "SAND": "沙尘",
        "WIND": "大风",
    }
    return weather_map.get(skycon_code, skycon_code)
# ========== 计算风向 ==========
def wind_direction_8(angle):
    """
    获取8方位风向
    Args:
        angle (float): 风向角度
    Returns:
        str: 8方位风向，如"北风"、"东风"等
    """
    if angle is None:
        return None

    angle = angle % 360
    # 8方位定义（每个45度）
    directions = [
        ("北风", 337.5, 22.5),  # 以0°为中心
        ("东北风", 22.5, 67.5),
        ("东风", 67.5, 112.5),
        ("东南风", 112.5, 157.5),
        ("南风", 157.5, 202.5),
        ("西南风", 202.5, 247.5),
        ("西风", 247.5, 292.5),
        ("西北风", 292.5, 337.5),
    ]

    # 特殊处理北风（跨越0度边界）
    if angle >= 337.5 or angle < 22.5:
        return "北风"
    for direction, start, end in directions:
        if start <= angle < end:
            return direction

    return "未知"
# ========== 计算风力等级 ==========
def wind_speed_to_bf_accurate(speed_kmh):
    """
    使用分段经验公式计算精确风力等级
    基于世界气象组织 (WMO) 推荐标准
    Args:
        speed_kmh (float): 风速，单位公里/小时 (km/h)
    Returns:
        int: 风力等级 (0-12)
        float: 转换后的风速 (m/s)，保留一位小数（可通过参数控制是否返回）
    """
    if speed_kmh is None or speed_kmh < 0:
        return -1, None

    # 公里/小时 转 米/秒 (1 km/h = 1/3.6 m/s),保留一位小数
    speed_m_per_s_rounded = round(speed_kmh / 3.6, 1)
    # 官方风速范围 (下限, 上限] 单位: m/s
    wind_ranges = [
        (0.0, 0.2),  # 0级
        (0.3, 1.5),  # 1级
        (1.6, 3.3),  # 2级
        (3.4, 5.4),  # 3级
        (5.5, 7.9),  # 4级
        (8.0, 10.7),  # 5级
        (10.8, 13.8),  # 6级
        (13.9, 17.1),  # 7级
        (17.2, 20.7),  # 8级
        (20.8, 24.4),  # 9级
        (24.5, 28.4),  # 10级
        (28.5, 32.6),  # 11级
        (32.7, float('inf'))  # 12级及以上
    ]
    for level, (low, high) in enumerate(wind_ranges):
        if low < speed_m_per_s_rounded <= high:
            return level, speed_m_per_s_rounded

    return 0, speed_m_per_s_rounded

# ========== 获取天气数据 ==========
def fetch_weather():
    """从和风天气API获取实时数据"""
    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get("status") == "ok":

            # 彩云API的数据路径: data['result']['realtime']
            realtime = data.get("result", {}).get("realtime", {})
            # 提取空气质量数据（彩云API中空气质量和天气在同一层级）
            air_quality = realtime.get("air_quality", {})
            # 提取风力数据
            wind = realtime.get("wind", {})
            weather_text = convert_skycon_to_weather(realtime.get("skycon") )
            logging.info(f"获取成功 - 天气: {weather_text}，温度: {realtime.get('temperature')}°C")

            obs_time = datetime.fromtimestamp(data.get("server_time")).isoformat()

            # 计算风力等级
            wind_scale, _ = wind_speed_to_bf_accurate(wind.get("speed"))
            wind_dir=wind_direction_8(wind.get("direction"))
            return {
                "text": weather_text,  # 天气描述 (如 "PARTLY_CLOUDY_DAY")
                "obsTime": obs_time,  # 数据观测时间
                "temp": realtime.get("temperature"),  # 温度
                "feels_like": realtime.get("apparent_temperature"),  # 体感温度
                "humidity": realtime.get("humidity")*100,  # 相对湿度 (0-1之间，需转换)
                "wind_speed": wind.get("speed"),  # 风速 (m/s)
                "wind_dir": wind_dir,  # 风向 (角度)
                "wind360": wind.get("direction"),  # 风向角 (与wind_dir相同)
                "wind_scale": wind_scale,  # 彩云API未直接提供风力等级
                "pressure": realtime.get("pressure")/100,  # 气压 (Pa)
                "visibility": realtime.get("visibility"),  # 能见度 (km)
                "aqi": air_quality.get("aqi",{}).get("chn"),  # AQI指数 (中国标准)
                "pm2p5": air_quality.get("pm25"),  # PM2.5浓度
                "pm10": air_quality.get("pm10"),  # PM10浓度
                "no2": air_quality.get("no2"),  # 二氧化氮浓度
                "o3": air_quality.get("o3"),  # 臭氧浓度
                "co": air_quality.get("co"),  # 一氧化碳浓度
                "raw_response": str(data)  # 原始返回数据
            }
        else:
            logging.error(f"API返回错误码: {data.get('code')}")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"网络请求失败: {e}")
        return None
    except Exception as e:
        logging.error(f"未知错误: {e}")
        return None




# ========== 保存到数据库 ==========
def save_to_db(weather_data):
    """保存天气和空气质量数据到数据库"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f'''
        INSERT INTO {CURRENT_TABLE}  
        (fetch_time, text, obsTime, temp, feels_like, humidity, 
         wind_speed, wind_dir,wind360, windScale, pressure, visibility,
         aqi, pm2p5, pm10, no2, o3, co,
         raw_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        weather_data.get("text") if weather_data else None,
        weather_data.get("obsTime") if weather_data else None,
        weather_data.get("temp") if weather_data else None,
        weather_data.get("feels_like") if weather_data else None,
        weather_data.get("humidity") if weather_data else None,
        weather_data.get("wind_speed") if weather_data else None,
        weather_data.get("wind_dir") if weather_data else None,
        weather_data.get("wind360") if weather_data else None,
        weather_data.get("wind_scale") if weather_data else None,
        weather_data.get("pressure") if weather_data else None,
        weather_data.get("visibility") if weather_data else None,
        weather_data.get("aqi") if weather_data else None,
        weather_data.get("pm2p5") if weather_data else None,
        weather_data.get("pm10") if weather_data else None,
        weather_data.get("no2") if weather_data else None,
        weather_data.get("o3") if weather_data else None,
        weather_data.get("co") if weather_data else None,
        weather_data.get("raw_response") if weather_data else None,

    ))
    conn.commit()

    # 获取并打印当前总记录数
    cursor.execute(f"SELECT COUNT(*) FROM {CURRENT_TABLE} ")
    total = cursor.fetchone()[0]

    conn.close()

    if weather_data :
        logging.info(f"数据保存成功 - 当前数据库共 {total} 条记录")
    else:
        logging.error("无数据可保存")


# ========== 浮点数保留两位小数 ==========
def safe_float(value, decimals=2):
    """安全转换为浮点数并保留两位小数"""
    if value is None:
        return None
    try:
        return round(float(value), decimals)
    except (ValueError, TypeError):
        return value


# ========== 保存到csv ==========
def save_to_csv(weather_data):
    """保存天气和空气质量数据到CSV文件（Excel兼容版）"""
    if not weather_data :
        logging.warning("无数据可保存到CSV")
        return

    # 准备数据行
    # 先获取基础数据
    weather = weather_data or {}

    # 计算风速（km/h 转 m/s）
    wind_speed_ms = None
    if weather.get("wind_speed"):
        try:
            wind_speed_ms = round(float(weather.get("wind_speed")) / 3.6, 2)
        except (ValueError, TypeError):
            pass

    row = {
        "获取时间": datetime.now().isoformat(),
        "天气状况": weather.get("text"),
        "天气数据更新时间": weather.get("obsTime"),
        "气温": safe_float(weather.get("temp")),
        "体感温度": safe_float(weather.get("feels_like")),
        "湿度": safe_float(weather.get("humidity")),
        "风速m/s": wind_speed_ms,
        "风向": weather.get("wind_dir"),
        "风向角": safe_float(weather.get("wind360")),
        "风力等级": weather.get("wind_scale"),
        "压强": safe_float(weather.get("pressure")),
        "能见度km": safe_float(weather.get("visibility")),
        "空气质量": (weather.get("aqi")),
        "pm2p5": safe_float(weather.get("pm2p5")),
        "pm10": safe_float(weather.get("pm10")),
        "no2": safe_float(weather.get("no2")),
        "o3": safe_float(weather.get("o3")),
        "co": safe_float(weather.get("co")),
    }
    fieldnames = list(row.keys())  # 直接使用row的键作为表头，确保一致

    try:
        # 使用 utf-8-sig 编码，Excel打开不会乱码
        with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            # 如果是空文件，写入表头
            if f.tell() == 0:
                writer.writeheader()
                logging.info(f"创建CSV文件并写入表头: {CSV_FILENAME}")
            writer.writerow(row)
        logging.info(f"数据已追加到CSV: {CSV_FILENAME}")
    except Exception as e:
        logging.error(f"CSV写入失败: {e}")


# ========== 退出处理 ==========
stop_event = threading.Event()


def signal_handler(sig, frame):
    stop_event.set()  # 立即唤醒等待
    logging.info("收到退出信号，正在优雅退出...")


signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # 终止信号


# ========== 主循环 ==========
def main():
    logging.info(f"程序启动，采集间隔:{INTERVAL // 3600}时{(INTERVAL % 3600) // 60}分")
    init_db()

    # 循环采集
    while not stop_event.is_set():
        # 获取数据
        data_time = datetime.now().replace(microsecond=0)
        logging.info(f"获取天气数据 - 执行时间: {data_time}")
        weather_data = fetch_weather()
        # 保存文件
        save_to_db(weather_data)
        save_to_csv(weather_data)
        # 等待 INTERVAL 秒，但如果 stop_event 被设置会立即返回
        if stop_event.wait(INTERVAL):
            break  # 收到退出信号

    logging.info("程序正常退出")


if __name__ == "__main__":
    main()


