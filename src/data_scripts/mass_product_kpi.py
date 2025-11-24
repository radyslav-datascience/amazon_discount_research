# ===========================================================================================
# МАСОВИЙ РОЗРАХУНОК KPI: Single Pack vs Double Pack
# ===========================================================================================

import pandas as pd
import numpy as np
import os
import re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import warnings
warnings.filterwarnings('ignore')

# ===========================================================================================
# НАЛАШТУВАННЯ
# ===========================================================================================

ROOT_DIR = '/Users/radyslav/data_analysis/Amazon/prod_perc_dpack'
COSTS_FILE_NAME = 'Product Cost Info.xlsx'
OUTPUT_FILE_NAME = 'All_Products_KPI.xlsx'

# ===========================================================================================
# ДОПОМІЖНІ ФУНКЦІЇ (З ПОПЕРЕДНЬОГО СКРИПТУ)
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
    except Exception:
        return {}
    
    df_costs.columns = df_costs.columns.str.strip().str.lower().str.replace(' ', '_')
    df_costs = df_costs.dropna(subset=['short_product_name']).reset_index(drop=True)

    df_product_group = df_costs[df_costs['short_product_name'].str.contains(base_name, case=False, na=False)].copy()

    if df_product_group.empty:
        return {}

    df_product_group['unit_count'] = df_product_group['short_product_name'].str.extract(r'(\d+)').astype(float)
    df_product_group = df_product_group.dropna(subset=['unit_count'])
    if len(df_product_group) < 2:
        return {}

    idx_dp = df_product_group['unit_count'].idxmax()
    idx_sp = df_product_group['unit_count'].idxmin()

    results_raw = {'Single Pack': df_product_group.loc[idx_sp], 'Double Pack': df_product_group.loc[idx_dp]}
    unit_economics_final = {}
    
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
        if not os.path.isdir(product_dir):
            return False, f"Директорія не знайдена: {product_dir}"

        all_items = os.listdir(product_dir)
        single_pack_folder = next((item for item in all_items if "single pack" in item.lower() and os.path.isdir(os.path.join(product_dir, item))), None)
        double_pack_folder = next((item for item in all_items if "double pack" in item.lower() and os.path.isdir(os.path.join(product_dir, item))), None)

        if not single_pack_folder or not double_pack_folder:
            return False, "Не знайдено підпапок Single Pack або Double Pack"

        single_pack_dir = os.path.join(product_dir, single_pack_folder)
        double_pack_dir = os.path.join(product_dir, double_pack_folder)

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

        sorted_cols = []
        for month in common_months:
            for pack in pack_type_order:
                sorted_cols.append((month, pack))

        df_comparison_pivot = df_comparison_pivot[sorted_cols]
        df_comparison_pivot.columns.names = ['Month_Year', 'Pack_Type']

        row_order_final = ['Sessions', 'Units Ordered', 'Ordered Product Sales', 'Product Costs', 'Net Profit', 'Actual Price']
        df_comparison_pivot = df_comparison_pivot.reindex(row_order_final)

        return True, df_comparison_pivot

    except Exception as e:
        return False, f"Помилка обробки: {str(e)}"


# ===========================================================================================
# НОВА ФУНКЦІЯ: РОЗРАХУНОК KPI
# ===========================================================================================

def calculate_product_kpi(df_comparison_pivot):
    """
    Розраховує 7 KPI метрик на основі df_comparison_pivot.
    
    Args:
        df_comparison_pivot: DataFrame з метриками (Sessions, Units Ordered тощо)
    
    Returns:
        tuple: (success: bool, df_kpi_pivot: pd.DataFrame or str error_message)
    """
    try:
        # Підготовка даних
        df_kpi = df_comparison_pivot.copy()
        metrics_for_calc = ['Sessions', 'Units Ordered', 'Actual Price', 'Net Profit', 'Product Costs']
        
        # Створення DataFrame для розрахунків
        df_calc = df_kpi.loc[metrics_for_calc].T.copy()
        df_calc.index.names = ['Month_Year', 'Pack_Type']
        
        # Розділяємо дані по паках
        df_sp = df_calc[df_calc.index.get_level_values('Pack_Type') == 'Single Pack'].droplevel('Pack_Type')
        df_dp = df_calc[df_calc.index.get_level_values('Pack_Type') == 'Double Pack'].droplevel('Pack_Type')
        
        # Об'єднуємо обидва DF за місяцями
        df_raw = df_sp.join(df_dp, lsuffix='_SP', rsuffix='_DP')
        
        # Розрахунок KPI
        # МАРКЕТИНГОВІ KPI
        df_raw['DP_DR'] = 1 - (df_raw['Actual Price_DP'] / (df_raw['Actual Price_SP'] * 2))
        df_raw['DP_CR'] = df_raw['Units Ordered_DP'] / df_raw['Sessions_DP']
        df_raw['DP_TAR'] = df_raw['Sessions_DP'] / df_raw['Sessions_SP']
        df_raw['DP_CSC'] = df_raw['Units Ordered_DP'] / df_raw['Sessions_SP']
        
        # ФІНАНСОВІ KPI
        df_raw['DP_NPS'] = df_raw['Net Profit_DP'] / (df_raw['Net Profit_SP'] + df_raw['Net Profit_DP'])
        df_raw['DP_NPPS'] = df_raw['Net Profit_DP'] / df_raw['Sessions_DP']
        df_raw['DP_CSPPS'] = df_raw['Net Profit_DP'] / df_raw['Sessions_SP']
        
        # Створення фінального DataFrame з KPI
        kpi_cols = ['DP_DR', 'DP_CR', 'DP_TAR', 'DP_CSC', 'DP_NPS', 'DP_NPPS', 'DP_CSPPS']
        df_kpi_calculated = df_raw[kpi_cols].copy()
        
        # Транспонуємо для формату: Метрики (рядки) x Місяці (колонки)
        df_kpi_pivot = df_kpi_calculated.T
        
        # Забезпечуємо правильний порядок рядків
        df_kpi_pivot = df_kpi_pivot.reindex(kpi_cols)
        
        return True, df_kpi_pivot
        
    except Exception as e:
        return False, f"Помилка розрахунку KPI: {str(e)}"


