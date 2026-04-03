import pandas as pd
import ast
import logging
from datetime import datetime
import numpy as np
# ==========================================
# 1. LOGGING CONFIGURATION
# ==========================================
from shared.logger import setup_logger
logger = setup_logger(__name__)
# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def safe_literal_eval(val):
    """
    Safely evaluates a string containing a Python literal (list/dict).
    """
    if val is None:
        return []
    if isinstance(val, float) and np.isnan(val):
        return []
    if isinstance(val, (list, dict)):
        return val
    if not val: # Handles empty string or other falsy non-structures
        return []
    try:
        return ast.literal_eval(str(val))
    except (ValueError, SyntaxError):
        return []
def extract_names(row, col_name='name'):
    """
    Extract Ar/En names safely from 'names' dict or fallback columns.
    Returns tuple: (name_ar, name_en)
    """
    val = row.get('names')
    # Default fallbacks to the main name column
    name_ar = row.get(col_name) if pd.notna(row.get(col_name)) else ''
    name_en = row.get('names.en') if 'names.en' in row and pd.notna(row.get('names.en')) else name_ar
    # Try parsing the dictionary format if exists in 'names' column
    if isinstance(val, str):
        try:
            names_dict = ast.literal_eval(val)
            if isinstance(names_dict, dict):
                name_ar = names_dict.get('ar', name_ar)
                name_en = names_dict.get('en', name_en)
        except:
            pass
  
    return str(name_ar), str(name_en)
def get_best_image(row, col_full='image_full_size', col_small='image'):
    """
    Selects the best available image URL.
    """
    if pd.notna(row.get(col_full)) and row.get(col_full) != '':
        return row.get(col_full)
    return row.get(col_small)
def handle_id_column(df, col):
    """
    Handles ID columns: If purely numeric, convert to Int64; else keep as object/str.
    """
    if col not in df.columns:
        return
    # Check if all non-null values are numeric strings
    sample = df[col].dropna().head(100) # Sample for efficiency
    if sample.apply(lambda x: str(x).isdigit() if pd.notnull(x) else True).all():
        # Pure numeric: Convert to Int64
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    else:
        # Alphanumeric or mixed: Keep as str, strip whitespace
        df[col] = df[col].astype('object').fillna('').apply(lambda x: str(x).strip())
# ==========================================
# 3. CATEGORIES TRANSFORMATION LOGIC
# ==========================================
def transform_categories_split(raw_df):
    logger.info("Processing Categories (Splitting into Main & Subs)...")
   
    if raw_df is None or raw_df.empty:
        logger.warning("No data for Categories.")
        return None, None
    df = pd.json_normalize(raw_df.to_dict(orient='records')) if (raw_df.dtypes == 'object').any() else raw_df
   
    main_categories_list = []
    sub_categories_list = []
   
    for _, row in df.iterrows():
        # --- 1. Process Sub Categories (Children) ---
        raw_subs = row.get('sub_categories')
        subs_list_parsed = safe_literal_eval(raw_subs)
       
        for sub in subs_list_parsed:
            # Extract names for sub-category
            s_name_ar = sub.get('name', '')
            s_name_en = sub.get('name', '')
           
            if 'names' in sub and isinstance(sub['names'], dict):
                s_name_ar = sub['names'].get('ar', s_name_ar)
                s_name_en = sub['names'].get('en', s_name_en)
            child_row = {
                'sub_category_id': sub.get('id'),
                'uuid': sub.get('uuid'),
                'category_id': row.get('id'),
                'parent_category_name': extract_names(row)[0],
                'name_ar': s_name_ar,
                'name_en': s_name_en,
                'products_count': 0, # Initialized to 0, will be updated in transform_data
                'is_published': sub.get('is_published', True)
            }
            sub_categories_list.append(child_row)
        # --- 2. Process Main Category (Parent) ---
        name_ar, name_en = extract_names(row)
           
        parent_row = {
            'category_id': row.get('id'),
            'uuid': row.get('uuid'),
            'name_ar': name_ar,
            'name_en': name_en,
            'products_count': 0, # Initialized to 0, will be updated in transform_data
            'is_published': row.get('is_published'),
            'url': row.get('url'),
            'seo_title': row.get('SEO_category_title'),
            'seo_description': row.get('SEO_category_description'),
            'description': row.get('description')
        }
        main_categories_list.append(parent_row)
       
    # --- Prepare Main Categories DataFrame ---
    df_main = None
    if main_categories_list:
        df_main = pd.DataFrame(main_categories_list)
       
        handle_id_column(df_main, 'category_id')
        df_main['products_count'] = pd.to_numeric(df_main['products_count'], errors='coerce').fillna(0).astype('Int64')
        df_main = df_main.replace({np.nan: None})
       
        null_pk = df_main[(df_main['category_id'].isnull()) | (df_main['category_id'] == '')]
        if not null_pk.empty:
            logger.warning(f"Main Categories with null/empty PK: {len(null_pk)} rows - These may fail on load.")
        logger.info(f"zid_dim_categories_main: {len(df_main)} rows")
   
    # --- Prepare Sub Categories DataFrame ---
    df_subs = None
    if sub_categories_list:
        df_subs = pd.DataFrame(sub_categories_list)
       
        handle_id_column(df_subs, 'sub_category_id')
        handle_id_column(df_subs, 'category_id')
       
        df_subs['products_count'] = pd.to_numeric(df_subs['products_count'], errors='coerce').fillna(0).astype('Int64')
        df_subs = df_subs.replace({np.nan: None})
       
        null_pk = df_subs[(df_subs['sub_category_id'].isnull()) | (df_subs['sub_category_id'] == '')]
        if not null_pk.empty:
            logger.warning(f"Sub Categories with null/empty PK: {len(null_pk)} rows - These may fail on load.")
        logger.info(f"zid_dim_categories_subs: {len(df_subs)} rows")
    return df_main, df_subs
