# ===========================================================================================
# МАСОВА АГРЕГАЦІЯ ПРОДУКТІВ: Single Pack vs Double Pack
# ===========================================================================================

import pandas as pd
import numpy as np
import os
import re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter
import warnings
warnings.filterwarnings('ignore')

# ===========================================================================================
# НАЛАШТУВАННЯ
# ===========================================================================================

ROOT_DIR = '/Users/radyslav/data_analysis/Amazon/prod_perc_dpack'
COSTS_FILE_NAME = 'Product Cost Info.xlsx'
OUTPUT_FILE_NAME = 'All_Products_Aggregation.xlsx'

# ===========================================================================================
# ДОПОМІЖНІ ФУНКЦІЇ
# ===========================================================================================

def create_sort_key(month_year_str):
    """Створює ключ сортування datetime для Month_Year."""
    if '_' in month_year_str:
        date_str = month_year_str.replace('_', ' ')
        try:
            return pd.to_datetime(date_str, format='%B %Y')
        except ValueError:
            return pd.NaT
    return pd.NaT


def get_product_unit_economics(file_path, base_name):
    """Витягує фінансові константи (COGS, FBA Fee, Ref Fee Rate, ASIN)."""
    try:
        df_costs = pd.read_excel(file_path, header=0)
    except FileNotFoundError:
        return {}
    except Exception as e:
        return {}
    
    # Очищення та фільтрація
    df_costs.columns = df_costs.columns.str.strip().str.lower().str.replace(' ', '_')
    df_costs = df_costs.dropna(subset=['short_product_name']).reset_index(drop=True)

    df_product_group = df_costs[df_costs['short_product_name'].str.contains(base_name, case=False, na=False)].copy()

    if df_product_group.empty:
        return {}

    # Ідентифікація паків за кількістю одиниць
    df_product_group['unit_count'] = df_product_group['short_product_name'].str.extract(r'(\d+)').astype(float)
    df_product_group = df_product_group.dropna(subset=['unit_count'])
    if len(df_product_group) < 2:
        return {}

    idx_dp = df_product_group['unit_count'].idxmax()
    idx_sp = df_product_group['unit_count'].idxmin()

    results_raw = {'Single Pack': df_product_group.loc[idx_sp], 'Double Pack': df_product_group.loc[idx_dp]}
    unit_economics_final = {}
    
    # Очищення та перетворення констант
    for pack_type, data in results_raw.items():
        costs = {}
        for col in ['cogs', 'fba_fee']:
            raw_value = str(data.get(col, 0))
            cleaned_value = raw_value.strip().replace('$', '').replace(',', '')
            costs[col] = pd.to_numeric(cleaned_value, errors='coerce')

        raw_ref_fee = str(data.get('ref_fee', '0%'))
        if '%' in raw_ref_fee:
            ref_fee_rate = pd.to_numeric(raw_ref_fee.strip().replace('%', ''), errors='coerce') / 100
        else:
            numeric_val = pd.to_numeric(raw_ref_fee, errors='coerce')
            ref_fee_rate = numeric_val / 100 if numeric_val > 1 else numeric_val

        costs['ref_fee_rate'] = ref_fee_rate
        costs['asin'] = data['asin']
        unit_economics_final[pack_type] = costs

    return unit_economics_final


def process_single_csv(file_path, file_name, current_asin):
    """Обробляє один CSV-файл, об'єднує Total/B2B метрики та витягує дату."""
    try:
        df = pd.read_csv(file_path, header=0, encoding='utf-8')
    except Exception:
        return None, 0

    cols_mapping = {
        'Sessions': ['Sessions - Total', 'Sessions - Total - B2B'],
        'Units Ordered': ['Units Ordered', 'Units Ordered - B2B'],
        'Ordered Product Sales': ['Ordered Product Sales', 'Ordered Product Sales - B2B']
    }
    
    monthly_data = {'ASIN': current_asin}
    
    for new_col, raw_cols in cols_mapping.items():
        temp_df = df[raw_cols].copy()
        for col in raw_cols:
            if temp_df[col].dtype == object:
                temp_df[col] = temp_df[col].astype(str).str.replace(r'[\$,\s]', '', regex=True)
            temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce')
        
        total_sum = temp_df.sum().sum()
        monthly_data[new_col] = total_sum

    date_match = re.search(r'([A-Za-z]+_\d{4})', file_name)
    monthly_data['Month_Year'] = date_match.group(1) if date_match else "Unknown_Date"

    return pd.DataFrame([monthly_data]), len(df)