# ===========================================================================================
# СТИЛІЗАЦІЯ
# ===========================================================================================

def style_summary_sheet(ws):
    """Застосовує стилізацію до Summary листа."""
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
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


def style_kpi_sheet(ws):
    """Застосовує стилізацію до листа KPI."""
    # Заголовок метрик (колонка A)
    metric_fill = PatternFill(start_color="F4B084", end_color="F4B084", fill_type="solid")
    metric_font = Font(bold=True, size=10)
    
    # Заголовки місяців (перший рядок)
    month_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    month_font = Font(bold=True, color="FFFFFF", size=11)
    
    # Стилізація заголовків місяців
    for cell in ws[1]:
        cell.fill = month_fill
        cell.font = month_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Стилізація назв метрик
    for cell in ws['A']:
        cell.fill = metric_fill
        cell.font = metric_font
        cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # Форматування чисел
    for row in ws.iter_rows(min_row=2, min_col=2):
        for cell in row:
            if cell.value is not None:
                cell.number_format = '0.0000'
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
    ws.column_dimensions['A'].width = 15
    for col_idx in range(2, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 14


# ===========================================================================================
# ГОЛОВНА ФУНКЦІЯ
# ===========================================================================================

def main():
    print("=" * 80)
    print("МАСОВИЙ РОЗРАХУНОК KPI: Single Pack vs Double Pack")
    print("=" * 80)
    print(f"\nКоренева директорія: {ROOT_DIR}")
    print(f"Вихідний файл: {OUTPUT_FILE_NAME}\n")
    
    if not os.path.isdir(ROOT_DIR):
        print(f"❌ КРИТИЧНА ПОМИЛКА: Коренева директорія не знайдена!")
        return
    
    costs_file_path = os.path.join(ROOT_DIR, COSTS_FILE_NAME)
    if not os.path.isfile(costs_file_path):
        print(f"❌ КРИТИЧНА ПОМИЛКА: Файл констант не знайдено: {costs_file_path}")
        return
    
    all_products = [item for item in os.listdir(ROOT_DIR) if os.path.isdir(os.path.join(ROOT_DIR, item))]
    all_products = sorted(all_products)
    
    print(f"Знайдено {len(all_products)} продуктів для обробки\n")
    
    results = {}
    summary_data = []
    
    for idx, product_name in enumerate(all_products, 1):
        product_dir = os.path.join(ROOT_DIR, product_name)
        print(f"[{idx}/{len(all_products)}] Обробка: {product_name}...")
        
        # Спочатку отримуємо базові дані
        success_base, result_base = process_single_product(product_name, product_dir, costs_file_path)
        
        if not success_base:
            summary_data.append({
                'Product Name': product_name,
                'Status': '❌ Error',
                'Message': result_base
            })
            print(f"    ❌ ПОМИЛКА (базові дані): {result_base}\n")
            continue
        
        # Потім розраховуємо KPI
        success_kpi, result_kpi = calculate_product_kpi(result_base)
        
        if success_kpi:
            results[product_name] = result_kpi
            summary_data.append({
                'Product Name': product_name,
                'Status': '✅ Success',
                'Message': f'{len(result_kpi.columns)} місяців оброблено'
            })
            print(f"    ✅ Успішно розраховано KPI\n")
        else:
            summary_data.append({
                'Product Name': product_name,
                'Status': '❌ Error',
                'Message': result_kpi
            })
            print(f"    ❌ ПОМИЛКА (KPI): {result_kpi}\n")
    
    # Створення Excel файлу
    output_path = os.path.join(ROOT_DIR, OUTPUT_FILE_NAME)
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # 1. Summary лист
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        
        ws_summary = writer.sheets['Summary']
        style_summary_sheet(ws_summary)
        
        # 2. Листи KPI продуктів (алфавітно)
        for product_name in sorted(results.keys()):
            df_kpi = results[product_name]
            
            sheet_name = product_name[:31]
            
            df_kpi.to_excel(writer, sheet_name=sheet_name)
            
            ws = writer.sheets[sheet_name]
            style_kpi_sheet(ws)
    
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
