# CONTEXT.md — Повний контекст проекту Amazon Discount Optimization

## Бізнес-контекст

### Клієнт

Власник бренду дієтичних добавок (supplements) на Amazon US marketplace з портфоліо 20+ SKU.

### Бізнес-проблема

Компанія продає продукти в двох варіаціях:
- **Single Pack** — базовий варіант (наприклад, 120 капсул)
- **Double Pack** — подвійний варіант зі знижкою (наприклад, 240 капсул)

**Критичне питання:** Яку знижку встановити на Double Pack, щоб максимізувати чистий прибуток?

### Виклики

1. **Канібалізація продажів:** Занадто велика знижка може переманити клієнтів з Single Pack
2. **Втрата маржі:** Занадто мала знижка не стимулює купувати Double Pack
3. **Конверсія:** Потрібно знайти баланс між ціною та конверсією
4. **Невизначеність:** Немає чіткого розуміння оптимального рівня знижки

### Мета проекту

Розробити **data-driven систему оптимізації знижок**, яка:
- Максимізує чистий прибуток Double Pack
- Враховує вплив на Single Pack продажі
- Зберігає конверсію та лояльність клієнтів
- Базується на реальних історичних даних Amazon

---

## Дані проекту

### Джерела даних

#### 1. Amazon Business Reports (CSV файли)

Місячні звіти з Amazon Seller Central:

**Основні метрики:**
- `Sessions - Total` — загальна кількість сесій
- `Sessions - Total - B2B` — B2B сесії
- `Units Ordered` — кількість замовлених одиниць
- `Units Ordered - B2B` — B2B замовлення
- `Ordered Product Sales` — виторг від продажів
- `Ordered Product Sales - B2B` — B2B виторг

**Період:** Березень 2025 — Серпень 2025 (6 місяців історичних даних)

**Приклад структури:**
```
data/raw/D-Mannose Capsules (example product)/
├── D-Mannose 120 Capsules (Single Pack)/
│   ├── BusinessReport_D-Mannose_120_March_2025.csv
│   ├── BusinessReport_D-Mannose_120_April_2025.csv
│   └── ...
└── D-Mannose 240 Capsules (Double Pack)/
    ├── BusinessReport_D-Mannose_240_April_2025.csv
    ├── BusinessReport_D-Mannose_240_May_2025.csv
    └── ...
```

#### 2. Unit Economics (Excel файл)

Файл `Product Cost Info.xlsx` містить фінансові константи для кожного продукту:

- **COGS** (Cost of Goods Sold) — собівартість товару
- **FBA Fee** — комісія Amazon за виконання замовлення
- **Ref Fee** (Referral Fee) — відсоток комісії Amazon від продажу
- **ASIN** — унікальний ідентифікатор продукту на Amazon

**Приклад:**
| Product | COGS | FBA Fee | Ref Fee | ASIN |
|---------|------|---------|---------|------|
| D-Mannose 120 | $8.50 | $3.22 | 15% | B08X1Y2Z3A |
| D-Mannose 240 | $15.20 | $4.89 | 15% | B08X1Y2Z3B |

### Обсяг даних

- **Продуктів:** 20+ SKU (кожен має Single Pack + Double Pack варіант)
- **Місяців:** 6 місяців історії (деякі продукти мають менше даних)
- **Записів:** ~500+ рядків агрегованих місячних даних

---

## Ключові метрики проекту

### 7 KPI метрик

#### Маркетингові метрики

**1. DP_DR (Double Pack Discount Rate)**
```
DP_DR = 1 - (Actual_Price_DP / (Actual_Price_SP × 2))
```
Рівень знижки Double Pack відносно подвоєної ціни Single Pack.

**Приклад:** Якщо Single Pack = $20, Double Pack = $34, то DP_DR = 1 - (34 / 40) = 0.15 (15% знижка)

---

**2. DP_CR (Conversion Rate)**
```
DP_CR = Units_Ordered_DP / Sessions_DP
```
Коефіцієнт конверсії Double Pack (скільки з відвідувачів купують).

---

**3. DP_TAR (Traffic Attraction Rate)**
```
DP_TAR = Sessions_DP / Sessions_SP
```
Співвідношення трафіку Double Pack до Single Pack (чи привертає знижка увагу).

---