def process_single_product(product_name, product_dir, costs_file_path):
    """
    Обробляє один продукт та повертає результат агрегації.
    
    Returns:
        tuple: (success: bool, result: pd.DataFrame or str error_message)
    """
    try:
        # Перевірка існування директорії
        if not os.path.isdir(product_dir):
            return False, f"Директорія не знайдена: {product_dir}"

        # Пошук підпапок Single/Double Pack
        all_items = os.listdir(product_dir)
        single_pack_folder = next((item for item in all_items if "single pack" in item.lower() and os.path.isdir(os.path.join(product_dir, item))), None)
        double_pack_folder = next((item for item in all_items if "double pack" in item.lower() and os.path.isdir(os.path.join(product_dir, item))), None)

        if not single_pack_folder or not double_pack_folder:
            return False, "Не знайдено підпапок Single Pack або Double Pack"

        single_pack_dir = os.path.join(product_dir, single_pack_folder)
        double_pack_dir = os.path.join(product_dir, double_pack_folder)

        # Отримання констант юніт-економіки
        base_product_name = product_name.replace(' Capsules', '').replace('(Stable Price)', '').strip()
        unit_economics = get_product_unit_economics(costs_file_path, base_product_name)

        if not unit_economics:
            return False, "Не знайдено констант юніт-економіки"

        # Обробка Single Pack
        single_pack_data = []
        csv_files_sp = [f for f in os.listdir(single_pack_dir) if f.endswith('.csv')]
        asin_sp = unit_economics.get('Single Pack', {}).get('asin', 'ASIN_NOT_FOUND')

        for file_name in csv_files_sp:
            df_month, _ = process_single_csv(os.path.join(single_pack_dir, file_name), file_name, asin_sp)
            if df_month is not None:
                single_pack_data.append(df_month)

        if not single_pack_data:
            return False, "Немає даних для Single Pack"

        df_single_raw = pd.concat(single_pack_data, ignore_index=True)
        df_single_raw['Date_Sort'] = df_single_raw['Month_Year'].apply(create_sort_key)
        df_single_kpi = df_single_raw.sort_values(by='Date_Sort').reset_index(drop=True)

        # Розрахунок метрик Single Pack
        cogs_sp = unit_economics['Single Pack']['cogs']
        fba_fee_sp = unit_economics['Single Pack']['fba_fee']
        ref_fee_rate_sp = unit_economics['Single Pack']['ref_fee_rate']

        df_single_kpi['Product Costs'] = (df_single_kpi['Units Ordered'] * (cogs_sp + fba_fee_sp)) + \
                                          (df_single_kpi['Ordered Product Sales'] * ref_fee_rate_sp)
        df_single_kpi['Net Profit'] = df_single_kpi['Ordered Product Sales'] - df_single_kpi['Product Costs']
        df_single_kpi['Actual Price'] = df_single_kpi['Ordered Product Sales'] / df_single_kpi['Units Ordered']

        # Обробка Double Pack
        double_pack_data = []
        csv_files_dp = [f for f in os.listdir(double_pack_dir) if f.endswith('.csv')]
        asin_dp = unit_economics.get('Double Pack', {}).get('asin', 'ASIN_NOT_FOUND')

        for file_name in csv_files_dp:
            df_month, _ = process_single_csv(os.path.join(double_pack_dir, file_name), file_name, asin_dp)
            if df_month is not None:
                double_pack_data.append(df_month)

        if not double_pack_data:
            return False, "Немає даних для Double Pack"

        df_double_raw = pd.concat(double_pack_data, ignore_index=True)
        df_double_raw['Date_Sort'] = df_double_raw['Month_Year'].apply(create_sort_key)
        df_double_kpi = df_double_raw.sort_values(by='Date_Sort').reset_index(drop=True)

        # Розрахунок метрик Double Pack
        cogs_dp = unit_economics['Double Pack']['cogs']
        fba_fee_dp = unit_economics['Double Pack']['fba_fee']
        ref_fee_rate_dp = unit_economics['Double Pack']['ref_fee_rate']

        df_double_kpi['Product Costs'] = (df_double_kpi['Units Ordered'] * (cogs_dp + fba_fee_dp)) + \
                                          (df_double_kpi['Ordered Product Sales'] * ref_fee_rate_dp)
        df_double_kpi['Net Profit'] = df_double_kpi['Ordered Product Sales'] - df_double_kpi['Product Costs']
        df_double_kpi['Actual Price'] = df_double_kpi['Ordered Product Sales'] / df_double_kpi['Units Ordered']

        # Створення порівняльної таблиці
        final_cols = ['Month_Year', 'Sessions', 'Units Ordered', 'Ordered Product Sales', 'Product Costs', 'Net Profit', 'Actual Price', 'Date_Sort']
        df_single_final = df_single_kpi[final_cols].copy()
        df_double_final = df_double_kpi[final_cols].copy()

        months_single = set(df_single_final['Month_Year'].unique())
        months_double = set(df_double_final['Month_Year'].unique())
        common_months = sorted(list(months_single.intersection(months_double)), key=create_sort_key)

        if not common_months:
            return False, "Немає спільних місяців для порівняння"

        # Об'єднання та трансформація
        df_single_combined = df_single_final.assign(Pack_Type='Single Pack')
        df_double_combined = df_double_final.assign(Pack_Type='Double Pack')
        df_combined = pd.concat([df_single_combined, df_double_combined], ignore_index=True)
        df_combined_filtered = df_combined[df_combined['Month_Year'].isin(common_months)].copy()

        pack_type_order = ['Single Pack', 'Double Pack']
        df_combined_filtered['Pack_Type'] = pd.Categorical(df_combined_filtered['Pack_Type'], categories=pack_type_order, ordered=True)
        comparison_values = ['Sessions', 'Units Ordered', 'Ordered Product Sales', 'Product Costs', 'Net Profit', 'Actual Price']

        df_for_pivot = df_combined_filtered[['Month_Year', 'Pack_Type'] + comparison_values].melt(
            id_vars=['Month_Year', 'Pack_Type'],
            value_vars=comparison_values,
            var_name='Metric',
            value_name='Value'
        )

        df_for_pivot['Date_Sort'] = df_for_pivot['Month_Year'].apply(create_sort_key)
        df_for_pivot = df_for_pivot.sort_values(by=['Date_Sort', 'Pack_Type']).drop(columns=['Date_Sort'])

        df_comparison_pivot = df_for_pivot.pivot_table(
            index='Metric',
            columns=['Month_Year', 'Pack_Type'],
            values='Value',
            aggfunc='sum',
            observed=False
        )

        # Сортування колонок
        sorted_cols = []
        for month in common_months:
            for pack in pack_type_order:
                sorted_cols.append((month, pack))

        df_comparison_pivot = df_comparison_pivot[sorted_cols]
        df_comparison_pivot.columns.names = ['Month_Year', 'Pack_Type']

        # Сортування рядків
        row_order_final = ['Sessions', 'Units Ordered', 'Ordered Product Sales', 'Product Costs', 'Net Profit', 'Actual Price']
        df_comparison_pivot = df_comparison_pivot.reindex(row_order_final)

        return True, df_comparison_pivot

    except Exception as e:
        return False, f"Помилка обробки: {str(e)}"


