# ========================================
# ОПТИМІЗАЦІЯ ЗНИЖКИ DOUBLE PACK
# Фінальна версія з усіма доопрацюваннями
# ========================================

# ========== ІМПОРТИ ==========
import pandas as pd
import numpy as np
import os
import re
from scipy.optimize import minimize_scalar
import warnings
warnings.filterwarnings('ignore')

# ========== ДОПОМІЖНІ ФУНКЦІЇ ==========

def get_product_unit_economics(file_path, base_name):
    """Витягує фінансові константи (COGS, FBA Fee, Ref Fee Rate, ASIN)."""
    try:
        df_costs = pd.read_excel(file_path, header=0)
    except FileNotFoundError:
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
    """Обробляє один CSV-файл, об'єднує Total/B2B метрики."""
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


def create_sort_key(month_year_str):
    """Створює ключ сортування datetime."""
    if '_' in month_year_str:
        date_str = month_year_str.replace('_', ' ')
        try:
            return pd.to_datetime(date_str, format='%B %Y')
        except ValueError:
            return pd.NaT
    return pd.NaT


def calculate_r_squared(y_true, y_pred):
    """Розрахунок R²."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - (ss_res / ss_tot) if ss_tot != 0 else 0


def calculate_mape(y_true, y_pred):
    """Розрахунок MAPE."""
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    non_zero_indices = y_true > 0
    if np.sum(non_zero_indices) == 0:
        return np.nan
    return np.mean(np.abs((y_true[non_zero_indices] - y_pred[non_zero_indices]) / y_true[non_zero_indices]))


def calculate_rmse(y_true, y_pred):
    """Розрахунок RMSE."""
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    return np.sqrt(np.mean((y_true - y_pred) ** 2))


# ========== НОВІ ФУНКЦІЇ ДЛЯ ПУНКТУ 2 ==========

def build_reg_units_dp(X, df_raw):
    """Побудова регресії Units_Ordered_DP(DP_DR)."""
    Y = df_raw['Units Ordered_DP'].values
    coefs = np.polyfit(X, Y, 3)
    return np.poly1d(coefs)


def build_reg_sessions_dp_with_check(X, df_raw, Sessions_DP_Avg):
    """Побудова регресії Sessions_DP(DP_DR) з перевіркою R²."""
    Y = df_raw['Sessions_DP'].values
    coefs = np.polyfit(X, Y, 3)
    poly_func = np.poly1d(coefs)
    r2 = calculate_r_squared(Y, poly_func(X))
    use_avg = r2 <= 0.1
    return poly_func, use_avg


def build_reg_price_dp(X, df_raw):
    """Побудова спільної регресії Actual_Price_DP(DP_DR)."""
    Y = df_raw['Actual Price_DP'].values
    coefs = np.polyfit(X, Y, 3)
    return np.poly1d(coefs)


def calc_predict_dp_cr_from_profit(predict_profit, optimal_dr, reg_sessions, reg_price, 
                                    Sessions_DP_Avg, Unit_Costs_Avg, use_avg_sessions):
    """Універсальна функція розрахунку predict_DP_CR для методів D/E/F/G."""
    sessions_val = Sessions_DP_Avg if use_avg_sessions else reg_sessions(optimal_dr)
    margin = reg_price(optimal_dr) - Unit_Costs_Avg
    if sessions_val == 0 or margin == 0:
        return np.nan
    return predict_profit / (sessions_val * margin)


def calc_predict_dp_tar_from_profit(predict_profit, predict_cr, optimal_dr, reg_price, 
                                     Sessions_SP_Avg, Unit_Costs_Avg):
    """Універсальна функція розрахунку predict_DP_TAR для методів D/E/F/G."""
    margin = reg_price(optimal_dr) - Unit_Costs_Avg
    if predict_cr == 0 or Sessions_SP_Avg == 0 or margin == 0:
        return np.nan
    return predict_profit / (predict_cr * Sessions_SP_Avg * margin)


# ========== ІНІЦІАЛІЗАЦІЯ ==========
root_dir = '/Users/radyslav/data_analysis/Amazon/prod_perc_dpack'
costs_file_name = 'Product Cost Info.xlsx'
costs_file_path = os.path.join(root_dir, costs_file_name)
ALL_METHODS_RESULTS = {}

product_folders = [f for f in os.listdir(root_dir) 
                   if os.path.isdir(os.path.join(root_dir, f)) 
                   and not f.startswith('.')]

print(f"Знайдено продуктів: {len(product_folders)}")
print(f"Список: {product_folders}\n")


# ========== ОСНОВНИЙ ЦИКЛ ПО ПРОДУКТАХ ==========
for product_name in product_folders:
    print(f"{'='*70}")
    print(f"Обробка: {product_name}")
    print(f"{'='*70}")
    
    try:
        # ==================== БЛОК 1: АГРЕГАЦІЯ ДАНИХ ====================
        product_dir = os.path.join(root_dir, product_name)
        base_product_name = product_name.replace(' Capsules', '').replace('(Stable Price)', '').strip()
        
        if not os.path.isdir(product_dir):
            raise FileNotFoundError(f"Директорія '{product_dir}' не знайдена")
        
        all_items = os.listdir(product_dir)
        single_pack_folder = next((item for item in all_items if "single pack" in item.lower() 
                                   and os.path.isdir(os.path.join(product_dir, item))), None)
        double_pack_folder = next((item for item in all_items if "double pack" in item.lower() 
                                   and os.path.isdir(os.path.join(product_dir, item))), None)
        
        if not single_pack_folder or not double_pack_folder:
            raise FileNotFoundError("Не знайдено Single/Double Pack папок")
        
        single_pack_dir = os.path.join(product_dir, single_pack_folder)
        double_pack_dir = os.path.join(product_dir, double_pack_folder)
        pack_dirs = {'Single Pack': single_pack_dir, 'Double Pack': double_pack_dir}
        
        def count_csv_files(directory):
            if not os.path.isdir(directory): 
                return 0, []
            csv_files = [f for f in os.listdir(directory) if f.endswith('.csv')]
            return len(csv_files), csv_files
        
        _, single_files_list = count_csv_files(single_pack_dir)
        _, double_files_list = count_csv_files(double_pack_dir)
        pack_files = {'Single Pack': single_files_list, 'Double Pack': double_files_list}
        
        unit_economics = get_product_unit_economics(costs_file_path, base_product_name)
        
        # Агрегація Single Pack
        pack_type = 'Single Pack'
        asin_sp = unit_economics.get(pack_type, {}).get('asin', 'ASIN_NOT_FOUND')
        single_pack_data = []
        
        for file_name in pack_files[pack_type]:
            df_month, _ = process_single_csv(os.path.join(pack_dirs[pack_type], file_name), file_name, asin_sp)
            if df_month is not None:
                single_pack_data.append(df_month)
        
        df_single_raw = pd.concat(single_pack_data, ignore_index=True)
        df_single_raw['Date_Sort'] = df_single_raw['Month_Year'].apply(create_sort_key)
        df_single_kpi = df_single_raw.sort_values(by='Date_Sort').reset_index(drop=True)
        
        if unit_economics and pack_type in unit_economics:
            cogs = unit_economics[pack_type]['cogs']
            fba_fee = unit_economics[pack_type]['fba_fee']
            ref_fee_rate = unit_economics[pack_type]['ref_fee_rate']
            df_single_kpi['Product Costs'] = (df_single_kpi['Units Ordered'] * (cogs + fba_fee)) + \
                                             (df_single_kpi['Ordered Product Sales'] * ref_fee_rate)
            df_single_kpi['Net Profit'] = df_single_kpi['Ordered Product Sales'] - df_single_kpi['Product Costs']
        else:
            df_single_kpi['Product Costs'] = np.nan
            df_single_kpi['Net Profit'] = np.nan
        
        df_single_kpi['Actual Price'] = df_single_kpi['Ordered Product Sales'] / df_single_kpi['Units Ordered']
        final_cols_sp = ['Month_Year', 'Sessions', 'Units Ordered', 'Ordered Product Sales', 
                         'Product Costs', 'Net Profit', 'Actual Price', 'Date_Sort']
        df_single_final = df_single_kpi[final_cols_sp].copy()
        
        # Агрегація Double Pack
        pack_type = 'Double Pack'
        asin_dp = unit_economics.get(pack_type, {}).get('asin', 'ASIN_NOT_FOUND')
        double_pack_data = []
        
        for file_name in pack_files[pack_type]:
            df_month, _ = process_single_csv(os.path.join(pack_dirs[pack_type], file_name), file_name, asin_dp)
            if df_month is not None:
                double_pack_data.append(df_month)
        
        df_double_raw = pd.concat(double_pack_data, ignore_index=True)
        df_double_raw['Date_Sort'] = df_double_raw['Month_Year'].apply(create_sort_key)
        df_double_kpi = df_double_raw.sort_values(by='Date_Sort').reset_index(drop=True)
        
        if unit_economics and pack_type in unit_economics:
            cogs = unit_economics[pack_type]['cogs']
            fba_fee = unit_economics[pack_type]['fba_fee']
            ref_fee_rate = unit_economics[pack_type]['ref_fee_rate']
            df_double_kpi['Product Costs'] = (df_double_kpi['Units Ordered'] * (cogs + fba_fee)) + \
                                             (df_double_kpi['Ordered Product Sales'] * ref_fee_rate)
            df_double_kpi['Net Profit'] = df_double_kpi['Ordered Product Sales'] - df_double_kpi['Product Costs']
        else:
            df_double_kpi['Product Costs'] = np.nan
            df_double_kpi['Net Profit'] = np.nan
        
        df_double_kpi['Actual Price'] = df_double_kpi['Ordered Product Sales'] / df_double_kpi['Units Ordered']
        df_double_final = df_double_kpi[final_cols_sp].copy()
        
        # Консолідація
        months_single = set(df_single_final['Month_Year'].unique())
        months_double = set(df_double_final['Month_Year'].unique())
        common_months = sorted(list(months_single.intersection(months_double)), key=create_sort_key)
        
        # Перевірка достатності даних
        if len(common_months) < 3:
            print(f"⚠️  Недостатньо місяців ({len(common_months)}). NaN.\n")
            methods = ['Method-A-DP_CR', 'Method-B-DP_TAR', 'Method-C-DP_CSC', 
                      'Method-D-DP_NPS', 'Method-E-DP_NPPS', 'Method-F-DP_CSPPS', 'Method-G-Net_Profit_DP_Reg']
            for method in methods:
                ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - {method} - optimal_DP_DR"] = np.nan
                ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - {method} - MAPE"] = np.nan
                ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - {method} - RMSE"] = np.nan
                ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - {method} - predict_Net_Profit_DP"] = np.nan
                ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - {method} - predict_DP_CR"] = np.nan
                ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - {method} - predict_DP_TAR"] = np.nan
                ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - {method} - predict_DP_CSC"] = np.nan
            # ПУНКТ 1: Історичні показники = NaN
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_DR_Avg"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - Net_Profit_DP_Avg"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - Sessions_SP_Avg"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - Sessions_DP_Avg"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_CR_Avg"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_TAR_Avg"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_CSC_Avg"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_NPS_Avg"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_NPPS_Avg"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_CSPPS_Avg"] = np.nan
            continue
        
        # Створення df_comparison_pivot
        pack_type_order = ['Single Pack', 'Double Pack']
        df_single_combined = df_single_final.assign(Pack_Type='Single Pack')
        df_double_combined = df_double_final.assign(Pack_Type='Double Pack')
        df_combined = pd.concat([df_single_combined, df_double_combined], ignore_index=True)
        df_combined_filtered = df_combined[df_combined['Month_Year'].isin(common_months)].copy()
        df_combined_filtered['Pack_Type'] = pd.Categorical(df_combined_filtered['Pack_Type'], 
                                                            categories=pack_type_order, ordered=True)
        
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
        
        
        # ==================== БЛОК 2: РОЗРАХУНОК KPI ====================
        df_kpi = df_comparison_pivot.copy()
        metrics_for_calc = ['Sessions', 'Units Ordered', 'Actual Price', 'Net Profit', 'Product Costs']
        df_calc = df_kpi.loc[metrics_for_calc].T.copy()
        df_calc.index.names = ['Month_Year', 'Pack_Type']
        
        df_sp = df_calc[df_calc.index.get_level_values('Pack_Type') == 'Single Pack'].droplevel('Pack_Type')
        df_dp = df_calc[df_calc.index.get_level_values('Pack_Type') == 'Double Pack'].droplevel('Pack_Type')
        df_raw = df_sp.join(df_dp, lsuffix='_SP', rsuffix='_DP')
        
        df_raw['DP_DR'] = 1 - (df_raw['Actual Price_DP'] / (df_raw['Actual Price_SP'] * 2))
        df_raw['DP_CR'] = df_raw['Units Ordered_DP'] / df_raw['Sessions_DP']
        df_raw['DP_TAR'] = df_raw['Sessions_DP'] / df_raw['Sessions_SP']
        df_raw['DP_CSC'] = df_raw['Units Ordered_DP'] / df_raw['Sessions_SP']
        df_raw['DP_NPS'] = df_raw['Net Profit_DP'] / (df_raw['Net Profit_SP'] + df_raw['Net Profit_DP'])
        df_raw['DP_NPPS'] = df_raw['Net Profit_DP'] / df_raw['Sessions_DP']
        df_raw['DP_CSPPS'] = df_raw['Net Profit_DP'] / df_raw['Sessions_SP']
        
        
        # ==================== ПУНКТ 1: ІСТОРИЧНІ ПОКАЗНИКИ ====================
        DP_DR_Avg = df_raw['DP_DR'].mean()
        Net_Profit_DP_Avg = df_raw['Net Profit_DP'].mean()
        Sessions_SP_Avg = df_raw['Sessions_SP'].mean()
        Sessions_DP_Avg = df_raw['Sessions_DP'].mean()
        DP_CR_Avg = df_raw['DP_CR'].mean()
        DP_TAR_Avg = df_raw['DP_TAR'].mean()
        DP_CSC_Avg = df_raw['DP_CSC'].mean()
        DP_NPS_Avg = df_raw['DP_NPS'].mean()
        DP_NPPS_Avg = df_raw['DP_NPPS'].mean()
        DP_CSPPS_Avg = df_raw['DP_CSPPS'].mean()
        
        # Запис історичних показників
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_DR_Avg"] = DP_DR_Avg
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - Net_Profit_DP_Avg"] = Net_Profit_DP_Avg
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - Sessions_SP_Avg"] = Sessions_SP_Avg
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - Sessions_DP_Avg"] = Sessions_DP_Avg
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_CR_Avg"] = DP_CR_Avg
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_TAR_Avg"] = DP_TAR_Avg
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_CSC_Avg"] = DP_CSC_Avg
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_NPS_Avg"] = DP_NPS_Avg
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_NPPS_Avg"] = DP_NPPS_Avg
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Historical - DP_CSPPS_Avg"] = DP_CSPPS_Avg
        
        
        # ==================== БЛОК 3: СПІЛЬНІ КОНСТАНТИ ТА РЕГРЕСІЇ ====================
        total_product_costs_dp = df_raw['Product Costs_DP'].sum()
        total_units_ordered_dp = df_raw['Units Ordered_DP'].sum()
        Unit_Costs_DP_Avg = total_product_costs_dp / total_units_ordered_dp if total_units_ordered_dp > 0 else 0
        
        Net_Profit_Total_Avg = (df_raw['Net Profit_SP'] + df_raw['Net Profit_DP']).mean()
        
        # Межі оптимізації (0.5 * StDev)
        dp_dr_series = df_raw['DP_DR']
        St_Dev_DP_DR = dp_dr_series.std()
        min_DP_DR = dp_dr_series.min()
        max_DP_DR = dp_dr_series.max()
        lower_bound_dr = max(0.0, min_DP_DR - 0.5 * St_Dev_DP_DR)
        upper_bound_dr = max_DP_DR + 0.5 * St_Dev_DP_DR
        def_Bound_DP_DR = [lower_bound_dr, upper_bound_dr]
        
        # Дані для регресій
        X = df_raw['DP_DR'].values
        poly_order = 3
        
        # ПУНКТ 2: Спільні регресії для всіх методів
        reg_Units_DP = build_reg_units_dp(X, df_raw)
        reg_Sessions_DP, use_avg_sessions = build_reg_sessions_dp_with_check(X, df_raw, Sessions_DP_Avg)
        reg_Price_DP = build_reg_price_dp(X, df_raw)
        
        # Побудова poly_cr один раз (використовується в багатьох методах)
        Y_DP_CR = df_raw['DP_CR'].values
        coefs_cr = np.polyfit(X, Y_DP_CR, poly_order)
        poly_cr = np.poly1d(coefs_cr)
        
        
        # ==================== БЛОК 4: METHOD A (DP_CR) ====================
        Y_Net_Profit_DP_Actual_A = df_raw['Net Profit_DP'].values
        
        if use_avg_sessions:
            final_sessions_func = lambda dp_dr: Sessions_DP_Avg
        else:
            final_sessions_func = reg_Sessions_DP
        
        def net_profit_dp_func_A(dp_dr):
            units_ordered_pred = poly_cr(dp_dr) * final_sessions_func(dp_dr)
            margin_per_unit = reg_Price_DP(dp_dr) - Unit_Costs_DP_Avg
            return units_ordered_pred * margin_per_unit
        
        Y_Net_Profit_DP_Predicted_A = net_profit_dp_func_A(X)
        mape_A = calculate_mape(Y_Net_Profit_DP_Actual_A, Y_Net_Profit_DP_Predicted_A)
        rmse_A = calculate_rmse(Y_Net_Profit_DP_Actual_A, Y_Net_Profit_DP_Predicted_A)
        
        result_A = minimize_scalar(lambda x: -net_profit_dp_func_A(x), bounds=def_Bound_DP_DR, method='bounded')
        optimal_dp_dr_A = result_A.x
        predict_net_profit_A = -result_A.fun
        predict_dp_cr_A = poly_cr(optimal_dp_dr_A)
        
        # ПУНКТ 2: Заповнення predict_DP_TAR та predict_DP_CSC
        units_dp_at_opt_A = reg_Units_DP(optimal_dp_dr_A)
        if predict_dp_cr_A != 0 and Sessions_SP_Avg != 0:
            predict_dp_tar_A = units_dp_at_opt_A / (predict_dp_cr_A * Sessions_SP_Avg)
        else:
            predict_dp_tar_A = np.nan
        predict_dp_csc_A = predict_dp_tar_A * predict_dp_cr_A if not np.isnan(predict_dp_tar_A) else np.nan
        
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-A-DP_CR - optimal_DP_DR"] = optimal_dp_dr_A
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-A-DP_CR - MAPE"] = mape_A
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-A-DP_CR - RMSE"] = rmse_A
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-A-DP_CR - predict_Net_Profit_DP"] = predict_net_profit_A
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-A-DP_CR - predict_DP_CR"] = predict_dp_cr_A
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-A-DP_CR - predict_DP_TAR"] = predict_dp_tar_A
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-A-DP_CR - predict_DP_CSC"] = predict_dp_csc_A
        
        
        # ==================== БЛОК 5: METHOD B (DP_TAR) ====================
        Y_DP_TAR = df_raw['DP_TAR'].values
        Y_Net_Profit_DP_Actual_B = df_raw['Net Profit_DP'].values
        
        coefs_tar = np.polyfit(X, Y_DP_TAR, poly_order)
        poly_tar = np.poly1d(coefs_tar)
        
        def net_profit_dp_func_B(dp_dr):
            sessions_dp_pred = Sessions_SP_Avg * poly_tar(dp_dr)
            units_ordered_pred = sessions_dp_pred * poly_cr(dp_dr)
            margin_per_unit = reg_Price_DP(dp_dr) - Unit_Costs_DP_Avg
            return units_ordered_pred * margin_per_unit
        
        Y_Net_Profit_DP_Predicted_B = net_profit_dp_func_B(X)
        mape_B = calculate_mape(Y_Net_Profit_DP_Actual_B, Y_Net_Profit_DP_Predicted_B)
        rmse_B = calculate_rmse(Y_Net_Profit_DP_Actual_B, Y_Net_Profit_DP_Predicted_B)
        
        result_B = minimize_scalar(lambda x: -net_profit_dp_func_B(x), bounds=def_Bound_DP_DR, method='bounded')
        optimal_dp_dr_B = result_B.x
        predict_net_profit_B = -result_B.fun
        predict_dp_cr_B = poly_cr(optimal_dp_dr_B)
        predict_dp_tar_B = poly_tar(optimal_dp_dr_B)
        
        # ПУНКТ 2: predict_DP_CSC
        predict_dp_csc_B = predict_dp_tar_B * predict_dp_cr_B
        
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-B-DP_TAR - optimal_DP_DR"] = optimal_dp_dr_B
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-B-DP_TAR - MAPE"] = mape_B
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-B-DP_TAR - RMSE"] = rmse_B
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-B-DP_TAR - predict_Net_Profit_DP"] = predict_net_profit_B
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-B-DP_TAR - predict_DP_CR"] = predict_dp_cr_B
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-B-DP_TAR - predict_DP_TAR"] = predict_dp_tar_B
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-B-DP_TAR - predict_DP_CSC"] = predict_dp_csc_B
        
        
        # ==================== БЛОК 6: METHOD C (DP_CSC) ====================
        Y_DP_CSC = df_raw['DP_CSC'].values
        Y_Net_Profit_DP_Actual_C = df_raw['Net Profit_DP'].values
        
        coefs_csc = np.polyfit(X, Y_DP_CSC, poly_order)
        poly_csc = np.poly1d(coefs_csc)
        
        def net_profit_dp_func_C(dp_dr):
            units_ordered_pred = Sessions_SP_Avg * poly_csc(dp_dr)
            margin_per_unit = reg_Price_DP(dp_dr) - Unit_Costs_DP_Avg
            return units_ordered_pred * margin_per_unit
        
        Y_Net_Profit_DP_Predicted_C = net_profit_dp_func_C(X)
        mape_C = calculate_mape(Y_Net_Profit_DP_Actual_C, Y_Net_Profit_DP_Predicted_C)
        rmse_C = calculate_rmse(Y_Net_Profit_DP_Actual_C, Y_Net_Profit_DP_Predicted_C)
        
        result_C = minimize_scalar(lambda x: -net_profit_dp_func_C(x), bounds=def_Bound_DP_DR, method='bounded')
        optimal_dp_dr_C = result_C.x
        predict_net_profit_C = -result_C.fun
        predict_dp_csc_C = poly_csc(optimal_dp_dr_C)
        
        # ПУНКТ 2: predict_DP_CR та predict_DP_TAR
        units_dp_at_opt_C = reg_Units_DP(optimal_dp_dr_C)
        sessions_dp_at_opt_C = Sessions_DP_Avg if use_avg_sessions else reg_Sessions_DP(optimal_dp_dr_C)
        if sessions_dp_at_opt_C != 0:
            predict_dp_cr_C = units_dp_at_opt_C / sessions_dp_at_opt_C
        else:
            predict_dp_cr_C = np.nan
        
        if predict_dp_cr_C != 0 and not np.isnan(predict_dp_cr_C):
            predict_dp_tar_C = predict_dp_csc_C / predict_dp_cr_C
        else:
            predict_dp_tar_C = np.nan
        
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-C-DP_CSC - optimal_DP_DR"] = optimal_dp_dr_C
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-C-DP_CSC - MAPE"] = mape_C
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-C-DP_CSC - RMSE"] = rmse_C
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-C-DP_CSC - predict_Net_Profit_DP"] = predict_net_profit_C
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-C-DP_CSC - predict_DP_CR"] = predict_dp_cr_C
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-C-DP_CSC - predict_DP_TAR"] = predict_dp_tar_C
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-C-DP_CSC - predict_DP_CSC"] = predict_dp_csc_C
        
        
        # ==================== БЛОК 7: METHOD D (DP_NPS) ====================
        Y_DP_NPS = df_raw['DP_NPS'].values
        Y_Net_Profit_DP_Actual_D = df_raw['Net Profit_DP'].values
        
        coefs_nps = np.polyfit(X, Y_DP_NPS, poly_order)
        poly_nps = np.poly1d(coefs_nps)
        
        def net_profit_dp_func_D(dp_dr):
            return Net_Profit_Total_Avg * poly_nps(dp_dr)
        
        Y_Net_Profit_DP_Predicted_D = net_profit_dp_func_D(X)
        mape_D = calculate_mape(Y_Net_Profit_DP_Actual_D, Y_Net_Profit_DP_Predicted_D)
        rmse_D = calculate_rmse(Y_Net_Profit_DP_Actual_D, Y_Net_Profit_DP_Predicted_D)
        
        result_D = minimize_scalar(lambda x: -net_profit_dp_func_D(x), bounds=def_Bound_DP_DR, method='bounded')
        optimal_dp_dr_D = result_D.x
        predict_net_profit_D = -result_D.fun
        
        # ПУНКТ 2: predict_DP_CR, predict_DP_TAR, predict_DP_CSC
        predict_dp_cr_D = calc_predict_dp_cr_from_profit(predict_net_profit_D, optimal_dp_dr_D, 
                                                          reg_Sessions_DP, reg_Price_DP, 
                                                          Sessions_DP_Avg, Unit_Costs_DP_Avg, use_avg_sessions)
        predict_dp_tar_D = calc_predict_dp_tar_from_profit(predict_net_profit_D, predict_dp_cr_D, 
                                                            optimal_dp_dr_D, reg_Price_DP, 
                                                            Sessions_SP_Avg, Unit_Costs_DP_Avg)
        predict_dp_csc_D = predict_dp_tar_D * predict_dp_cr_D if not (np.isnan(predict_dp_tar_D) or np.isnan(predict_dp_cr_D)) else np.nan
        
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-D-DP_NPS - optimal_DP_DR"] = optimal_dp_dr_D
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-D-DP_NPS - MAPE"] = mape_D
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-D-DP_NPS - RMSE"] = rmse_D
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-D-DP_NPS - predict_Net_Profit_DP"] = predict_net_profit_D
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-D-DP_NPS - predict_DP_CR"] = predict_dp_cr_D
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-D-DP_NPS - predict_DP_TAR"] = predict_dp_tar_D
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-D-DP_NPS - predict_DP_CSC"] = predict_dp_csc_D
        
        
        # ==================== БЛОК 8: METHOD E (DP_NPPS) ====================
        Y_DP_NPPS = df_raw['DP_NPPS'].values
        Y_Net_Profit_DP_Actual_E = df_raw['Net Profit_DP'].values
        
        coefs_npps = np.polyfit(X, Y_DP_NPPS, poly_order)
        poly_npps = np.poly1d(coefs_npps)
        
        def net_profit_dp_func_E(dp_dr):
            return Sessions_DP_Avg * poly_npps(dp_dr)
        
        Y_Net_Profit_DP_Predicted_E = net_profit_dp_func_E(X)
        mape_E = calculate_mape(Y_Net_Profit_DP_Actual_E, Y_Net_Profit_DP_Predicted_E)
        rmse_E = calculate_rmse(Y_Net_Profit_DP_Actual_E, Y_Net_Profit_DP_Predicted_E)
        
        result_E = minimize_scalar(lambda x: -net_profit_dp_func_E(x), bounds=def_Bound_DP_DR, method='bounded')
        optimal_dp_dr_E = result_E.x
        predict_net_profit_E = -result_E.fun
        
        # ПУНКТ 2: аналогічно Method D
        predict_dp_cr_E = calc_predict_dp_cr_from_profit(predict_net_profit_E, optimal_dp_dr_E, 
                                                          reg_Sessions_DP, reg_Price_DP, 
                                                          Sessions_DP_Avg, Unit_Costs_DP_Avg, use_avg_sessions)
        predict_dp_tar_E = calc_predict_dp_tar_from_profit(predict_net_profit_E, predict_dp_cr_E, 
                                                            optimal_dp_dr_E, reg_Price_DP, 
                                                            Sessions_SP_Avg, Unit_Costs_DP_Avg)
        predict_dp_csc_E = predict_dp_tar_E * predict_dp_cr_E if not (np.isnan(predict_dp_tar_E) or np.isnan(predict_dp_cr_E)) else np.nan
        
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-E-DP_NPPS - optimal_DP_DR"] = optimal_dp_dr_E
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-E-DP_NPPS - MAPE"] = mape_E
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-E-DP_NPPS - RMSE"] = rmse_E
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-E-DP_NPPS - predict_Net_Profit_DP"] = predict_net_profit_E
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-E-DP_NPPS - predict_DP_CR"] = predict_dp_cr_E
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-E-DP_NPPS - predict_DP_TAR"] = predict_dp_tar_E
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-E-DP_NPPS - predict_DP_CSC"] = predict_dp_csc_E
        
        
        # ==================== БЛОК 9: METHOD F (DP_CSPPS) ====================
        Y_DP_CSPPS = df_raw['DP_CSPPS'].values
        Y_Net_Profit_DP_Actual_F = df_raw['Net Profit_DP'].values
        
        coefs_cspps = np.polyfit(X, Y_DP_CSPPS, poly_order)
        poly_cspps = np.poly1d(coefs_cspps)
        
        def net_profit_dp_func_F(dp_dr):
            return Sessions_SP_Avg * poly_cspps(dp_dr)
        
        Y_Net_Profit_DP_Predicted_F = net_profit_dp_func_F(X)
        mape_F = calculate_mape(Y_Net_Profit_DP_Actual_F, Y_Net_Profit_DP_Predicted_F)
        rmse_F = calculate_rmse(Y_Net_Profit_DP_Actual_F, Y_Net_Profit_DP_Predicted_F)
        
        result_F = minimize_scalar(lambda x: -net_profit_dp_func_F(x), bounds=def_Bound_DP_DR, method='bounded')
        optimal_dp_dr_F = result_F.x
        predict_net_profit_F = -result_F.fun
        
        # ПУНКТ 2: аналогічно Method D
        predict_dp_cr_F = calc_predict_dp_cr_from_profit(predict_net_profit_F, optimal_dp_dr_F, 
                                                          reg_Sessions_DP, reg_Price_DP, 
                                                          Sessions_DP_Avg, Unit_Costs_DP_Avg, use_avg_sessions)
        predict_dp_tar_F = calc_predict_dp_tar_from_profit(predict_net_profit_F, predict_dp_cr_F, 
                                                            optimal_dp_dr_F, reg_Price_DP, 
                                                            Sessions_SP_Avg, Unit_Costs_DP_Avg)
        predict_dp_csc_F = predict_dp_tar_F * predict_dp_cr_F if not (np.isnan(predict_dp_tar_F) or np.isnan(predict_dp_cr_F)) else np.nan
        
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-F-DP_CSPPS - optimal_DP_DR"] = optimal_dp_dr_F
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-F-DP_CSPPS - MAPE"] = mape_F
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-F-DP_CSPPS - RMSE"] = rmse_F
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-F-DP_CSPPS - predict_Net_Profit_DP"] = predict_net_profit_F
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-F-DP_CSPPS - predict_DP_CR"] = predict_dp_cr_F
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-F-DP_CSPPS - predict_DP_TAR"] = predict_dp_tar_F
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-F-DP_CSPPS - predict_DP_CSC"] = predict_dp_csc_F
        
        
        # ==================== БЛОК 10: METHOD G (DIRECT REGRESSION) ====================
        Y_Net_Profit_DP_Actual_G = df_raw['Net Profit_DP'].values
        
        coefs_profit = np.polyfit(X, Y_Net_Profit_DP_Actual_G, poly_order)
        poly_profit = np.poly1d(coefs_profit)
        
        def net_profit_dp_func_G(dp_dr):
            return poly_profit(dp_dr)
        
        Y_Net_Profit_DP_Predicted_G = net_profit_dp_func_G(X)
        mape_G = calculate_mape(Y_Net_Profit_DP_Actual_G, Y_Net_Profit_DP_Predicted_G)
        rmse_G = calculate_rmse(Y_Net_Profit_DP_Actual_G, Y_Net_Profit_DP_Predicted_G)
        
        result_G = minimize_scalar(lambda x: -net_profit_dp_func_G(x), bounds=def_Bound_DP_DR, method='bounded')
        optimal_dp_dr_G = result_G.x
        predict_net_profit_G = -result_G.fun
        
        # ПУНКТ 2: аналогічно Method D
        predict_dp_cr_G = calc_predict_dp_cr_from_profit(predict_net_profit_G, optimal_dp_dr_G, 
                                                          reg_Sessions_DP, reg_Price_DP, 
                                                          Sessions_DP_Avg, Unit_Costs_DP_Avg, use_avg_sessions)
        predict_dp_tar_G = calc_predict_dp_tar_from_profit(predict_net_profit_G, predict_dp_cr_G, 
                                                            optimal_dp_dr_G, reg_Price_DP, 
                                                            Sessions_SP_Avg, Unit_Costs_DP_Avg)
        predict_dp_csc_G = predict_dp_tar_G * predict_dp_cr_G if not (np.isnan(predict_dp_tar_G) or np.isnan(predict_dp_cr_G)) else np.nan
        
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-G-Net_Profit_DP_Reg - optimal_DP_DR"] = optimal_dp_dr_G
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-G-Net_Profit_DP_Reg - MAPE"] = mape_G
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-G-Net_Profit_DP_Reg - RMSE"] = rmse_G
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-G-Net_Profit_DP_Reg - predict_Net_Profit_DP"] = predict_net_profit_G
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-G-Net_Profit_DP_Reg - predict_DP_CR"] = predict_dp_cr_G
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-G-Net_Profit_DP_Reg - predict_DP_TAR"] = predict_dp_tar_G
        ALL_METHODS_RESULTS[f"{product_name} - ASIN: {asin_dp} - Method-G-Net_Profit_DP_Reg - predict_DP_CSC"] = predict_dp_csc_G
        
        print(f"✅ Продукт {product_name} оброблено\n")
        
    except Exception as e:
        print(f"❌ Помилка: {product_name} - {e}\n")
        methods = ['Method-A-DP_CR', 'Method-B-DP_TAR', 'Method-C-DP_CSC', 
                  'Method-D-DP_NPS', 'Method-E-DP_NPPS', 'Method-F-DP_CSPPS', 'Method-G-Net_Profit_DP_Reg']
        for method in methods:
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: UNKNOWN - {method} - optimal_DP_DR"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: UNKNOWN - {method} - MAPE"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: UNKNOWN - {method} - RMSE"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: UNKNOWN - {method} - predict_Net_Profit_DP"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: UNKNOWN - {method} - predict_DP_CR"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: UNKNOWN - {method} - predict_DP_TAR"] = np.nan
            ALL_METHODS_RESULTS[f"{product_name} - ASIN: UNKNOWN - {method} - predict_DP_CSC"] = np.nan
        continue


# ========== ПУНКТ 3: ВИВІД РЕЗУЛЬТАТІВ В EXCEL ==========
print(f"\n{'='*70}")
print("ТРАНСФОРМАЦІЯ ТА ВИВІД РЕЗУЛЬТАТІВ")
print(f"{'='*70}\n")

# Створення DataFrame
results_list = []
for key, value in ALL_METHODS_RESULTS.items():
    parts = key.split(' - ')
    product_name = parts[0]
    asin = parts[1].replace('ASIN: ', '')
    category_or_method = parts[2]
    metric = parts[3]
    
    results_list.append({
        'Product': product_name,
        'ASIN': asin,
        'Category': category_or_method,
        'Metric': metric,
        'Value': value
    })

df_results = pd.DataFrame(results_list)
df_results['Product_ASIN'] = df_results['Product'] + ' - ASIN: ' + df_results['ASIN']
df_results['Category_Metric'] = df_results['Category'] + ' - ' + df_results['Metric']

# Базовий pivot
df_pivot = df_results.pivot_table(
    index='Product_ASIN',
    columns='Category_Metric',
    values='Value',
    aggfunc='first',
    dropna=False
)

# ПУНКТ 1: Впорядкування колонок (Історичні показники + Методи)
historical_cols = [
    'Historical - DP_DR_Avg',
    'Historical - Net_Profit_DP_Avg',
    'Historical - Sessions_SP_Avg',
    'Historical - Sessions_DP_Avg',
    'Historical - DP_CR_Avg',
    'Historical - DP_TAR_Avg',
    'Historical - DP_CSC_Avg',
    'Historical - DP_NPS_Avg',
    'Historical - DP_NPPS_Avg',
    'Historical - DP_CSPPS_Avg'
]

methods_order = ['Method-A-DP_CR', 'Method-B-DP_TAR', 'Method-C-DP_CSC', 
                 'Method-D-DP_NPS', 'Method-E-DP_NPPS', 'Method-F-DP_CSPPS', 
                 'Method-G-Net_Profit_DP_Reg']
metrics_order = ['optimal_DP_DR', 'MAPE', 'RMSE', 'predict_Net_Profit_DP', 
                 'predict_DP_CR', 'predict_DP_TAR', 'predict_DP_CSC']

ordered_cols = []
for col in historical_cols:
    if col in df_pivot.columns:
        ordered_cols.append(col)

for method in methods_order:
    for metric in metrics_order:
        col_name = f"{method} - {metric}"
        if col_name in df_pivot.columns:
            ordered_cols.append(col_name)

df_final_full = df_pivot[ordered_cols]

# ПУНКТ 3a: Sheet 1 - Full Results
print("✅ Sheet 1: Full Results")

# ПУНКТ 3b: Sheet 2 - Min Discount
print("✅ Sheet 2: Min Discount")
df_min_discount_list = []
for product_asin in df_final_full.index:
    row_data = {'Product_ASIN': product_asin}
    
    # Історичні показники
    for col in historical_cols:
        if col in df_final_full.columns:
            row_data[col] = df_final_full.loc[product_asin, col]
    
    # Знайти метод з мінімальною знижкою
    discount_cols = [f"{m} - optimal_DP_DR" for m in methods_order]
    discount_values = {col: df_final_full.loc[product_asin, col] for col in discount_cols if col in df_final_full.columns}
    discount_values_clean = {k: v for k, v in discount_values.items() if not np.isnan(v)}
    
    if discount_values_clean:
        min_discount_col = min(discount_values_clean, key=discount_values_clean.get)
        best_method = min_discount_col.replace(' - optimal_DP_DR', '')
        
        for metric in metrics_order:
            col_name = f"{best_method} - {metric}"
            if col_name in df_final_full.columns:
                row_data[col_name] = df_final_full.loc[product_asin, col_name]
    
    df_min_discount_list.append(row_data)

df_min_discount = pd.DataFrame(df_min_discount_list).set_index('Product_ASIN')

# ПУНКТ 3c: Sheet 3 - Min MAPE
print("✅ Sheet 3: Min MAPE")
df_min_mape_list = []
for product_asin in df_final_full.index:
    row_data = {'Product_ASIN': product_asin}
    
    for col in historical_cols:
        if col in df_final_full.columns:
            row_data[col] = df_final_full.loc[product_asin, col]
    
    mape_cols = [f"{m} - MAPE" for m in methods_order]
    mape_values = {col: df_final_full.loc[product_asin, col] for col in mape_cols if col in df_final_full.columns}
    mape_values_clean = {k: v for k, v in mape_values.items() if not np.isnan(v)}
    
    if mape_values_clean:
        min_mape_col = min(mape_values_clean, key=mape_values_clean.get)
        best_method = min_mape_col.replace(' - MAPE', '')
        
        for metric in metrics_order:
            col_name = f"{best_method} - {metric}"
            if col_name in df_final_full.columns:
                row_data[col_name] = df_final_full.loc[product_asin, col_name]
    
    df_min_mape_list.append(row_data)

df_min_mape = pd.DataFrame(df_min_mape_list).set_index('Product_ASIN')

# ПУНКТ 3d: Sheet 4 - Min RMSE
print("✅ Sheet 4: Min RMSE")
df_min_rmse_list = []
for product_asin in df_final_full.index:
    row_data = {'Product_ASIN': product_asin}
    
    for col in historical_cols:
        if col in df_final_full.columns:
            row_data[col] = df_final_full.loc[product_asin, col]
    
    rmse_cols = [f"{m} - RMSE" for m in methods_order]
    rmse_values = {col: df_final_full.loc[product_asin, col] for col in rmse_cols if col in df_final_full.columns}
    rmse_values_clean = {k: v for k, v in rmse_values.items() if not np.isnan(v)}
    
    if rmse_values_clean:
        min_rmse_col = min(rmse_values_clean, key=rmse_values_clean.get)
        best_method = min_rmse_col.replace(' - RMSE', '')
        
        for metric in metrics_order:
            col_name = f"{best_method} - {metric}"
            if col_name in df_final_full.columns:
                row_data[col_name] = df_final_full.loc[product_asin, col_name]
    
    df_min_rmse_list.append(row_data)

df_min_rmse = pd.DataFrame(df_min_rmse_list).set_index('Product_ASIN')

# ПУНКТ 3e: Sheet 5 - Average Metrics
print("✅ Sheet 5: Average Metrics")
df_average_list = []
for product_asin in df_final_full.index:
    row_data = {'Product_ASIN': product_asin}
    
    for col in historical_cols:
        if col in df_final_full.columns:
            row_data[col] = df_final_full.loc[product_asin, col]
    
    # Розрахунок середніх по всіх методах
    for metric in metrics_order:
        metric_cols = [f"{m} - {metric}" for m in methods_order]
        values = [df_final_full.loc[product_asin, col] for col in metric_cols if col in df_final_full.columns]
        values_clean = [v for v in values if not np.isnan(v)]
        
        if values_clean:
            row_data[f"Average - {metric}"] = np.mean(values_clean)
        else:
            row_data[f"Average - {metric}"] = np.nan
    
    df_average_list.append(row_data)

df_average = pd.DataFrame(df_average_list).set_index('Product_ASIN')

# ПУНКТ 3f: Запис в один Excel файл з 5 sheets
output_path = os.path.join(root_dir, 'optimization_results.xlsx')
with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    df_final_full.to_excel(writer, sheet_name='Full Results')
    df_min_discount.to_excel(writer, sheet_name='Min Discount')
    df_min_mape.to_excel(writer, sheet_name='Min MAPE')
    df_min_rmse.to_excel(writer, sheet_name='Min RMSE')
    df_average.to_excel(writer, sheet_name='Average Metrics')

print(f"\n✅ Результати збережено: {output_path}")
print("✅ 5 sheets: Full Results, Min Discount, Min MAPE, Min RMSE, Average Metrics")
print("\n🎉 ЗАВЕРШЕНО!")