# ==========================================
# 4. PRODUCT TRANSFORMATION LOGIC
# ==========================================
def transform_products(raw_df):
    logger.info("Processing Products (Splitting & Cleaning)...")
   
    if raw_df is None or raw_df.empty:
        logger.warning("No data for Products.")
        return None, None, None
    df = pd.json_normalize(raw_df.to_dict(orient='records')) if (raw_df.dtypes == 'object').any() else raw_df
   
    # Lists for new tables
    products_list = []
    product_categories_bridge = [] # Bridge Table
    product_stocks_fact = [] # Stock per location
   
    # Columns to Drop
    cols_to_drop = [
        'product_class', 'parent_id', 'formatted_sale_price',
        'metafields', 'meta', 'related_products_settings', 'related_products_title',
        'badge', 'group_products', 'videos', 'attributes',
        'rating.average', 'rating.total_count',
        'slug', 'images'
    ]
   
    # Dynamically drop extra rating/restriction columns
    cols_to_drop += [c for c in df.columns if 'rating.' in c or 'purchase_restrictions' in c]
    for _, row in df.iterrows():
        # --- 1. Prepare Main Product Row ---
        prod_row = row.drop(labels=[c for c in cols_to_drop if c in row.index]).to_dict()
       
        # Handle Keywords
        keywords_raw = safe_literal_eval(row.get('keywords'))
        prod_row['keywords'] = ", ".join(keywords_raw) if isinstance(keywords_raw, list) else ""
        # --- 2. Handle Categories (Smart Bridge Table with Sub-Categories) ---
        cats_list = safe_literal_eval(row.get('categories'))
        cat_names_accum = []
       
        # Temporary map: Main_ID -> Sub_ID (or None)
        product_cats_map = {}
        for cat in cats_list:
            cat_id = cat.get('id')
            cat_name = cat.get('name')
            cat_names_accum.append(cat_name)
            if pd.notna(cat_id):
                meta = cat.get('meta', {})
                parents = meta.get('parents', [])
               
                if parents:
                    # It's a Sub-Category
                    main_id = parents[0]
                    sub_id = cat_id
                else:
                    # It's a Main Category
                    main_id = cat_id
                    sub_id = None
                # Prioritize specific sub-category connection over generic main connection
                if main_id not in product_cats_map:
                    product_cats_map[main_id] = sub_id
                elif product_cats_map[main_id] is None and sub_id is not None:
                    product_cats_map[main_id] = sub_id
        # Add to bridge list
        for main_id, sub_id in product_cats_map.items():
            product_categories_bridge.append({
                'product_id': row.get('id'),
                'category_id': main_id,
                'sub_category_id': sub_id
            })
        prod_row['category_names_flat'] = ", ".join(cat_names_accum)
        if 'categories' in prod_row: del prod_row['categories']
        # --- 3. Handle Stocks (Fact Table) ---
        stocks_list = safe_literal_eval(row.get('stocks'))
        for stock in stocks_list:
            loc = stock.get('location', {})
            loc_id = loc.get('id')
            if pd.notna(loc_id):
                product_stocks_fact.append({
                    'product_id': row.get('id'),
                    'stock_id': stock.get('id'),
                    'location_id': loc_id,
                    'quantity': stock.get('available_quantity', 0)
                })
       
        if 'stocks' in prod_row: del prod_row['stocks']
        # Clean SEO
        if 'seo.title' in prod_row: prod_row['seo_title'] = prod_row.pop('seo.title')
        if 'seo.description' in prod_row: prod_row['seo_description'] = prod_row.pop('seo.description')
        # Ensure Numerics
        if 'sold_products_count' in prod_row:
             prod_row['sold_products_count'] = pd.to_numeric(prod_row['sold_products_count'], errors='coerce') or 0
       
        # Ensure Money Columns
        if 'price' in prod_row:
             prod_row['price'] = pd.to_numeric(prod_row['price'], errors='coerce') or 0.0
       
        if 'sale_price' in prod_row:
             prod_row['sale_price'] = pd.to_numeric(prod_row['sale_price'], errors='coerce') or 0.0
        products_list.append(prod_row)
    # --- Prepare DataFrames ---
   
    # 1. Dim_Products
    df_products = None
    if products_list:
        df_products = pd.DataFrame(products_list)
       
        # Dates
        date_cols = ['created_at', 'updated_at']
        for col in date_cols:
            if col in df_products.columns:
                df_products[col] = pd.to_datetime(df_products[col], errors='coerce', utc=True).dt.tz_localize(None)
       
        # PK & Types
        df_products = df_products.rename(columns={'id': 'product_id'})
        handle_id_column(df_products, 'product_id')
        handle_id_column(df_products, 'store_id')
       
        if 'quantity' in df_products.columns:
            df_products['quantity'] = pd.to_numeric(df_products['quantity'], errors='coerce').fillna(0).astype('Int64')
        if 'sold_products_count' in df_products.columns:
            df_products['sold_products_count'] = pd.to_numeric(df_products['sold_products_count'], errors='coerce').fillna(0).astype('Int64')
        df_products = df_products.dropna(subset=['product_id'])
        df_products = df_products.replace({np.nan: None, pd.NaT: None})
        # Reorder Columns
        priority_cols = [
            'product_id', 'sku', 'name', 'keywords',
            'price', 'sale_price', 'currency', 'formatted_price',
            'quantity', 'sold_products_count', 'weight', 'weight.unit', 'weight.value',
            'is_taxable', 'requires_shipping', 'is_draft', 'is_infinite',
            'store_id', 'created_at', 'updated_at'
        ]
        existing_cols = [c for c in priority_cols if c in df_products.columns]
        remaining_cols = [c for c in df_products.columns if c not in priority_cols]
        df_products = df_products[existing_cols + remaining_cols]
        logger.info(f"zid_dim_products: {len(df_products)} rows")
    # 2. Bridge_Product_Categories
    df_bridge = None
    if product_categories_bridge:
        df_bridge = pd.DataFrame(product_categories_bridge)
        handle_id_column(df_bridge, 'product_id')
        handle_id_column(df_bridge, 'category_id')
        handle_id_column(df_bridge, 'sub_category_id')
       
        df_bridge = df_bridge.replace({np.nan: None})
        df_bridge = df_bridge.dropna(subset=['product_id', 'category_id'])
       
        # --- FIX: Safe FillNA to avoid Future Warning & PK Errors ---
        if 'sub_category_id' in df_bridge.columns:
             # 1. Fill NaNs with 0 (Required for Primary Key)
             df_bridge['sub_category_id'] = df_bridge['sub_category_id'].fillna(0)
             # 2. Convert to Integer type explicitly
             df_bridge['sub_category_id'] = df_bridge['sub_category_id'].astype('int64')
        else:
             df_bridge['sub_category_id'] = 0
        logger.info(f"zid_bridge_product_categories: {len(df_bridge)} rows")
   
    # 3. Fact_Product_Stocks
    df_stocks = None
    if product_stocks_fact:
        df_stocks = pd.DataFrame(product_stocks_fact)
        handle_id_column(df_stocks, 'product_id')
        handle_id_column(df_stocks, 'stock_id')
       
        df_stocks['quantity'] = pd.to_numeric(df_stocks['quantity'], errors='coerce').fillna(0).astype('Int64')
        df_stocks = df_stocks.replace({np.nan: None})
        df_stocks = df_stocks.dropna(subset=['product_id'])
        logger.info(f"zid_fact_product_stocks: {len(df_stocks)} rows")
    return df_products, df_bridge, df_stocks