**4. DP_CSC (Cross-Single Conversion)**
```
DP_CSC = Units_Ordered_DP / Sessions_SP
```
Скільки покупців Single Pack в результаті купують Double Pack.

---

#### Фінансові метрики

**5. DP_NPS (Net Profit Share)**
```
DP_NPS = Net_Profit_DP / (Net_Profit_SP + Net_Profit_DP)
```
Частка прибутку Double Pack у загальному прибутку обох варіантів.

---

**6. DP_NPPS (Net Profit Per Session DP)**
```
DP_NPPS = Net_Profit_DP / Sessions_DP
```
Середній прибуток на одну сесію Double Pack.

---

**7. DP_CSPPS (Cross-Single Pack Profit per Session)**
```
DP_CSPPS = Net_Profit_DP / Sessions_SP
```
Прибуток Double Pack на одну сесію Single Pack (вимірює ефективність крос-селу).

---

### Допоміжні розрахункові метрики

**Product Costs:**
```
Product_Costs = (Units_Ordered × (COGS + FBA_Fee)) + (Ordered_Product_Sales × Ref_Fee_Rate)
```

**Net Profit:**
```
Net_Profit = Ordered_Product_Sales - Product_Costs
```

**Actual Price:**
```
Actual_Price = Ordered_Product_Sales / Units_Ordered
```

---

## Методологія

### Data Pipeline

```
1. RAW DATA (CSV)
   ↓
2. AGGREGATION (mass_product_aggregation.py)
   - Об'єднання Total + B2B метрик
   - Розрахунок Product Costs, Net Profit, Actual Price
   - Створення порівняльних таблиць Single vs Double Pack
   ↓
3. KPI CALCULATION (mass_product_kpi.py)
   - Розрахунок 7 KPI метрик
   - Агрегація по місяцях
   ↓
4. MODELING (amazon_dp_dr_model_production.py)
   - Побудова регресій
   - Оптимізація знижок
   - Валідація результатів
   ↓
5. BUSINESS REPORTS (Excel)
   - Full Results
   - Min Discount / Min MAPE / Min RMSE
   - Average Metrics
```

---

### Machine Learning підхід

#### Поліноміальна регресія 3-го порядку

Використовується `np.polyfit(X, Y, 3)` для моделювання залежностей:

```python
y = a₀ + a₁·x + a₂·x² + a₃·x³
```

де:
- `x = DP_DR` (рівень знижки)
- `y` = KPI метрика (DP_CR, DP_TAR, тощо)

**Чому 3-й порядок?**
- Достатньо гнучкий для нелінійних залежностей
- Не перенавчається (на відміну від 4-5 порядків)
- Добре моделює типові залежності ціна-конверсія

---

#### 7 методів оптимізації (Methods A-G)

Кожен метод будує функцію `Net_Profit_DP(DP_DR)` через різні KPI:

**Method A (DP_CR):**
```python
Net_Profit_DP = DP_CR(DP_DR) × Sessions_DP × [Price_DP(DP_DR) - Unit_Costs]
```
Оптимізація через конверсію Double Pack.

**Method B (DP_TAR):**
```python
Net_Profit_DP = DP_TAR(DP_DR) × Sessions_SP × DP_CR(DP_DR) × Margin
```
Оптимізація через залучення трафіку.

**Method C (DP_CSC):**
```python
Net_Profit_DP = DP_CSC(DP_DR) × Sessions_SP × Margin
```
Оптимізація через крос-конверсію з Single Pack.

**Method D (DP_NPS):**
```python
Net_Profit_DP = DP_NPS(DP_DR) × Net_Profit_Total_Avg
```
Оптимізація через частку в загальному прибутку.

**Method E (DP_NPPS):**
```python
Net_Profit_DP = DP_NPPS(DP_DR) × Sessions_DP_Avg
```
Оптимізація через прибуток на сесію DP.

**Method F (DP_CSPPS):**
```python
Net_Profit_DP = DP_CSPPS(DP_DR) × Sessions_SP_Avg
```
Оптимізація через прибуток на сесію SP.

**Method G (Direct Regression):**
```python
Net_Profit_DP = poly_profit(DP_DR)
```
Пряма регресія прибутку від знижки.

---

#### Оптимізація

Використовується `scipy.optimize.minimize_scalar`:

```python
result = minimize_scalar(
    lambda x: -net_profit_dp_func(x),  # Максимізуємо через мінімізацію негативу
    bounds=[lower_bound_dr, upper_bound_dr],
    method='bounded'
)
optimal_DP_DR = result.x
```

**Межі оптимізації:**
```python
lower_bound = max(0.0, min_DP_DR - 0.5 × StDev_DP_DR)
upper_bound = max_DP_DR + 0.5 × StDev_DP_DR
```

Це дозволяє виходити за межі історичних даних, але обмежено (на 0.5 стандартного відхилення).

---

#### Валідація моделей

**MAPE (Mean Absolute Percentage Error):**
```python
MAPE = mean(|y_true - y_pred| / y_true)
```
Показує точність прогнозу у відсотках. **Нижче = краще.**

**RMSE (Root Mean Square Error):**
```python
RMSE = √(mean((y_true - y_pred)²))
```
Показує середню похибку в абсолютних одиницях. **Нижче = краще.**

**R² (Coefficient of Determination):**
```python
R² = 1 - (SS_res / SS_tot)
```
Показує якість апроксимації (0-1). **Вище = краще.**

**Спеціальна логіка:**
Якщо для регресії Sessions_DP(DP_DR) отримано R² ≤ 0.1, використовується середнє значення замість регресії (бо регресія погана).

---

### Стратегії вибору найкращої моделі

Система генерує 5 Excel листів з різними підходами:

1. **Full Results** — всі 7 методів для кожного продукту
2. **Min Discount** — метод з найменшою знижкою (консервативний підхід)
3. **Min MAPE** — метод з найкращою точністю прогнозу
4. **Min RMSE** — метод з найменшою похибкою
5. **Average Metrics** — середнє значення по всіх 7 методах (ensemble)

---

## Результати проекту

### Бізнес-результати (реальні)

- **+24.85%** збільшення чистого прибутку Double Pack
- **~$25,000 - $30,000** додаткового прибутку на місяць
- **20+ продуктів** оптимізовано з індивідуальними рекомендаціями

### Технічні результати

- **7 методів оптимізації** з різними підходами
- **MAPE < 15%** для більшості продуктів (висока точність)
- **R² > 0.7** для ключових регресій
- **Автоматизований pipeline** для масової обробки продуктів

### Приклад рекомендації

**Продукт:** D-Mannose Capsules
**Історична знижка:** 12%
**Рекомендована знижка:** 16.5% (Method B - Min MAPE)
**Прогноз прибутку:** +28% до поточного рівня

---

## Структура проекту (детально)

```
amazon_discount_research/
│
├── business_reports/
│   ├── documents/
│   │   ├── All_Products_Discount_Recommendations.xlsx  # Фінальні рекомендації
│   │   ├── All_Products_KPI.xlsx                       # Агреговані KPI
│   │   └── research_report_d_mannose_capsules_prod_model.html  # HTML звіт
│   └── figures/                                        # Графіки та візуалізації
│
├── data/
│   ├── raw/
│   │   ├── D-Mannose Capsules (example product)/      # Приклад продукту
│   │   │   ├── D-Mannose 120 Capsules (Single Pack)/
│   │   │   │   └── BusinessReport_*.csv               # Місячні звіти
│   │   │   └── D-Mannose 240 Capsules (Double Pack)/
│   │   │       └── BusinessReport_*.csv
│   │   └── Status_Example_Product_August_2025.csv     # Статус продукту
│   │
│   └── processed/
│       ├── D-Mannose Capsules_Comparison_KPI_Summary.xlsx  # Порівняння SP vs DP
│       ├── D-Mannose Capsules_Single_Pack_Final_KPI.xlsx
│       └── D-Mannose Capsules_Double_Pack_Final_KPI.xlsx
│
├── docs/
│   └── technical_specifications_Lomanov.png           # Технічна специфікація
│
├── notebooks/
│   └── exploratory/
│       ├── 01_01_primary_research_by_b_complex.ipynb          # Первинне дослідження
│       ├── 01_02_statistical_analysis_by_mannose.ipynb       # Статистичний аналіз
│       ├── 02_01_product_conversion_benchmarking.ipynb       # Бенчмаркінг
│       └── 02_02_production_model.ipynb                      # Продакшн модель
│
├── src/
│   ├── data_scripts/
│   │   ├── mass_product_aggregation.py                # Агрегація даних SP vs DP
│   │   └── mass_product_kpi.py                        # Розрахунок 7 KPI метрик
│   │
│   └── models_training/
│       └── amazon_dp_dr_model_production.py           # ML модель оптимізації (7 methods)
│
├── CLAUDE.md                                          # Інструкції для Claude Code
├── CONTEXT.md                                         # Цей файл (повний контекст)
├── README.md                                          # Головна документація (English + Ukrainian)
├── LICENSE.txt                                        # Proprietary license
├── requirements.txt                                   # Python залежності
├── environment.yml                                    # Conda environment
└── references.txt                                     # Посилання на методологію
```

