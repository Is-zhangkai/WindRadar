#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
@Project        ：WindRadar
@File           ：export_csv.py
@Author         ：zhangkai
@Date           ：2026-04-23
@Version        : 1.0.0
@Description    : 导出数据库数据到csv
"""
import sqlite3
import logging
from datetime import datetime
import csv
import os

# ========== 配置==========


# 数据保存路径
Data_DIR = "weather_data"  # 文件目录
os.makedirs(Data_DIR, exist_ok=True)# 确保目录存在
DB_FILENAME = "weather_data.db"      # SQLite数据库文件路径
CSV_FILENAME = "weather_records.csv"  # CSV文件名（按日期分文件可修改）
# LOG_FILENAME = "weather_fetcher.log"  # CSV文件名（按日期分文件可修改）
DB_PATH=os.path.join(Data_DIR, DB_FILENAME)
csv_path = os.path.join(Data_DIR, CSV_FILENAME)
# log_path = os.path.join(Data_DIR, LOG_FILENAME)

# ========== 设置日志 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler(log_path, encoding='utf-8'),  # 输出到文件
        logging.StreamHandler()                      # 同时输出到控制台
    ]
)

# ========== CSV文件配置 ==========
# 按日期新建文件
def get_csv_path():
    """获取CSV文件路径（按日期分文件）"""
    os.makedirs(Data_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")

    return os.path.join(Data_DIR, f"weather_{today}.csv")


# ========== 导出为CSV ==========此程序未完成
def export_to_csv():
    """手动调用时导出数据到CSV文件（覆盖模式）"""

    os.makedirs(Data_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 使用最新的字段列表
    cursor.execute('''
        SELECT 
            id, fetch_time, text, obsTime, temp, feels_like, humidity,
            wind_speed, wind_dir, wind360, windScale, pressure, visibility,
            aqi, pm2p5, pm10, no2, o3, co
        FROM weather_records 
        ORDER BY fetch_time
    ''')
    rows = cursor.fetchall()
    conn.close()

    if rows:
        today = datetime.now().strftime("%Y%m%d")
        export_path = os.path.join(Data_DIR, f"weather_export_{today}.csv")
        # 检查文件是否已存在
        if os.path.exists(export_path):
            logging.warning(f"文件已存在，停止导出: {export_path}")
            return None

        with open(export_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "fetch_time", "weather", "obsTime", "temp", "feels_like",
                "humidity", "wind_speed_km/h", "wind_dir", "wind360", "windScale",
                "pressure", "visibility", "aqi", "pm2p5", "pm10", "no2", "o3", "co"
            ])
            writer.writerows(rows)

        logging.info(f"已导出 {len(rows)} 条记录到 {export_path}")
        return None
    else:
        logging.warning("数据库无数据，无法导出")
        return None
if __name__ == "__main__":

    # 导出数据库文件到csv文件
    export_to_csv()
    logging.info("程序正常退出")