# ==========================================
# 5. CUSTOMER TRANSFORMATION LOGIC
# ==========================================
def transform_customers(raw_df):
    logger.info("Processing Customers...")
  
    if raw_df is None or raw_df.empty:
        logger.warning("No data for Customers.")
        return None
    df = pd.json_normalize(raw_df.to_dict(orient='records')) if (raw_df.dtypes == 'object').any() else raw_df
  
    # 1. Drop Useless/Redundant Columns
    cols_to_drop = ['source', 'city', 'pivotEmail', 'pivotMobile', 'nickname']
    df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)
  
    # 2. Rename Nested Location Columns (Clean dots)
    rename_map = {
        'id': 'customer_id',
        'city.id': 'city_id',
        'city.name': 'city_name',
        'city.ar_name': 'city_name_ar',
        'city.en_name': 'city_name_en',
        'city.country_id': 'country_id',
        'city.country_name': 'country_name',
        'city.country_code': 'country_code',
        'city.national_id': 'city_national_id',
        'city.priority': 'city_priority',
        'order_total_payments': 'total_spent'
    }
    df.rename(columns=rename_map, inplace=True)
  
    # 3. Handle Dates
    date_cols = ['created_at', 'updated_at', 'last_order_date', 'birth_date']
    for col in date_cols:
        if col in df.columns:
            # Convert to datetime, coerce errors, strip timezone
            df[col] = pd.to_datetime(df[col], errors='coerce', utc=True).dt.tz_localize(None)
    # 4. Format Mobile Numbers (Ensure they are strings, not scientific notation)
    if 'mobile' in df.columns:
        df['mobile'] = df['mobile'].apply(
            lambda x: str(int(x)) if pd.notnull(x) and str(x).replace('.','').isdigit() else x
        )
    # 5. Ensure Numeric Columns for Analysis
    numeric_cols = ['order_counts', 'points']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    if 'total_spent' in df.columns:
        df['total_spent'] = pd.to_numeric(df['total_spent'], errors='coerce').fillna(0.0)
    # Handle IDs conditionally
    id_cols = ['customer_id', 'city_id', 'country_id', 'city_national_id', 'city_priority']
    for col in id_cols:
        handle_id_column(df, col)
    # Replace NaN with None
    df = df.replace({np.nan: None, pd.NaT: None})
    # Log truly null/empty PK
    null_pk = df[(df['customer_id'].isnull()) | (df['customer_id'] == '')]
    if not null_pk.empty:
        logger.warning(f"Customers with null/empty PK: {len(null_pk)} rows - These may fail on load.")
    logger.info(f"zid_dim_customers: {len(df)} rows")
    return df
# ==========================================
# 6. ORDERS TRANSFORMATION LOGIC
# ==========================================
def parse_date(date_str):
    """
    Parses date strings with potential custom formats like '22-12-2025 | 09:00 PM'.
    """
    if pd.isna(date_str):
        return None
    try:
        clean_date_part = str(date_str).split('|')[0].strip()
        return pd.to_datetime(clean_date_part, dayfirst=True, utc=True).tz_localize(None)
    except:
        return None
