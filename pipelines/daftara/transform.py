import json
import pandas as pd

from pipelines.daftara.column_blacklist import COLUMN_BLACKLIST
from shared.logger import setup_logger

logger = setup_logger(__name__)


class DaftraTransformer:
    # =========================
    # Helpers
    # =========================
    @staticmethod
    def _extract_category_id(value):
        try:
            if isinstance(value, list) and value:
                category = value[0].get("category")
                if isinstance(category, dict):
                    return category.get("id")
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_client_balance(value):
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict):
                balance = value.get("client_balance")
                return float(balance) if balance is not None else None
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_supplier_balance(value):
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict):
                return value.get("supplier_balance")
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_tax_id(value):
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict) and value.get("id"):
                return int(value.get("id"))
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_payment_terms(value):
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict):
                return value.get("payment_terms")
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_order_fields(value, field_name):
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict):
                return value.get(field_name)
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_role_name(value):
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict):
                return value.get("name")
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_staff_info(value):
        if value is None:
            return None, None
        try:
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict):
                return value.get("birth_date"), value.get("gender")
        except Exception:
            return None, None
        return None, None

    @staticmethod
    def _remove_non_numeric_invoice_no(df: pd.DataFrame) -> pd.DataFrame:
        if "no" not in df.columns:
            return df
    
        df = df.copy()
    
        # 1️⃣ شيل أي invoice فيها كلمة draft (case-insensitive)
        df["no_str"] = df["no"].astype(str).str.strip().str.lower()
        df = df[~df["no_str"].str.contains("draft", na=False)]
    
        # 2️⃣ خليه رقم فقط
        numeric_no = pd.to_numeric(df["no"], errors="coerce")
        df = df[numeric_no.notna()]
        df["no"] = numeric_no.astype(int)
    
        # تنظيف
        df = df.drop(columns=["no_str"]).reset_index(drop=True)
    
        return df

    @staticmethod
    def _fix_purchase_payment_values(df: pd.DataFrame) -> pd.DataFrame:
        required_cols = {"summary_total", "summary_paid", "summary_unpaid"}
        if not required_cols.issubset(df.columns):
            return df

        df = df.copy()
        total = df["summary_total"].fillna(0)
        paid = df["summary_paid"].fillna(0)
        unpaid = df["summary_unpaid"].fillna(0)

        mask_fix_unpaid = (paid > 0) & (unpaid == 0)
        df.loc[mask_fix_unpaid, "summary_unpaid"] = (
            total - paid
        ).clip(lower=0)

        mask_fix_paid = (unpaid > 0) & (paid == 0)
        df.loc[mask_fix_paid, "summary_paid"] = (
            total - unpaid
        ).clip(lower=0)

        return df

    # =========================
    # Cleaning
    # =========================
    @staticmethod
    def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df.replace(["0000-00-00", "0000-00-00 00:00:00"], None, inplace=True)
        df = df.where(pd.notnull(df), None)
        return df

    # =========================
    # Normalize IDs
    # =========================
    @staticmethod
    def _normalize_id_columns(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in [c for c in df.columns if c == "id" or c.endswith("_id")]:
            df[col] = df[col].where(pd.notnull(df[col]), None)
            if pd.api.types.is_float_dtype(df[col]):
                df[col] = df[col].apply(
                    lambda x: int(x) if isinstance(x, float) and pd.notna(x) else None
                )
        return df

    # =========================
    # Entity Transform
    # =========================
    def transform(self, entity: str, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df = self._clean_dataframe(df)

        if entity == "invoice":
            df = self._remove_non_numeric_invoice_no(df)
        
        if entity == "refund_receipt" and "extra_details" in df.columns:
            df["client_balance"] = df["extra_details"].apply(self._extract_client_balance)

        if entity in ("purchase_order", "purchase_refund"):
            df = self._fix_purchase_payment_values(df)

        if entity in ("purchase_order", "purchase_refund") and "extra_details" in df.columns:
            df["supplier_balance"] = df["extra_details"].apply(self._extract_supplier_balance)

        if entity in ("invoice_item", "product"):
            if "tax1" in df.columns:
                df["tax1_id"] = df["tax1"].apply(self._extract_tax_id)
            if "tax2" in df.columns:
                df["tax2_id"] = df["tax2"].apply(self._extract_tax_id)

        if entity == "supplier" and "supplier_custom_data" in df.columns:
            df["payment_terms"] = df["supplier_custom_data"].apply(self._extract_payment_terms)

        if entity in ("purchase_order", "purchase_refund") and "purchase_order_custom_data" in df.columns:
            df["order_type"] = df["purchase_order_custom_data"].apply(
                lambda x: self._extract_order_fields(x, "order_type")
            )
            df["order_reason"] = df["purchase_order_custom_data"].apply(
                lambda x: self._extract_order_fields(x, "order_reason")
            )
            df["notes"] = df["purchase_order_custom_data"].apply(
                lambda x: self._extract_order_fields(x, "notes")
            )

        if entity == "product" and "product_categories" in df.columns:
            df["category_id"] = df["product_categories"].apply(self._extract_category_id)

        if entity == "staff" and "role" in df.columns:
            df["role_name"] = df["role"].apply(self._extract_role_name)

        if entity == "staff" and "staff_info" in df.columns:
            extracted = df["staff_info"].apply(self._extract_staff_info)
            df["birth_date"], df["gender"] = zip(*extracted)

        cols_to_drop = [c for c in COLUMN_BLACKLIST.get(entity, []) if c in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)

        df = self._normalize_id_columns(df)

        return df


    # Transform All
    def transform_all(self, data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        transformed = {}

        for entity, df in data.items():
            logger.info(f"[TRANSFORM] {entity}")
            transformed[f"daftra_{entity}"] = self.transform(entity, df)

        return transformed



