import logging
from base64 import b64decode
from io import StringIO
import os
import csv
import pysftp
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from csv import reader
except (ImportError, IOError) as err:
    _logger.error(err)

CONCESIONARIO: str = '02055342'

class DiazCepedaExportCSV(models.TransientModel):
    _name = "diazcepeda.export.csv"
    _description = "Exportador Diaz Cepeda"

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)

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

        # Return a dictionary to download the file
        # return {
        #     'type': 'ir.actions.act_url',
        #     'url': f'/web/content/?model={self._name}&id={self.id}&field=csv_file&download=true&filename=5534201C.csv',
        #     'target': 'self'
        # }

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
                    n_imp_dto = line.quantity * ( line.price_subtotal * line.discount ) / 100
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
                ])

        #  creamos el csv con los datos recopilados
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', newline='') as file:
            writer = csv.writer(file)
            # writer.writerow(['yearmonth', 'yearmonthady', 'NumFac', 'Concesionario', 'referenciadeart', 'n_tot_uni_venta', 'n_tot_uni_reg', 'n_imp_reg', 'n_imp_dto', totaldescuento])
            for articulo in articulos:
                writer.writerow([
                    articulo[5],
                    articulo[5],
                    articulo[6],
                    CONCESIONARIO,
                    articulo[0],
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
                ])

        #  creamos el csv con los datos recopilados
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', newline='') as file:
            writer = csv.writer(file)
            # writer.writerow(['yearmonthady', 'Concesionario', 'referenciadeart', 'stockActual', 'n_tot_uni_venta'])
            for articulo in articulos:
                writer.writerow([
                    articulo[2],
                    CONCESIONARIO,
                    articulo[0],
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

    def upload_csv_to_ftp(self, file_path):
        # FTP server details
        ftp_server = 'conecta.uvesolutions.com'
        ftp_user = 'Agent-177005'
        ftp_password = 'Opcm_554'
        ftp_target_path = '/'

        print("***************************************************")
        print("Entro a subir al ftp")

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

        params = {
            "host": 'conecta.uvesolutions.com',
            "username": 'Agent-177005',
            "port": '22',
            "passphrase": 'Opcm_554',
        }
        _logger.debug(
            "Trying to connect to sftp://%(username)s@%(host)s:%(port)d", extra=params
        )

        return pysftp.Connection(**params)


        # Connect to the FTP server
        # with ftplib.FTP(ftp_server) as ftp:
        #     ftp.login(user=ftp_user, passwd=ftp_password)
        #     print(f"Logged in to FTP server: {ftp_server}")
        #
        #     # Open the file in binary mode
        #     with open(file_path, 'rb') as file:
        #         # Store the file on the FTP server
        #         ftp.storbinary(f'STOR {ftp_target_path}', file)
        #         print(f"File uploaded to FTP server at {ftp_target_path}")