def transform_orders(raw_df):
    logger.info("Processing Orders (Splitting Orders, Items & Shipping)...")
   
    if raw_df is None or raw_df.empty:
        logger.warning("No data for Orders.")
        return None, None, None
    df = pd.json_normalize(raw_df.to_dict(orient='records')) if (raw_df.dtypes == 'object').any() else raw_df
   
    orders_list = []
    order_items_list = []
    shipping_list = []
   
    # Pre-calculate common transformations
    for _, row in df.iterrows():
        # --- 1. Data Parsing & Cleaning ---
       
        # Date Parsing
        issue_date_clean = parse_date(row.get('issue_date'))
        created_at = pd.to_datetime(row.get('created_at'), errors='coerce', utc=True).tz_localize(None) if pd.notna(row.get('created_at')) else None
        updated_at = pd.to_datetime(row.get('updated_at'), errors='coerce', utc=True).tz_localize(None) if pd.notna(row.get('updated_at')) else None
        delivered_at = pd.to_datetime(row.get('delivered_at'), errors='coerce', utc=True).tz_localize(None) if pd.notna(row.get('delivered_at')) else None
       
        # Calculate Delivery Duration
        delivery_days = (delivered_at - created_at).days if (created_at and delivered_at) else None
        # Flatten Tags
        tags_raw = safe_literal_eval(row.get('tags'))
        tags_str = ", ".join([t.get('name', '') for t in tags_raw if isinstance(t, dict)])
        # Financials
        invoice_data = safe_literal_eval(row.get('payment.invoice'))
        shipping_cost = 0.0
        tax_total = 0.0
        subtotal = 0.0
        discount_amount = 0.0
       
        for item in invoice_data:
            code = item.get('code')
            val = float(item.get('value', 0))
            if code == 'shipping': shipping_cost = val
            elif code in ['vat', 'tax']: tax_total = val
            elif code in ['sub_totals_after_vat', 'sub_totals']: subtotal = val
            elif code == 'coupon' or 'discount' in str(code).lower(): discount_amount = abs(val)
        referer = row.get('referer') if 'referer' in row else row.get('referer_code')
        # --- A. FACT ORDERS ---
        order_row = {
            # 1. IDs & Keys
            'order_id': row.get('id'),
            'invoice_number': row.get('invoice_number'),
            'store_id': row.get('store_id'),
            'customer_id': row.get('customer.id'),
            'coupon_id': row.get('coupon.id'),
            'transaction_reference': row.get('transaction_reference'),
           
            # 2. Dates
            'created_at': created_at,
            'updated_at': updated_at,
            'issue_date': issue_date_clean,
            'delivered_at': delivered_at,
            'delivery_days': delivery_days,
            # 3. Status & Flags
            'status': row.get('order_status.name'),
            'status_code': row.get('order_status.code'),
            'payment_status': row.get('payment_status'),
            'source': row.get('source'),
            'is_gift_order': row.get('is_gift_order'),
            'is_guest': row.get('is_guest_customer'),
            'is_cod': row.get('is_cod_enabled'),
            'cod_confirmed': row.get('cod_confirmed'),
            'requires_shipping': row.get('requires_shipping'),
            'has_different_consignee': row.get('has_different_consignee'),
            'is_reseller_transaction': row.get('is_reseller_transaction'),
            # 4. Financials
            'currency': row.get('currency_code'),
            'order_total': float(row.get('order_total', 0)),
            'subtotal': subtotal,
            'tax_total': tax_total,
            'shipping_cost': shipping_cost,
            'discount_amount': discount_amount,
            'coupon_discount': row.get('coupon.discount'),
            'payment_method': row.get('payment.method.name'),
            'payment_network': row.get('payment_network'),
           
            # 5. Metrics & Counts
            'products_count': row.get('products_count'),
            'packages_count': row.get('packages_count'),
            'edits_count': row.get('edits_count', 0),
            # 6. Metadata / Other
            'referer': referer,
            'tags': tags_str,
            'customer_note': row.get('customer_note'),
            'order_url': row.get('order_url'),
            'reseller_meta': str(row.get('reseller_meta')) if pd.notna(row.get('reseller_meta')) else None,
            'store_exchange_rate': float(row.get('currency.order_store_currency.exchange_rate') or 1.0),
            'order_exchange_rate': float(row.get('currency.order_currency.exchange_rate') or 1.0),
        }
        orders_list.append(order_row)
        # --- B. FACT ORDER SHIPPING ---
        lat = row.get('shipping.address.lat')
        lng = row.get('shipping.address.lng')
        gmaps_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}" if pd.notna(lat) and pd.notna(lng) and lat != 0 else ""
        ship_row = {
            # 1. IDs
            'order_id': row.get('id'),
           
            # 2. Method Details
            'method_name': row.get('shipping.method.name'),
            'method_code': row.get('shipping.method.code'),
            'courier_name': row.get('shipping.method.courier.name.ar') or row.get('shipping.method.courier.name.en'),
            'delivery_estimate': row.get('shipping.method.estimated_delivery_time'),
           
            # 3. Address
            'country': row.get('shipping.address.country.name'),
            'city': row.get('shipping.address.city.name'),
            'district': row.get('shipping.address.district'),
            'street': row.get('shipping.address.street'),
            'short_address': row.get('shipping.address.short_address'),
            'formatted_address': row.get('shipping.address.formatted_address'),
           
            # 4. Receiver Info
            'consignee_name': row.get('consignee.name'),
            'consignee_mobile': row.get('consignee.mobile'),
           
            # 5. Geo / Metrics
            'lat': lat,
            'lng': lng,
            'total_weight': row.get('weight'),
            'google_maps_link': gmaps_link
        }
        shipping_list.append(ship_row)
        # --- C. FACT ORDER ITEMS ---
        products_raw = row.get('products')
        products_list_item = safe_literal_eval(products_raw)
       
        for item in products_list_item:
            product_id = item.get('id')
            if pd.notna(product_id):
                item_row = {
                    # 1. IDs
                    'order_id': row.get('id'),
                    'product_id': product_id,
                   
                    # 2. Details
                    'name': item.get('name'),
                    # Removed 'sku' as requested
                   
                    # 3. Metrics (Quantity & Weight)
                    'quantity': item.get('quantity', 0),
                    'weight': item.get('weight', {}).get('value') if isinstance(item.get('weight'), dict) else 0,
                    # 4. Financials
                    'price': float(item.get('price', 0)), # Unit Price
                    'net_price': float(item.get('net_price', 0)), # Before Tax
                    'tax_amount': float(item.get('tax_amount', 0)),
                    'total': float(item.get('total', 0)), # Line Total
                }
                order_items_list.append(item_row)
    # --- Prepare DataFrames ---
   
    # 1. Fact Orders
    df_orders = None
    if orders_list:
        df_orders = pd.DataFrame(orders_list)
        # Type Enforcement
        for col in ['created_at', 'updated_at', 'issue_date', 'delivered_at']:
            if col in df_orders.columns:
                df_orders[col] = pd.to_datetime(df_orders[col], errors='coerce', utc=True).dt.tz_localize(None)
       
        id_cols = ['order_id', 'store_id', 'customer_id', 'coupon_id']
        for col in id_cols:
            handle_id_column(df_orders, col)
           
        int_cols = ['edits_count', 'packages_count', 'products_count', 'delivery_days']
        for col in int_cols:
            if col in df_orders.columns:
                df_orders[col] = pd.to_numeric(df_orders[col], errors='coerce').astype('Int64')
        # Handle Booleans -> 0/1 for SQL consistency
        bool_cols = ['has_different_consignee', 'is_gift_order', 'requires_shipping', 'cod_confirmed', 'is_reseller_transaction', 'is_guest', 'is_cod']
        for col in bool_cols:
             if col in df_orders.columns:
                df_orders[col] = pd.to_numeric(df_orders[col], errors='coerce').fillna(0).astype(int)
        df_orders = df_orders.replace({np.nan: None, pd.NaT: None})
        df_orders = df_orders.dropna(subset=['order_id'])
        logger.info(f"zid_fact_orders: {len(df_orders)} rows")
    # 2. Fact Shipping
    df_shipping = None
    if shipping_list:
        df_shipping = pd.DataFrame(shipping_list)
        handle_id_column(df_shipping, 'order_id')
        df_shipping = df_shipping.replace({np.nan: None})
        df_shipping = df_shipping.dropna(subset=['order_id'])
        logger.info(f"zid_fact_order_shipping: {len(df_shipping)} rows")
   
    # 3. Fact Order Items
    df_items = None
    if order_items_list:
        df_items = pd.DataFrame(order_items_list)
       
        # Aggregation to remove duplicates (if any products appear twice in same order)
        # Removed 'sku' from aggregation dict
        df_items = df_items.groupby(['order_id', 'product_id']).agg({
            'name': 'first',
            'quantity': 'sum',
            'weight': 'sum', # Weight should sum up
            'price': 'first', # Unit price shouldn't change
            'net_price': 'first',
            'tax_amount': 'sum', # Tax sums up
            'total': 'sum' # Total sums up
        }).reset_index()
       
        handle_id_column(df_items, 'order_id')
        handle_id_column(df_items, 'product_id')
       
        df_items['quantity'] = pd.to_numeric(df_items['quantity'], errors='coerce').astype('Int64')
        df_items = df_items.replace({np.nan: None})
        df_items = df_items.dropna(subset=['order_id', 'product_id'])
       
        # Organize Column Order
        cols_order = ['order_id', 'product_id', 'name', 'quantity', 'weight', 'price', 'net_price', 'tax_amount', 'total']
        df_items = df_items[cols_order]
        logger.info(f"zid_fact_order_items: {len(df_items)} rows")
    return df_orders, df_shipping, df_items
