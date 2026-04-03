
COLUMN_BLACKLIST = {

    "invoice": [
        "site_id","subscription_id","po_number","name","address_id","client_business_name","client_first_name","client_last_name",
        "client_email","client_address1","client_address2","client_postal_code","client_city","client_state","client_country_code",
        "tax1","tax2","deposit","deposit_type","date_format","language_id","label_invoice_no","label_date","label_po_no","label_total",
        "label_status","label_due_after","label_due_date","label_deposit","label_paid_amount","label_unpaid_amount","label_subtotal",
        "label_description","label_item","label_tax1","label_tax2","label_quantity","label_unit_price","label_item_total","label_from_date",
        "label_to_date","summary_tax1","summary_tax2","adjustment_label","adjustment_value","notes","html_notes","required_terms",
        "terms","terms_id","subscription_unit","subscription_period","subscription_repeated","subscription_max_repeat","from","to",
        "required_terms_file","invoice_layout_id","last_sent","subscription_notify","show_from_to","subscription_issue_before",
        "shipping_options","client_active_secondary_address","client_secondary_name","client_secondary_address1","client_secondary_address2",
        "client_secondary_city","client_secondary_state","client_secondary_postal_code","client_secondary_country_code","follow_up_status",
        "auto_payment","discount_amount","discount_amount","shipping_option_id","work_order_id","item_columns","inventory_request_status",
        "source_type","source_id","extra_details","requisition_delivery_status","group_price_id","external_source","order_source_id",
        "invoice_html_url","invoice_pdf_url","branch_id",
    ],

    "invoice_item": [
        "tax1","tax2","col_3","col_4","col_5","unit_factor","col_6","col_7","col_8", "unit_factor_id","offer_id",
        "tracking_data","serials","extra_details","sales_account_id","cost_center_id","invoice","product","Offer","store"
    ],

    "invoice_payment": [
        "transaction_id","email","notes","response_code","response_message","country_code","attachment",
        "payment_work_order_id","pos_shift_id","extra_details","invoice_payment_files_s3","invoice",
        "client","work_order","treasury","pos_shift","branch","invoice_payment_attachment","transaction_id"
    ],

    "refund_receipt": [
        "type","po_number","is_offline","client_business_name","client_first_name","client_last_name","client_email",
        "client_address1", "client_address2","client_postal_code","client_city","client_state","client_country_code",
        "draft","due_after","terms_id","html_notes","required_terms_file","last_sent","invoice_layout_id","estimate_id",
        "shipping_option_id","client_active_secondary_address","client_secondary_name","client_secondary_address1",
        "client_secondary_address2","client_secondary_city","client_secondary_state","client_secondary_postal_code",
        "client_secondary_country_code","follow_up_status","source_type","source_id","work_order_id","extra_details",
        "item_columns","requisition_delivery_status","pos_shift_id","order_source_id","staff","store","clients",
        "branch","work_orders","pos_shifts","invoice_client","invoice_layout","invoice_source_order","invoice"
    ],

    "estimate": [
        "subscription_id","po_number","is_offline","client_business_name","client_first_name","client_last_name","client_email","client_address1",
        "client_address2","client_postal_code","client_city","client_state","client_country_code","terms_id","html_notes","required_terms_file",
        "invoice_layout_id","estimate_id","shipping_option_id","client_active_secondary_address","client_secondary_name","client_secondary_address1",
        "client_secondary_address2","client_secondary_city","client_secondary_state","client_secondary_postal_code","client_secondary_country_code",
        "follow_up_status","source_type","source_id","extra_details","work_order_id","item_columns","requisition_delivery_status",
        "pos_shift_id","adjustment_label","adjustment_value","order_source_id","staff","store","clients","branch",
        "work_orders","pos_shifts","invoice_client","invoice_layout","invoice_source_order"
    ],

    "credit_note": [
        "subscription_id","po_number","is_offline","client_business_name","client_first_name","client_last_name","client_email","client_address1",
        "client_address2","client_postal_code","client_city","client_state","client_country_code","html_notes","terms_id","required_terms_file",
        "invoice_layout_id","estimate_id","shipping_options","client_active_secondary_address","client_secondary_name","client_secondary_address1",
        "client_active_secondary_address","client_secondary_name","client_secondary_address1","client_secondary_address2","client_secondary_city",
        "client_secondary_state","client_secondary_postal_code","client_secondary_country_code","client_secondary_postal_code","client_secondary_country_code",
        "follow_up_status","source_type","source_id","sales_person_id","extra_details","work_order_id","item_columns","staff","store",
        "clients","branch","work_orders","pos_shifts","invoice_client","invoice_layout","invoice_source_order","invoice","order_source_id","pos_shift_id",
        "requisition_delivery_status","adjustment_label","adjustment_value","last_sent"
        
    ],

    "client": [
        "group_price_id","notes","language_code","last_login","last_ip","follow_up_status","photo","map_location",
        "national_id","secondary_follow_up_status","timezone","client_photo_s3","staff","branch","priceGroup",
        "followUpStatus","clientCategory","country","assigned_to","tags"
    ],

    "supplier": [
        "is_offline","notes","active_secondary_address","secondary_address1","secondary_address2","secondary_city",
        "secondary_state","secondary_postal_code","language_code","supplier_custom_data","branch","country","staff","tags"
    ],

    "product": [
        "is_featured","notes","profit_margin","default_quantity","raw_store_id","unit_template_id","default_buy_factor_id",   
        "default_retail_factor_id","extra_details","source_type","source_id","bundle_type","category","item_group_id","brand_id",
        "display_order","staff","supplier","branch","item_tax1","item_tax2","store","unit_template","unit_template_factor",
        "default_retail_factor","item_group","product_brand","product_attributes","product_categories","product_store_stock_balances",
        "product_images_s3","supplier_code","tax1", "tax2",
    ],

    "product_category": [
        "parent_id","description","category_type","image","display_order","metadata1","metadata2","metadata3","classification_id1",
        "classification_id2","classification_id3","branch"
    ],
    
    "expense": [
        "recurring_expense_id","tax1_name","tax1_value","tax2_name","tax2_value","total","work_order_id","source_id","source_type",
        "expense_category_id","journal_account_id","accounts_data","category","tax1","tax2","treasury","work_order","journal_account",
        "recurring_expense","expense_staff"
    ],

    "purchase_order": [
       "is_offline","supplier_business_name","supplier_first_name","supplier_last_name","supplier_email","supplier_address1",
        "supplier_address2","supplier_postal_code","supplier_city","supplier_state","supplier_country_code","label_due_date",
        "html_notes","invoice_layout_id","subscription_notify","supplier_secondary_address2","received_date","follow_up_status",
        "work_order_id","item_columns","extra_details","source_id","source_type","approved_by","subscription_id","shipping_tax_id",
        "purchase_order_custom_data","supplier","staff","invoice_layout","order_follow_up_status","warehouse","work_order",
        "branch","approved","purchase_order_tax","purchase_orders_tags"
    ],

    "purchase_refund": [
        "follow_up_status","is_offline","supplier_business_name","supplier_first_name","supplier_last_name","supplier_email",
        "supplier_address1","supplier_address2","supplier_postal_code","supplier_city","supplier_state","supplier_country_code",
        "issue_date","label_due_date","html_notes","invoice_layout_id","last_sent","subscription_notify","supplier_secondary_address2",
        "is_received","work_order_id","item_columns","extra_details","requisition_delivery_status","source_id","source_type",
        "approved_by","subscription_id","shipping_tax_id","purchase_order_custom_data","supplier","staff","invoice_layout","order_follow_up_status",
        "warehouse","work_order","branch","approved","purchase_order_tax","purchase_invoice","purchase_orders_tags"
    ],

    "treasury": [
        "metainfo"
    ],

    "staff": [
        "role_id","photo","fax","note","last_login","default_store_id","default_treasury_id","maximum_general_discount","language_code",
        "attendance_restriction_id","default_account_id","official_id","staff_info","staff_job","added_by_staff","role","default_warehouse",
        "default_treasury","branch","default_journal_account","attendance_restriction"
    ],

    "tax": [
        "branch"
    ],

}

