from odoo import models, fields, api
import csv
import os
import ftplib

class AccountMove(models.Model):
    _inherit = 'account.move'

    def export_invoice_line_csv(self):
        # Create the CSV file
        file_path = self.create_csv()

        if file_path:
            # Upload the CSV file to the FTP server
            self.upload_csv_to_ftp(file_path)

        # Return a dictionary to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model={self._name}&id={self.id}&field=csv_file&download=true&filename=invoice.csv',
            'target': 'self'
        }

    def create_csv(self):
        # Define the file path
        file_path = '/home/manuel/Documentos/odoo/17/odoo/custom/src/custom-diazcepeda/diazcepeda_export_csv/static/csv/invoices.csv'

        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Open the file in write mode
        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)

            # Write the header
            writer.writerow(['Invoice Number', 'Partner', 'Date', 'Product', 'Quantity', 'Price', 'Total'])

            # Fetch all invoices
            invoices = self.search([])

            # Write invoice data
            for invoice in invoices:
                for line in invoice.invoice_line_ids:
                    writer.writerow([
                        invoice.name,
                        invoice.partner_id.name,
                        invoice.invoice_date,
                        line.product_id.name,
                        line.quantity,
                        line.price_unit,
                        line.price_subtotal
                    ])

        print(f"CSV file created at {file_path}")

        return file_path

    def upload_csv_to_ftp(self, file_path):
        # FTP server details
        ftp_server = 'ftp.example.com'
        ftp_user = 'your_username'
        ftp_password = 'your_password'
        ftp_target_path = '/path/on/ftp/server/invoices.csv'

        # Connect to the FTP server
        with ftplib.FTP(ftp_server) as ftp:
            ftp.login(user=ftp_user, passwd=ftp_password)
            print(f"Logged in to FTP server: {ftp_server}")

            # Open the file in binary mode
            with open(file_path, 'rb') as file:
                # Store the file on the FTP server
                ftp.storbinary(f'STOR {ftp_target_path}', file)
                print(f"File uploaded to FTP server at {ftp_target_path}")