# ==========================================
# 7. LOCATIONS TRANSFORMATION LOGIC
# ==========================================
def transform_locations(raw_df):
    logger.info("Processing Locations (Splitting & Cleaning)...")
  
    if raw_df is None or raw_df.empty:
        logger.warning("No data for Locations.")
        return None
    df = pd.json_normalize(raw_df.to_dict(orient='records')) if (raw_df.dtypes == 'object').any() else raw_df
  
    # 1. Clean Channels (List to String)
    if 'channels' in df.columns:
        df['channels'] = df['channels'].apply(
            lambda x: ", ".join(safe_literal_eval(x)) if isinstance(x, str) else x
        )
    # 2. Create Google Maps Link (Enrichment)
    # Useful for visualizing warehouse locations on a map in the dashboard
    if 'coordinates.latitude' in df.columns and 'coordinates.longitude' in df.columns:
        df['google_maps_link'] = df.apply(
            lambda row: f"http://maps.google.com/?q={row['coordinates.latitude']},{row['coordinates.longitude']}",
            axis=1
        )
    # 3. Rename Columns (Mapping to Standard Schema)
    # Renaming nested JSON keys to flat column names for better BI compatibility
    rename_map = {
        'id': 'location_id',
        'name': 'location_name',
        'city.id': 'city_id',
        'city.name': 'city_en',
        'city.ar_name': 'city_ar',
        'city.country.id': 'country_id',
        'city.country.name': 'country_en',
        'city.country.ar_name': 'country_ar',
        'city.country_code': 'country_code',
        'coordinates.latitude': 'latitude',
        'coordinates.longitude': 'longitude'
    }
    df.rename(columns=rename_map, inplace=True)
    # 4. Drop Useless Columns
    # Only dropping columns that are completely empty or technical lists with no analytical value
    cols_to_drop = [
        'fulfillment_priority',
        'linked_users',
        'city.country.iso_code_2',
        'city.country.iso_code_3',
        'city.country.code'
    ]
    df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)
    # Handle IDs conditionally
    id_cols = ['location_id', 'city_id', 'country_id']
    for col in id_cols:
        handle_id_column(df, col)
    # Replace NaN with None
    df = df.replace({np.nan: None})
    # Log truly null/empty PK
    null_pk = df[(df['location_id'].isnull()) | (df['location_id'] == '')]
    if not null_pk.empty:
        logger.warning(f"Locations with null/empty PK: {len(null_pk)} rows - These may fail on load.")
    logger.info(f"zid_dim_locations: {len(df)} rows")
    return df
