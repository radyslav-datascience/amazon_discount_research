# 📊 Amazon Double Pack Discount Optimization

> Data-driven optimization system for maximizing profit through intelligent discount strategies on Amazon US marketplace

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE.txt)
[![Status](https://img.shields.io/badge/Status-Production-success.svg)]()

---

## 🎯 Business Challenge

A dietary supplement brand selling on Amazon US faced a critical pricing decision: **What discount should be applied to Double Pack products to maximize net profit?**

### The Problem

The company offers products in two variations:
- **Single Pack** — base variant (e.g., 120 capsules)
- **Double Pack** — bundle with discount (e.g., 240 capsules)

**Key challenges:**
- ❌ Too large discount → cannibalization of Single Pack sales
- ❌ Too small discount → customers don't purchase Double Pack
- ❌ No data-driven approach → guessing optimal discount rate
- ❌ Risk of losing margin or conversion

---

## 💡 Solution

A **machine learning-powered optimization system** that:

✅ Analyzes historical Amazon Business Reports data
✅ Calculates 7 custom KPI metrics for e-commerce
✅ Builds polynomial regression models (3rd order)
✅ Tests 7 different optimization methods (A-G)
✅ Recommends optimal discount for each product
✅ Validates results using MAPE, RMSE, R² metrics

---

## 📈 Results

### Business Impact (Real Data)

| Metric | Value |
|--------|-------|
| 💰 **Net Profit Increase** | **+24.85%** |
| 💵 **Additional Monthly Profit** | **$25,000 - $30,000** |
| 📦 **Products Optimized** | **20+ SKUs** |
| 🎯 **Average Model Accuracy (MAPE)** | **<15%** |

### Example: D-Mannose Capsules

- **Historical Discount:** 12%
- **Recommended Discount:** 16.5% (Method B - Min MAPE)
- **Profit Increase:** +28% vs current level

---

## 🔬 Methodology

### Data Pipeline

```
┌─────────────────┐
│  Amazon Reports │  Sessions, Orders, Sales (CSV)
│   (6 months)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Aggregation   │  Combine Total + B2B metrics
│                 │  Calculate costs, profit, prices
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ KPI Calculation │  7 Custom Metrics (DP_DR, DP_CR, etc.)
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ML Modeling    │  Polynomial Regression (3rd order)
│   (7 Methods)   │  scipy.optimize.minimize_scalar
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Business Report │  5 Excel Sheets with Recommendations
│                 │
└─────────────────┘
```

---

### Machine Learning Approach

#### 1. Polynomial Regression (3rd Order)

Models relationships between discount rate and KPIs:

```python
y = a₀ + a₁·x + a₂·x² + a₃·x³
```

where:
- `x = DP_DR` (discount rate)
- `y = KPI` (conversion, profit, traffic, etc.)

#### 2. Seven Optimization Methods

Each method builds a different profit function:

| Method | Optimization Target | Formula |
|--------|-------------------|---------|
| **A** | Conversion Rate | `Net_Profit = DP_CR(DR) × Sessions × Margin` |
| **B** | Traffic Attraction | `Net_Profit = DP_TAR(DR) × Sessions_SP × DP_CR × Margin` |
| **C** | Cross-Sell Conversion | `Net_Profit = DP_CSC(DR) × Sessions_SP × Margin` |
| **D** | Net Profit Share | `Net_Profit = DP_NPS(DR) × Total_Profit_Avg` |
| **E** | Profit Per Session DP | `Net_Profit = DP_NPPS(DR) × Sessions_DP_Avg` |
| **F** | Cross-Sell Profit | `Net_Profit = DP_CSPPS(DR) × Sessions_SP_Avg` |
| **G** | Direct Regression | `Net_Profit = poly_profit(DR)` |

#### 3. Optimization Algorithm

Uses `scipy.optimize.minimize_scalar` with bounded search:

```python
optimal_discount = minimize_scalar(
    lambda x: -net_profit_function(x),
    bounds=[lower_bound, upper_bound],
    method='bounded'
)
```

#### 4. Model Validation

- **MAPE** (Mean Absolute Percentage Error) — forecast accuracy
- **RMSE** (Root Mean Square Error) — prediction error
- **R²** (Coefficient of Determination) — model quality

---

### Key Metrics (7 KPIs)

| Metric | Description | Type |
|--------|-------------|------|
| **DP_DR** | Double Pack Discount Rate | Marketing |
| **DP_CR** | Conversion Rate | Marketing |
| **DP_TAR** | Traffic Attraction Rate | Marketing |
| **DP_CSC** | Cross-Single Conversion | Marketing |
| **DP_NPS** | Net Profit Share | Financial |
| **DP_NPPS** | Net Profit Per Session DP | Financial |
| **DP_CSPPS** | Cross-Single Profit Per Session | Financial |

---

## 🛠 Tech Stack

### Core Technologies

- **Python 3.11+** — programming language
- **pandas** — data processing, aggregation, pivot tables
- **numpy** — mathematical operations, polynomial fitting
- **scipy** — optimization algorithms (`minimize_scalar`)
- **statsmodels** — statistical analysis

### Data & Reporting

- **openpyxl** — Excel files with formatting
- **matplotlib** — data visualization
- **seaborn** — statistical plots
- **jupyter** — interactive notebooks

---

## 📁 Project Structure

```
amazon_discount_research/
│
├── business_reports/              # Final business reports and recommendations
│   ├── documents/
│   │   ├── All_Products_Discount_Recommendations.xlsx
│   │   ├── All_Products_KPI.xlsx
│   │   └── research_report_*.html
│   └── figures/                   # Charts and visualizations
│
├── data/
│   ├── raw/                       # Amazon Business Reports (CSV)
│   │   └── D-Mannose Capsules (example product)/
│   │       ├── D-Mannose 120 Capsules (Single Pack)/
│   │       └── D-Mannose 240 Capsules (Double Pack)/
│   └── processed/                 # Processed data with calculated KPIs
│
├── docs/                          # Technical documentation
│
├── notebooks/
│   └── exploratory/               # Jupyter notebooks with research
│       ├── 01_01_primary_research_by_b_complex.ipynb
│       ├── 01_02_statistical_analysis_by_mannose.ipynb
│       ├── 02_01_product_conversion_benchmarking.ipynb
│       └── 02_02_production_model.ipynb
│
├── src/
│   ├── data_scripts/
│   │   ├── mass_product_aggregation.py    # Data aggregation SP vs DP
│   │   └── mass_product_kpi.py            # Calculate 7 KPI metrics
│   │
│   └── models_training/
│       └── amazon_dp_dr_model_production.py   # ML optimization model (7 methods)
│
├── CLAUDE.md                      # Instructions for Claude Code
├── CONTEXT.md                     # Full project context
├── README.md                      # This file
├── LICENSE.txt                    # Proprietary license
├── requirements.txt               # Python dependencies
├── environment.yml                # Conda environment
└── references.txt                 # Methodology references
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- pip or conda package manager

### Installation

#### Option 1: pip

```bash
# Clone repository
git clone https://github.com/radyslav-datascience/amazon_discount_research.git
cd amazon_discount_research

# Install dependencies
pip install -r requirements.txt
```

#### Option 2: conda

```bash
# Clone repository
git clone https://github.com/radyslav-datascience/amazon_discount_research.git
cd amazon_discount_research

# Create conda environment
conda env create -f environment.yml
conda activate research
```

### Usage

#### 1. Aggregate Data

```bash
python src/data_scripts/mass_product_aggregation.py
```

Outputs: `All_Products_Aggregation.xlsx`

#### 2. Calculate KPIs

```bash
python src/data_scripts/mass_product_kpi.py
```

Outputs: `All_Products_KPI.xlsx`

#### 3. Run Optimization Model

```bash
python src/models_training/amazon_dp_dr_model_production.py
```

Outputs: `optimization_results.xlsx` with 5 sheets:
- **Full Results** — all methods for all products
- **Min Discount** — conservative strategy (smallest discount)
- **Min MAPE** — best forecast accuracy
- **Min RMSE** — smallest prediction error
- **Average Metrics** — ensemble approach (average across methods)

---

## 📊 Sample Output

The system generates Excel reports with:

### Discount Recommendations Table

| Product | ASIN | Optimal Discount | Method | Predicted Profit | MAPE | RMSE |
|---------|------|-----------------|--------|-----------------|------|------|
| D-Mannose 120/240 | B08X1Y2Z3B | 16.5% | Method-B | $8,542 | 12.3% | $421 |
| B-Complex 60/120 | B07K9M3N4P | 14.2% | Method-A | $6,234 | 10.8% | $312 |
| ... | ... | ... | ... | ... | ... | ... |

### KPI Predictions

For each product and optimal discount:
- Predicted Conversion Rate (DP_CR)
- Predicted Traffic Attraction (DP_TAR)
- Predicted Cross-Sell Rate (DP_CSC)
- Predicted Net Profit (DP)

---

## 📚 Documentation

- **[CONTEXT.md](CONTEXT.md)** — Full project context (business problem, data, methodology)
- **[CLAUDE.md](CLAUDE.md)** — Instructions for Claude Code
- **[Technical Specifications](docs/)** — Detailed technical documentation
- **[Research Notebooks](notebooks/exploratory/)** — Jupyter notebooks with analysis
- **[Data Science Methods (Notion)](https://tr.ee/radyslav-datascience-notion)** — Methodology deep-dive

---

## 🎓 Skills Demonstrated

This project showcases:

- ✅ **Business Analytics** — translating business problems into data science solutions
- ✅ **E-commerce Domain Expertise** — Amazon marketplace, unit economics, pricing
- ✅ **Data Engineering** — ETL pipelines, data aggregation, cleaning
- ✅ **Feature Engineering** — creating custom KPI metrics from raw data
- ✅ **Machine Learning** — polynomial regression, optimization algorithms
- ✅ **Statistical Validation** — MAPE, RMSE, R² analysis
- ✅ **Python Development** — pandas, numpy, scipy, openpyxl
- ✅ **Automation** — scalable scripts for 20+ products
- ✅ **Business Reporting** — Excel dashboards with actionable insights

---

## 👤 Author

**Radyslav Lomanov**

Data Scientist | Business Analyst | E-commerce Analytics Specialist

### Contact

- 📧 **Email:** [lomanov.mail@gmail.com](mailto:lomanov.mail@gmail.com)
- 📱 **Phone:** +380950359405
- 💬 **Telegram:** [@radyslav_datascience](https://t.me/radyslav_datascience)

### Links

- 🔗 **All Links:** [linktr.ee/radyslav.datascience](https://linktr.ee/radyslav.datascience)
- 💼 **Portfolio Website:** [tr.ee/radyslav-portfolio-en](https://tr.ee/radyslav-portfolio-en)
- 📚 **Data Science Methods:** [tr.ee/radyslav-datascience-notion](https://tr.ee/radyslav-datascience-notion)
- 💻 **GitHub:** [github.com/radyslav-datascience](https://github.com/radyslav-datascience)

---

## 📜 License

This project is proprietary and confidential. All rights reserved.

**Copyright © 2025 Radyslav Lomanov**

Unauthorized reproduction, distribution, or commercial use is strictly prohibited without prior written permission from the author.

For collaboration inquiries or licensing arrangements, please contact:
- Email: lomanov.mail@gmail.com
- Telegram: https://t.me/radyslav_datascience

See [LICENSE.txt](LICENSE.txt) for full terms.

---

## 🙏 Acknowledgments

This project was developed as part of a real client engagement for an Amazon US marketplace seller. All sensitive client data has been anonymized. The methodologies and results presented are authentic and reflect production-level work.

---

<br>

---

<br>

# 🇺🇦 Українська версія

> Система оптимізації знижок на основі даних для максимізації прибутку на маркетплейсі Amazon US

---

## 🎯 Бізнес-виклик

Бренд дієтичних добавок на Amazon US зіткнувся з критичним питанням ціноутворення: **Яку знижку встановити на Double Pack продукти, щоб максимізувати чистий прибуток?**

### Проблема

Компанія пропонує продукти в двох варіантах:
- **Single Pack** — базовий варіант (наприклад, 120 капсул)
- **Double Pack** — подвійний пакет зі знижкою (наприклад, 240 капсул)

**Ключові виклики:**
- ❌ Занадто велика знижка → канібалізація продажів Single Pack
- ❌ Занадто мала знижка → клієнти не купують Double Pack
- ❌ Відсутність data-driven підходу → вгадування оптимальної знижки
- ❌ Ризик втрати маржі або конверсії

---

## 💡 Рішення

**Система оптимізації на основі машинного навчання**, яка:

✅ Аналізує історичні дані Amazon Business Reports
✅ Розраховує 7 власних KPI метрик для e-commerce
✅ Будує моделі поліноміальної регресії (3-го порядку)
✅ Тестує 7 різних методів оптимізації (A-G)
✅ Рекомендує оптимальну знижку для кожного продукту
✅ Валідує результати через метрики MAPE, RMSE, R²

---

## 📈 Результати

### Бізнес-вплив (Реальні дані)

| Метрика | Значення |
|---------|----------|
| 💰 **Збільшення чистого прибутку** | **+24.85%** |
| 💵 **Додатковий місячний прибуток** | **$25,000 - $30,000** |
| 📦 **Оптимізовано продуктів** | **20+ SKU** |
| 🎯 **Середня точність моделі (MAPE)** | **<15%** |

### Приклад: D-Mannose Capsules

- **Історична знижка:** 12%
- **Рекомендована знижка:** 16.5% (Method B - Min MAPE)
- **Збільшення прибутку:** +28% відносно поточного рівня

---

## 🔬 Методологія

### Data Pipeline

```
┌─────────────────┐
│  Amazon Reports │  Sessions, Orders, Sales (CSV)
│   (6 місяців)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Агрегація    │  Об'єднання Total + B2B метрик
│                 │  Розрахунок витрат, прибутку, цін
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Розрахунок KPI  │  7 власних метрик (DP_DR, DP_CR тощо)
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ML Моделювання │  Поліноміальна регресія (3-й порядок)
│   (7 методів)   │  scipy.optimize.minimize_scalar
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Бізнес-звіт     │  5 Excel листів з рекомендаціями
│                 │
└─────────────────┘
```

---

### Підхід машинного навчання

#### 1. Поліноміальна регресія (3-го порядку)

Моделює залежності між рівнем знижки та KPI:

```python
y = a₀ + a₁·x + a₂·x² + a₃·x³
```

де:
- `x = DP_DR` (рівень знижки)
- `y = KPI` (конверсія, прибуток, трафік тощо)

#### 2. Сім методів оптимізації

Кожен метод будує різну функцію прибутку:

| Метод | Ціль оптимізації | Формула |
|-------|-----------------|---------|
| **A** | Коефіцієнт конверсії | `Net_Profit = DP_CR(DR) × Sessions × Margin` |
| **B** | Залучення трафіку | `Net_Profit = DP_TAR(DR) × Sessions_SP × DP_CR × Margin` |
| **C** | Крос-продаж | `Net_Profit = DP_CSC(DR) × Sessions_SP × Margin` |
| **D** | Частка чистого прибутку | `Net_Profit = DP_NPS(DR) × Total_Profit_Avg` |
| **E** | Прибуток на сесію DP | `Net_Profit = DP_NPPS(DR) × Sessions_DP_Avg` |
| **F** | Прибуток крос-продажу | `Net_Profit = DP_CSPPS(DR) × Sessions_SP_Avg` |
| **G** | Пряма регресія | `Net_Profit = poly_profit(DR)` |

#### 3. Алгоритм оптимізації

Використовується `scipy.optimize.minimize_scalar` з обмеженим пошуком:

```python
optimal_discount = minimize_scalar(
    lambda x: -net_profit_function(x),
    bounds=[lower_bound, upper_bound],
    method='bounded'
)
```

#### 4. Валідація моделі

- **MAPE** (Mean Absolute Percentage Error) — точність прогнозу
- **RMSE** (Root Mean Square Error) — похибка передбачення
- **R²** (Coefficient of Determination) — якість моделі

---

### Ключові метрики (7 KPI)

| Метрика | Опис | Тип |
|---------|------|-----|
| **DP_DR** | Рівень знижки Double Pack | Маркетинг |
| **DP_CR** | Коефіцієнт конверсії | Маркетинг |
| **DP_TAR** | Коефіцієнт залучення трафіку | Маркетинг |
| **DP_CSC** | Крос-конверсія з Single Pack | Маркетинг |
| **DP_NPS** | Частка чистого прибутку | Фінанси |
| **DP_NPPS** | Чистий прибуток на сесію DP | Фінанси |
| **DP_CSPPS** | Прибуток крос-продажу на сесію | Фінанси |

---

## 🛠 Технологічний стек

### Основні технології

- **Python 3.11+** — мова програмування
- **pandas** — обробка даних, агрегація, pivot таблиці
- **numpy** — математичні операції, polynomial fitting
- **scipy** — алгоритми оптимізації (`minimize_scalar`)
- **statsmodels** — статистичний аналіз

### Дані та звітність

- **openpyxl** — Excel файли з форматуванням
- **matplotlib** — візуалізація даних
- **seaborn** — статистичні графіки
- **jupyter** — інтерактивні notebooks

---

## 📁 Структура проекту

```
amazon_discount_research/
│
├── business_reports/              # Фінальні бізнес-звіти та рекомендації
│   ├── documents/
│   │   ├── All_Products_Discount_Recommendations.xlsx
│   │   ├── All_Products_KPI.xlsx
│   │   └── research_report_*.html
│   └── figures/                   # Графіки та візуалізації
│
├── data/
│   ├── raw/                       # Amazon Business Reports (CSV)
│   │   └── D-Mannose Capsules (example product)/
│   │       ├── D-Mannose 120 Capsules (Single Pack)/
│   │       └── D-Mannose 240 Capsules (Double Pack)/
│   └── processed/                 # Оброблені дані з розрахованими KPI
│
├── docs/                          # Технічна документація
│
├── notebooks/
│   └── exploratory/               # Jupyter notebooks з дослідженнями
│       ├── 01_01_primary_research_by_b_complex.ipynb
│       ├── 01_02_statistical_analysis_by_mannose.ipynb
│       ├── 02_01_product_conversion_benchmarking.ipynb
│       └── 02_02_production_model.ipynb
│
├── src/
│   ├── data_scripts/
│   │   ├── mass_product_aggregation.py    # Агрегація даних SP vs DP
│   │   └── mass_product_kpi.py            # Розрахунок 7 KPI метрик
│   │
│   └── models_training/
│       └── amazon_dp_dr_model_production.py   # ML модель оптимізації (7 методів)
│
├── CLAUDE.md                      # Інструкції для Claude Code
├── CONTEXT.md                     # Повний контекст проекту
├── README.md                      # Цей файл
├── LICENSE.txt                    # Proprietary ліцензія
├── requirements.txt               # Python залежності
├── environment.yml                # Conda environment
└── references.txt                 # Посилання на методологію
```

---

## 🚀 Швидкий старт

### Передумови

- Python 3.11 або вище
- pip або conda менеджер пакетів

### Встановлення

#### Варіант 1: pip

```bash
# Клонувати репозиторій
git clone https://github.com/radyslav-datascience/amazon_discount_research.git
cd amazon_discount_research

# Встановити залежності
pip install -r requirements.txt
```

#### Варіант 2: conda

```bash
# Клонувати репозиторій
git clone https://github.com/radyslav-datascience/amazon_discount_research.git
cd amazon_discount_research

# Створити conda environment
conda env create -f environment.yml
conda activate research
```

### Використання

#### 1. Агрегувати дані

```bash
python src/data_scripts/mass_product_aggregation.py
```

Виводить: `All_Products_Aggregation.xlsx`

#### 2. Розрахувати KPI

```bash
python src/data_scripts/mass_product_kpi.py
```

Виводить: `All_Products_KPI.xlsx`

#### 3. Запустити модель оптимізації

```bash
python src/models_training/amazon_dp_dr_model_production.py
```

Виводить: `optimization_results.xlsx` з 5 листами:
- **Full Results** — всі методи для всіх продуктів
- **Min Discount** — консервативна стратегія (найменша знижка)
- **Min MAPE** — найкраща точність прогнозу
- **Min RMSE** — найменша похибка передбачення
- **Average Metrics** — ансамблевий підхід (середнє по методах)

---

## 📊 Приклад виводу

Система генерує Excel звіти з:

### Таблиця рекомендацій щодо знижок

| Продукт | ASIN | Оптимальна знижка | Метод | Прогноз прибутку | MAPE | RMSE |
|---------|------|------------------|-------|-----------------|------|------|
| D-Mannose 120/240 | B08X1Y2Z3B | 16.5% | Method-B | $8,542 | 12.3% | $421 |
| B-Complex 60/120 | B07K9M3N4P | 14.2% | Method-A | $6,234 | 10.8% | $312 |
| ... | ... | ... | ... | ... | ... | ... |

### Прогнози KPI

Для кожного продукту та оптимальної знижки:
- Прогнозний коефіцієнт конверсії (DP_CR)
- Прогнозне залучення трафіку (DP_TAR)
- Прогнозний крос-продаж (DP_CSC)
- Прогнозний чистий прибуток (DP)

---

## 📚 Документація

- **[CONTEXT.md](CONTEXT.md)** — Повний контекст проекту (бізнес-проблема, дані, методологія)
- **[CLAUDE.md](CLAUDE.md)** — Інструкції для Claude Code
- **[Технічні специфікації](docs/)** — Детальна технічна документація
- **[Дослідницькі ноутбуки](notebooks/exploratory/)** — Jupyter notebooks з аналізом
- **[Методи Data Science (Notion)](https://tr.ee/radyslav-datascience-notion)** — Глибоке занурення в методологію

---

## 🎓 Продемонстровані навички

Цей проект демонструє:

- ✅ **Бізнес-аналітика** — переклад бізнес-проблем у data science рішення
- ✅ **Експертиза в e-commerce** — Amazon marketplace, unit economics, pricing
- ✅ **Data Engineering** — ETL pipeline, агрегація даних, очищення
- ✅ **Feature Engineering** — створення власних KPI метрик з сирих даних
- ✅ **Machine Learning** — поліноміальна регресія, алгоритми оптимізації
- ✅ **Статистична валідація** — аналіз MAPE, RMSE, R²
- ✅ **Python розробка** — pandas, numpy, scipy, openpyxl
- ✅ **Автоматизація** — масштабовані скрипти для 20+ продуктів
- ✅ **Бізнес-звітність** — Excel дашборди з практичними інсайтами

---

## 👤 Автор

**Радислав Ломанов**

Data Scientist | Business Analyst | E-commerce Analytics Specialist

### Контакти

- 📧 **Email:** [lomanov.mail@gmail.com](mailto:lomanov.mail@gmail.com)
- 📱 **Телефон:** +380950359405
- 💬 **Telegram:** [@radyslav_datascience](https://t.me/radyslav_datascience)

### Посилання

- 🔗 **Всі посилання:** [linktr.ee/radyslav.datascience](https://linktr.ee/radyslav.datascience)
- 💼 **Сайт портфоліо:** [tr.ee/radyslav-portfolio-en](https://tr.ee/radyslav-portfolio-en)
- 📚 **Методи Data Science:** [tr.ee/radyslav-datascience-notion](https://tr.ee/radyslav-datascience-notion)
- 💻 **GitHub:** [github.com/radyslav-datascience](https://github.com/radyslav-datascience)

---

## 📜 Ліцензія

Цей проект є власністю автора та конфіденційним. Всі права захищені.

**Copyright © 2025 Radyslav Lomanov**

Несанкціоноване відтворення, поширення або комерційне використання суворо заборонено без попереднього письмового дозволу автора.

Для питань співпраці або ліцензування зверніться:
- Email: lomanov.mail@gmail.com
- Telegram: https://t.me/radyslav_datascience

Дивіться [LICENSE.txt](LICENSE.txt) для повних умов.

---

## 🙏 Подяки

Цей проект було розроблено в рамках реального замовлення клієнта — продавця на маркетплейсі Amazon US. Всі конфіденційні дані клієнта анонімізовано. Представлені методології та результати є автентичними та відображають роботу продакшн-рівня.

---

**Останнє оновлення:** 2025-11-24
