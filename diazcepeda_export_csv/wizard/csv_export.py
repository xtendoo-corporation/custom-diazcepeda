import ftplib
import logging
import base64
import os
import csv
import zipfile
from datetime import date, timedelta
from itertools import product

from odoo.exceptions import UserError

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

try:
    from csv import reader
except (ImportError, IOError) as err:
    _logger.error(err)

try:
    import pysftp
except ImportError:  # pragma: no cover
    _logger.debug("Cannot import pysftp")

CONCESIONARIO: str = '02055342'
FTP_SERVER: str = '13.93.124.174'
FTP_DIRECTORY: str = ''

def _default_start_date():
    today = date.today()
    return today.replace(day=1)

def _default_end_date():
    today = date.today()
    next_month = today.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)


class DiazCepedaExportCSV(models.TransientModel):
    _name = "diazcepeda.export.csv"
    _description = "Exportador Diaz Cepeda"

    start_date = fields.Date(string="Fecha inicio", required=True, default=_default_start_date() )

    end_date = fields.Date(string="Fecha fin", required=True, default=_default_end_date() )

    csv_file = fields.Binary(string="CSV File", readonly=True)
    csv_file_name = fields.Char(string="CSV File Name", readonly=True)

    def export_file(self):
        """ Process the file chosen in the wizard, create bank statement(s) and go to reconciliation. """
        self.ensure_one()

        # SACO LOS DATOS QUE NECESITO Y SE LO PASO A LA FUNCION QUE CREA EL CSV
        invoices = self.env['account.move'].search([
            ('invoice_date', '>=', self.start_date),
            ('invoice_date', '<=', self.end_date)]
        )
        invoices_lines = invoices.invoice_line_ids.filtered(lambda l: l.product_id.categ_id.name == ('Cerveza'))
        partners = invoices_lines.mapped('partner_id')

        file_path_a = self.create_a_csv(invoices_lines)
        file_path_b = self.create_b_csv(invoices_lines)
        file_path_c = self.create_c_csv(partners)

        if file_path_a:
            print("File A created at:", file_path_a)
            self.show_csv_content(file_path_a)
            self.upload_csv_to_ftp(file_path_a)

        if file_path_b:
            print("File B created at:", file_path_b)
            self.show_csv_content(file_path_b)
            self.upload_csv_to_ftp(file_path_b)

        if file_path_c:
            print("File C created at:", file_path_c)
            self.show_csv_content(file_path_c)
            self.upload_csv_to_ftp(file_path_c)

        zip_path = '/tmp/invoices_csv.zip'
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            if file_path_a:
                zipf.write(file_path_a, os.path.basename(file_path_a))
            if file_path_b:
                zipf.write(file_path_b, os.path.basename(file_path_b))
            if file_path_c:
                zipf.write(file_path_c, os.path.basename(file_path_c))

        with open(zip_path, 'rb') as file:
            self.csv_file = base64.b64encode(file.read())
        self.csv_file_name = 'invoices_csv.zip'

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/csv_file/{self.csv_file_name}?download=true',
            'target': 'self',
        }

    def preview_file(self):
        """ Process the file chosen in the wizard, create bank statement(s) and go to reconciliation. """
        self.ensure_one()

        # SACO LOS DATOS QUE NECESITO Y SE LO PASO A LA FUNCION QUE CREA EL CSV
        invoices = self.env['account.move'].search([
            ('invoice_date', '>=', self.start_date),
            ('invoice_date', '<=', self.end_date)]
        )
        invoices_lines = invoices.invoice_line_ids.filtered(lambda l: l.product_id.categ_id.name == ('Cerveza'))
        partners = invoices_lines.mapped('partner_id')

        file_path_a = self.create_a_csv(invoices_lines)
        file_path_b = self.create_b_csv(invoices_lines)
        file_path_c = self.create_c_csv(partners)

        if file_path_a:
            print("File A created at:", file_path_a)
            self.show_csv_content(file_path_a)

        if file_path_b:
            print("File B created at:", file_path_b)
            self.show_csv_content(file_path_b)

        if file_path_c:
            print("File C created at:", file_path_c)
            self.show_csv_content(file_path_c)

        zip_path = '/tmp/invoices_csv.zip'
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            if file_path_a:
                zipf.write(file_path_a, os.path.basename(file_path_a))
            if file_path_b:
                zipf.write(file_path_b, os.path.basename(file_path_b))
            if file_path_c:
                zipf.write(file_path_c, os.path.basename(file_path_c))

        with open(zip_path, 'rb') as file:
            self.csv_file = base64.b64encode(file.read())
        self.csv_file_name = 'invoices_csv.zip'

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/csv_file/{self.csv_file_name}?download=true',
            'target': 'self',
        }

    def create_a_csv(self, invoices_lines):
        path = '/tmp/5534201A.csv'

        # Preparamos un array con los datos que queremos exportar
        products = []

        for line in invoices_lines:
            total_importe_descuento = 0
            total_unidades_venta = line.quantity

            if line.price_unit != 0:
                total_unidades_regalo = 0
                total_importe_regalo = 0
                if line.discount != 0:
                    if line.product_id.codigo_normalizado != '':
                        total_importe_descuento = total_unidades_venta * ( ( line.price_unit * line.discount ) / 100 )
                    else:
                        total_importe_descuento = total_unidades_venta * ( ( line.product_id.standard_price * line.discount ) / 100 )

            else:
                total_unidades_regalo = total_unidades_venta
                total_importe_regalo = total_unidades_venta * line.product_id.lst_price

            print("Factura: ", line.move_id.name)
            print("Producto: ", line.product_id.default_code)
            print("Unidades venta: ", total_unidades_venta)
            print("Precio unitario: ", line.price_unit)
            print("Descuento: ", line.discount)
            print("Unidades regalo: ", total_unidades_regalo)
            print("Importe regalo: ", total_importe_regalo)
            print("Importe descuento: ", total_importe_descuento)

            # Check if the product already exists in the products array
            product_exists = False
            for product in products:
                if product["invoice_number"] == line.move_id.name and product["default_code"] == line.product_id.default_code:
                    product["total_unidades_venta"] += total_unidades_venta
                    product["total_unidades_regalo"] += total_unidades_regalo
                    product["total_importe_regalo"] += total_importe_regalo
                    product["total_importe_descuento"] += total_importe_descuento
                    product_exists = True
                    break

            if not product_exists:
                products.append({
                    "statistic_date": str( line.move_id.invoice_date.year ) + str( line.move_id.invoice_date.month ).zfill(2),
                    "invoice_date": str( line.move_id.invoice_date.year ) + str( line.move_id.invoice_date.month ).zfill(2) + str( line.move_id.invoice_date.day ).zfill(2),
                    "invoice_number": line.move_id.name,
                    "partner_ref": line.move_id.partner_id.ref,
                    "auxiliar_reference": line.product_id.referencia_auxiliar,
                    "default_code": line.product_id.default_code,
                    "total_unidades_venta": total_unidades_venta,
                    "total_unidades_regalo": total_unidades_regalo,
                    "total_importe_regalo": total_importe_regalo,
                    "total_importe_descuento": total_importe_descuento,
                    "stock_quantity": self.env['stock.quant'].search([('product_id', '=', line.product_id.id), ('location_id.usage', '=', 'internal')], limit=1).quantity,
                })

        #  creamos el csv con los datos recopilados
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', newline='') as file:
            writer = csv.writer(file, delimiter=';')
            for product in products:
                writer.writerow([
                    product["statistic_date"],
                    product["invoice_date"],
                    product["invoice_number"],
                    CONCESIONARIO,
                    product["partner_ref"],
                    product["auxiliar_reference"],
                    str( product["total_unidades_venta"] ).replace(".", ","),
                    str( product["total_unidades_regalo"] ).replace(".", ","),
                    str(round(product["total_importe_regalo"],2)).replace(".", ","),
                    str(round(product["total_importe_descuento"], 2)).replace(".", ","),
                    str(round(product["total_importe_regalo"] + product["total_importe_descuento"],2)).replace(".", ","),
                ])

        return path

    def create_b_csv(self, invoices_lines):
        path = '/tmp/5534201B.csv'

        # Preparamos un array con los datos que queremos exportar
        products = []

        for line in invoices_lines:
            total_unidades_venta = line.quantity

            # Check if the product already exists in the products array
            product_exists = False
            for product in products:
                if (product["default_code"] == line.product_id.default_code):
                    product["total_unidades_venta"] += total_unidades_venta
                    product_exists = True
                    break

            if not product_exists:
                products.append({
                    "invoice_date": str( line.move_id.invoice_date.year ) + str( line.move_id.invoice_date.month ).zfill(2) + str( line.move_id.invoice_date.day ).zfill(2),
                    "invoice_number": line.move_id.name,
                    "partner_ref": line.move_id.partner_id.ref,
                    "auxiliar_reference": line.product_id.referencia_auxiliar,
                    "default_code": line.product_id.default_code,
                    "total_unidades_venta": total_unidades_venta,
                    "stock_quantity": self.calculate_real_stock(line.product_id.id),
                })

        #  creamos el csv con los datos recopilados
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', newline='') as file:
            writer = csv.writer(file, delimiter=';')
            for product in products:
                writer.writerow([
                    product["invoice_date"],
                    CONCESIONARIO,
                    product["auxiliar_reference"],
                    str(product["stock_quantity"]).replace(".", ","),
                    str(product["total_unidades_venta"]).replace(".", ","),
                ])

        return path

    def create_c_csv(self, partners):

        path = '/tmp/5534201C.csv'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', newline='') as file:
            writer = csv.writer(file, delimiter=';')
            for partner in partners:
                writer.writerow([
                    CONCESIONARIO,
                    partner.ref or '',
                    partner.comercial if partner.comercial else partner.name,
                    partner.street or '',
                    partner.city or '',
                    partner.zip or '',
                    partner.name or '',
                    partner.vat or '',
                    partner.street or '',
                    partner.city or '',
                    partner.zip or '',
                ])

        return path

    # Function to check if the item is in the two-dimensional array
    def is_in_array(self, array, item):
        for sub_array in array:
            if item in sub_array:
                return True
        return False

    def calculate_real_stock(self, product_id):
        stock_quant = self.env['stock.quant'].search([
            ('product_id', '=', product_id),
            ('location_id.usage', '=', 'internal')
        ])
        real_stock = sum(stock_quant.mapped('quantity'))
        return real_stock

    def show_csv_content(self, file_path):
        print("***************************************************")
        print("File created at:", file_path)
        with open(file_path, mode='r', newline='') as file:
            reader = csv.reader(file)
            for row in reader:
                print(row)
        print("***************************************************")

    def upload_csv_to_ftp(self, file_path):
        with self.sftp_connection() as sftp:
            sftp.cwd(FTP_DIRECTORY)
            sftp.put(file_path, os.path.basename(file_path))

    def action_sftp_test_connection(self):
        """Check if the SFTP settings are correct."""
        try:
            # Just open and close the connection
            with self.sftp_connection():
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Test de conexión'),
                        'message': _('Connection test succeeded!'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except (
            pysftp.CredentialException,
            pysftp.ConnectionException,
            pysftp.SSHException,
        ) as exc:
            _logger.info("Connection Test Failed!", exc_info=True)
            raise UserError(_("Connection Test Failed!")) from exc

    def sftp_connection(self):
        """Return a new SFTP connection with found parameters."""
        self.ensure_one()

        ftp_user = self.env['ir.config_parameter'].sudo().get_param('ftp_user')
        ftp_password = self.env['ir.config_parameter'].sudo().get_param('ftp_password')

        params = {
            "host": self.ftp_server,
            "username": ftp_user,
            "port": 22,
        }
        _logger.debug(
            "Trying to connect to sftp://%(username)s@%(host)s:%(port)d", extra=params
        )
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None

        params["password"] = ftp_password

        return pysftp.Connection(**params, cnopts=cnopts)