# ==========================================
# 8. SHIPPING METHODS TRANSFORMATION LOGIC
# ==========================================
def transform_shipping_methods(raw_df):
    logger.info("Processing Shipping Methods...")
  
    if raw_df is None or raw_df.empty:
        logger.warning("No data for Shipping_Methods.")
        return None, None
    df = pd.json_normalize(raw_df.to_dict(orient='records')) if (raw_df.dtypes == 'object').any() else raw_df
  
    shipping_methods_list = []
    shipping_cities_bridge = []
  
    for _, row in df.iterrows():
        # --- 1. Main Shipping Method Dimension ---
        method_row = {
            'shipping_method_id': row.get('id'),
            'name': row.get('name'),
            'code': row.get('system_option_code'),
            'status': row.get('shipping_method_status'),
            # Flag to identify if it targets specific cities
            'has_specific_cities': 1 if row.get('select_cities') and str(row.get('select_cities')) != '[]' else 0
        }
        shipping_methods_list.append(method_row)
      
        # --- 2. Shipping Cities Bridge (Explode Cities) ---
        cities_raw = row.get('select_cities')
        cities_list = safe_literal_eval(cities_raw)
      
        for city in cities_list:
            city_id = city.get('id')
            if pd.notna(city_id):
                bridge_row = {
                    'shipping_method_id': row.get('id'),
                    'city_id': city_id,
                    'city_name_ar': city.get('ar_name') or city.get('name'),
                    'city_name_en': city.get('en_name'),
                    'country_name': city.get('country_name'),
                    'country_code': city.get('country_code')
                }
                shipping_cities_bridge.append(bridge_row)
    # --- Prepare DataFrames ---
  
    # 1. Dim Shipping Methods
    df_methods = None
    if shipping_methods_list:
        df_methods = pd.DataFrame(shipping_methods_list)
        # Handle IDs conditionally
        handle_id_column(df_methods, 'shipping_method_id')
        df_methods['has_specific_cities'] = pd.to_numeric(df_methods['has_specific_cities'], errors='coerce').astype('Int64')
        df_methods = df_methods.replace({np.nan: None})
        null_pk = df_methods[(df_methods['shipping_method_id'].isnull()) | (df_methods['shipping_method_id'] == '')]
        if not null_pk.empty:
            logger.warning(f"Shipping Methods with null/empty PK: {len(null_pk)} rows - These may fail on load.")
        logger.info(f"zid_dim_shipping_methods: {len(df_methods)} rows")
  
    # 2. Bridge Shipping Cities
    df_bridge = None
    if shipping_cities_bridge:
        df_bridge = pd.DataFrame(shipping_cities_bridge)
        # Handle IDs conditionally
        handle_id_column(df_bridge, 'shipping_method_id')
        handle_id_column(df_bridge, 'city_id')
        df_bridge = df_bridge.replace({np.nan: None})
        null_pk = df_bridge[(df_bridge['shipping_method_id'].isnull()) | (df_bridge['shipping_method_id'] == '') |
                            (df_bridge['city_id'].isnull()) | (df_bridge['city_id'] == '')]
        if not null_pk.empty:
            logger.warning(f"Shipping Cities Bridge with null/empty keys: {len(null_pk)} rows - These may fail on load.")
        logger.info(f"zid_bridge_shipping_cities: {len(df_bridge)} rows")
    else:
        # Create empty dataframe with columns if no cities found to avoid errors later
        df_bridge = pd.DataFrame(columns=['shipping_method_id', 'city_id', 'city_name_ar', 'city_name_en', 'country_name', 'country_code'])
    return df_methods, df_bridge
# ==========================================
# 9. ABANDONED CARTS TRANSFORMATION LOGIC
# ==========================================
def transform_abandoned_carts(raw_df):
    logger.info("Processing Abandoned Carts...")
   
    if raw_df is None or raw_df.empty:
        logger.warning("No data for Abandoned_Carts.")
        return None
    df = pd.json_normalize(raw_df.to_dict(orient='records')) if (raw_df.dtypes == 'object').any() else raw_df
   
    # 1. Drop Useless/Requested Columns
    cols_to_drop = [
        'whatsapp_message',
        'cart_total_string',
        'session_id',
        'cart_id',
        'url',
        'customer_name',
        'customer_email',
        'customer_mobile',
        'city_id'
    ]
   
    df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)
   
    # 2. Handle Dates
    date_cols = ['created_at', 'updated_at']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', utc=True).dt.tz_localize(None)
    # 3. Ensure Numeric Metrics
    if 'cart_total' in df.columns:
        df['cart_total'] = pd.to_numeric(df['cart_total'], errors='coerce').fillna(0.0)
   
    if 'products_count' in df.columns:
        df['products_count'] = pd.to_numeric(df['products_count'], errors='coerce').fillna(0).astype('Int64')
    if 'reminders_count' in df.columns:
        df['reminders_count'] = pd.to_numeric(df['reminders_count'], errors='coerce').fillna(0).astype('Int64')
    # Handle IDs
    # Warning: Abandoned Cart ID in Zid is usually a UUID string, NOT numeric.
    # We strip whitespace but do NOT force numeric conversion to avoid data loss.
    if 'id' in df.columns:
        df['id'] = df['id'].astype(str).str.strip()
   
    if 'customer_id' in df.columns:
        handle_id_column(df, 'customer_id')
       
    if 'store_id' in df.columns:
        handle_id_column(df, 'store_id')
    # Replace NaN with None for SQL compatibility
    df = df.replace({np.nan: None, pd.NaT: None})
    # Log empty PKs
    null_pk = df[(df['id'].isnull()) | (df['id'] == '')]
    if not null_pk.empty:
        logger.warning(f"Abandoned Carts with null/empty PK: {len(null_pk)} rows - These may fail on load.")
   
    logger.info(f"zid_fact_abandoned_carts: {len(df)} rows")
   
    # 4. Rename PK
    df = df.rename(columns={'id': 'abandoned_carts_id'})
    # 5. Reorder Columns (Logical Order)
    # Define preferred order
    priority_cols = [
        'abandoned_carts_id', 'store_id', 'customer_id',
        'cart_total', 'currency_code',
        'products_count', 'reminders_count',
        'phase', 'source',
        'created_at', 'updated_at'
    ]
    # Get actual columns that exist
    existing_cols = [c for c in priority_cols if c in df.columns]
    # Apply order
    df = df[existing_cols]
   
    return df
