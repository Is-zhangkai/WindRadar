#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@Project        ：WindRadar
@File           ：weather_hefeng.py
@Author         ：zhangkai
@Date           ：2026-05-08
@Version        : 3.0.0
@Description    : 通过和风天气3个API获取天气和空气质量，保存到数据库和csv
@Record         : 20260508--从实时天气获取能见度，并将格点天气和实时天气进行对比保存

@Issue          :
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
LATITUDE = "43.85"                        # 纬度
LONGITUDE = "125.41"                      # 经度
LOCATION = f"125.41,43.85"
LOCATION_ID="101060107" #直接取城市id
INTERVAL = 3600  # 采集间隔（秒）

# 和风天气API接口
API_HOST = "https://kw3v5an2q7.re.qweatherapi.com"
API_KEY = "d1b303e61b474dfbb17a1bb7a72bac5a"  # API Key
# 实时天气接口
url = f"{API_HOST}/v7/weather/now" #实时天气
url_grid = f"{API_HOST}/v7/grid-weather/now" #格点实时天气



# 空气质量接口    注意：URL中的经纬度顺序是 纬度/经度
air_url = f"{API_HOST}/airquality/v1/current/{LATITUDE}/{LONGITUDE}"
params = {"location": LOCATION}
params_id = {"location": LOCATION_ID}
headers = {"X-QW-Api-Key": API_KEY}


# 当前使用的数据表名，改名修改这里(数据库表名,-log,csv文件名)
# CURRENT_TABLE = "weather_records_20260508"
# 按日期命名
today = datetime.now().strftime("%Y%m%d")
CURRENT_TABLE=f"weather_records_{today}"
"""

"""
# 数据保存路径
Data_DIR = "weather_data_hefeng_v3"  # 文件目录
# log_dir = os.path.join(Data_DIR, "log")

os.makedirs(Data_DIR, exist_ok=True)# 确保目录存在
# os.makedirs(log_dir, exist_ok=True)          # 如果目录不存在则创建
DB_FILENAME = "weather_data_hefeng_v3.db"      # SQLite数据库文件路径
CSV_FILENAME = f"{CURRENT_TABLE}_hefeng_v3.csv"  # CSV文件名
# LOG_FILENAME = f"{CURRENT_TABLE}.log"  # log文件名
LOG_FILENAME = "weather_fetcher.log"  # 日志文件名
DB_PATH=os.path.join(Data_DIR, DB_FILENAME)
csv_path = os.path.join(Data_DIR, CSV_FILENAME)
log_path = os.path.join(Data_DIR, LOG_FILENAME)
CSV_CMP_FILENAME = f"{CURRENT_TABLE}_hefeng_v3_cmp.csv"  # CSV文件名
csv_cmp_path = os.path.join(Data_DIR, CSV_CMP_FILENAME)
# ========== 设置日志 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),  # 输出到文件
        logging.StreamHandler()                      # 同时输出到控制台
    ]
)

# ========== CSV文件配置 ==========
# # 按日期新建文件
# def get_csv_path():
#     """获取CSV文件路径（按日期分文件）"""
#     os.makedirs(Data_DIR, exist_ok=True)
#     today = datetime.now().strftime("%Y%m%d")
#     return os.path.join(Data_DIR, f"weather_{today}.csv")
#

