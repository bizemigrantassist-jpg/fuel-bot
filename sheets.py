"""
Модуль для роботи з Google Sheets
Зберігає пробіги та читає список авто/карток
"""

import os
import json
import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
MILEAGE_SHEET = "Пробіги"
CARS_SHEET = "Картки_Авто"

# Заголовки таблиці пробігів
MILEAGE_HEADERS = [
    "Дата", "Час", "Водій", "Telegram ID",
    "Авто (держ. номер)", "Картка E100",
    "Пробіг (км)", "File ID фото", "Статус"
]


def get_client():
    """Авторизація в Google Sheets через service account"""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        # Для локального запуску — файл credentials.json
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds)


def get_or_create_sheet(spreadsheet, name: str, headers: list):
    """Отримати або створити лист з заголовками"""
    try:
        sheet = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers))
        sheet.append_row(headers)
        logger.info(f"Created sheet: {name}")
    return sheet


def get_car_list() -> list[str]:
    """
    Читає список авто з листа 'Картки_Авто'
    Формат: стовпець A = держ. номер, стовпець B = картка E100, стовпець C = водій
    Повертає список рядків виду: "WPI1751C | KOLTAKOV"
    """
    try:
        client = get_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet(CARS_SHEET)
        records = sheet.get_all_records()

        cars = []
        for row in records:
            plate = str(row.get("Держ. номер", "")).strip()
            card = str(row.get("Картка E100", "")).strip()
            driver = str(row.get("Водій", "")).strip()
            if plate:
                label = f"{plate}"
                if driver:
                    label += f" | {driver}"
                cars.append(label)

        return cars
    except Exception as e:
        logger.error(f"Error reading car list: {e}")
        return []


def save_mileage_record(
    driver_name: str,
    driver_id: str,
    car: str,
    mileage: int,
    photo_file_id: str,
    timestamp: datetime
):
    """Зберегти запис пробігу в Google Sheets"""
    client = get_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    sheet = get_or_create_sheet(spreadsheet, MILEAGE_SHEET, MILEAGE_HEADERS)

    # Витягуємо держ. номер і картку з вибору водія (формат "WPI1751C | KOLTAKOV")
    plate = car.split("|")[0].strip()

    # Знаходимо картку E100 для цього авто
    card = get_card_for_plate(spreadsheet, plate)

    row = [
        timestamp.strftime("%d.%m.%Y"),
        timestamp.strftime("%H:%M"),
        driver_name,
        driver_id,
        plate,
        card,
        mileage,
        photo_file_id,
        "✅ OK"
    ]

    sheet.append_row(row)
    logger.info(f"Saved: {driver_name} | {plate} | {mileage} km")


def get_card_for_plate(spreadsheet, plate: str) -> str:
    """Знайти картку E100 за держ. номером"""
    try:
        sheet = spreadsheet.worksheet(CARS_SHEET)
        records = sheet.get_all_records()
        for row in records:
            if str(row.get("Держ. номер", "")).strip() == plate:
                return str(row.get("Картка E100", "")).strip()
    except Exception as e:
        logger.error(f"Error finding card for plate {plate}: {e}")
    return ""