# ==========================================
# 10. COUPONS TRANSFORMATION LOGIC
# ==========================================
def transform_coupons(raw_df):
    logger.info("Processing Coupons...")
   
    if raw_df is None or raw_df.empty:
        logger.warning("No data for Coupons.")
        return None
    df = pd.json_normalize(raw_df.to_dict(orient='records')) if (raw_df.dtypes == 'object').any() else raw_df
   
    # 1. Clean Dates
    date_cols = ['date_start', 'date_end', 'created_at']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', utc=True).dt.tz_localize(None)
    # 2. Rename & Select Columns
    df_clean = pd.DataFrame()
    df_clean['coupon_id'] = df.get('id')
    df_clean['code'] = df.get('code')
    df_clean['name'] = df.get('name')
    df_clean['status'] = df.get('status_code') # e.g. coupon_active
   
    # Metrics
    df_clean['discount_value'] = pd.to_numeric(df.get('discount'), errors='coerce').fillna(0)
    df_clean['discount_type'] = df.get('discount_type') # 'p' (percentage) or 'f' (fixed)
   
    # Usage Stats
    df_clean['usage_count'] = pd.to_numeric(df.get('total_usage'), errors='coerce').astype('Int64')
    # 'uses_total' and 'usage_limit' often refer to the same concept (max allowed uses)
    df_clean['uses_total'] = pd.to_numeric(df.get('uses_total'), errors='coerce').astype('Int64')
    df_clean['usage_limit'] = pd.to_numeric(df.get('uses_total'), errors='coerce').astype('Int64') # Kept as per request
    df_clean['customer_limit'] = pd.to_numeric(df.get('uses_customer'), errors='coerce').astype('Int64')
   
    # Rules & Settings
    df_clean['min_order_total'] = pd.to_numeric(df.get('total'), errors='coerce').fillna(0)
    df_clean['max_discount'] = pd.to_numeric(df.get('maximum_discount_value'), errors='coerce').fillna(0)
   
    # Requested Additions
    df_clean['applying_method'] = df.get('applying_method')
    df_clean['apply_to'] = df.get('apply_to')
   
    # Booleans (Convert to 0/1)
    df_clean['is_free_shipping'] = pd.to_numeric(df.get('free_shipping'), errors='coerce').fillna(0).astype(int)
    df_clean['is_active'] = pd.to_numeric(df.get('is_active'), errors='coerce').fillna(0).astype(int)
   
    # Dates
    df_clean['start_date'] = df.get('date_start')
    df_clean['end_date'] = df.get('date_end')
    df_clean['created_at'] = df.get('created_at')
    # Handle coupon_id conditionally
    handle_id_column(df_clean, 'coupon_id')
    # Replace NaN with None
    df_clean = df_clean.replace({np.nan: None, pd.NaT: None})
    # Log truly null/empty PK
    null_pk = df_clean[(df_clean['coupon_id'].isnull()) | (df_clean['coupon_id'] == '')]
    if not null_pk.empty:
        logger.warning(f"Coupons with null/empty PK: {len(null_pk)} rows - These may fail on load.")
    logger.info(f"zid_dim_coupons: {len(df_clean)} rows")
    return df_clean
# ==========================================
# 11. PRODUCT REVIEWS TRANSFORMATION LOGIC
# ==========================================
def transform_reviews(raw_df):
    logger.info("Processing Product Reviews...")
   
    if raw_df is None or raw_df.empty:
        logger.warning("No data for Product Reviews.")
        return None
    df = pd.json_normalize(raw_df.to_dict(orient='records')) if (raw_df.dtypes == 'object').any() else raw_df
   
    # 1. Drop Useless/Requested Columns
    cols_to_drop = [
        'original_snapshot',
        'images',
        'customer.name', # Removed for privacy/normalization (already in Dim_Customers)
        'product.image',
        'product.name', # Redundant, already in Dim_Products
        'reply' # Empty in your sample
    ]
    df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)
   
    # 2. Rename Columns
    rename_map = {
        'id': 'review_id',
        'status': 'review_status',
        'rating': 'rating_score',
        'comment': 'comment_text',
        'product.id': 'product_id',
        'customer.id': 'customer_id',
        'product.bought_this_item': 'is_verified_purchase' # Meaningful name
    }
    df.rename(columns=rename_map, inplace=True)
    # 3. Handle Dates
    date_cols = ['created_at', 'updated_at']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', utc=True).dt.tz_localize(None)
    # 4. Handle IDs & Numerics
    if 'customer_id' in df.columns:
        handle_id_column(df, 'customer_id')
   
    if 'product_id' in df.columns:
        # Product ID in reviews seems to be UUID string in your sample,
        # BUT in Dim_Products it is Numeric Int64.
        # We need to check if this UUID maps to 'product_uuid' or actual 'product_id'.
        # Based on sample: '90c4a5a7...' is a UUID.
        # So we should rename it to 'product_uuid' to avoid mismatch with 'product_id' (Int64).
        df.rename(columns={'product_id': 'product_uuid'}, inplace=True)
       
    # 5. Booleans & Integers
    if 'is_anonymous' in df.columns:
        df['is_anonymous'] = df['is_anonymous'].astype(int)
       
    if 'is_verified_purchase' in df.columns:
        df['is_verified_purchase'] = df['is_verified_purchase'].astype(int)
       
    if 'rating_score' in df.columns:
        df['rating_score'] = pd.to_numeric(df['rating_score'], errors='coerce').fillna(0).astype('Int64')
    # Replace NaN
    df = df.replace({np.nan: None, pd.NaT: None})
    # Log
    logger.info(f"zid_fact_product_reviews: {len(df)} rows")
   
    return df
