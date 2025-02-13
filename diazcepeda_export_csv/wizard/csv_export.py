import ftplib
import logging
import base64
import os
import csv
import zipfile
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

class DiazCepedaExportCSV(models.TransientModel):
    _name = "diazcepeda.export.csv"
    _description = "Exportador Diaz Cepeda"

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)

    csv_file = fields.Binary(string="CSV File", readonly=True)
    csv_file_name = fields.Char(string="CSV File Name", readonly=True)

    ftp_server = 'connecta.uvesolutions.com'
    ftp_directory = ''

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
            self.upload_csv_to_ftp(file_path_a, self.ftp_server, self.ftp_directory)

        if file_path_b:
            print("File B created at:", file_path_b)
            self.show_csv_content(file_path_b)
            self.upload_csv_to_ftp(file_path_b, self.ftp_server, self.ftp_directory)

        if file_path_c:
            print("File C created at:", file_path_c)
            self.show_csv_content(file_path_c)
            self.upload_csv_to_ftp(file_path_c, self.ftp_server, self.ftp_directory)



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
        articulos = []

        for line in invoices_lines:
            n_tot_uni_venta = 0
            n_tot_uni_reg = 0
            n_imp_reg = 0
            n_imp_dto = 0

            if line.price_unit != 0:
                n_tot_uni_venta = 0
                n_tot_uni_reg = 0
                n_imp_reg = 0
                n_imp_dto = 0
                if line.discount != 0:
                    if line.product_id.codigo_normalizado != '':
                        n_imp_dto = line.quantity * ( line.price_unit * line.discount ) / 100
                    else:
                        n_imp_dto = line.quantity * ( line.product_id.standard_price * line.discount ) / 100
            else:
                n_tot_uni_venta = line.quantity
                n_tot_uni_reg = line.quantity
                n_imp_reg = line.quantity * line.price_unit
                n_imp_dto = 0

            if self.is_in_array(articulos, line.product_id.default_code):
                for articulo in articulos:
                    if articulo[0] == line.product_id.default_code:
                        articulo[1] = articulo[1] + n_tot_uni_venta
                        articulo[2] = articulo[2] + n_tot_uni_reg
                        articulo[3] = articulo[3] + n_imp_reg
                        articulo[4] = articulo[4] + n_imp_dto
            else:
                articulos.append([
                    line.product_id.default_code,
                    n_tot_uni_venta,
                    n_tot_uni_reg,
                    n_imp_reg,
                    n_imp_dto,
                    line.move_id.invoice_date,
                    line.move_id.name,
                    line.move_id.partner_id.ref,
                    line.product_id.referencia_auxiliar,
                ])

        #  creamos el csv con los datos recopilados
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', newline='') as file:
            writer = csv.writer(file)
            for articulo in articulos:
                writer.writerow([
                    articulo[5],
                    articulo[5],
                    articulo[6],
                    CONCESIONARIO,
                    articulo[8],
                    articulo[1],
                    articulo[2],
                    articulo[3],
                    articulo[4],
                    articulo[3] + articulo[4],
                    ])

        return path

    def create_b_csv(self, invoices_lines):
        path = '/tmp/5534201B.csv'

        # Preparamos un array con los datos que queremos exportar
        articulos = []

        for line in invoices_lines:
            n_tot_uni_venta = 0

            if line.price_unit != 0:
                n_tot_uni_venta = 0
            else:
                n_tot_uni_venta = line.quantity

            if self.is_in_array(articulos, line.product_id.default_code):
                for articulo in articulos:
                    if articulo[0] == line.product_id.default_code:
                        articulo[1] = articulo[1] + n_tot_uni_venta
            else:
                articulos.append([
                    line.product_id.default_code,
                    n_tot_uni_venta,
                    line.move_id.invoice_date,
                    self.env['stock.quant'].search(
                        [('product_id', '=', line.product_id.id), ('location_id.usage', '=', 'internal')],
                        limit=1).quantity,
                    line.product_id.referencia_auxiliar,
                ])

        #  creamos el csv con los datos recopilados
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', newline='') as file:
            writer = csv.writer(file)
            for articulo in articulos:
                writer.writerow([
                    articulo[2],
                    CONCESIONARIO,
                    articulo[4],
                    articulo[3],
                    articulo[1],
                ])

        return path

    def create_c_csv(self, partners):

        path = '/tmp/5534201C.csv'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', newline='') as file:
            writer = csv.writer(file)
            for partner in partners:
                writer.writerow([
                    CONCESIONARIO,
                    partner.ref,
                    partner.name,
                    partner.street,
                    partner.city,
                    partner.zip,
                    partner.name,
                    partner.street,
                    partner.city,
                    partner.zip,
                ])

        return path

    # Function to check if the item is in the two-dimensional array
    def is_in_array(self, array, item):
        for sub_array in array:
            if item in sub_array:
                return True
        return False

    def show_csv_content(self, file_path):
        print("***************************************************")
        print("File created at:", file_path)
        with open(file_path, mode='r', newline='') as file:
            reader = csv.reader(file)
            for row in reader:
                print(row)
        print("***************************************************")

    def upload_csv_to_ftp(self, file_path, ftp_directory):
        with self.sftp_connection() as sftp:
            sftp.cwd(ftp_directory)
            sftp.put(file_path, os.path.basename(file_path))

    def action_sftp_test_connection(self):
        """Check if the SFTP settings are correct."""
        try:
            # Just open and close the connection
            with self.sftp_connection():
                raise UserError(_("Connection Test Succeeded!"))
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
