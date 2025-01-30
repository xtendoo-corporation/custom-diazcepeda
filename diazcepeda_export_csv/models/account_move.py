from odoo import models, fields, api
import csv
import os
import ftplib

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def export_file(self):
        """ Process the file chosen in the wizard, create bank statement(s) and go to reconciliation. """
        self.ensure_one()

        print("Entro a ejecutar el wizard")

    # @api.model
    # def export_invoice_line_csv(self):
    #
    #     print("----------------------Entro en export_invoice_line_csv--------------------------------")
    #
    #     # Create the CSV file
    #     file_path_a = self.create_a_csv()
    #     file_path_b = self.create_b_csv()
    #     file_path_c = self.create_c_csv()
    #
    #     if file_path_a:
    #         # Upload the CSV file to the FTP server
    #         # self.upload_csv_to_ftp(file_path)
    #         print("**********************file_path**********************")
    #         print(file_path_a)
    #
    #     if file_path_b:
    #         # Upload the CSV file to the FTP server
    #         # self.upload_csv_to_ftp(file_path_b)
    #         print("**********************file_path_B**********************")
    #         print(file_path_b)
    #
    #     if file_path_c:
    #         # Upload the CSV file to the FTP server
    #         # self.upload_csv_to_ftp(file_path_c)
    #         print("**********************file_path_c**********************")
    #         print(file_path_c)
    #
    #     # Return a dictionary to download the file
    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': f'/web/content/?model={self._name}&id={self.id}&field=csv_file&download=true&filename=5534201A.csv',
    #         'target': 'self'
    #     }
    #
    # @api.model
    # def create_a_csv(self):
    #     # Define the file path
    #     path = '/home/dario/5534201A.csv'
    #
    #     # Ensure the directory exists
    #     os.makedirs(os.path.dirname(path), exist_ok=True)
    #
    #     # Open the file in write mode
    #     with open(path, mode='w', newline='') as file:
    #         writer = csv.writer(file)
    #
    #         # Write the header
    #         writer.writerow(['Invoice Number', 'Partner', 'Date', 'Product', 'Quantity', 'Price', 'Total'])
    #
    #         # Fetch all invoices
    #         invoices = self.search([])
    #
    #         # Write invoice data
    #         for invoice in invoices:
    #             for line in invoice.invoice_line_ids:
    #                 writer.writerow([
    #                     invoice.name,
    #                     invoice.partner_id.name,
    #                     invoice.invoice_date,
    #                     line.product_id.name,
    #                     line.quantity,
    #                     line.price_unit,
    #                     line.price_subtotal
    #                 ])
    #
    #     print(f"CSV file created at {path}")
    #
    #     return path
    #
    # @api.model
    # def create_b_csv(self):
    #     # Define the file path
    #     path = '/home/dario/5534201B.csv'
    #
    #     # Ensure the directory exists
    #     os.makedirs(os.path.dirname(path), exist_ok=True)
    #
    #     # Open the file in write mode
    #     with open(path, mode='w', newline='') as file:
    #         writer = csv.writer(file)
    #
    #         # Write the header
    #         writer.writerow(['Invoice Number', 'Partner', 'Date', 'Product', 'Quantity', 'Price', 'Total'])
    #
    #         # Fetch all invoices
    #         invoices = self.search([])
    #
    #         # Write invoice data
    #         for invoice in invoices:
    #             for line in invoice.invoice_line_ids:
    #                 writer.writerow([
    #                     invoice.name,
    #                     invoice.partner_id.name,
    #                     invoice.invoice_date,
    #                     line.product_id.name,
    #                     line.quantity,
    #                     line.price_unit,
    #                     line.price_subtotal
    #                 ])
    #
    #     print(f"CSV file created at {path}")
    #
    #     return path
    #
    # @api.model
    # def create_c_csv(self):
    #     # Define the file path
    #     path = '/home/dario/5534201C.csv'
    #
    #     # Ensure the directory exists
    #     os.makedirs(os.path.dirname(path), exist_ok=True)
    #
    #     # Open the file in write mode
    #     with open(path, mode='w', newline='') as file:
    #         writer = csv.writer(file)
    #
    #         # Write the header
    #         writer.writerow(['Invoice Number', 'Partner', 'Date', 'Product', 'Quantity', 'Price', 'Total'])
    #
    #         # Fetch all invoices
    #         invoices = self.search([])
    #
    #         # Write invoice data
    #         for invoice in invoices:
    #             for line in invoice.invoice_line_ids:
    #                 writer.writerow([
    #                     invoice.name,
    #                     invoice.partner_id.name,
    #                     invoice.invoice_date,
    #                     line.product_id.name,
    #                     line.quantity,
    #                     line.price_unit,
    #                     line.price_subtotal
    #                 ])
    #
    #     print(f"CSV file created at {path}")
    #
    #     return path

    # def upload_csv_to_ftp(self, file_path):
    #     # FTP server details
    #     ftp_server = 'ftp.example.com'
    #     ftp_user = 'your_username'
    #     ftp_password = 'your_password'
    #     ftp_target_path = '/path/on/ftp/server/invoices.csv'
    #
    #     # Connect to the FTP server
    #     with ftplib.FTP(ftp_server) as ftp:
    #         ftp.login(user=ftp_user, passwd=ftp_password)
    #         print(f"Logged in to FTP server: {ftp_server}")
    #
    #         # Open the file in binary mode
    #         with open(file_path, 'rb') as file:
    #             # Store the file on the FTP server
    #             ftp.storbinary(f'STOR {ftp_target_path}', file)
    #             print(f"File uploaded to FTP server at {ftp_target_path}")