# ========== 初始化数据库 ==========
def init_db():
    """创建SQLite数据表（如果不存在）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA auto_vacuum = FULL")
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

            raw_response_w TEXT,              -- 格点天气原始返回数据（备用）
            raw_response_aqi TEXT,               -- 空气质量原始返回数据（备用）
            raw_response_v TEXT               -- 天气原始返回数据（备用）
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("数据库初始化完成")
    logging.info(f"文件保存目录:{os.path.join(Data_DIR, CSV_FILENAME)} ")



# ========== 获取实时天气数据 ==========
def fetch_weather_now():
    """从和风天气API获取实时数据"""
    try:
        response = requests.get(url, headers=headers, params=params_id, timeout=10)
        data = response.json()

        if data.get("code") == "200":
            now = data.get("now", {})
            logging.info(f"实时天气获取成功 - 天气: {now.get('text')}，温度: {now.get('temp')}°C，能见度: {now.get('vis')}")
            # logging.info(f"数据页面 - :{data.get('fxLink')}")

            # 转换时区
            cst_time = (datetime.fromisoformat(now.get("obsTime"))).astimezone(ZoneInfo("Asia/Shanghai"))

            return {
                "text": now.get("text"),#天气描述
                # "obsTime":datetime.fromisoformat((now.get("obsTime")).replace('+00:00', '')) + timedelta(hours=8),
                # "obsTime":cst_time.isoformat(),
                "temp": now.get("temp"),
                "feels_like": now.get("feelsLike"),
                "humidity": now.get("humidity"),
                "wind_speed": now.get("windSpeed"),
                # "wind_dir": now.get("windDir"),
                "wind360": now.get("wind360"),
                # "wind_scale": now.get("windScale"),
                "pressure": now.get("pressure"),
                "visibility": now.get("vis"),
                "raw_response_v": str(data)#天气原始返回数据（备用）
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


# ========== 获取格点天气数据 ==========
def fetch_weather():
    """从和风天气API获取格点天气数据"""
    try:
        response = requests.get(url_grid, headers=headers, params=params, timeout=10)
        data = response.json()

        if data.get("code") == "200":
            now = data.get("now", {})
            logging.info(f"格点天气获取成功 - 天气: {now.get('text')}，温度: {now.get('temp')}°C")
            # logging.info(f"数据页面 - :{data.get('fxLink')}")

            # 转换时区
            cst_time = (datetime.fromisoformat(now.get("obsTime"))).astimezone(ZoneInfo("Asia/Shanghai"))

            return {
                "text": now.get("text"),#天气描述
                # "obsTime":datetime.fromisoformat((now.get("obsTime")).replace('+00:00', '')) + timedelta(hours=8),
                "obsTime":cst_time.isoformat(),
                "temp": now.get("temp"),
                "feels_like": now.get("feelsLike"),
                "humidity": now.get("humidity"),
                "wind_speed": now.get("windSpeed"),
                "wind_dir": now.get("windDir"),
                "wind360": now.get("wind360"),
                "wind_scale": now.get("windScale"),
                "pressure": now.get("pressure"),
                "visibility": now.get("vis"),
                "raw_response_w": str(data)#天气原始返回数据（备用）
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

# ========== 获取空气质量数据 ==========
def fetch_air_quality():
    """从空气质量API获取数据"""
    try:
        response = requests.get(air_url, headers=headers, timeout=10)
        data = response.json()
        # print("响应内容:", response.json())  # 按 JSON 格式输出
        # 根据实际返回的数据结构解析（需要根据API文档调整）
        if response.status_code == 200:
            # 提取AQI
            aqi_value = None
            for index in data.get("indexes", []):
                if index.get("code") == "cn-mee":
                    aqi_value = index.get("aqi")
                    break
            # 提取污染物浓度
            pollutants = {}
            for pollutant in data.get("pollutants", []):
                code = pollutant.get("code")
                concentration = pollutant.get("concentration", {}).get("value")
                if code == "pm2p5":
                    pollutants["pm2p5"] = concentration
                elif code == "pm10":
                    pollutants["pm10"] = concentration
                elif code == "no2":
                    pollutants["no2"] = concentration
                elif code == "o3":
                    pollutants["o3"] = concentration
                elif code == "co":
                    pollutants["co"] = concentration

            logging.info(f"空气质量获取成功 - AQI: {aqi_value}")

            return {
                "aqi": aqi_value,
                "pm2p5": pollutants.get("pm2p5"),
                "pm10": pollutants.get("pm10"),
                "no2": pollutants.get("no2"),
                "o3": pollutants.get("o3"),
                "co": pollutants.get("co"),
                "raw_response_aqi": str(data)
            }
        else:
            logging.error(f"空气质量API返回状态码: {response.status_code}, 响应: {data}")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"空气质量网络请求失败: {e}")
        return None
    except Exception as e:
        logging.error(f"空气质量数据解析错误: {e}")
        return None


# ========== 保存到数据库 ==========
def save_to_db(grid_weather_data, air_quality_data,now_weather_data):
    """保存天气和空气质量数据到数据库"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f'''
        INSERT INTO {CURRENT_TABLE}  
        (fetch_time, text, obsTime, temp, feels_like, humidity, 
         wind_speed, wind_dir,wind360, windScale, pressure, visibility,
         aqi, pm2p5, pm10, no2, o3, co,
         raw_response_w, raw_response_aqi,raw_response_v)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)
    ''', (
        datetime.now().isoformat(),
        grid_weather_data.get("text") if grid_weather_data else None,
        grid_weather_data.get("obsTime") if grid_weather_data else None,
        grid_weather_data.get("temp") if grid_weather_data else None,
        grid_weather_data.get("feels_like") if grid_weather_data else None,
        grid_weather_data.get("humidity") if grid_weather_data else None,
        grid_weather_data.get("wind_speed") if grid_weather_data else None,
        grid_weather_data.get("wind_dir") if grid_weather_data else None,
        grid_weather_data.get("wind360") if grid_weather_data else None,
        grid_weather_data.get("wind_scale") if grid_weather_data else None,
        grid_weather_data.get("pressure") if grid_weather_data else None,
        now_weather_data.get("visibility") if now_weather_data else None,#能见度从now_weather_data获取
        air_quality_data.get("aqi") if air_quality_data else None,
        air_quality_data.get("pm2p5") if air_quality_data else None,
        air_quality_data.get("pm10") if air_quality_data else None,
        air_quality_data.get("no2") if air_quality_data else None,
        air_quality_data.get("o3") if air_quality_data else None,
        air_quality_data.get("co") if air_quality_data else None,
        grid_weather_data.get("raw_response_w") if grid_weather_data else None,
        air_quality_data.get("raw_response_aqi") if air_quality_data else None,
        now_weather_data.get("raw_response_v") if now_weather_data else None
    ))
    conn.commit()

    # 获取并打印当前总记录数
    cursor.execute(f"SELECT COUNT(*) FROM {CURRENT_TABLE} ")
    total = cursor.fetchone()[0]

    conn.close()

    if grid_weather_data and air_quality_data and now_weather_data:
        logging.info(f"数据保存成功 - 当前数据库共 {total} 条记录")
    elif not grid_weather_data:
        logging.warning("数据保存成功 - 缺失网格天气数据")
    elif not air_quality_data:
        logging.warning("数据保存成功 - 缺失空气质量数据")
    elif not now_weather_data:
        logging.warning("数据保存成功 - 缺失实时天气数据")
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
def save_to_csv(weather_data, air_quality_data, now_weather_data):
    """保存天气和空气质量数据到CSV文件（Excel兼容版）"""
    if not weather_data and not air_quality_data:
        logging.warning("无数据可保存到CSV")
        return

    # 准备数据行
    # 先获取基础数据
    weather = weather_data or {}
    air = air_quality_data or {}
    now_weather = now_weather_data or {}

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
        "能见度km": safe_float(now_weather.get("visibility")),# 能见度从实时天气获取
        "空气质量": (air.get("aqi")),
        "pm2p5": safe_float(air.get("pm2p5")),
        "pm10": safe_float(air.get("pm10")),
        "no2": safe_float(air.get("no2")),
        "o3": safe_float(air.get("o3")),
        "co": safe_float(air.get("co")),
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
# ========== 保存到csv（比较实时天气和网格天气区别） ==========
def save_to_csv_cmp(weather_data, now_weather_data):
    """保存天气和空气质量数据到CSV文件（Excel兼容版）"""
    if not weather_data and not now_weather_data:
        logging.warning("无数据可保存到CSV")
        return

    # 准备数据行
    # 先获取基础数据
    weather = weather_data or {}
    now_weather = now_weather_data or {}


    row = {
        "获取时间": datetime.now().isoformat(),
        "天气g": weather.get("text"),
        "天气n": now_weather.get("text"),
        "气温g": safe_float(weather.get("temp")),
        "气温n": safe_float(now_weather.get("temp")),
        "体感g": safe_float(weather.get("feels_like")),
        "体感n": safe_float(now_weather.get("feels_like")),
        "湿度g": safe_float(weather.get("humidity")),
        "湿度n": safe_float(now_weather.get("humidity")),
        "风速g": weather.get("wind_speed"),
        "风速n": now_weather.get("wind_speed"),
        "风向角g": safe_float(weather.get("wind360")),
        "风向角n": safe_float(now_weather.get("wind360")),
        "压强g": safe_float(weather.get("pressure")),
        "压强n": safe_float(now_weather.get("pressure")),
        "能见度km": safe_float(now_weather.get("visibility")),# 能见度从实时天气获取

    }
    fieldnames = list(row.keys())  # 直接使用row的键作为表头，确保一致

    try:
        # 使用 utf-8-sig 编码，Excel打开不会乱码
        with open(csv_cmp_path, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            # 如果是空文件，写入表头
            if f.tell() == 0:
                writer.writeheader()
                logging.info(f"创建CSV_cmp文件并写入表头: {CSV_CMP_FILENAME}")
            writer.writerow(row)
        logging.info(f"数据已追加到CSV_cmp: {CSV_CMP_FILENAME}")
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
        weather_data = fetch_weather_now()
        grid_weather_data = fetch_weather()
        air_quality_data= fetch_air_quality()

        # 保存文件
        save_to_db(grid_weather_data, air_quality_data,weather_data)
        save_to_csv(grid_weather_data, air_quality_data,weather_data)
        save_to_csv_cmp(grid_weather_data,weather_data)
        # 等待 INTERVAL 秒，但如果 stop_event 被设置会立即返回
        if stop_event.wait(INTERVAL):
            break  # 收到退出信号

    logging.info("程序正常退出")

if __name__ == "__main__":
    main()
    # 导出数据库文件到csv文件
    # export_to_csv()
    # logging.info("程序正常退出")