# ==========================================
# 12. MAIN TRANSFORM FUNCTION
# ==========================================
def transform_data(raw_data_catalog):
    """
    Main entry point for transformation.
    """
    logger.info("=" * 50)
    logger.info(" DATA TRANSFORMATION ENGINE STARTED")
    logger.info("=" * 50)
   
    processed_data_catalog = {}
   
    # --- 1. Basic Transformations ---
   
    # A. Categories
    df_main, df_subs = transform_categories_split(raw_data_catalog.get('Categories'))
   
    # B. Products & Bridge
    df_products, df_bridge, df_stocks = transform_products(raw_data_catalog.get('Products'))
   
    # Recalculate Product Counts for Categories (Inventory Count)
    if df_bridge is not None and not df_bridge.empty:
        logger.info("Recalculating accurate product counts for categories...")
        sub_prod_counts = df_bridge.groupby('sub_category_id')['product_id'].nunique()
        main_prod_counts = df_bridge.groupby('category_id')['product_id'].nunique()
       
        if df_subs is not None and not df_subs.empty:
            df_subs['products_count'] = df_subs['sub_category_id'].map(sub_prod_counts).fillna(0).astype('Int64')
       
        if df_main is not None and not df_main.empty:
            df_main['products_count'] = df_main['category_id'].map(main_prod_counts).fillna(0).astype('Int64')
    # C. Customers
    df_customers = transform_customers(raw_data_catalog.get('Customers'))
   
    # D. Locations
    df_locations = transform_locations(raw_data_catalog.get('Locations'))
   
    # E. Shipping Methods
    df_methods, df_shipping_bridge = transform_shipping_methods(raw_data_catalog.get('Shipping_Methods'))
   
    # F. Abandoned Carts
    df_abandoned = None
    if 'Abandoned_Carts' in raw_data_catalog:
        df_abandoned = transform_abandoned_carts(raw_data_catalog.get('Abandoned_Carts'))
   
    # G. Coupons
    df_coupons = transform_coupons(raw_data_catalog.get('Coupons'))
    # H. Orders
    df_orders = None
    df_shipping = None
    df_items = None
   
    if 'Orders' in raw_data_catalog:
        df_orders, df_shipping, df_items = transform_orders(raw_data_catalog.get('Orders'))
    # I. Product Reviews
    df_reviews = None
    if 'Product_Reviews' in raw_data_catalog:
        df_reviews = transform_reviews(raw_data_catalog.get('Product_Reviews'))
    # --- 2. Link Orders to Abandoned Carts ---
    if df_orders is not None:
        if df_abandoned is not None and not df_abandoned.empty:
            logger.info("Linking Orders to Abandoned Carts...")
            cart_lookup = df_abandoned.sort_values('created_at', ascending=False) \
                                      .drop_duplicates(subset=['customer_id']) \
                                      .set_index('customer_id')['abandoned_carts_id']
           
            df_orders['abandoned_carts_id'] = df_orders['customer_id'].map(cart_lookup)
            df_orders['abandoned_carts_id'] = df_orders['abandoned_carts_id'].where(pd.notnull(df_orders['abandoned_carts_id']), None)
        else:
            df_orders['abandoned_carts_id'] = None
    # --- 3. Finalize ---
    if df_main is not None: processed_data_catalog['zid_dim_categories_main'] = df_main
    if df_subs is not None: processed_data_catalog['zid_dim_categories_subs'] = df_subs
    if df_products is not None: processed_data_catalog['zid_dim_products'] = df_products
    if df_bridge is not None: processed_data_catalog['zid_bridge_product_categories'] = df_bridge
    if df_stocks is not None: processed_data_catalog['zid_fact_product_stocks'] = df_stocks
    if df_customers is not None: processed_data_catalog['zid_dim_customers'] = df_customers
    if df_locations is not None: processed_data_catalog['zid_dim_locations'] = df_locations
    if df_methods is not None: processed_data_catalog['zid_dim_shipping_methods'] = df_methods
    if df_shipping_bridge is not None: processed_data_catalog['zid_bridge_shipping_cities'] = df_shipping_bridge
    if df_abandoned is not None: processed_data_catalog['zid_fact_abandoned_carts'] = df_abandoned
    if df_coupons is not None: processed_data_catalog['zid_dim_coupons'] = df_coupons
    if df_orders is not None: processed_data_catalog['zid_fact_orders'] = df_orders
    if df_shipping is not None: processed_data_catalog['zid_fact_order_shipping'] = df_shipping
    if df_items is not None: processed_data_catalog['zid_fact_order_items'] = df_items
    if df_reviews is not None: processed_data_catalog['zid_fact_product_reviews'] = df_reviews # Added
    logger.info("=" * 50)
    logger.info(" TRANSFORMATION COMPLETED")
    logger.info("=" * 50)
   
    return processed_data_catalog
# ==========================================
# 13. EXECUTION ENTRY POINT (FOR TESTING)
# ==========================================
if __name__ == "__main__":
    # For testing: Assume raw_data_catalog is provided or empty
    # In real pipeline, this would be called with extract_data() output
    processed = transform_data({})
    for key, df in processed.items():
        logger.info(f"Processed DataFrame: {key} -> Shape: {df.shape if df is not None else 'None'}")