def style_summary_sheet(ws):
    """Застосовує стилізацію до Summary листа."""
    # Заголовки
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Границі
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    for row in ws.iter_rows():
        for cell in row:
            cell.border = thin_border
            cell.alignment = Alignment(vertical='center')
    
    # Автоширина колонок
    for col_idx, col in enumerate(ws.columns, 1):
        max_length = 0
        column_letter = get_column_letter(col_idx)
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width


def style_product_sheet(ws, df_pivot):
    """Застосовує стилізацію до листа продукту з багаторівневими заголовками."""
    # Заголовки місяців (перший рядок)
    month_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    month_font = Font(bold=True, color="FFFFFF", size=11)
    
    # Заголовки паків (другий рядок)
    pack_fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
    pack_font = Font(bold=True, color="FFFFFF", size=10)
    
    # Заголовок метрик
    metric_fill = PatternFill(start_color="F4B084", end_color="F4B084", fill_type="solid")
    metric_font = Font(bold=True, size=10)
    
    # Стилізація заголовків
    for cell in ws[1]:
        cell.fill = month_fill
        cell.font = month_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    for cell in ws[2]:
        cell.fill = pack_fill
        cell.font = pack_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    for cell in ws['A']:
        cell.fill = metric_fill
        cell.font = metric_font
        cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # Форматування чисел
    for row in ws.iter_rows(min_row=3, min_col=2):
        for cell in row:
            if cell.value is not None:
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal='right', vertical='center')
    
    # Границі
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    for row in ws.iter_rows():
        for cell in row:
            cell.border = thin_border
    
    # Автоширина колонок
    ws.column_dimensions['A'].width = 20
    for col_idx in range(2, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 14


# ===========================================================================================
# ГОЛОВНА ФУНКЦІЯ
# ===========================================================================================

def main():
    print("=" * 80)
    print("МАСОВА АГРЕГАЦІЯ ПРОДУКТІВ: Single Pack vs Double Pack")
    print("=" * 80)
    print(f"\nКоренева директорія: {ROOT_DIR}")
    print(f"Вихідний файл: {OUTPUT_FILE_NAME}\n")
    
    # Перевірка існування кореневої директорії
    if not os.path.isdir(ROOT_DIR):
        print(f"❌ КРИТИЧНА ПОМИЛКА: Коренева директорія не знайдена!")
        return
    
    costs_file_path = os.path.join(ROOT_DIR, COSTS_FILE_NAME)
    if not os.path.isfile(costs_file_path):
        print(f"❌ КРИТИЧНА ПОМИЛКА: Файл констант не знайдено: {costs_file_path}")
        return
    
    # Отримання списку всіх продуктів (директорій)
    all_products = [item for item in os.listdir(ROOT_DIR) if os.path.isdir(os.path.join(ROOT_DIR, item))]
    all_products = sorted(all_products)  # Алфавітне сортування
    
    print(f"Знайдено {len(all_products)} продуктів для обробки\n")
    
    # Обробка кожного продукту
    results = {}
    summary_data = []
    
    for idx, product_name in enumerate(all_products, 1):
        product_dir = os.path.join(ROOT_DIR, product_name)
        print(f"[{idx}/{len(all_products)}] Обробка: {product_name}...")
        
        success, result = process_single_product(product_name, product_dir, costs_file_path)
        
        if success:
            results[product_name] = result
            summary_data.append({
                'Product Name': product_name,
                'Status': '✅ Success',
                'Message': f'{len(result.columns)} місяців оброблено'
            })
            print(f"    ✅ Успішно оброблено\n")
        else:
            summary_data.append({
                'Product Name': product_name,
                'Status': '❌ Error',
                'Message': result
            })
            print(f"    ❌ ПОМИЛКА: {result}\n")
    
    # Створення Excel файлу
    output_path = os.path.join(ROOT_DIR, OUTPUT_FILE_NAME)
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # 1. Summary лист
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        
        # Стилізація Summary
        ws_summary = writer.sheets['Summary']
        style_summary_sheet(ws_summary)
        
        # 2. Листи продуктів (алфавітно)
        for product_name in sorted(results.keys()):
            df_pivot = results[product_name]
            
            # Скорочення назви листа (Excel має ліміт 31 символ)
            sheet_name = product_name[:31]
            
            # Запис даних
            df_pivot.to_excel(writer, sheet_name=sheet_name)
            
            # Стилізація
            ws = writer.sheets[sheet_name]
            style_product_sheet(ws, df_pivot)
    
    print("=" * 80)
    print(f"✅ ЗАВЕРШЕНО!")
    print(f"Успішно оброблено: {len(results)} продуктів")
    print(f"Помилок: {len(summary_data) - len(results)}")
    print(f"\nФайл збережено: {output_path}")
    print("=" * 80)


# ===========================================================================================
# ЗАПУСК
# ===========================================================================================

if __name__ == "__main__":
    main()