---

## Tech Stack

### Python 3.11+

**Core Data Processing:**
- `pandas` >= 2.0.0 — обробка даних, aggregation, pivot tables
- `numpy` >= 1.24.0 — математичні операції, polyfit

**Excel/Spreadsheet:**
- `openpyxl` >= 3.1.0 — читання/запис Excel з форматуванням

**Scientific Computing:**
- `scipy` >= 1.10.0 — optimize.minimize_scalar
- `statsmodels` >= 0.14.0 — статистичні тести

**Visualization:**
- `matplotlib` >= 3.7.0 — графіки
- `seaborn` >= 0.12.0 — статистичні візуалізації

**Development:**
- `jupyter` — інтерактивні notebooks
- `ipykernel` — kernel для Jupyter

---

## Особливості реалізації

### 1. Робота з B2B даними

Amazon надає окремі колонки для B2B метрик. Скрипти об'єднують Total + B2B:

```python
cols_mapping = {
    'Sessions': ['Sessions - Total', 'Sessions - Total - B2B'],
    'Units Ordered': ['Units Ordered', 'Units Ordered - B2B'],
    'Ordered Product Sales': ['Ordered Product Sales', 'Ordered Product Sales - B2B']
}
```

### 2. Обробка спільних місяців

Порівнюються тільки місяці, коли є дані для обох варіантів (Single та Double Pack):

```python
months_single = set(df_single['Month_Year'].unique())
months_double = set(df_double['Month_Year'].unique())
common_months = sorted(list(months_single.intersection(months_double)))
```

### 3. Мінімальна кількість даних

Якщо продукт має менше 3 спільних місяців, він пропускається з попередженням:

```python
if len(common_months) < 3:
    print(f"⚠️  Недостатньо місяців ({len(common_months)}). NaN.")
    continue
```

### 4. Перевірка якості регресії

Для Sessions_DP регресія може бути поганою (немає залежності від знижки). Перевірка:

```python
r2 = calculate_r_squared(Y, poly_func(X))
use_avg = r2 <= 0.1  # Якщо R² низький, беремо середнє
```

### 5. Excel форматування

Всі вихідні файли мають професійне форматування:
- Кольорові заголовки
- Границі комірок
- Автоширина колонок
- Числові формати (#,##0.00)

---

## Обмеження та припущення

### Обмеження

1. **Історичні дані:** Модель базується на минулих даних, може не враховувати майбутні зміни ринку
2. **Сезонність:** 6 місяців даних недостатньо для виявлення річної сезонності
3. **Зовнішні фактори:** Не враховуються конкуренти, PPC витрати, зміни алгоритмів Amazon
4. **Лінійність Unit Economics:** Припускається, що COGS, FBA Fee константи (не залежать від обсягу)

### Припущення

1. Історичні паттерни поведінки покупців зберігаються
2. Конкуренти не змінюють різко цінову політику
3. Amazon не змінює комісії та алгоритми ранжування
4. Якість продукту та відгуки залишаються стабільними

---

## Контактна інформація

**Автор:** Radyslav Lomanov
**Email:** lomanov.mail@gmail.com
**Telegram:** [@radyslav_datascience](https://t.me/radyslav_datascience)
**GitHub:** [radyslav-datascience](https://github.com/radyslav-datascience)
**Portfolio:** [linktr.ee/radyslav.datascience](https://linktr.ee/radyslav.datascience)
**Resume:** [tr.ee/radyslav-portfolio-en](https://tr.ee/radyslav-portfolio-en)

---

**Останнє оновлення:** 2025-11-24
