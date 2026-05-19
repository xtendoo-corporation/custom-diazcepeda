import math
from unidecode import unidecode

def clean_text(text, length):
    if not text:
        return ' ' * length
    cleaned = unidecode(str(text)).upper().strip()
    return cleaned[:length].ljust(length)

def format_numeric(number, length, decimals=0):
    if not number:
        number = 0.0
    # Example: 4.5 -> "000000450" if 9 length and 2 decimals
    # Means we multiply by 10^decimals and zfill
    multiplier = 10 ** decimals
    val = int(round(number * multiplier))
    str_val = str(abs(val))
    # If it exceeds length, we return 9999... to avoid breaking format
    if len(str_val) > length:
        return '9' * length
    if val < 0:
        # Negative numbers in Schweppes format: -00001145
        return '-' + str_val.zfill(length - 1)
    return str_val.zfill(length)

def format_ct(date_str, type_g_s, sequence_nn, code_dist):
    return f"CT   {clean_text(date_str, 8)}{clean_text(type_g_s, 1)}{clean_text(sequence_nn, 2)}{clean_text(code_dist, 10)}"

def format_dicp(order_name, route_code, customer_code, date_order, date_delivery, payment_type, customer_ref=""):
    return f"DICP {clean_text(order_name, 10)}{clean_text(route_code, 4)}{clean_text(customer_code, 15)}{clean_text(date_order, 8)}{clean_text(date_delivery, 8)}{clean_text(payment_type, 2)}{clean_text(customer_ref, 10)}EUR  "

def format_didp(order_name, product_code, qty_ordered, qty_return_expected, qty_delivered, qty_returned, price_unit, promo_ssa=""):
    # Spec: Field 6 (Served) never has minus sign; Field 7 (Returned) is for returns.
    # IRIS quantities should be positive integers.
    if qty_delivered < 0:
        qty_returned = abs(qty_delivered)
        qty_delivered = 0

    # Ensure absolute values for all quantity fields to avoid signs
    qty_ordered = abs(qty_ordered)
    qty_return_expected = abs(qty_return_expected)

    base = f"DIDP {clean_text(order_name, 10)}{clean_text(product_code, 8)}{format_numeric(qty_ordered, 8, 0)}{format_numeric(qty_return_expected, 8, 0)}{format_numeric(qty_delivered, 8, 0)}{format_numeric(qty_returned, 8, 0)}{format_numeric(price_unit, 9, 2)}"
    if promo_ssa:
        return base + clean_text(promo_ssa, 10)
    return base.ljust(74)

def format_didd(order_name, product_code, discount_type, amount, promo_ssa=""):
    return f"DIDD {clean_text(order_name, 10)}{clean_text(product_code, 8)}{clean_text(discount_type, 5)}{format_numeric(amount, 11, 2)}{clean_text(promo_ssa, 10)}"

def format_dimc(cust_code, route, commercial_name, legal_name, address, vat, delivery_type, estab_type, payment_type, status, discount_variant, collab_agree, fixed_cond, visit_days, old_cust, chain, group, active_sl, email, city, state, zip_code, phone, fax, ssa_code, sequence):
    return f"DIMC {clean_text(cust_code, 15)}{clean_text(route, 4)}{clean_text(commercial_name, 50)}{clean_text(legal_name, 70)}{clean_text(address, 35)}{clean_text(vat, 12)}{clean_text(delivery_type, 1)}{clean_text(estab_type, 2)}{clean_text(payment_type, 2)}{clean_text(status, 2)}{clean_text(discount_variant, 6)}{clean_text(collab_agree, 8)}{clean_text(fixed_cond, 1)}{clean_text(visit_days, 7)}{clean_text(old_cust, 15)}{clean_text(chain, 2)}{clean_text(group, 5)}{clean_text(active_sl, 1)}{clean_text(email, 35)}{clean_text(city, 20)}{clean_text(state, 12)}{clean_text(zip_code, 5)}{clean_text(phone, 12)}{clean_text(fax, 12)}{clean_text(ssa_code, 8)}{clean_text(sequence, 10)}"


def format_dimp(product_code, brand, product_class, flavor, product_type, product_name, schweppes_product_code):
    return (
        f"DIMP {clean_text(product_code, 8)}{clean_text(brand, 3)}{clean_text(product_class, 6)}"
        f"{clean_text(flavor, 5)}{clean_text(product_type, 4)}{clean_text(product_name, 25)}"
        f"{clean_text(schweppes_product_code, 8)}"
    )

def format_ft(records_count, orders_count):
    return f"FT   {format_numeric(records_count, 7, 0)}{format_numeric(orders_count, 7, 0)}"
