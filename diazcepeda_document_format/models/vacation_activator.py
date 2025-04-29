# -*- coding: utf-8 -*-
from odoo import api, models, fields
from datetime import datetime


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def is_vacation_period(self):
        # Obtener los parámetros de fechas
        vacation_start = self.get_param('diazcepeda.vacation_start_date', False)
        vacation_end = self.get_param('diazcepeda.vacation_end_date', False)

        # Si no hay fechas configuradas, no mostrar mensaje
        if not vacation_start or not vacation_end:
            return False

        try:
            # Convertir strings a objetos datetime
            start_date = datetime.strptime(vacation_start, '%Y-%m-%d')
            end_date = datetime.strptime(vacation_end, '%Y-%m-%d')
            today = datetime.now()

            # Verificar si la fecha actual está en el rango
            return start_date <= today <= end_date
        except:
            return False
