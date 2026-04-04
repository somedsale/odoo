# models/project_task_inherit.py
from odoo import models, fields, api, _

class ProjectTask(models.Model):
    _inherit = "project.task"

