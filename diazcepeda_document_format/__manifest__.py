{
    "name": "Diaz Cepeda Document Format",
    "summary": """Diaz Cepeda Document Format""",
    "version": "17.0.1.0.0",
    "description": """Diaz Cepeda Document Format""",
    "company": "Xtendoo",
    "author": "Daniel Dominguez",
    "website": "http://www.xtendoo.es",
    "category": "Website",
    "license": "AGPL-3",
    "depends": [
        "account",
        "web",
        "sale",
        "stock"
    ],
    "data": [
        "views/sale/report_saleorder_document.xml",
        "views/invoice/report_invoice_document.xml",
        "views/invoice/report_invoice_document_preprinted.xml",
        "views/stock_picking/report_delivery_document.xml",
        "views/layout/external_layout_striped.xml",
        "views/interface/product_template_view.xml",
        "views/sale/report_saleorder_document_with_vat.xml",
        "views/sale/report_saleorder_document_without_prices.xml",
    ],
    "installable": True,
    'application': False,
}
